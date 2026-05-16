"""`TerminalProfile` + detection per §7.0.2.

> "At startup, every Sange process computes a `TerminalProfile`
> exactly once and caches it." — §7.0.2

This module is pure capability detection + glyph mapping. No rich /
textual / questionary integration yet — those land in later slices
when concrete visual primitives (tree / panel / progress / prompt)
need a `TerminalProfile` to switch glyphs against.

Detection rules per §7.0.2:

  1. `NO_COLOR` env (any value) → color_mode=none, use_emoji=False,
     use_unicode_box_chars=True (color is the noise; structure stays).
  2. `FORCE_COLOR` env (any value) → max capability regardless of TTY
     (CI dashboards rendering ANSI).
  3. `CI=true` (GitHub Actions / GitLab CI / etc.) → is_ci=True,
     use_emoji=False, use_unicode_box_chars=True, JSON-log default.
  4. Windows + no `WT_SESSION` + encoding ≠ UTF-8 → ASCII fallback.
  5. Non-TTY stdout → progress/spinner/tree never animate; single-line
     milestones.

The rules are layered: rule 1 takes precedence over rule 2, rule 2
over rule 3, etc. — `NO_COLOR` always wins because it's an explicit
opt-out, `FORCE_COLOR` is an explicit opt-in that overrides the
TTY-sniffing heuristics, and the heuristics layer below those.
"""

from __future__ import annotations

import locale
import os
import shutil
import sys
from dataclasses import dataclass
from typing import Literal

import wcwidth

ColorMode = Literal["truecolor", "256", "16", "none"]


@dataclass(frozen=True)
class TerminalProfile:
    """Detected capabilities of the terminal Sange is running in.

    Computed once per process via `detect_profile()`; immutable so the
    cached instance can be safely passed to visual primitives without
    "did someone mutate this?" worries.
    """

    is_tty: bool
    is_ci: bool
    encoding: str
    has_utf8: bool
    is_windows: bool
    is_modern_windows_terminal: bool
    shell: str
    color_mode: ColorMode
    use_emoji: bool
    use_unicode_box_chars: bool
    width: int


@dataclass(frozen=True)
class Glyphs:
    """Visual glyph map for a given `TerminalProfile`.

    Every visual primitive (tree, panel, status line) reads from
    this struct so the switch between emoji / Unicode / ASCII is a
    single decision, not threaded ad-hoc through render code.
    """

    success: str
    failure: str
    warning: str
    in_progress: str
    bullet: str
    tree_branch: str       # `├──` or `+--`
    tree_last: str         # `└──` or `\--`
    tree_vert: str         # `│ ` or `|  `
    section_rule: str      # `─` or `-`


_GLYPHS_EMOJI: Glyphs = Glyphs(
    success="✅",
    failure="❌",
    warning="⚠️",
    in_progress="…",
    bullet="•",
    tree_branch="├──",
    tree_last="└──",
    tree_vert="│  ",
    section_rule="─",
)

_GLYPHS_UNICODE: Glyphs = Glyphs(
    success="✓",
    failure="✗",
    warning="△",
    in_progress="…",
    bullet="•",
    tree_branch="├──",
    tree_last="└──",
    tree_vert="│  ",
    section_rule="─",
)

_GLYPHS_ASCII: Glyphs = Glyphs(
    success="[OK]",
    failure="[FAIL]",
    warning="[WARN]",
    in_progress="...",
    bullet="*",
    tree_branch="+--",
    tree_last="\\--",
    tree_vert="|  ",
    section_rule="-",
)


