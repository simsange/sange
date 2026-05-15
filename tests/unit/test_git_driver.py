"""Integration tests for src/sange/adapters/vcs/git/driver.py — GitDriver.

These tests spin up ephemeral real-git repositories under `tmp_path` and
exercise the driver's read methods against them. Skipped automatically
when `git` is not on PATH (CI's ARM matrix may run before `git` is
provisioned in early stages).
"""

from __future__ import annotations

import shutil
import subprocess
from collections.abc import Iterator
from pathlib import Path

import pytest

from sange.adapters.vcs._protocol import DriverCapabilities, DriverError, VCSDriver
from sange.adapters.vcs.git import GitDriver, GitRepoNotFound
from sange.core.models import (
    BranchInfo,
    CommitRef,
    DiffSummary,
    Repo,
    WorkingCopyStatus,
)

# Skip the entire module when git isn't available.
pytestmark = pytest.mark.skipif(
    shutil.which("git") is None,
    reason="git not installed; GitDriver integration tests skipped",
)


# --------------------------------------------------------------------------- #
# Ephemeral repo fixture
# --------------------------------------------------------------------------- #


def _run(cwd: Path, *args: str) -> str:
    """Run a shell command in `cwd`. Helper for the fixture only."""

    result = subprocess.run(
        args, cwd=str(cwd), capture_output=True, text=True, check=True,
    )
    return result.stdout


@pytest.fixture
def ephemeral_repo(tmp_path: Path) -> Iterator[Path]:
    """Initialize a real git repo with a small fixed history.

    History (oldest → newest):
      1. "initial commit" — adds README.md
      2. "add hello" — adds hello.py
      3. "tweak hello" — modifies hello.py
      Then a fresh "feature" branch from HEAD.
    """

    repo = tmp_path / "repo"
    repo.mkdir()
    _run(repo, "git", "init", "--initial-branch=main")
    _run(repo, "git", "config", "user.email", "test@example.com")
    _run(repo, "git", "config", "user.name", "Test User")
    _run(repo, "git", "config", "commit.gpgsign", "false")

    # Commit 1
    (repo / "README.md").write_text("# Test repo\n")
    _run(repo, "git", "add", "README.md")
    _run(repo, "git", "commit", "-m", "initial commit")

    # Commit 2
    (repo / "hello.py").write_text("print('hello')\n")
    _run(repo, "git", "add", "hello.py")
    _run(repo, "git", "commit", "-m", "add hello")

    # Commit 3
    (repo / "hello.py").write_text("print('hello, world')\n")
    _run(repo, "git", "add", "hello.py")
    _run(repo, "git", "commit", "-m", "tweak hello")

    # Tag for show_commit tests.
    _run(repo, "git", "tag", "v0.1.0")
    _run(repo, "git", "tag", "-a", "-m", "First release", "v0.1.0-annotated")

    # Feature branch (off HEAD~1 so it's distinct).
    _run(repo, "git", "branch", "feature", "HEAD~1")

    yield repo


# --------------------------------------------------------------------------- #
# Capabilities + Protocol compliance
# --------------------------------------------------------------------------- #


class TestCapabilitiesAndShape:
    def test_capabilities_is_descriptor(self) -> None:
        caps = GitDriver.capabilities
        assert isinstance(caps, DriverCapabilities)
        assert caps.vcs == "git"
        assert caps.vcs_version.startswith("git ")

    def test_satisfies_vcsdriver_structurally(self) -> None:
        # Static-typing assertion — if the Protocol grows a method GitDriver
        # doesn't implement, this assignment fails type-checking.
        d: VCSDriver = GitDriver()
        assert d is not None


# --------------------------------------------------------------------------- #
# detect
# --------------------------------------------------------------------------- #


class TestDetect:
    def test_detect_at_repo_root(self, ephemeral_repo: Path) -> None:
        repo = GitDriver.detect(ephemeral_repo)
        assert repo.path == ephemeral_repo.resolve()
        assert repo.vcs == "git"
        assert repo.default_branch == "main"

    def test_detect_from_subdirectory(self, ephemeral_repo: Path) -> None:
        # Make a subdir; detect from inside.
        sub = ephemeral_repo / "subdir"
        sub.mkdir()
        repo = GitDriver.detect(sub)
        # Resolves to the toplevel, not the subdir.
        assert repo.path == ephemeral_repo.resolve()

    def test_detect_on_non_repo_raises(self, tmp_path: Path) -> None:
        not_a_repo = tmp_path / "no-git-here"
        not_a_repo.mkdir()
        with pytest.raises(GitRepoNotFound):
            GitDriver.detect(not_a_repo)

    def test_remote_none_when_no_origin(self, ephemeral_repo: Path) -> None:
        repo = GitDriver.detect(ephemeral_repo)
        assert repo.remote is None


