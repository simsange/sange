"""Tests for src/sange/core/hooks/gates.py — registry + add/remove."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from sange.core.hooks.gates import (
    Gate,
    GateError,
    GateEvent,
    GateRegistry,
    add_gate,
    default_gate_roots,
    load_gate,
    remove_gate,
)


def _write(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


def _write_exec(path: Path, body: str) -> None:
    _write(path, body)
    path.chmod(path.stat().st_mode | 0o111)


def _gate_dir(
    root: Path,
    name: str,
    *,
    events: dict[str, tuple[int, str]] | None = None,
    description: str = "test gate",
    required_tool: str = "",
) -> Path:
    """Build a fixture gate directory + manifest under `root/<name>/`."""

    gate_dir = root / name
    gate_dir.mkdir(parents=True, exist_ok=True)

    events = events or {"pre-commit": (50, "pre-commit.sh")}
    parts = [
        "[gate]",
        f'name = "{name}"',
        f'display_name = "{name.title()}"',
        'version = "1.0.0"',
        f'description = "{description}"',
        f'required_tool = "{required_tool}"',
    ]
    for ev, (priority, source) in events.items():
        parts.append("")
        parts.append(f"[events.{ev}]")
        parts.append(f"priority = {priority}")
        parts.append(f'source = "{source}"')
        # Materialize the script file too.
        _write_exec(gate_dir / source,
                    "#!/usr/bin/env bash\nexit 0\n")
    _write(gate_dir / "manifest.toml", "\n".join(parts) + "\n")
    return gate_dir


# --------------------------------------------------------------------------- #
# load_gate
# --------------------------------------------------------------------------- #


class TestLoadGate:
    def test_minimal(self, tmp_path: Path) -> None:
        gd = _gate_dir(tmp_path, "x")
        gate = load_gate(gd / "manifest.toml")
        assert gate.name == "x"
        assert gate.events[0].event == "pre-commit"
        assert gate.events[0].priority == 50
        assert gate.events[0].source == "pre-commit.sh"

    def test_missing_manifest_raises(self, tmp_path: Path) -> None:
        with pytest.raises(GateError, match="not found"):
            load_gate(tmp_path / "no-such" / "manifest.toml")

    def test_missing_gate_section_raises(self, tmp_path: Path) -> None:
        _write(tmp_path / "manifest.toml", "[events.pre-commit]\npriority = 5\nsource = \"x.sh\"\n")
        with pytest.raises(GateError, match=r"\[gate\]"):
            load_gate(tmp_path / "manifest.toml")

    def test_missing_name_raises(self, tmp_path: Path) -> None:
        _write(tmp_path / "manifest.toml",
               '[gate]\nversion = "1"\n[events.pre-commit]\npriority = 5\nsource = "x.sh"\n')
        with pytest.raises(GateError, match="name required"):
            load_gate(tmp_path / "manifest.toml")

    def test_missing_events_raises(self, tmp_path: Path) -> None:
        _write(tmp_path / "manifest.toml",
               '[gate]\nname = "x"\n')
        with pytest.raises(GateError, match=r"\[events\]"):
            load_gate(tmp_path / "manifest.toml")

    def test_priority_out_of_range(self, tmp_path: Path) -> None:
        _write(tmp_path / "manifest.toml",
               '[gate]\nname = "x"\n[events.pre-commit]\npriority = 100\nsource = "x.sh"\n')
        _write_exec(tmp_path / "x.sh", "#!/usr/bin/env bash\n")
        with pytest.raises(GateError, match=r"0\.\.99"):
            load_gate(tmp_path / "manifest.toml")

    def test_source_must_exist(self, tmp_path: Path) -> None:
        _write(tmp_path / "manifest.toml",
               '[gate]\nname = "x"\n[events.pre-commit]\npriority = 5\nsource = "missing.sh"\n')
        with pytest.raises(GateError, match="not found"):
            load_gate(tmp_path / "manifest.toml")


# --------------------------------------------------------------------------- #
# Gate invariants
# --------------------------------------------------------------------------- #


class TestGateInvariants:
    def test_name_must_be_slug(self) -> None:
        e = (GateEvent(event="pre-commit", priority=10, source="x.sh"),)
        with pytest.raises(GateError, match="lowercase slug"):
            Gate(name="BadName", events=e)

    def test_no_events_rejected(self) -> None:
        with pytest.raises(GateError, match="at least one event"):
            Gate(name="x", events=())

    def test_duplicate_event_rejected(self) -> None:
        e = (
            GateEvent(event="pre-commit", priority=10, source="a.sh"),
            GateEvent(event="pre-commit", priority=20, source="b.sh"),
        )
        with pytest.raises(GateError, match="duplicate"):
            Gate(name="x", events=e)


# --------------------------------------------------------------------------- #
# GateRegistry
# --------------------------------------------------------------------------- #


class TestGateRegistry:
    def test_discovers_gates(self, tmp_path: Path) -> None:
        _gate_dir(tmp_path, "alpha")
        _gate_dir(tmp_path, "beta")
        reg = GateRegistry([tmp_path])
        names = [g.name for g in reg.all_gates()]
        assert names == ["alpha", "beta"]

    def test_shadowing(self, tmp_path: Path) -> None:
        shipped = tmp_path / "shipped"
        per_repo = tmp_path / "repo"
        _gate_dir(shipped, "alpha", description="shipped version")
        _gate_dir(per_repo, "alpha", description="repo override")
        reg = GateRegistry([per_repo, shipped])
        assert reg.get("alpha").description == "repo override"

    def test_bad_manifest_skipped(self, tmp_path: Path) -> None:
        _gate_dir(tmp_path, "good")
        # Bad gate dir: manifest missing [gate].
        (tmp_path / "bad").mkdir()
        _write(tmp_path / "bad" / "manifest.toml", "[events.pre-commit]\n")
        reg = GateRegistry([tmp_path])
        assert reg.has("good")
        assert not reg.has("bad")
        assert len(reg.skipped) == 1

    def test_get_unknown(self, tmp_path: Path) -> None:
        reg = GateRegistry([tmp_path])
        with pytest.raises(GateError, match="not found"):
            reg.get("nope")


class TestShippedGates:
    """Smoke: every gate under templates/hooks/ loads cleanly."""

    def test_four_shipped_gates_load(self) -> None:
        reg = GateRegistry(default_gate_roots())
        names = {g.name for g in reg.all_gates()}
        # T-103 ships these four.
        assert {"gitleaks", "trufflehog", "make-test", "make-lint"} <= names
        assert reg.skipped == ()


# --------------------------------------------------------------------------- #
# add_gate / remove_gate
# --------------------------------------------------------------------------- #


class TestAddGate:
    def test_copies_script_and_makes_executable(self, tmp_path: Path) -> None:
        gates_root = tmp_path / "gates"
        repo = tmp_path / "repo"
        repo.mkdir()
        _gate_dir(gates_root, "x")
        reg = GateRegistry([gates_root])
        results = add_gate(repo, reg.get("x"))
        assert len(results) == 1
        assert results[0].status == "added"
        # Target path.
        target = repo / ".sange" / "hooks" / "pre-commit" / "50-x.sh"
        assert target.is_file()
        assert os.access(target, os.X_OK)

    def test_idempotent_update(self, tmp_path: Path) -> None:
        gates_root = tmp_path / "gates"
        repo = tmp_path / "repo"
        repo.mkdir()
        _gate_dir(gates_root, "x")
        reg = GateRegistry([gates_root])
        add_gate(repo, reg.get("x"))
        results = add_gate(repo, reg.get("x"))
        assert results[0].status == "updated"

    def test_event_filter(self, tmp_path: Path) -> None:
        gates_root = tmp_path / "gates"
        repo = tmp_path / "repo"
        repo.mkdir()
        _gate_dir(gates_root, "x", events={
            "pre-commit": (50, "pre-commit.sh"),
            "pre-push": (50, "pre-push.sh"),
        })
        reg = GateRegistry([gates_root])
        results = add_gate(repo, reg.get("x"), events=("pre-commit",))
        statuses = {r.event: r.status for r in results}
        assert statuses["pre-commit"] == "added"
        assert statuses["pre-push"] == "skipped-event-not-requested"
        assert (repo / ".sange" / "hooks" / "pre-commit" / "50-x.sh").is_file()
        assert not (repo / ".sange" / "hooks" / "pre-push" / "50-x.sh").exists()


class TestRemoveGate:
    def test_removes_added_script(self, tmp_path: Path) -> None:
        gates_root = tmp_path / "gates"
        repo = tmp_path / "repo"
        repo.mkdir()
        _gate_dir(gates_root, "x")
        reg = GateRegistry([gates_root])
        add_gate(repo, reg.get("x"))
        results = remove_gate(repo, reg.get("x"))
        assert results[0].status == "removed"
        assert not (repo / ".sange" / "hooks" / "pre-commit" / "50-x.sh").exists()

    def test_absent_reports_skipped_absent(self, tmp_path: Path) -> None:
        gates_root = tmp_path / "gates"
        repo = tmp_path / "repo"
        repo.mkdir()
        _gate_dir(gates_root, "x")
        reg = GateRegistry([gates_root])
        results = remove_gate(repo, reg.get("x"))
        assert results[0].status == "skipped-absent"
