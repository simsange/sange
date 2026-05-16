"""`Profile` — a single gitignore profile loaded from TOML.

Per §6.5 + ADR-032, every profile under `templates/gitignore-profiles/`
follows the same schema:

  [profile]    name / display_name / category / version / maintainer / ...
  [detect]     required_any[]  (files that activate the profile)
               boost_any[]     (confidence boosters)
  [patterns]   always[]        (lines emitted in every stage)
               dev_only[]      (lines emitted when stage=dev)
               prod_only[]     (lines emitted when stage=prod)
  [extends]    profiles[]      (profile names this one extends)

This module owns the in-memory representation + the TOML-to-model
mapping. Validation lives here (cycle detection on extends-chains
happens in `registry.py` since it needs the registry to resolve
references; per-profile invariants are enforced here).
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path


class ProfileError(Exception):
    """Raised when a profile's TOML is malformed or violates invariants."""


@dataclass(frozen=True)
class Profile:
    """One gitignore profile.

    Fields:
      * `name`              — slash-separated `<category>/<topic>` (e.g.
                              `lang/python`, `framework/django`).
      * `display_name`      — human-readable label.
      * `category`          — top-level category (`lang` / `framework` /
                              `infra` / `editor` / `os` / `_core`).
      * `version`           — semver string of the profile itself.
      * `maintainer`        — `Name <email>` string.
      * `upstream_source`   — origin URL the patterns derive from, or "".
      * `notes`             — free-text caveats / context, or "".
      * `required_any`      — files that mark a repo as needing this profile.
      * `boost_any`         — files that boost the auto-detection confidence.
      * `patterns_always`   — gitignore lines always emitted.
      * `patterns_dev`      — gitignore lines emitted only when stage=dev.
      * `patterns_prod`     — gitignore lines emitted only when stage=prod.
      * `extends`           — names of profiles this one extends (in order).
      * `source_path`       — absolute on-disk path the profile was loaded from.
    """

    name: str
    category: str
    display_name: str = ""
    version: str = ""
    maintainer: str = ""
    upstream_source: str = ""
    notes: str = ""
    required_any: tuple[str, ...] = ()
    boost_any: tuple[str, ...] = ()
    patterns_always: tuple[str, ...] = ()
    patterns_dev: tuple[str, ...] = ()
    patterns_prod: tuple[str, ...] = ()
    extends: tuple[str, ...] = ()
    source_path: Path = field(default_factory=lambda: Path())

    def __post_init__(self) -> None:
        if not self.name:
            raise ProfileError("Profile.name must be non-empty")
        if not self.category:
            raise ProfileError(f"Profile {self.name!r}: category must be non-empty")
        if "/" not in self.name and self.category != "_core":
            raise ProfileError(
                f"Profile.name {self.name!r} must be `<category>/<topic>` (except `_core/*`)"
            )
        if self.name in self.extends:
            raise ProfileError(
                f"Profile {self.name!r}: extends list cannot contain self"
            )
        # Fill display_name from name when omitted (load_profile already
        # does this when the TOML omits the key; this catches direct
        # construction paths in tests / plugin code).
        if not self.display_name:
            object.__setattr__(self, "display_name", self.name)

    def patterns_for_stage(self, stage: str) -> tuple[str, ...]:
        """Return the patterns this profile contributes for `stage`.

        `stage` is one of `"dev"` / `"prod"`. Unknown stages fall
        back to `patterns_always` only.
        """

        if stage == "dev":
            return self.patterns_always + self.patterns_dev
        if stage == "prod":
            return self.patterns_always + self.patterns_prod
        return self.patterns_always


def load_profile(path: Path) -> Profile:
    """Load a `Profile` from a TOML file at `path`.

    Raises `ProfileError` if the file is malformed or required keys
    are missing.
    """

    if not path.is_file():
        raise ProfileError(f"profile file not found: {path}")

    try:
        with path.open("rb") as fp:
            data = tomllib.load(fp)
    except tomllib.TOMLDecodeError as exc:
        raise ProfileError(f"{path}: invalid TOML — {exc}") from exc

    prof = data.get("profile")
    if not isinstance(prof, dict):
        raise ProfileError(f"{path}: missing [profile] section")

    name = prof.get("name", "")
    category = prof.get("category", "")
    if not name or not category:
        raise ProfileError(
            f"{path}: [profile] requires `name` and `category`"
        )

    detect = data.get("detect", {}) or {}
    patterns = data.get("patterns", {}) or {}
    extends_section = data.get("extends", {}) or {}

    return Profile(
        name=str(name),
        display_name=str(prof.get("display_name", name)),
        category=str(category),
        version=str(prof.get("version", "")),
        maintainer=str(prof.get("maintainer", "")),
        upstream_source=str(prof.get("upstream_source", "")),
        notes=str(prof.get("notes", "")),
        required_any=tuple(_string_list(detect.get("required_any"))),
        boost_any=tuple(_string_list(detect.get("boost_any"))),
        patterns_always=tuple(_string_list(patterns.get("always"))),
        patterns_dev=tuple(_string_list(patterns.get("dev_only"))),
        patterns_prod=tuple(_string_list(patterns.get("prod_only"))),
        extends=tuple(_string_list(extends_section.get("profiles"))),
        source_path=path.resolve(),
    )


def _string_list(value: object) -> list[str]:
    """Coerce a TOML value to a list[str], rejecting non-string entries."""

    if value is None:
        return []
    if not isinstance(value, list):
        raise ProfileError(f"expected list of strings, got {type(value).__name__}")
    out: list[str] = []
    for item in value:
        if not isinstance(item, str):
            raise ProfileError(
                f"list contains non-string entry {item!r} ({type(item).__name__})"
            )
        out.append(item)
    return out


__all__ = ["Profile", "ProfileError", "load_profile"]