# --------------------------------------------------------------------------- #
# status
# --------------------------------------------------------------------------- #


class TestStatus:
    def test_clean_repo(self, ephemeral_repo: Path) -> None:
        repo = GitDriver.detect(ephemeral_repo)
        ws = GitDriver().status(repo)
        assert ws.branch == "main"
        assert ws.is_clean

    def test_modified_file_visible(self, ephemeral_repo: Path) -> None:
        (ephemeral_repo / "hello.py").write_text("print('changed')\n")
        repo = GitDriver.detect(ephemeral_repo)
        ws = GitDriver().status(repo)
        assert not ws.is_clean
        paths = [str(e.path) for e in ws.entries]
        assert "hello.py" in paths

    def test_untracked_file_visible(self, ephemeral_repo: Path) -> None:
        (ephemeral_repo / "newfile.txt").write_text("hi\n")
        repo = GitDriver.detect(ephemeral_repo)
        ws = GitDriver().status(repo)
        # Find the newfile entry
        paths = {str(e.path): e.state.value for e in ws.entries}
        assert "newfile.txt" in paths
        assert paths["newfile.txt"] == "untracked"


# --------------------------------------------------------------------------- #
# log + show_commit
# --------------------------------------------------------------------------- #


class TestLogAndShowCommit:
    def test_log_returns_all_3_commits(self, ephemeral_repo: Path) -> None:
        repo = GitDriver.detect(ephemeral_repo)
        records = GitDriver().log(repo)
        assert len(records) == 3
        subjects = [r.subject for r in records]
        assert subjects == ["tweak hello", "add hello", "initial commit"]

    def test_log_max_count(self, ephemeral_repo: Path) -> None:
        repo = GitDriver.detect(ephemeral_repo)
        records = GitDriver().log(repo, max_count=1)
        assert len(records) == 1

    def test_log_revision_range(self, ephemeral_repo: Path) -> None:
        repo = GitDriver.detect(ephemeral_repo)
        # HEAD~1..HEAD → only the most-recent commit.
        records = GitDriver().log(repo, revision_range="HEAD~1..HEAD")
        assert len(records) == 1
        assert records[0].subject == "tweak hello"

    def test_show_commit_by_sha(self, ephemeral_repo: Path) -> None:
        repo = GitDriver.detect(ephemeral_repo)
        all_records = GitDriver().log(repo)
        first_record = all_records[-1]  # oldest
        c = GitDriver().show_commit(repo, first_record.sha)
        assert c.subject == "initial commit"

    def test_show_commit_by_short_sha(self, ephemeral_repo: Path) -> None:
        repo = GitDriver.detect(ephemeral_repo)
        all_records = GitDriver().log(repo)
        short = all_records[0].sha[:8]
        c = GitDriver().show_commit(repo, short)
        assert c.subject == "tweak hello"

    def test_show_commit_unknown_sha_raises(self, ephemeral_repo: Path) -> None:
        repo = GitDriver.detect(ephemeral_repo)
        with pytest.raises(DriverError):
            GitDriver().show_commit(repo, "deadbeefdeadbeefdeadbeefdeadbeefdeadbeef")


# --------------------------------------------------------------------------- #
# diff
# --------------------------------------------------------------------------- #


class TestDiff:
    def test_clean_repo_has_empty_diff(self, ephemeral_repo: Path) -> None:
        repo = GitDriver.detect(ephemeral_repo)
        d = GitDriver().diff(repo)
        assert d.is_empty

    def test_modified_file_has_non_empty_diff(self, ephemeral_repo: Path) -> None:
        (ephemeral_repo / "hello.py").write_text(
            "print('hello, much longer text now')\nextra = 'line'\n"
        )
        repo = GitDriver.detect(ephemeral_repo)
        d = GitDriver().diff(repo)
        assert not d.is_empty
        assert d.files_changed == 1
        assert d.insertions >= 1
        assert d.content_hash  # non-empty sha256
        assert len(d.content_hash) == 64

    def test_diff_between_two_commits(self, ephemeral_repo: Path) -> None:
        repo = GitDriver.detect(ephemeral_repo)
        d = GitDriver().diff(repo, revision_range="HEAD~1..HEAD")
        # Commit 2 → Commit 3 modifies hello.py.
        assert d.files_changed == 1
        assert d.insertions >= 1
        assert d.deletions >= 1


