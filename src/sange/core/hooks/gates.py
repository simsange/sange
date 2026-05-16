"""Named-gate library (T-103) — preconfigured hook scripts on top of T-102.

A "gate" is a Sange-shipped (or user-shipped) named bundle of hook
scripts. Each gate lives under one of these roots:

  1. `<repo>/.sange/gates/<name>/`        — per-repo overrides
  2. `~/.sange/gates/<name>/`             — per-user overrides
  3. `<sange-install>/templates/hooks/<name>/`  — shipped defaults

Each gate directory holds:

  ./manifest.toml                  — required metadata.
  ./<event>.sh / .py / etc.        — the hook script(s).

The manifest looks like:

    [gate]
    name = "gitleaks"
    display_name = "Gitleaks (secret scanner)"
    version = "1.0.0"
    description = "Scans the staged diff for committed secrets."
    required_tool = "gitleaks"
    install_hint = "brew install gitleaks  # or https://gitleaks.io/"

    [events.pre-commit]
    priority = 5
    source = "pre-commit.sh"

`add_gate(repo, name)` copies every event's `source` script into
`<repo>/.sange/hooks/<event>/<priority>-<name><.ext>` and `chmod
+x`'s it. `remove_gate(repo, name)` removes the same files (any
file under `.sange/hooks/<event>/` whose name matches
`<priority>-<name>.<ext>` for the gate's declared events).

This module owns the registry + add/remove plumbing only. The
`sange hooks add/remove/gates` CLI surfaces wrap it. The actual
scripts ship under `templates/hooks/<name>/`.
"""

from __future__ import annotations

import os
import re
import shutil
import stat
import tomllib
from dataclasses import dataclass, field
from pathlib import Path


class GateError(Exception):
    """Raised when a gate manifest is malformed or a gate operation fails."""


@dataclass(frozen=True)
class GateEvent:
    """One event's hook script within a gate.

    Fields:
      * `event`    — the git lifecycle event (e.g. `pre-commit`).
      * `priority` — 0..99 — passed through to T-102's filename
                     convention (`<priority:02d>-<name>`).
      * `source`   — relative path within the gate directory.
    """

    event: str
    priority: int
    source: str


@dataclass(frozen=True)
class Gate:
    """One named gate.

    Fields:
      * `name`           — short slug (e.g. `gitleaks`).
      * `display_name`   — human label.
      * `version`        — semver string.
      * `description`    — one-line summary.
      * `required_tool`  — the external binary the gate depends on
                           (e.g. `gitleaks`, `trufflehog`, `make`).
                           When set, scripts can shell out to detect
                           presence + skip when missing.
      * `install_hint`   — one-line install command suggestion shown
                           on missing-tool.
      * `events`         — tuple of `GateEvent` (one per supported
                           lifecycle event).
      * `source_dir`     — absolute on-disk path of the gate dir.
    """

    name: str
    display_name: str = ""
    version: str = ""
    description: str = ""
    required_tool: str = ""
    install_hint: str = ""
    events: tuple[GateEvent, ...] = ()
    source_dir: Path = field(default_factory=Path)

    def __post_init__(self) -> None:
        if not self.name:
            raise GateError("Gate.name must be non-empty")
        if not re.fullmatch(r"[a-z0-9](?:-?[a-z0-9])*", self.name):
            raise GateError(
                f"Gate.name {self.name!r} must be lowercase slug-like "
                f"(letters/digits/hyphens)"
            )
        if not self.events:
            raise GateError(
                f"Gate {self.name!r}: at least one event must be declared"
            )
        seen_events: set[str] = set()
        for e in self.events:
            if e.event in seen_events:
                raise GateError(
                    f"Gate {self.name!r}: duplicate event {e.event!r}"
                )
            seen_events.add(e.event)
        if not self.display_name:
            object.__setattr__(self, "display_name", self.name)


