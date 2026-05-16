"""Tests for src/sange/core/gitignore/swap.py — atomic swap + recovery.

Each crash-at-phase-N test simulates a `kill -9` by manually
writing a journal at the chosen phase + leaving the rest of the
filesystem in the intermediate state, then calls `recover()` and
verifies the swap completes cleanly.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
from pathlib import Path

import pytest

from sange.core.gitignore.compose import compose
from sange.core.gitignore.registry import ProfileRegistry
from sange.core.gitignore.swap import GitignoreSwap


def _write(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


def _toml_min(name: str, category: str, *, always: list[str] | None = None) -> str:
    items = always or []
    joined = ", ".join(f'"{x}"' for x in items)
    return (
        f'[profile]\nname = "{name}"\ncategory = "{category}"\n'
        f'[patterns]\nalways = [{joined}]\n'
    )


_FIXED_CLOCK = _dt.datetime(2026, 5, 16, 12, 0, 0, tzinfo=_dt.UTC)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """An empty repo root with a small profile registry alongside."""

    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    return repo_root


@pytest.fixture
def registry(tmp_path: Path) -> ProfileRegistry:
    profile_dir = tmp_path / "profiles"
    _write(profile_dir / "py.toml",
           _toml_min("lang/python", "lang", always=["__pycache__/", "*.pyc"]))
    _write(profile_dir / "node.toml",
           _toml_min("lang/node", "lang", always=["node_modules/"]))
    return ProfileRegistry([profile_dir])


class TestSwapHappyPath:
    def test_first_swap_writes_gitignore_and_active_profile(
        self, repo: Path, registry: ProfileRegistry,
    ) -> None:
        swap = GitignoreSwap(repo, registry=registry, clock=_FIXED_CLOCK)
        result = swap.swap(["lang/python"], stage="dev")
        assert result.profiles == ("lang/python",)
        assert result.stage == "dev"
        assert result.was_recovered is False
        assert result.bytes_written > 0
        # Artifacts on disk.
        assert (repo / ".gitignore").is_file()
        assert (repo / ".sange" / ".active-profile").is_file()
        # Journal cleaned up.
        assert list((repo / ".sange" / ".recovery").glob("swap-*.json")) == []

    def test_active_profile_records_request(
        self, repo: Path, registry: ProfileRegistry,
    ) -> None:
        swap = GitignoreSwap(repo, registry=registry, clock=_FIXED_CLOCK)
        swap.swap(["lang/python"], stage="dev")
        text = (repo / ".sange" / ".active-profile").read_text(encoding="utf-8")
        assert "profiles=lang/python" in text
        assert "stage=dev" in text

    def test_subsequent_swap_replaces_gitignore(
        self, repo: Path, registry: ProfileRegistry,
    ) -> None:
        swap = GitignoreSwap(repo, registry=registry, clock=_FIXED_CLOCK)
        swap.swap(["lang/python"], stage="dev")
        first = (repo / ".gitignore").read_text(encoding="utf-8")
        swap.swap(["lang/node"], stage="dev")
        second = (repo / ".gitignore").read_text(encoding="utf-8")
        assert first != second
        assert "__pycache__/" in first
        assert "node_modules/" in second
        assert "__pycache__/" not in second

    def test_gitignore_includes_provenance_header(
        self, repo: Path, registry: ProfileRegistry,
    ) -> None:
        swap = GitignoreSwap(repo, registry=registry, clock=_FIXED_CLOCK)
        swap.swap(["lang/python"], stage="dev")
        text = (repo / ".gitignore").read_text(encoding="utf-8")
        assert "composed by `sange gitignore swap`" in text
        assert "lang/python" in text


class TestSwapAtomicity:
    def test_no_tmp_files_left_after_success(
        self, repo: Path, registry: ProfileRegistry,
    ) -> None:
        swap = GitignoreSwap(repo, registry=registry, clock=_FIXED_CLOCK)
        swap.swap(["lang/python"], stage="dev")
        # No `.gitignore.<...>swap-tmp` files leak.
        leftovers = list(repo.glob(".gitignore.*"))
        assert leftovers == [], f"leaked tmp files: {leftovers}"
        # Same in .sange/.
        sange_leftovers = list((repo / ".sange").glob(".active-profile.*"))
        assert sange_leftovers == [], f"leaked .sange tmp files: {sange_leftovers}"


def _write_journal_at_phase(
    repo: Path,
    *,
    phase: str,
    profiles: list[str],
    stage: str,
    registry: ProfileRegistry,
) -> Path:
    """Plant a journal file simulating a crash at `phase`."""

    planned = compose(profiles, stage=stage, registry=registry,
                      clock=_FIXED_CLOCK)
    journal_dir = repo / ".sange" / ".recovery"
    journal_dir.mkdir(parents=True, exist_ok=True)
    journal_id = "swap-20260516T120000Z"
    journal_path = journal_dir / f"{journal_id}.json"
    payload = {
        "journal_id": journal_id,
        "profiles": profiles,
        "stage": stage,
        "planned_sha256": hashlib.sha256(planned.encode("utf-8")).hexdigest(),
        "old_gitignore_content": None,
        "old_active_profile_content": None,
        "phase": phase,
        "started_at": _FIXED_CLOCK.isoformat(),
        "planned_content": planned,
    }
    journal_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return journal_path


class TestRecoveryFromCrash:
    def test_recover_no_journals_is_noop(
        self, repo: Path, registry: ProfileRegistry,
    ) -> None:
        swap = GitignoreSwap(repo, registry=registry, clock=_FIXED_CLOCK)
        results = swap.recover()
        assert results == []

    def test_recover_from_prepared_phase(
        self, repo: Path, registry: ProfileRegistry,
    ) -> None:
        # Simulated crash right after the journal landed but before any
        # other artifact was written.
        _write_journal_at_phase(
            repo, phase="prepared",
            profiles=["lang/python"], stage="dev", registry=registry,
        )
        swap = GitignoreSwap(repo, registry=registry, clock=_FIXED_CLOCK)
        results = swap.recover()
        assert len(results) == 1
        assert results[0].was_recovered is True
        # Recovery wrote the missing artifacts.
        assert (repo / ".gitignore").is_file()
        assert (repo / ".sange" / ".active-profile").is_file()
        # Journal cleaned up.
        assert list((repo / ".sange" / ".recovery").glob("swap-*.json")) == []

    def test_recover_from_wrote_gitignore_phase(
        self, repo: Path, registry: ProfileRegistry,
    ) -> None:
        # Simulated crash after .gitignore was written but before
        # .active-profile.
        _write_journal_at_phase(
            repo, phase="wrote_gitignore",
            profiles=["lang/node"], stage="dev", registry=registry,
        )
        # Pretend .gitignore was already written (we don't bother with
        # exact content — the recovery path skips re-writing it).
        (repo / ".gitignore").write_text("placeholder\n")
        swap = GitignoreSwap(repo, registry=registry, clock=_FIXED_CLOCK)
        results = swap.recover()
        assert len(results) == 1
        # Recovery wrote the missing .active-profile.
        assert (repo / ".sange" / ".active-profile").is_file()
        text = (repo / ".sange" / ".active-profile").read_text(encoding="utf-8")
        assert "lang/node" in text

    def test_recover_from_activated_phase_just_cleans(
        self, repo: Path, registry: ProfileRegistry,
    ) -> None:
        # Phase 3 done, only the journal cleanup didn't happen.
        _write_journal_at_phase(
            repo, phase="activated",
            profiles=["lang/python"], stage="dev", registry=registry,
        )
        swap = GitignoreSwap(repo, registry=registry, clock=_FIXED_CLOCK)
        results = swap.recover()
        assert len(results) == 1
        # Journal is gone.
        assert list((repo / ".sange" / ".recovery").glob("swap-*.json")) == []