# --------------------------------------------------------------------------- #
# branches / current_branch
# --------------------------------------------------------------------------- #


class TestBranches:
    def test_lists_both_branches(self, ephemeral_repo: Path) -> None:
        repo = GitDriver.detect(ephemeral_repo)
        branches = GitDriver().branches(repo)
        names = {b.name for b in branches}
        assert names == {"main", "feature"}

    def test_current_branch_is_main(self, ephemeral_repo: Path) -> None:
        repo = GitDriver.detect(ephemeral_repo)
        cb = GitDriver().current_branch(repo)
        assert cb is not None
        assert cb.name == "main"
        assert cb.is_current

    def test_current_branch_after_checkout(self, ephemeral_repo: Path) -> None:
        _run(ephemeral_repo, "git", "checkout", "feature")
        repo = GitDriver.detect(ephemeral_repo)
        cb = GitDriver().current_branch(repo)
        assert cb is not None
        assert cb.name == "feature"

    def test_current_branch_detached_returns_none(self, ephemeral_repo: Path) -> None:
        # Detach by checking out a SHA.
        _run(ephemeral_repo, "git", "checkout", "--detach", "HEAD")
        repo = GitDriver.detect(ephemeral_repo)
        cb = GitDriver().current_branch(repo)
        assert cb is None

    def test_branches_sorted_current_first(self, ephemeral_repo: Path) -> None:
        repo = GitDriver.detect(ephemeral_repo)
        branches = GitDriver().branches(repo)
        # main is current → must come first.
        assert branches[0].name == "main"
        assert branches[0].is_current


# --------------------------------------------------------------------------- #
# tags
# --------------------------------------------------------------------------- #


class TestTags:
    def test_lightweight_and_annotated_tags_present(self, ephemeral_repo: Path) -> None:
        repo = GitDriver.detect(ephemeral_repo)
        tags = GitDriver().tags(repo)
        names = {t.name: t for t in tags}
        assert "v0.1.0" in names
        assert "v0.1.0-annotated" in names
        # The annotated one has is_annotated=True; lightweight doesn't.
        assert not names["v0.1.0"].is_annotated
        assert names["v0.1.0-annotated"].is_annotated
        # Annotated tag has the annotation message.
        assert names["v0.1.0-annotated"].message == "First release"


# --------------------------------------------------------------------------- #
# remotes
# --------------------------------------------------------------------------- #


class TestRemotes:
    def test_no_remotes_by_default(self, ephemeral_repo: Path) -> None:
        repo = GitDriver.detect(ephemeral_repo)
        rs = GitDriver().remotes(repo)
        assert rs == ()

    def test_added_remote_visible(self, ephemeral_repo: Path) -> None:
        _run(
            ephemeral_repo, "git", "remote", "add", "origin",
            "git@example.com:test/repo.git",
        )
        repo = GitDriver.detect(ephemeral_repo)
        rs = GitDriver().remotes(repo)
        assert len(rs) == 1
        assert rs[0].name == "origin"
        assert rs[0].url == "git@example.com:test/repo.git"


# --------------------------------------------------------------------------- #
# Write methods — smoke-tested against ephemeral_repo (full coverage in
# test_git_driver_write.py)
# --------------------------------------------------------------------------- #


class TestWriteMethodsImplemented:
    """T-005 superseded T-004's NotImplementedError placeholders. Full
    coverage lives in test_git_driver_write.py against `fresh_repo`; here
    we just confirm the methods callable + return the documented type."""

    def test_add_callable(self, ephemeral_repo: Path) -> None:
        (ephemeral_repo / "new_file.txt").write_text("x\n")
        repo = GitDriver.detect(ephemeral_repo)
        GitDriver().add(repo, [Path("new_file.txt")])  # No raise = success.

    def test_commit_returns_commitref(self, ephemeral_repo: Path) -> None:
        (ephemeral_repo / "new_file.txt").write_text("x\n")
        repo = GitDriver.detect(ephemeral_repo)
        d = GitDriver()
        d.add(repo, [Path("new_file.txt")])
        commit = d.commit(repo, message="add new_file")
        assert isinstance(commit, CommitRef)
        assert commit.subject == "add new_file"