def load_gate(manifest_path: Path) -> Gate:
    """Parse a `manifest.toml` into a `Gate`.

    The manifest lives at `<gate_dir>/manifest.toml`; this loader
    reads it + verifies every event's `source` file exists in the
    same directory.
    """

    if not manifest_path.is_file():
        raise GateError(f"manifest not found: {manifest_path}")

    try:
        with manifest_path.open("rb") as fp:
            data = tomllib.load(fp)
    except tomllib.TOMLDecodeError as exc:
        raise GateError(f"{manifest_path}: invalid TOML — {exc}") from exc

    gate_section = data.get("gate")
    if not isinstance(gate_section, dict):
        raise GateError(f"{manifest_path}: missing [gate] section")
    name = str(gate_section.get("name", "") or "")
    if not name:
        raise GateError(f"{manifest_path}: [gate].name required")

    gate_dir = manifest_path.parent.resolve()

    events_section = data.get("events")
    if not isinstance(events_section, dict):
        raise GateError(
            f"{manifest_path}: missing [events] table"
        )
    events: list[GateEvent] = []
    for event_name, event_data in events_section.items():
        if not isinstance(event_data, dict):
            raise GateError(
                f"{manifest_path}: [events.{event_name}] must be a table"
            )
        priority_raw = event_data.get("priority", 50)
        if not isinstance(priority_raw, int):
            raise GateError(
                f"{manifest_path}: events.{event_name}.priority must be int"
            )
        if not 0 <= priority_raw <= 99:
            raise GateError(
                f"{manifest_path}: events.{event_name}.priority "
                f"must be 0..99, got {priority_raw}"
            )
        source_raw = event_data.get("source", "")
        if not isinstance(source_raw, str) or not source_raw:
            raise GateError(
                f"{manifest_path}: events.{event_name}.source required (string)"
            )
        source_path = gate_dir / source_raw
        if not source_path.is_file():
            raise GateError(
                f"{manifest_path}: events.{event_name}.source file "
                f"not found at {source_path}"
            )
        events.append(GateEvent(
            event=str(event_name),
            priority=priority_raw,
            source=source_raw,
        ))

    return Gate(
        name=name,
        display_name=str(gate_section.get("display_name", "") or ""),
        version=str(gate_section.get("version", "") or ""),
        description=str(gate_section.get("description", "") or ""),
        required_tool=str(gate_section.get("required_tool", "") or ""),
        install_hint=str(gate_section.get("install_hint", "") or ""),
        events=tuple(events),
        source_dir=gate_dir,
    )


# --------------------------------------------------------------------------- #
# Registry
# --------------------------------------------------------------------------- #


class GateRegistry:
    """Indexed view over discoverable gates.

    Roots searched in priority order (highest first). A gate name
    seen in a higher-priority root shadows lower-priority entries.
    """

    def __init__(self, roots: list[Path]) -> None:
        self._roots = [Path(r) for r in roots]
        self._by_name: dict[str, Gate] = {}
        self._skipped: list[tuple[Path, str]] = []
        self._load_all()

    @property
    def roots(self) -> tuple[Path, ...]:
        return tuple(self._roots)

    @property
    def skipped(self) -> tuple[tuple[Path, str], ...]:
        return tuple(self._skipped)

    def get(self, name: str) -> Gate:
        try:
            return self._by_name[name]
        except KeyError as exc:
            raise GateError(
                f"gate not found: {name!r} (known: "
                f"{', '.join(sorted(self._by_name)) or '<empty>'})"
            ) from exc

    def has(self, name: str) -> bool:
        return name in self._by_name

    def all_gates(self) -> tuple[Gate, ...]:
        return tuple(sorted(self._by_name.values(), key=lambda g: g.name))

    def _load_all(self) -> None:
        for root in self._roots:
            if not root.is_dir():
                continue
            for child in sorted(root.iterdir()):
                if not child.is_dir():
                    continue
                manifest = child / "manifest.toml"
                if not manifest.is_file():
                    continue
                try:
                    gate = load_gate(manifest)
                except GateError as exc:
                    self._skipped.append((manifest, str(exc)))
                    continue
                if gate.name in self._by_name:
                    # Higher-priority root won; skip the duplicate.
                    continue
                self._by_name[gate.name] = gate


def default_gate_roots(repo_root: Path | None = None) -> list[Path]:
    """Build the canonical three-tier root list (per-repo > user > shipped)."""

    roots: list[Path] = []
    if repo_root is not None:
        roots.append(Path(repo_root).resolve() / ".sange" / "gates")
    home = Path.home()
    roots.append(home / ".sange" / "gates")
    # The shipped templates live at <repo>/templates/hooks/ —
    # locate via the package layout.
    here = Path(__file__).resolve()
    # core/hooks/gates.py → core/hooks → core → sange → src → <repo>
    pkg_root = here.parent.parent.parent.parent.parent
    roots.append(pkg_root / "templates" / "hooks")
    return roots


