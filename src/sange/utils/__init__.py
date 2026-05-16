"""`sange.utils` — cross-cutting helpers used by both the CLI and core.

Currently exports:

  * `TerminalProfile`     — frozen dataclass describing terminal capabilities.
  * `detect_profile()`    — compute the profile once per process (§7.0.2).
  * `Glyphs`              — Unicode-vs-ASCII glyph map.
  * `glyphs_for(profile)` — get the `Glyphs` instance matching a profile.
  * `truncate_to_width()` — wcwidth-aware truncation.

Future modules: `progress.py` (§7.0.4), `gate.py` (§7.0.5 typed-phrase).
"""

from __future__ import annotations

from sange.utils.terminal import (
    Glyphs,
    TerminalProfile,
    detect_profile,
    glyphs_for,
    truncate_to_width,
)

__all__ = [
    "Glyphs",
    "TerminalProfile",
    "detect_profile",
    "glyphs_for",
    "truncate_to_width",
]
