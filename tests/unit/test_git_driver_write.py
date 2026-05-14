"""Tests for GitDriver write operations (T-005).

Each test starts from a tiny ephemeral repo + exercises a write method
against it. The fixture from test_git_driver.py would re-set-up history
we don't need; tests here use a minimal `fresh_repo` fixture that just
inits an empty repo with identity configured.

All tests skipped automatically when git is not on PATH.
"""

from __future__ import annotations

import shutil
import subprocess
from collections.abc import Iterator
from pathlib import Path

import pytest

from sange.adapters.vcs._protocol import DriverError, PushResult, TagInfo
from sange.adapters.vcs.git import GitDriver
from sange.adapters.vcs.git._subprocess import GitCommandFailed
from sange.core.models import BranchInfo, CommitRef


pytestmark = pytest.mark.skipif(
    shutil.which("git") is None,
    reason="git not installed; GitDriver write tests skipped",
)


def _run(cwd: Path, *args: str) -> str:
    return subprocess.run(
        args, cwd=str(cwd), capture_output=True, text=True, check=True,
    ).stdout


@pytest.fixture
def fresh_repo(tmp_path: Path) -> Iterator[Path]:
    """A clean repo with identity configured but no commits yet."""

    repo = tmp_path / "fresh"
    repo.mkdir()
    _run(repo, "git", "init", "--initial-branch=main")
    _run(repo, "git", "config", "user.email", "test@example.com")
    _run(repo, "git", "config", "user.name", "Test User")
    _run(repo, "git", "config", "commit.gpgsign", "false")
    yield repo


@pytest.fixture
def repo_with_one_commit(fresh_repo: Path) -> Path:
    """Fresh repo with one initial commit so HEAD exists."""

    (fresh_repo / "README.md").write_text("# initial\n")
    _run(fresh_repo, "git", "add", "README.md")
    _run(fresh_repo, "git", "commit", "-m", "initial")
    return fresh_repo


# --------------------------------------------------------------------------- #
# add
# --------------------------------------------------------------------------- #


class TestAdd:
    def test_stages_a_new_file(self, fresh_repo: Path) -> None:
        (fresh_repo / "a.txt").write_text("a\n")
        repo = GitDriver.detect(fresh_repo)
        GitDriver().add(repo, [Path("a.txt")])
        out = _run(fresh_repo, "git", "diff", "--cached", "--name-only")
        assert "a.txt" in out

    def test_empty_paths_is_no_op(self, fresh_repo: Path) -> None:
        repo = GitDriver.detect(fresh_repo)
        GitDriver().add(repo, [])  # No-op, no error.

    def test_absolute_path_rejected(self, fresh_repo: Path) -> None:
        repo = GitDriver.detect(fresh_repo)
        with pytest.raises(DriverError, match="relative"):
            GitDriver().add(repo, [Path("/etc/passwd")])


# --------------------------------------------------------------------------- #
# commit
# --------------------------------------------------------------------------- #


class TestCommit:
    def test_simple_commit(self, fresh_repo: Path) -> None:
        (fresh_repo / "foo.py").write_text("x = 1\n")
        repo = GitDriver.detect(fresh_repo)
        d = GitDriver()
        d.add(repo, [Path("foo.py")])
        commit = d.commit(repo, message="add foo")
        assert isinstance(commit, CommitRef)
        assert commit.subject == "add foo"
        assert len(commit.sha) == 40  # full sha1

    def test_commit_with_explicit_author(self, fresh_repo: Path) -> None:
        (fresh_repo / "x.txt").write_text("x\n")
        repo = GitDriver.detect(fresh_repo)
        d = GitDriver()
        d.add(repo, [Path("x.txt")])
        c = d.commit(
            repo, message="x",
            author_name="Alice", author_email="alice@example.com",
        )
        assert c.author_name == "Alice"
        assert c.author_email == "alice@example.com"

    def test_partial_author_rejected(self, fresh_repo: Path) -> None:
        (fresh_repo / "x.txt").write_text("x\n")
        repo = GitDriver.detect(fresh_repo)
        d = GitDriver()
        d.add(repo, [Path("x.txt")])
        with pytest.raises(DriverError, match="both be set or both omitted"):
            d.commit(repo, message="x", author_name="Alice")

    def test_empty_message_rejected(self, fresh_repo: Path) -> None:
        repo = GitDriver.detect(fresh_repo)
        with pytest.raises(DriverError, match="non-empty"):
            GitDriver().commit(repo, message="")

    def test_cr_in_subject_rejected(self, fresh_repo: Path) -> None:
        repo = GitDriver.detect(fresh_repo)
        with pytest.raises(DriverError, match="single-line"):
            GitDriver().commit(repo, message="bad\rsubject\nbody")

    def test_allow_empty(self, repo_with_one_commit: Path) -> None:
        repo = GitDriver.detect(repo_with_one_commit)
        # Without --allow-empty, git refuses; with it, succeeds.
        c = GitDriver().commit(repo, message="empty", allow_empty=True)
        assert c.subject == "empty"