# --------------------------------------------------------------------------- #
# add_gate / remove_gate
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class GateActionResult:
    """One file's outcome from `add_gate` / `remove_gate`."""

    event: str
    target_path: Path
    status: str
    # status ∈ {"added", "updated", "removed", "skipped-event-not-requested",
    #           "skipped-absent"}


def add_gate(
    repo_root: Path,
    gate: Gate,
    *,
    events: tuple[str, ...] | None = None,
) -> tuple[GateActionResult, ...]:
    """Copy `gate`'s event scripts into `<repo>/.sange/hooks/<event>/`.

    `events=None` installs every event the gate declares.
    Otherwise, restricts to the named events.

    Returns one `GateActionResult` per event copy attempt — status
    `"added"` when the script was newly written, `"updated"` when
    it overwrote a prior version (same target path), or
    `"skipped-event-not-requested"` when `events` filtered it out.
    """

    if events is not None and not events:
        raise GateError("add_gate: events list must be non-empty (or None)")

    selected_events = (
        set(events) if events is not None else {e.event for e in gate.events}
    )

    repo_root = Path(repo_root).resolve()
    results: list[GateActionResult] = []
    for ge in gate.events:
        if ge.event not in selected_events:
            results.append(GateActionResult(
                event=ge.event,
                target_path=Path(),
                status="skipped-event-not-requested",
            ))
            continue
        # Target filename: <priority:02d>-<gate.name><suffix>.
        # Preserve the source's file extension so the kernel's
        # shebang-driven dispatch works.
        suffix = Path(ge.source).suffix
        target = (
            repo_root / ".sange" / "hooks" / ge.event
            / f"{ge.priority:02d}-{gate.name}{suffix}"
        )
        target.parent.mkdir(parents=True, exist_ok=True)
        source_path = gate.source_dir / ge.source
        existed = target.exists()
        shutil.copy(source_path, target)
        # Ensure +x.
        mode = target.stat().st_mode
        target.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        results.append(GateActionResult(
            event=ge.event,
            target_path=target,
            status="updated" if existed else "added",
        ))

    return tuple(results)


def remove_gate(
    repo_root: Path,
    gate: Gate,
    *,
    events: tuple[str, ...] | None = None,
) -> tuple[GateActionResult, ...]:
    """Remove `gate`'s event scripts from `<repo>/.sange/hooks/`.

    `events=None` removes every event the gate declares. Otherwise,
    restricts to the named events. Files that don't exist on disk
    yield status `"skipped-absent"`.
    """

    if events is not None and not events:
        raise GateError("remove_gate: events list must be non-empty (or None)")

    selected_events = (
        set(events) if events is not None else {e.event for e in gate.events}
    )

    repo_root = Path(repo_root).resolve()
    results: list[GateActionResult] = []
    for ge in gate.events:
        if ge.event not in selected_events:
            results.append(GateActionResult(
                event=ge.event,
                target_path=Path(),
                status="skipped-event-not-requested",
            ))
            continue
        suffix = Path(ge.source).suffix
        target = (
            repo_root / ".sange" / "hooks" / ge.event
            / f"{ge.priority:02d}-{gate.name}{suffix}"
        )
        if not target.exists():
            results.append(GateActionResult(
                event=ge.event,
                target_path=target,
                status="skipped-absent",
            ))
            continue
        try:
            target.unlink()
        except OSError as exc:
            raise GateError(
                f"remove_gate: cannot remove {target}: {exc}"
            ) from exc
        results.append(GateActionResult(
            event=ge.event,
            target_path=target,
            status="removed",
        ))

    return tuple(results)


__all__ = [
    "Gate",
    "GateActionResult",
    "GateError",
    "GateEvent",
    "GateRegistry",
    "add_gate",
    "default_gate_roots",
    "load_gate",
    "remove_gate",
]


# Suppress flake on the unused import (load_gate is exported, registry uses it).
_ = os
