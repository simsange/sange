"""Tests for src/sange/core/hooks/shim.py — .git/hooks/<event> shim writer."""

from __future__ import annotations

import os
import stat
from pathlib import Path

import pytest

from sange.core.hooks.shim import (
    GIT_HOOK_EVENTS,
    SHIM_MARKER,
    ShimError,
    install_git_shims,
    uninstall_git_shims,
)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A repo root with `.git/` and `.sange/` skeletons."""

    r = tmp_path / "repo"
    (r / ".git").mkdir(parents=True)
    (r / ".sange" / "hooks").mkdir(parents=True)
    return r


def _write_hook(path: Path, body: str = "exit 0\n", *, executable: bool = True) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("#!/usr/bin/env bash\n" + body, encoding="utf-8")
    if executable:
        mode = path.stat().st_mode
        path.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


class TestInstallGitShims:
    def test_no_hooks_no_shims_written(self, repo: Path) -> None:
        results = install_git_shims(repo)
        installed = [r for r in results if r.status == "installed"]
        assert installed == []
        no_hook = [r for r in results if r.status == "skipped-no-hooks"]
        assert len(no_hook) == len(GIT_HOOK_EVENTS)

    def test_installs_only_events_with_hooks(self, repo: Path) -> None:
        _write_hook(repo / ".sange" / "hooks" / "pre-commit" / "10-x.sh")
        results = install_git_shims(repo)
        installed = [r for r in results if r.status == "installed"]
        assert len(installed) == 1
        assert installed[0].event == "pre-commit"
        # Shim is executable.
        assert os.access(installed[0].path, os.X_OK)
        # Shim carries the marker.
        content = installed[0].path.read_text(encoding="utf-8")
        assert SHIM_MARKER in content
        assert "exec sange hooks run pre-commit" in content

    def test_idempotent_rerun_marks_updated(self, repo: Path) -> None:
        _write_hook(repo / ".sange" / "hooks" / "pre-commit" / "10-x.sh")
        install_git_shims(repo)
        results = install_git_shims(repo)
        updated = [r for r in results if r.status == "updated"]
        assert len(updated) == 1
        assert updated[0].event == "pre-commit"

    def test_foreign_hook_skipped_by_default(self, repo: Path) -> None:
        _write_hook(repo / ".sange" / "hooks" / "pre-commit" / "10-x.sh")
        # Pre-existing user hook in .git/hooks/.
        foreign = repo / ".git" / "hooks" / "pre-commit"
        foreign.parent.mkdir(parents=True, exist_ok=True)
        foreign.write_text("#!/bin/sh\necho hand-written\nexit 0\n")
        foreign.chmod(0o755)

        results = install_git_shims(repo)
        skipped = [r for r in results if r.status == "skipped-foreign"]
        assert len(skipped) == 1
        # Foreign content unchanged.
        assert "hand-written" in foreign.read_text(encoding="utf-8")

    def test_force_overwrites_foreign(self, repo: Path) -> None:
        _write_hook(repo / ".sange" / "hooks" / "pre-commit" / "10-x.sh")
        foreign = repo / ".git" / "hooks" / "pre-commit"
        foreign.parent.mkdir(parents=True, exist_ok=True)
        foreign.write_text("#!/bin/sh\necho hand-written\n")

        results = install_git_shims(repo, force=True)
        installed = [r for r in results if r.status == "installed"]
        assert len(installed) == 1
        # Foreign content replaced with shim.
        assert SHIM_MARKER in foreign.read_text(encoding="utf-8")

    def test_restrict_to_events(self, repo: Path) -> None:
        _write_hook(repo / ".sange" / "hooks" / "pre-commit" / "10-x.sh")
        _write_hook(repo / ".sange" / "hooks" / "pre-push" / "10-y.sh")
        results = install_git_shims(repo, events=["pre-commit"])
        assert len(results) == 1
        assert results[0].event == "pre-commit"
        assert results[0].status == "installed"
        # pre-push shim is NOT written.
        assert not (repo / ".git" / "hooks" / "pre-push").exists()

    def test_non_git_repo_rejected(self, tmp_path: Path) -> None:
        with pytest.raises(ShimError, match="not a git working tree"):
            install_git_shims(tmp_path / "no-git")


class TestUninstallGitShims:
    def test_removes_sange_shims(self, repo: Path) -> None:
        _write_hook(repo / ".sange" / "hooks" / "pre-commit" / "10-x.sh")
        install_git_shims(repo)
        results = uninstall_git_shims(repo)
        removed = [r for r in results if r.status == "removed"]
        assert len(removed) == 1
        assert not (repo / ".git" / "hooks" / "pre-commit").exists()

    def test_leaves_foreign_alone(self, repo: Path) -> None:
        foreign = repo / ".git" / "hooks" / "pre-commit"
        foreign.parent.mkdir(parents=True, exist_ok=True)
        foreign.write_text("#!/bin/sh\necho not-sange\nexit 0\n")

        results = uninstall_git_shims(repo)
        sf = [r for r in results if r.status == "skipped-foreign"]
        assert len(sf) == 1
        # Foreign file still on disk.
        assert "not-sange" in foreign.read_text(encoding="utf-8")

    def test_absent_event_reported(self, repo: Path) -> None:
        results = uninstall_git_shims(repo, events=["pre-commit"])
        assert len(results) == 1
        assert results[0].status == "skipped-absent"