def detect_profile(
    *,
    env: os._Environ[str] | dict[str, str] | None = None,
    stream: object | None = None,
) -> TerminalProfile:
    """Compute the active `TerminalProfile`.

    Args:
      env:    environment mapping to consult (default: `os.environ`).
              Tests pass a custom dict to exercise specific scenarios
              without touching the real env.
      stream: stream to query for TTY-ness + encoding (default:
              `sys.stdout`). Tests pass a mock with `.isatty()` /
              `.encoding`.

    Note: this function is NOT memoized — callers are expected to
    compute once at startup and pass the result down. A
    process-global cache would defeat the test-injection pattern;
    if a global is desired later it can wrap this with `@cache`.
    """

    effective_env: dict[str, str] = dict(env if env is not None else os.environ)
    out = stream if stream is not None else sys.stdout

    no_color = "NO_COLOR" in effective_env
    force_color = "FORCE_COLOR" in effective_env
    ci = effective_env.get("CI", "").lower() in {"true", "1", "yes"}

    is_tty = bool(getattr(out, "isatty", lambda: False)())
    encoding = (
        getattr(out, "encoding", None) or locale.getpreferredencoding(False) or "ascii"
    ).lower()
    has_utf8 = "utf" in encoding

    is_windows = sys.platform.startswith("win") or effective_env.get("OS", "") == "Windows_NT"
    wt_session = "WT_SESSION" in effective_env
    is_modern_windows_terminal = is_windows and wt_session

    # Color mode resolution: NO_COLOR > FORCE_COLOR > CI > TTY heuristics.
    color_mode: ColorMode
    if no_color:
        color_mode = "none"
    elif force_color:
        color_mode = "truecolor"
    elif not is_tty and not ci:
        # Piped stdout, no CI signal — be conservative.
        color_mode = "none"
    elif effective_env.get("COLORTERM", "").lower() in {"truecolor", "24bit"}:
        color_mode = "truecolor"
    elif effective_env.get("TERM", "").lower() == "dumb":
        color_mode = "none"
    elif "256" in effective_env.get("TERM", "").lower():
        color_mode = "256"
    elif is_tty:
        color_mode = "16"
    else:
        color_mode = "none"

    # Emoji: requires UTF-8 + non-CI + non-NO_COLOR + not legacy-Windows.
    use_emoji = (
        has_utf8
        and not no_color
        and not ci
        and not (is_windows and not is_modern_windows_terminal)
    )

    # Unicode box chars: similar but more permissive — they're structure,
    # not decoration. CI keeps them (deterministic non-emoji glyphs).
    use_unicode_box_chars = (
        has_utf8
        and not (is_windows and not is_modern_windows_terminal and not has_utf8)
    )
    # NO_COLOR explicitly preserves structure (per §7.0.2 rule 1).
    if no_color:
        use_unicode_box_chars = has_utf8
    # Legacy Windows without UTF-8 falls back to ASCII boxes.
    if is_windows and not is_modern_windows_terminal and not has_utf8:
        use_unicode_box_chars = False

    width = _terminal_width()

    shell_name = _detect_shell(effective_env)

    return TerminalProfile(
        is_tty=is_tty,
        is_ci=ci,
        encoding=encoding,
        has_utf8=has_utf8,
        is_windows=is_windows,
        is_modern_windows_terminal=is_modern_windows_terminal,
        shell=shell_name,
        color_mode=color_mode,
        use_emoji=use_emoji,
        use_unicode_box_chars=use_unicode_box_chars,
        width=width,
    )


def glyphs_for(profile: TerminalProfile) -> Glyphs:
    """Pick the glyph set matching `profile`.

    Priority: emoji > Unicode > ASCII. A profile with both `use_emoji`
    AND `use_unicode_box_chars` (the typical modern terminal) gets the
    emoji set; a non-emoji UTF-8 terminal gets Unicode arrows + check
    marks; everything else falls back to ASCII.
    """

    if profile.use_emoji:
        return _GLYPHS_EMOJI
    if profile.use_unicode_box_chars:
        return _GLYPHS_UNICODE
    return _GLYPHS_ASCII


def truncate_to_width(text: str, width: int, *, suffix: str = "…") -> str:
    """Truncate `text` to a maximum display width using `wcwidth`.

    Display width != string length: CJK chars are width 2, combining
    accents are width 0, zero-width joiners + emoji-modifier sequences
    are width-tricky. We use `wcwidth.wcswidth` which `rich` itself uses.

    The suffix (default `…`) is appended only when truncation happens,
    and counts toward the width budget.
    """

    if width <= 0:
        return ""
    total_width = wcwidth.wcswidth(text)
    if total_width < 0:
        # `wcswidth` returns -1 for strings containing non-printable
        # characters. Best-effort: trust the character count.
        if len(text) <= width:
            return text
        return text[:max(width - len(suffix), 0)] + suffix
    if total_width <= width:
        return text

    suffix_width = max(wcwidth.wcswidth(suffix), 0)
    budget = max(width - suffix_width, 0)
    out: list[str] = []
    used = 0
    for ch in text:
        ch_width = wcwidth.wcwidth(ch)
        if ch_width < 0:
            ch_width = 1  # treat non-printable as 1-wide for budget math
        if used + ch_width > budget:
            break
        out.append(ch)
        used += ch_width
    return "".join(out) + suffix


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _terminal_width() -> int:
    """Width via `shutil.get_terminal_size`, with a sane fallback."""

    try:
        size = shutil.get_terminal_size(fallback=(80, 24))
        return size.columns
    except OSError:
        return 80


def _detect_shell(env: dict[str, str]) -> str:
    """Detect the parent shell name; gracefully degrade if shellingham fails.

    The §7.0.1 library-picks table mandates `shellingham`; the
    architecture prompt also says "fallback to env vars on import
    failure". We honor both: try shellingham first, fall back to
    SHELL/COMSPEC env-var inspection.
    """

    try:
        import shellingham
    except ImportError:
        return _shell_from_env(env)

    try:
        name, _path = shellingham.detect_shell()
        return str(name)
    except Exception:
        return _shell_from_env(env)


def _shell_from_env(env: dict[str, str]) -> str:
    """Last-resort shell guess from env vars."""

    if "SHELL" in env:
        return os.path.basename(env["SHELL"]) or "unknown"
    if "COMSPEC" in env:
        return os.path.basename(env["COMSPEC"]).lower().replace(".exe", "") or "cmd"
    return "unknown"


__all__ = [
    "ColorMode",
    "Glyphs",
    "TerminalProfile",
    "detect_profile",
    "glyphs_for",
    "truncate_to_width",
]
