"""SangeConfig loader — precedence-chain merge + file discovery + ENV overrides.

Implements §6.3 of the architecture prompt:

    built-in defaults
      ← /etc/sange/config.{toml,json}
        ← ~/.sange/config.{toml,json}
          ← ${repo}/.sange/config.{toml,json}
            ← SANGE__* environment variables
              ← CLI flags (passed as a dict by the caller)

Rightmost wins on conflict. The result is a single validated
`SangeConfig` instance.

File-extension dispatch:
  * `*.toml` parsed with stdlib `tomllib` (Python 3.11+); on 3.10 we fall
    back to `tomli` (declared as a transitive dependency for testing).
  * `*.json` parsed with stdlib `json`.
  * If both `config.toml` AND `config.json` exist at the same level,
    JSON wins (machine-authoritative) with a warning per §6.3.

Repository discovery walks up from the supplied `cwd` (or `os.getcwd()`)
looking for a `.sange/` directory. The first hit is the repo's config
location; missing files are silently treated as empty (no override).

ENV-override format:
  * Variables matching `SANGE__SECTION__SUBSECTION__FIELD=value` map onto
    the nested model — e.g. `SANGE__VARIANTS__DEFAULT_STAGE=staging`
    overrides `variants.default_stage`.
  * `__` (two underscores) is the nesting separator.
  * List-valued fields use comma-separated values:
    `SANGE__VARIANTS__STAGES=dev,staging,production`.

Schema-version handling:
  * On-disk `schema_version` is compared to `SCHEMA_CURRENT`.
  * Same major + same-or-older minor → accepted.
  * Older major → auto-migration (creates a backup at `<file>.bak-<ts>`).
  * Newer than current → `SchemaVersionError` (the config file is from a
    future Sange version; we refuse to silently drop fields).

Pure stdlib (no `pydantic-settings` dependency) — works during bootstrap
before `pip install -e ".[dev]"` runs.
"""

from __future__ import annotations

import datetime as _dt
import json
import os
import re
import shutil

# tomllib is stdlib in Python 3.11+. The project floor is 3.12
# (pyproject.toml::requires-python) so tomllib is always available; the
# legacy try/except fallback to `tomli` was kept for paranoia but mypy
# correctly flags it as dead code. Plain import — no fallback needed.
import tomllib
import warnings
from pathlib import Path
from typing import Any

from sange.core.config.models import (
    SCHEMA_CURRENT,
    SangeConfig,
    SchemaVersion,
)

# --------------------------------------------------------------------------- #
# Exceptions
# --------------------------------------------------------------------------- #


class ConfigError(Exception):
    """Base exception for config-related failures."""


class EnvOverrideError(ConfigError):
    """An `SANGE__*` env var couldn't be applied — malformed key or value."""


class SchemaVersionError(ConfigError):
    """The on-disk `schema_version` is incompatible with the current code."""


# --------------------------------------------------------------------------- #
# Defaults
# --------------------------------------------------------------------------- #


DEFAULT_USER_DIR = Path.home() / ".sange"
DEFAULT_SYSTEM_DIR = Path("/etc/sange")
ENV_PREFIX = "SANGE__"
ENV_SEPARATOR = "__"


# --------------------------------------------------------------------------- #
# Repository discovery
# --------------------------------------------------------------------------- #


def discover_repo_config(start: Path | None = None) -> Path | None:
    """Walk upward from `start` (or cwd) looking for `.sange/config.{json,toml}`.

    Returns the path to the first matching config file, or None if no
    `.sange/` directory is found before reaching the filesystem root.
    """

    here = Path(start) if start is not None else Path.cwd()
    here = here.resolve()
    while True:
        candidate_dir = here / ".sange"
        if candidate_dir.is_dir():
            # JSON wins when both exist (§6.3 + ADR-009).
            json_path = candidate_dir / "config.json"
            toml_path = candidate_dir / "config.toml"
            if json_path.is_file() and toml_path.is_file():
                warnings.warn(
                    f"Both config.json and config.toml exist in {candidate_dir} — "
                    "JSON wins (machine-authoritative per ADR-009).",
                    stacklevel=2,
                )
                return json_path
            if json_path.is_file():
                return json_path
            if toml_path.is_file():
                return toml_path
            # `.sange/` exists but no config file → no override; keep walking
            # up in case a parent has one (unusual but harmless).
        parent = here.parent
        if parent == here:
            return None
        here = parent


# --------------------------------------------------------------------------- #
# File parsing
# --------------------------------------------------------------------------- #


