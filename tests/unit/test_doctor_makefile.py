"""Tests for the §10.3 Makefile-tracked check in `sange doctor`."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from sange.cli.doctor import _check_makefile_tracked


_GIT = shutil.which("git")

_ENV = {
    "PATH": "/usr/bin:/usr/local/bin:/opt/homebrew/bin",
    "HOME": "/tmp",
    "GIT_AUTHOR_NAME": "Test",
    "GIT_AUTHOR_EMAIL": "t@t",
    "GIT_COMMITTER_NAME": "Test",
    "GIT_COMMITTER_EMAIL": "t@t",
}


def _init_repo(path: Path) -> None:
    subprocess.run(
        ["git", "init", "-q", "-b", "main", str(path)], env=_ENV, check=True
    )
    for cmd in (
        ["git", "config", "user.email", "t@t"],
        ["git", "config", "user.name", "Test"],
    ):
        subprocess.run(cmd, cwd=path, env=_ENV, check=True)


# --------------------------------------------------------------------------- #
# Edge cases — no git, no makefile, etc.
# --------------------------------------------------------------------------- #


class TestNotGitRepo:
    def test_skipped_when_not_in_git_repo(self, tmp_path: Path) -> None:
        result = _check_makefile_tracked(tmp_path)
        assert result.ok is True
        assert "skipped" in result.message.lower() or "not a git" in result.message.lower()


@pytest.mark.skipif(_GIT is None, reason="git not on PATH")
class TestGitNoMakefile:
    def test_no_makefile_passes(self, tmp_path: Path) -> None:
        _init_repo(tmp_path)
        result = _check_makefile_tracked(tmp_path)
        assert result.ok is True
        assert "not present" in result.message.lower()


# --------------------------------------------------------------------------- #
# The §10.3 happy path — Makefile gitignored
# --------------------------------------------------------------------------- #


@pytest.mark.skipif(_GIT is None, reason="git not on PATH")
class TestGitignored:
    def test_makefile_in_gitignore_passes(self, tmp_path: Path) -> None:
        _init_repo(tmp_path)
        (tmp_path / ".gitignore").write_text("Makefile\n")
        (tmp_path / "Makefile").write_text("# generated\n")
        result = _check_makefile_tracked(tmp_path)
        assert result.ok is True
        assert "gitignored" in result.message.lower()
        assert result.details == {"tracked": False}

    def test_makefile_not_yet_added_passes(self, tmp_path: Path) -> None:
        # Makefile exists, no .gitignore, but the file isn't `git add`-ed.
        # Per §10.3 the contract is "must be gitignored"; an unadded file
        # is OK (the user hasn't touched it yet) — the failure case is
        # only when it's actually tracked.
        _init_repo(tmp_path)
        (tmp_path / "Makefile").write_text("# fresh emit\n")
        result = _check_makefile_tracked(tmp_path)
        assert result.ok is True


# --------------------------------------------------------------------------- #
# The §10.3 failure path — Makefile tracked
# --------------------------------------------------------------------------- #


@pytest.mark.skipif(_GIT is None, reason="git not on PATH")
class TestTracked:
    def test_tracked_makefile_fails(self, tmp_path: Path) -> None:
        _init_repo(tmp_path)
        (tmp_path / "Makefile").write_text("all:\n\t@echo hi\n")
        subprocess.run(
            ["git", "add", "Makefile"], cwd=tmp_path, env=_ENV, check=True
        )
        subprocess.run(
            ["git", "commit", "-q", "-m", "initial"],
            cwd=tmp_path, env=_ENV, check=True,
        )
        result = _check_makefile_tracked(tmp_path)
        assert result.ok is False
        assert "tracked" in result.message.lower()
        assert "§10.3" in result.message
        assert "sange fix-makefile-tracked" in result.message
        assert result.details == {"tracked": True}

    def test_tracked_staged_but_uncommitted_fails(
        self, tmp_path: Path
    ) -> None:
        """`git ls-files --error-unmatch` returns 0 for staged-but-uncommitted
        files too, so the check fires before the bad commit even lands."""

        _init_repo(tmp_path)
        (tmp_path / "Makefile").write_text("all:\n\t@echo hi\n")
        subprocess.run(
            ["git", "add", "Makefile"], cwd=tmp_path, env=_ENV, check=True
        )
        result = _check_makefile_tracked(tmp_path)
        assert result.ok is False


# --------------------------------------------------------------------------- #
# Repo-root override
# --------------------------------------------------------------------------- #


@pytest.mark.skipif(_GIT is None, reason="git not on PATH")
class TestRepoRootArg:
    def test_explicit_repo_root_used(self, tmp_path: Path) -> None:
        # Build two repos under tmp_path; the check must look at the
        # one we pass, not the cwd.
        repo_clean = tmp_path / "clean"
        repo_clean.mkdir()
        _init_repo(repo_clean)

        repo_bad = tmp_path / "bad"
        repo_bad.mkdir()
        _init_repo(repo_bad)
        (repo_bad / "Makefile").write_text("all:\n\t@echo hi\n")
        subprocess.run(
            ["git", "add", "Makefile"], cwd=repo_bad, env=_ENV, check=True
        )

        # Passing repo_clean → ok.
        r1 = _check_makefile_tracked(repo_clean)
        assert r1.ok is True
        # Passing repo_bad → fail.
        r2 = _check_makefile_tracked(repo_bad)
        assert r2.ok is False