# --------------------------------------------------------------------------- #
# remove + revert_working_copy
# --------------------------------------------------------------------------- #


class TestRemoveAndRevert:
    def test_remove_staged_file(self, repo_with_one_commit: Path) -> None:
        repo = GitDriver.detect(repo_with_one_commit)
        d = GitDriver()
        d.remove(repo, [Path("README.md")])
        out = _run(repo_with_one_commit, "git", "status", "--porcelain")
        # README.md should show as deleted (staged).
        assert "D" in out.split("\n")[0]

    def test_remove_empty_paths_noop(self, repo_with_one_commit: Path) -> None:
        repo = GitDriver.detect(repo_with_one_commit)
        GitDriver().remove(repo, [])  # No-op.

    def test_remove_absolute_path_rejected(self, repo_with_one_commit: Path) -> None:
        repo = GitDriver.detect(repo_with_one_commit)
        with pytest.raises(DriverError, match="relative"):
            GitDriver().remove(repo, [Path("/etc/passwd")])

    def test_revert_working_copy_discards_changes(
        self, repo_with_one_commit: Path,
    ) -> None:
        # Modify the file, then revert.
        (repo_with_one_commit / "README.md").write_text("tampered\n")
        repo = GitDriver.detect(repo_with_one_commit)
        GitDriver().revert_working_copy(repo, [Path("README.md")])
        # File should be back to the committed version.
        assert (repo_with_one_commit / "README.md").read_text() == "# initial\n"


# --------------------------------------------------------------------------- #
# branch_create / branch_delete / switch
# --------------------------------------------------------------------------- #


class TestBranchOps:
    def test_create_and_list(self, repo_with_one_commit: Path) -> None:
        repo = GitDriver.detect(repo_with_one_commit)
        b = GitDriver().branch_create(repo, "feature/x")
        assert b.name == "feature/x"
        # Verify via raw git too.
        out = _run(repo_with_one_commit, "git", "branch", "--list")
        assert "feature/x" in out

    def test_create_empty_name_rejected(self, repo_with_one_commit: Path) -> None:
        repo = GitDriver.detect(repo_with_one_commit)
        with pytest.raises(DriverError, match="non-empty"):
            GitDriver().branch_create(repo, "")

    def test_switch_to_existing_branch(self, repo_with_one_commit: Path) -> None:
        repo = GitDriver.detect(repo_with_one_commit)
        d = GitDriver()
        d.branch_create(repo, "feature")
        cb = d.switch(repo, "feature")
        assert cb.name == "feature"
        assert cb.is_current

    def test_switch_unknown_branch_raises(self, repo_with_one_commit: Path) -> None:
        repo = GitDriver.detect(repo_with_one_commit)
        with pytest.raises((DriverError, GitCommandFailed)):
            GitDriver().switch(repo, "nope")

    def test_delete_branch(self, repo_with_one_commit: Path) -> None:
        repo = GitDriver.detect(repo_with_one_commit)
        d = GitDriver()
        d.branch_create(repo, "throwaway")
        d.branch_delete(repo, "throwaway", force=True)
        names = {b.name for b in d.branches(repo)}
        assert "throwaway" not in names


