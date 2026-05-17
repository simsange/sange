"""`rich.console.Console` factory that honors a `TerminalProfile`.

Per §7.0.1 + §7.0.2: every visual primitive accepts a `TerminalProfile`
and selects its color/emoji/box-char behavior accordingly. This
module is the glue between the profile + the `rich` library —
construct one `Console` at startup from the cached profile, then
pass that around.

Surface:

  * `make_console(profile, *, stderr=False, file=None)` — build a
    `rich.console.Console` whose color/encoding/width match the
    profile's detection result.
  * `success_panel(profile, message, *, title=None)` /
    `failure_panel(...)` / `warning_panel(...)` — `rich.panel.Panel`
    instances whose border + glyph come from the profile's glyph
    map. Used by the §7.0.8 error rendering convention
    (`Panel(title="Error", border_style="red")`).
  * `success_text(profile, message)` / `failure_text(...)` /
    `warning_text(...)` — single-line rich `Text` objects with the
    profile's glyph prefixed. Lighter than a Panel for inline use
    (e.g. progress per-task status).

Color-mode mapping into rich:

  * `color_mode="none"`    → `Console(color_system=None)`
  * `color_mode="16"`      → `Console(color_system="standard")`
  * `color_mode="256"`     → `Console(color_system="256")`
  * `color_mode="truecolor"` → `Console(color_system="truecolor")`

`is_ci` → `force_terminal=False, force_interactive=False`. Width
is taken from the profile (not from rich's own detection) so that
CI logs are wrapped to a deterministic column count.
"""

from __future__ import annotations

from typing import IO, Literal

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from sange.utils.terminal import TerminalProfile, glyphs_for

# `rich.console.Console` types `color_system` as a Literal of the allowed
# system names (plus None). Mirror that so mypy stays happy.
_RichColorSystem = Literal["auto", "standard", "256", "truecolor", "windows"]

_COLOR_MODE_MAP: dict[str, _RichColorSystem | None] = {
    "none": None,
    "16": "standard",
    "256": "256",
    "truecolor": "truecolor",
}


def make_console(
    profile: TerminalProfile,
    *,
    stderr: bool = False,
    file: IO[str] | None = None,
) -> Console:
    """Construct a `rich.console.Console` matching `profile`.

    Args:
      profile: cached `TerminalProfile` from `detect_profile()`.
      stderr:  when True, write to stderr (status / progress).
      file:    explicit file override (tests).

    The width / no_color / force_terminal / color_system fields are
    derived from the profile; the caller doesn't need to know rich's
    internal flags.
    """

    color_system = _COLOR_MODE_MAP.get(profile.color_mode)
    no_color = profile.color_mode == "none"

    return Console(
        file=file,
        stderr=stderr,
        color_system=color_system,
        force_terminal=profile.is_tty and not profile.is_ci,
        force_interactive=profile.is_tty and not profile.is_ci,
        no_color=no_color,
        width=profile.width,
        emoji=profile.use_emoji,
        markup=True,
        soft_wrap=False,
    )


# --------------------------------------------------------------------------- #
# Status panels + texts
# --------------------------------------------------------------------------- #


def success_text(profile: TerminalProfile, message: str) -> Text:
    """Single-line `Text` with the profile's success glyph + message."""

    g = glyphs_for(profile)
    return Text.assemble((g.success + " ", "green"), message)


def failure_text(profile: TerminalProfile, message: str) -> Text:
    g = glyphs_for(profile)
    return Text.assemble((g.failure + " ", "red bold"), message)


def warning_text(profile: TerminalProfile, message: str) -> Text:
    g = glyphs_for(profile)
    return Text.assemble((g.warning + " ", "yellow"), message)


def success_panel(
    profile: TerminalProfile,
    message: str,
    *,
    title: str | None = None,
) -> Panel:
    """`Panel` with green border for a successful operation summary."""

    body = success_text(profile, message)
    return Panel(
        body,
        title=title,
        border_style="green",
        padding=(0, 1),
    )


def failure_panel(
    profile: TerminalProfile,
    message: str,
    *,
    title: str | None = "Error",
) -> Panel:
    """`Panel` with red border for an error.

    Default title matches §7.0.8: `Panel(title="Error",
    border_style="red")`.
    """

    body = failure_text(profile, message)
    return Panel(
        body,
        title=title,
        border_style="red",
        padding=(0, 1),
    )


def warning_panel(
    profile: TerminalProfile,
    message: str,
    *,
    title: str | None = "Warning",
) -> Panel:
    body = warning_text(profile, message)
    return Panel(
        body,
        title=title,
        border_style="yellow",
        padding=(0, 1),
    )


__all__ = [
    "failure_panel",
    "failure_text",
    "make_console",
    "success_panel",
    "success_text",
    "warning_panel",
    "warning_text",
]
