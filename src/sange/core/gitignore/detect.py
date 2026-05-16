"""Profile auto-detection.

Walks `repo_root` checking each profile's `[detect].required_any`
against the visible top-level files, then optionally boosts the
match via `[detect].boost_any`. Returns an ordered list of
candidates with confidence scores.

The detector is **structural only** — no AI, no inference. Each
profile's `required_any` is a list of file globs / names; if any
one matches a file at the repo root, the profile is a candidate.
`boost_any` adds 1 confidence point per matching file. Required
matches contribute 2 points each (capped at the profile's
required_any length to prevent runaway scoring on weird repos).

Caller patterns:

  * `sange init --auto-detect-profile`  — pick the single best
    candidate; if there are ties, surface them to the user.
  * `sange gitignore detect`            — show every candidate
    with its score.
  * Programmatic                        — `detect_profiles(...)`
                                          returns the full
                                          ranking.
"""

from __future__ import annotations

import fnmatch
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from sange.core.gitignore.profile import Profile
from sange.core.gitignore.registry import ProfileRegistry

# Detection looks at the repo root only by default. Some patterns
# (`pyproject.toml`, `package.json`) live there; deeper-nested
# markers (e.g. an Android module's `build.gradle`) need a wider
# walk. The walk depth is a v0.5-alpha boundary; the v1.0 detector
# will tier confidence by depth.
_DEFAULT_WALK_DEPTH = 1


@dataclass(frozen=True)
class DetectionResult:
    """One profile candidate with its evidence + confidence score."""

    profile: Profile
    confidence: int
    matched_required: tuple[str, ...]
    matched_boost: tuple[str, ...]


def detect_profiles(
    repo_root: Path,
    registry: ProfileRegistry,
    *,
    walk_depth: int = _DEFAULT_WALK_DEPTH,
) -> tuple[DetectionResult, ...]:
    """Rank every loaded profile against `repo_root`.

    Returns candidates with `confidence > 0`, sorted by confidence
    descending then by profile name (stable for tied scores).
    Profiles whose `required_any` is empty (rare; the `_core/*`
    profiles tend to omit it) are skipped — they apply unconditionally,
    not via detection.

    Args:
      repo_root:  the directory to inspect.
      registry:   the loaded profile registry.
      walk_depth: how deep to look for marker files. 0 = root only;
                  1 = root + immediate subdirs; etc. Default 1.

    The detector reads file names only — it never opens files.
    Symlinks are followed at most one level (`Path.iterdir` default).
    """

    if walk_depth < 0:
        raise ValueError(f"walk_depth must be >= 0; got {walk_depth}")

    present = _collect_files(Path(repo_root), max_depth=walk_depth)

    results: list[DetectionResult] = []
    for profile in registry.all_profiles():
        if not profile.required_any:
            continue
        matched_req = tuple(_matches(present, profile.required_any))
        if not matched_req:
            continue
        matched_boost = tuple(_matches(present, profile.boost_any))
        confidence = 2 * len(matched_req) + len(matched_boost)
        results.append(
            DetectionResult(
                profile=profile,
                confidence=confidence,
                matched_required=matched_req,
                matched_boost=matched_boost,
            )
        )

    results.sort(key=lambda r: (-r.confidence, r.profile.name))
    return tuple(results)


def _collect_files(root: Path, *, max_depth: int) -> set[str]:
    """Return every visible file name (basename) within `max_depth` of `root`.

    Hidden directories (`.git/`, `node_modules/`, etc.) are skipped
    because they generate noise without adding signal. The shipped
    `.sange/` directory is also skipped (its presence is implied
    when this detector runs).
    """

    skip_dirs = {".git", "node_modules", "__pycache__", ".sange",
                 ".venv", "venv", "dist", "build", ".tox",
                 ".mypy_cache", ".ruff_cache", ".pytest_cache"}
    if not root.is_dir():
        return set()

    out: set[str] = set()

    def _walk(d: Path, depth: int) -> None:
        try:
            children = list(d.iterdir())
        except (PermissionError, OSError):
            return
        for child in children:
            if child.name in skip_dirs:
                continue
            if child.is_file() or child.is_symlink():
                out.add(child.name)
            elif child.is_dir() and depth < max_depth:
                _walk(child, depth + 1)

    _walk(root, 0)
    return out


def _matches(present: Iterable[str], patterns: Iterable[str]) -> list[str]:
    """Return every pattern that matches at least one file in `present`.

    Each pattern is a literal filename or a `fnmatch`-style glob
    (`*.py`, `*.lock`, etc.). The presence check tests against
    basenames only — directory paths in patterns are stripped.
    """

    present_set = set(present)
    matched: list[str] = []
    for pattern in patterns:
        # Strip leading directory paths from the pattern; the
        # `[detect].required_any` convention is to use bare
        # filenames or globs.
        base = pattern.split("/")[-1]
        # Literal match first (faster + clearer signal in tests).
        if base in present_set:
            matched.append(pattern)
            continue
        # Glob match second.
        if any(fnmatch.fnmatchcase(name, base) for name in present_set):
            matched.append(pattern)
    return matched


__all__ = ["DetectionResult", "detect_profiles"]