def _parse_config_file(path: Path) -> dict[str, Any]:
    """Parse a TOML or JSON config file. Returns {} on missing file."""

    if not path.is_file():
        return {}
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".toml":
        return tomllib.loads(text)
    if path.suffix.lower() == ".json":
        parsed: dict[str, Any] = json.loads(text)
        return parsed
    raise ConfigError(
        f"config file {path} has unrecognized extension; expected .toml or .json"
    )


def _candidate_files(directory: Path) -> list[Path]:
    """Return existing config files in `directory`, JSON-first per ADR-009."""

    if not directory.is_dir():
        return []
    found: list[Path] = []
    json_path = directory / "config.json"
    toml_path = directory / "config.toml"
    if json_path.is_file() and toml_path.is_file():
        warnings.warn(
            f"Both config.json and config.toml exist in {directory} — JSON wins.",
            stacklevel=3,
        )
        found.append(json_path)
    elif json_path.is_file():
        found.append(json_path)
    elif toml_path.is_file():
        found.append(toml_path)
    return found


# --------------------------------------------------------------------------- #
# Merge utilities
# --------------------------------------------------------------------------- #


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Right-wins deep merge. Lists are replaced; dicts are merged recursively.

    Pure function — returns a new dict, doesn't mutate either input.
    """

    out: dict[str, Any] = dict(base)
    for key, value in override.items():
        if (
            key in out
            and isinstance(out[key], dict)
            and isinstance(value, dict)
        ):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = value
    return out


# --------------------------------------------------------------------------- #
# ENV-var → nested dict
# --------------------------------------------------------------------------- #


_ENV_KEY_RE = re.compile(r"^SANGE(?:__[A-Z][A-Z0-9_]*)+$")


def _env_value_cast(value: str) -> Any:
    """Convert a raw env-var string to a typed Python value.

    The model layer does strict pydantic validation, so we only do the
    rough cast here: bool literals, numerics, comma-lists, otherwise str.
    """

    stripped = value.strip()
    lower = stripped.lower()
    if lower in {"true", "yes", "on"}:
        return True
    if lower in {"false", "no", "off"}:
        return False
    if stripped and stripped.lstrip("-").isdigit():
        try:
            return int(stripped)
        except ValueError:
            pass
    if "," in stripped:
        return [item.strip() for item in stripped.split(",") if item.strip()]
    # Float?
    try:
        if "." in stripped and stripped.lstrip("-").replace(".", "").isdigit():
            return float(stripped)
    except ValueError:
        pass
    return stripped


def env_overrides(environ: dict[str, str] | None = None) -> dict[str, Any]:
    """Extract `SANGE__SECTION__FIELD=value` env vars into a nested dict.

    Example:
        SANGE__VARIANTS__DEFAULT_STAGE=staging
        SANGE__VARIANTS__STAGES=dev,staging,production
        SANGE__AUDIT__ENABLED=false

    →   {
            "variants": {
                "default_stage": "staging",
                "stages": ["dev", "staging", "production"],
            },
            "audit": {"enabled": False},
        }

    Returns {} when no matching env vars are present. Malformed keys raise
    `EnvOverrideError`.
    """

    src = environ if environ is not None else dict(os.environ)
    out: dict[str, Any] = {}
    for raw_key, raw_value in sorted(src.items()):  # sorted for determinism
        if not raw_key.startswith(ENV_PREFIX):
            continue
        if not _ENV_KEY_RE.match(raw_key):
            raise EnvOverrideError(
                f"env var {raw_key!r} matches the {ENV_PREFIX} prefix but isn't "
                f"a valid nested key (expected SANGE__SECTION__FIELD...)"
            )
        # Strip prefix, split on the separator, lowercase each segment.
        body = raw_key[len(ENV_PREFIX):]
        path_parts = [p.lower() for p in body.split(ENV_SEPARATOR) if p]
        if not path_parts:
            continue
        cursor: dict[str, Any] = out
        for segment in path_parts[:-1]:
            existing = cursor.get(segment)
            if not isinstance(existing, dict):
                cursor[segment] = {}
            cursor = cursor[segment]
        cursor[path_parts[-1]] = _env_value_cast(raw_value)
    return out


# --------------------------------------------------------------------------- #
# Schema-version handling
# --------------------------------------------------------------------------- #


def _check_schema_version(
    payload: dict[str, Any],
    source_path: Path | None,
) -> dict[str, Any]:
    """Validate the on-disk schema_version and migrate if needed.

    Returns the (possibly migrated) payload. Raises `SchemaVersionError`
    if the file is from a future Sange version.
    """

    if "schema_version" not in payload:
        # Older format that pre-dates schema versioning — assume v1.0 and
        # let pydantic stamp the current version on save.
        return payload

    raw = payload["schema_version"]
    if isinstance(raw, dict):
        on_disk = SchemaVersion(**raw)
    elif isinstance(raw, str):
        # Forgiving parse for `"1.0"` string form.
        try:
            major, minor = raw.split(".")
            on_disk = SchemaVersion(major=int(major), minor=int(minor))
        except (ValueError, KeyError) as exc:
            raise SchemaVersionError(
                f"schema_version {raw!r} in {source_path} is not parseable"
            ) from exc
    else:
        raise SchemaVersionError(
            f"schema_version in {source_path} has unsupported type {type(raw).__name__}"
        )

    if on_disk.is_newer_than(SCHEMA_CURRENT):
        raise SchemaVersionError(
            f"Config at {source_path} declares schema_version {on_disk.as_tuple()} "
            f"which is newer than this Sange's {SCHEMA_CURRENT.as_tuple()}. "
            "Upgrade Sange or downgrade the config."
        )

    if not on_disk.is_compatible_with(SCHEMA_CURRENT):
        # Older major — back up the file and write a migration marker.
        if source_path is not None:
            _backup_file(source_path)
        warnings.warn(
            f"Config at {source_path} declares schema_version {on_disk.as_tuple()} "
            f"(older major than {SCHEMA_CURRENT.as_tuple()}). A backup was written; "
            "field migration may be incomplete. Re-save the config to upgrade.",
            stacklevel=3,
        )

    return payload


def _backup_file(path: Path) -> Path:
    ts = _dt.datetime.now(_dt.UTC).strftime("%Y%m%dT%H%M%SZ")
    backup = path.with_suffix(path.suffix + f".bak-{ts}")
    shutil.copy2(path, backup)
    return backup


# --------------------------------------------------------------------------- #
# Public loader
# --------------------------------------------------------------------------- #


def load_config(
    *,
    repo_root: Path | None = None,
    user_dir: Path | None = None,
    system_dir: Path | None = None,
    environ: dict[str, str] | None = None,
    cli_overrides: dict[str, Any] | None = None,
    skip_discovery: bool = False,
) -> SangeConfig:
    """Load the full precedence chain into a validated `SangeConfig`.

    Args:
      repo_root: Optional explicit `${repo}/.sange/` parent. If None,
                 `discover_repo_config()` walks upward from cwd.
      user_dir:  Default `~/.sange/`.
      system_dir: Default `/etc/sange/`.
      environ:   Mapping to use instead of `os.environ` (for testing).
      cli_overrides: Highest-priority override dict (nested shape).
      skip_discovery: When True, do not walk upward looking for `.sange/`.
                      Useful in tests that pass an explicit `repo_root`.

    Returns:
      A validated, immutable `SangeConfig`.
    """

    layers: list[dict[str, Any]] = []

    # Layer 1: built-in defaults (the model's own defaults).
    layers.append(SangeConfig().model_dump())

    # Layer 2: /etc/sange
    sys_dir = system_dir or DEFAULT_SYSTEM_DIR
    for f in _candidate_files(sys_dir):
        layers.append(_parse_config_file(f))

    # Layer 3: ~/.sange
    usr_dir = user_dir or DEFAULT_USER_DIR
    for f in _candidate_files(usr_dir):
        layers.append(_parse_config_file(f))

    # Layer 4: ${repo}/.sange
    repo_config: Path | None = None
    if repo_root is not None:
        for f in _candidate_files(repo_root / ".sange"):
            repo_config = f
            layers.append(_parse_config_file(f))
    elif not skip_discovery:
        repo_config = discover_repo_config()
        if repo_config is not None:
            layers.append(_parse_config_file(repo_config))

    # Layer 5: ENV
    layers.append(env_overrides(environ))

    # Layer 6: CLI flags
    if cli_overrides:
        layers.append(cli_overrides)

    # Merge in order, then validate.
    merged: dict[str, Any] = {}
    for layer in layers:
        merged = _deep_merge(merged, layer)

    merged = _check_schema_version(merged, source_path=repo_config)

    try:
        return SangeConfig.model_validate(merged)
    except Exception as exc:
        raise ConfigError(
            f"merged config failed validation: {exc}"
        ) from exc


__all__ = [
    "DEFAULT_SYSTEM_DIR",
    "DEFAULT_USER_DIR",
    "ENV_PREFIX",
    "ENV_SEPARATOR",
    "ConfigError",
    "EnvOverrideError",
    "SchemaVersionError",
    "discover_repo_config",
    "env_overrides",
    "load_config",
]