# --------------------------------------------------------------------------- #
# tag_create / tag_delete
# --------------------------------------------------------------------------- #


class TestTagOps:
    def test_lightweight_tag(self, repo_with_one_commit: Path) -> None:
        repo = GitDriver.detect(repo_with_one_commit)
        t = GitDriver().tag_create(repo, "v0.0.1")
        assert isinstance(t, TagInfo)
        assert t.name == "v0.0.1"
        assert not t.is_annotated

    def test_annotated_tag(self, repo_with_one_commit: Path) -> None:
        repo = GitDriver.detect(repo_with_one_commit)
        t = GitDriver().tag_create(
            repo, "v1.0.0", message="First release",
        )
        assert t.is_annotated
        assert t.message == "First release"

    def test_tag_empty_name_rejected(self, repo_with_one_commit: Path) -> None:
        repo = GitDriver.detect(repo_with_one_commit)
        with pytest.raises(DriverError, match="non-empty"):
            GitDriver().tag_create(repo, "")

    def test_tag_targeting_specific_sha(self, repo_with_one_commit: Path) -> None:
        repo = GitDriver.detect(repo_with_one_commit)
        d = GitDriver()
        # Get the SHA of the only commit.
        records = d.log(repo)
        target = records[0].sha
        t = d.tag_create(repo, "v0.0.2", target_sha=target)
        assert t.target_sha == target

    def test_tag_delete(self, repo_with_one_commit: Path) -> None:
        repo = GitDriver.detect(repo_with_one_commit)
        d = GitDriver()
        d.tag_create(repo, "v0.0.3")
        d.tag_delete(repo, "v0.0.3")
        names = {t.name for t in d.tags(repo)}
        assert "v0.0.3" not in names


# --------------------------------------------------------------------------- #
# push (no real remote; we test the error mapping + force-mutex)
# --------------------------------------------------------------------------- #


class TestPush:
    def test_force_and_force_with_lease_rejected_together(
        self, repo_with_one_commit: Path,
    ) -> None:
        repo = GitDriver.detect(repo_with_one_commit)
        with pytest.raises(DriverError, match="mutually exclusive"):
            GitDriver().push(repo, force=True, force_with_lease=True)

    def test_push_to_local_file_remote(self, repo_with_one_commit: Path, tmp_path: Path) -> None:
        # Set up a local bare repo as the remote, push to it.
        bare = tmp_path / "bare.git"
        _run(tmp_path, "git", "init", "--bare", str(bare))
        _run(repo_with_one_commit, "git", "remote", "add", "origin", str(bare))
        repo = GitDriver.detect(repo_with_one_commit)
        result = GitDriver().push(repo, remote="origin", branch="main")
        assert isinstance(result, PushResult)
        assert result.remote == "origin"
        assert not result.was_no_op  # First push has content.

    def test_push_no_op_returns_was_no_op_true(
        self, repo_with_one_commit: Path, tmp_path: Path,
    ) -> None:
        bare = tmp_path / "bare.git"
        _run(tmp_path, "git", "init", "--bare", str(bare))
        _run(repo_with_one_commit, "git", "remote", "add", "origin", str(bare))
        repo = GitDriver.detect(repo_with_one_commit)
        d = GitDriver()
        d.push(repo, remote="origin", branch="main")
        # Second push of the same state.
        result = d.push(repo, remote="origin", branch="main")
        assert result.was_no_op


# --------------------------------------------------------------------------- #
# fetch / pull (require a remote)
# --------------------------------------------------------------------------- #


class TestFetchPull:
    def test_fetch_after_push_no_op(
        self, repo_with_one_commit: Path, tmp_path: Path,
    ) -> None:
        bare = tmp_path / "bare.git"
        _run(tmp_path, "git", "init", "--bare", str(bare))
        _run(repo_with_one_commit, "git", "remote", "add", "origin", str(bare))
        repo = GitDriver.detect(repo_with_one_commit)
        d = GitDriver()
        d.push(repo, remote="origin", branch="main")
        # fetch should complete without raising.
        d.fetch(repo, remote="origin")
