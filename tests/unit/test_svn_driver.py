"""Tests for src/sange/adapters/vcs/svn/driver.py — SvnDriver.

The pure parser tests live in test_svn_parsers.py. These tests
exercise the driver against a real `svn` binary + ephemeral
`svnadmin create` repositories, so they're gated on `svn` being on
PATH (skip-with-prejudice otherwise).
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from sange.adapters.vcs.svn import (
    SvnDriver,
    SvnNotInstalled,
    SvnRepoNotFound,
    SvnVersion,
)
from sange.core.models.repo import Repo
from sange.core.models.working_copy import FileState, WorkingCopyStatus

_SVN = shutil.which("svn")
_SVNADMIN = shutil.which("svnadmin")


@pytest.fixture
def svn_wc(tmp_path: Path) -> Path:
    """Ephemeral SVN repo + working-copy checkout.

    Returns the path to the working copy. The repo lives at
    `tmp_path/repo`; the working copy at `tmp_path/wc`. One initial
    commit lands `a.txt`; `a.txt` is then modified and `b.txt` added
    so the working copy has a non-clean status.
    """

    repo = tmp_path / "repo"
    wc = tmp_path / "wc"

    subprocess.run(
        ["svnadmin", "create", str(repo)], check=True
    )
    subprocess.run(
        ["svn", "checkout", "-q", f"file://{repo}", str(wc)], check=True
    )

    (wc / "a.txt").write_text("v1\n")
    subprocess.run(["svn", "add", "-q", "a.txt"], cwd=wc, check=True)
    subprocess.run(["svn", "commit", "-q", "-m", "init"], cwd=wc, check=True)
    # `svn update` syncs the WC's local revision to match the repo's
    # HEAD revision (rev 1). Without this, `svn info` on the WC root
    # reports the checkout-time revision (0).
    subprocess.run(["svn", "update", "-q"], cwd=wc, check=True)

    # Make working copy non-clean.
    (wc / "a.txt").write_text("v1\nv2\n")
    (wc / "b.txt").write_text("new\n")
    subprocess.run(["svn", "add", "-q", "b.txt"], cwd=wc, check=True)

    return wc


@pytest.mark.skipif(_SVN is None or _SVNADMIN is None, reason="svn / svnadmin not on PATH")
class TestSvnDriverIntegration:
    def test_version(self) -> None:
        v = SvnDriver.version()
        assert isinstance(v, SvnVersion)
        assert v.major >= 1   # any modern SVN

    def test_capabilities(self) -> None:
        c = SvnDriver.capabilities
        assert c.vcs == "svn"
        assert c.vcs_version  # non-empty
        # SVN's optional capability stance:
        assert c.supports_stash is False
        assert c.supports_bisect is False
        assert c.supports_rebase is False
        assert c.supports_lfs is False

    def test_detect_resolves_to_wc_root(self, svn_wc: Path) -> None:
        # Run detect from a subdir; should resolve to the wc root.
        (svn_wc / "sub").mkdir()
        repo = SvnDriver.detect(svn_wc / "sub")
        assert isinstance(repo, Repo)
        assert repo.path == svn_wc.resolve()
        assert repo.vcs == "svn"
        assert repo.default_branch == "trunk"
        assert repo.remote and repo.remote.startswith("file://")
        # Metadata enriches the Repo with SVN-specific fields.
        assert "repository_uuid" in repo.metadata
        assert "revision" in repo.metadata
        assert repo.metadata["revision"] == "1"   # one commit landed in fixture

    def test_detect_rejects_non_working_copy(self, tmp_path: Path) -> None:
        with pytest.raises(SvnRepoNotFound):
            SvnDriver.detect(tmp_path)

    def test_status_returns_modified_and_added(self, svn_wc: Path) -> None:
        d = SvnDriver()
        repo = d.detect(svn_wc)
        status = d.status(repo)

        assert isinstance(status, WorkingCopyStatus)
        assert status.branch == "trunk"

        by_path = {str(e.path): e.state for e in status.entries}
        # a.txt was edited after the initial commit.
        assert by_path.get("a.txt") is FileState.MODIFIED
        # b.txt was newly added.
        assert by_path.get("b.txt") is FileState.ADDED
        # The fixture creates exactly those two dirty entries.
        assert set(by_path.keys()) == {"a.txt", "b.txt"}

    def test_status_clean_working_copy(self, tmp_path: Path) -> None:
        # Build a clean wc — repo with one commit, no subsequent edits.
        repo = tmp_path / "repo"
        wc = tmp_path / "wc"
        subprocess.run(["svnadmin", "create", str(repo)], check=True)
        subprocess.run(["svn", "checkout", "-q", f"file://{repo}", str(wc)], check=True)
        (wc / "only.txt").write_text("clean\n")
        subprocess.run(["svn", "add", "-q", "only.txt"], cwd=wc, check=True)
        subprocess.run(["svn", "commit", "-q", "-m", "init"], cwd=wc, check=True)
        subprocess.run(["svn", "update", "-q"], cwd=wc, check=True)

        d = SvnDriver()
        r = d.detect(wc)
        st = d.status(r)
        assert st.entries == ()
        assert st.is_clean
        assert st.is_pristine

    # Write methods now ship — see TestSvnDriverWriteOps below.
    pass


# --------------------------------------------------------------------------- #
# T-100b — log / diff / branches / current_branch / remotes / tags / show_commit
# --------------------------------------------------------------------------- #


@pytest.fixture
def trunk_wc(tmp_path: Path) -> Path:
    """Working copy checked out at trunk, with branches + tags populated.

    Layout in the repo:

      ^/trunk/a.txt            (modified locally → dirty WC)
      ^/branches/feature-x/    (svn copy from trunk @ r2)
      ^/tags/v0.1/             (svn copy from trunk @ r2)

    Returns the path to the trunk working-copy checkout.
    """

    repo = tmp_path / "repo"
    wc = tmp_path / "wc"
    trunk_wc = tmp_path / "trunk-wc"

    subprocess.run(["svnadmin", "create", str(repo)], check=True)
    subprocess.run(["svn", "checkout", "-q", f"file://{repo}", str(wc)], check=True)
    subprocess.run(["svn", "mkdir", "-q", "trunk", "branches", "tags"], cwd=wc, check=True)
    subprocess.run(["svn", "commit", "-q", "-m", "layout"], cwd=wc, check=True)
    subprocess.run(["svn", "update", "-q"], cwd=wc, check=True)

    # Initial trunk commit.
    (wc / "trunk" / "a.txt").write_text("v1\n")
    subprocess.run(["svn", "add", "-q", "trunk/a.txt"], cwd=wc, check=True)
    subprocess.run(["svn", "commit", "-q", "-m", "trunk c1"], cwd=wc, check=True)
    subprocess.run(["svn", "update", "-q"], cwd=wc, check=True)

    # Branch + tag (copies of trunk @ r2).
    subprocess.run(
        ["svn", "copy", "-q", "^/trunk", "^/branches/feature-x", "-m", "branch off"],
        cwd=wc, check=True,
    )
    subprocess.run(
        ["svn", "copy", "-q", "^/trunk", "^/tags/v0.1", "-m", "tag v0.1"],
        cwd=wc, check=True,
    )

    # Check out trunk as a standalone working copy + dirty it.
    subprocess.run(
        ["svn", "checkout", "-q", f"file://{repo}/trunk", str(trunk_wc)],
        check=True,
    )
    (trunk_wc / "a.txt").write_text("v1\nmodified\n")

    return trunk_wc


@pytest.mark.skipif(_SVN is None or _SVNADMIN is None, reason="svn / svnadmin not on PATH")
class TestSvnDriverReadOps:
    def test_log_returns_history_newest_first(self, trunk_wc: Path) -> None:
        d = SvnDriver()
        repo = d.detect(trunk_wc)
        refs = d.log(repo, max_count=5)
        assert len(refs) >= 2
        revs = [int(r.sha) for r in refs]
        assert revs == sorted(revs, reverse=True)
        # Each entry has author + non-empty subject.
        for r in refs:
            assert r.author_name  # populated
            assert r.author_email == ""  # SVN doesn't have email

    def test_log_max_count_zero(self, trunk_wc: Path) -> None:
        d = SvnDriver()
        repo = d.detect(trunk_wc)
        refs = d.log(repo, max_count=0)
        assert refs == ()

    def test_log_revision_range(self, trunk_wc: Path) -> None:
        d = SvnDriver()
        repo = d.detect(trunk_wc)
        refs = d.log(repo, revision_range="1:HEAD")
        assert len(refs) >= 1

    def test_diff_returns_positive_stats(self, trunk_wc: Path) -> None:
        d = SvnDriver()
        repo = d.detect(trunk_wc)
        summary = d.diff(repo)
        # a.txt was modified after checkout.
        assert summary.files_changed >= 1
        assert summary.insertions >= 1
        assert summary.content_hash  # sha256 hex non-empty

    def test_diff_clean_returns_zero(self, tmp_path: Path) -> None:
        # Build a clean WC.
        repo = tmp_path / "repo"
        wc = tmp_path / "wc"
        subprocess.run(["svnadmin", "create", str(repo)], check=True)
        subprocess.run(["svn", "checkout", "-q", f"file://{repo}", str(wc)], check=True)
        (wc / "x.txt").write_text("x\n")
        subprocess.run(["svn", "add", "-q", "x.txt"], cwd=wc, check=True)
        subprocess.run(["svn", "commit", "-q", "-m", "init"], cwd=wc, check=True)
        subprocess.run(["svn", "update", "-q"], cwd=wc, check=True)

        d = SvnDriver()
        r = d.detect(wc)
        s = d.diff(r)
        assert s.files_changed == 0
        assert s.insertions == 0
        assert s.deletions == 0
        assert s.content_hash == ""

    def test_branches_lists_trunk_plus_branches(self, trunk_wc: Path) -> None:
        d = SvnDriver()
        repo = d.detect(trunk_wc)
        bs = d.branches(repo)
        names = [b.name for b in bs]
        assert "trunk" in names
        assert "feature-x" in names
        # Current marker: the WC is at trunk, so trunk is_current.
        by_name = {b.name: b for b in bs}
        assert by_name["trunk"].is_current
        assert not by_name["feature-x"].is_current

    def test_current_branch_is_trunk(self, trunk_wc: Path) -> None:
        d = SvnDriver()
        repo = d.detect(trunk_wc)
        cb = d.current_branch(repo)
        assert cb is not None
        assert cb.name == "trunk"
        assert cb.is_current

    def test_current_branch_repo_root_is_none(self, tmp_path: Path) -> None:
        # A WC checked out at the repo root (no trunk/branches/tags
        # convention) returns None for current_branch.
        repo = tmp_path / "repo"
        wc = tmp_path / "wc"
        subprocess.run(["svnadmin", "create", str(repo)], check=True)
        subprocess.run(["svn", "checkout", "-q", f"file://{repo}", str(wc)], check=True)

        d = SvnDriver()
        r = d.detect(wc)
        assert d.current_branch(r) is None

    def test_remotes_returns_origin(self, trunk_wc: Path) -> None:
        d = SvnDriver()
        repo = d.detect(trunk_wc)
        remotes = d.remotes(repo)
        assert len(remotes) == 1
        assert remotes[0].name == "origin"
        assert remotes[0].url.startswith("file://")

    def test_tags_lists_tags_dir(self, trunk_wc: Path) -> None:
        d = SvnDriver()
        repo = d.detect(trunk_wc)
        tags = d.tags(repo)
        names = [t.name for t in tags]
        assert "v0.1" in names
        v01 = next(t for t in tags if t.name == "v0.1")
        assert v01.target_sha  # non-empty
        assert v01.is_annotated is False
        assert v01.is_signed is False
        assert v01.created_at is not None  # SVN's commit timestamp

    def test_tags_no_tags_dir(self, tmp_path: Path) -> None:
        # Repo without a ^/tags directory.
        repo = tmp_path / "repo"
        wc = tmp_path / "wc"
        subprocess.run(["svnadmin", "create", str(repo)], check=True)
        subprocess.run(["svn", "checkout", "-q", f"file://{repo}", str(wc)], check=True)

        d = SvnDriver()
        r = d.detect(wc)
        assert d.tags(r) == ()

    def test_show_commit_returns_single_ref(self, trunk_wc: Path) -> None:
        d = SvnDriver()
        repo = d.detect(trunk_wc)
        ref = d.show_commit(repo, "2")
        assert ref.sha == "2"
        assert ref.author_name  # populated
        assert ref.committed_at.tzinfo is not None

    def test_show_commit_missing_sha_raises(self, trunk_wc: Path) -> None:
        d = SvnDriver()
        repo = d.detect(trunk_wc)
        from sange.adapters.vcs._protocol import DriverError
        with pytest.raises(DriverError, match="non-empty"):
            d.show_commit(repo, "")

    def test_show_commit_nonexistent_revision_raises(self, trunk_wc: Path) -> None:
        d = SvnDriver()
        repo = d.detect(trunk_wc)
        # Revision 9999 doesn't exist in this repo; svn returns
        # a SvnCommandFailed which propagates as DriverError.
        from sange.adapters.vcs._protocol import DriverError
        with pytest.raises(DriverError):
            d.show_commit(repo, "9999")


# --------------------------------------------------------------------------- #
# T-100c — write methods (add / remove / revert / commit / branch_* / switch /
#          fetch / pull / push / tag_*)
# --------------------------------------------------------------------------- #


@pytest.mark.skipif(_SVN is None or _SVNADMIN is None, reason="svn / svnadmin not on PATH")
class TestSvnDriverWriteOps:
    def test_add_and_commit_returns_new_revision(self, trunk_wc: Path) -> None:
        d = SvnDriver()
        repo = d.detect(trunk_wc)
        (trunk_wc / "added.txt").write_text("hello\n")
        d.add(repo, [Path("added.txt")])
        ref = d.commit(repo, message="Add a new file")
        # commit returns the NEW revision, not the WC's last-changed rev.
        assert int(ref.sha) >= 3   # trunk repo starts at r2; r3+ is the commit
        assert ref.subject == "Add a new file"

    def test_add_rejects_absolute_path(self, trunk_wc: Path) -> None:
        d = SvnDriver()
        repo = d.detect(trunk_wc)
        from sange.adapters.vcs._protocol import DriverError
        with pytest.raises(DriverError, match="must be relative"):
            d.add(repo, [Path("/etc/passwd")])

    def test_add_empty_list_is_noop(self, trunk_wc: Path) -> None:
        d = SvnDriver()
        repo = d.detect(trunk_wc)
        d.add(repo, [])   # must not raise

    def test_remove_with_force_for_dirty_file(self, trunk_wc: Path) -> None:
        d = SvnDriver()
        repo = d.detect(trunk_wc)
        # a.txt was dirtied by the trunk_wc fixture; remove with force.
        d.remove(repo, [Path("a.txt")], force=True)
        d.commit(repo, message="Remove a.txt")
        assert not (trunk_wc / "a.txt").exists()

    def test_revert_discards_local_changes(self, trunk_wc: Path) -> None:
        d = SvnDriver()
        repo = d.detect(trunk_wc)
        # trunk_wc fixture leaves a.txt with `v1\nmodified\n` locally.
        assert "modified" in (trunk_wc / "a.txt").read_text()
        d.revert_working_copy(repo, [Path("a.txt")])
        # After revert, the file is back to its repo-tracked content.
        assert "modified" not in (trunk_wc / "a.txt").read_text()

    def test_commit_empty_message_raises(self, trunk_wc: Path) -> None:
        d = SvnDriver()
        repo = d.detect(trunk_wc)
        from sange.adapters.vcs._protocol import DriverError
        with pytest.raises(DriverError, match="non-empty"):
            d.commit(repo, message="")

    def test_commit_allow_empty_raises(self, trunk_wc: Path) -> None:
        d = SvnDriver()
        repo = d.detect(trunk_wc)
        from sange.adapters.vcs._protocol import DriverError
        with pytest.raises(DriverError, match="--allow-empty"):
            d.commit(repo, message="x", allow_empty=True)

    def test_commit_sign_raises(self, trunk_wc: Path) -> None:
        d = SvnDriver()
        repo = d.detect(trunk_wc)
        from sange.adapters.vcs._protocol import DriverError
        with pytest.raises(DriverError, match="GPG signing"):
            d.commit(repo, message="x", sign=True)

    def test_commit_partial_author_raises(self, trunk_wc: Path) -> None:
        d = SvnDriver()
        repo = d.detect(trunk_wc)
        from sange.adapters.vcs._protocol import DriverError
        with pytest.raises(DriverError, match="both be set or both omitted"):
            d.commit(repo, message="x", author_name="Solo")

    def test_branch_create_and_list(self, trunk_wc: Path) -> None:
        d = SvnDriver()
        repo = d.detect(trunk_wc)
        bi = d.branch_create(repo, "new-feature")
        assert bi.name == "new-feature"
        names = {b.name for b in d.branches(repo)}
        assert "new-feature" in names

    def test_branch_create_invalid_name(self, trunk_wc: Path) -> None:
        d = SvnDriver()
        repo = d.detect(trunk_wc)
        from sange.adapters.vcs._protocol import DriverError
        with pytest.raises(DriverError, match="non-empty"):
            d.branch_create(repo, "")
        with pytest.raises(DriverError, match="cannot contain"):
            d.branch_create(repo, "with/slash")

    def test_branch_delete(self, trunk_wc: Path) -> None:
        d = SvnDriver()
        repo = d.detect(trunk_wc)
        d.branch_create(repo, "doomed")
        assert "doomed" in {b.name for b in d.branches(repo)}
        d.branch_delete(repo, "doomed")
        assert "doomed" not in {b.name for b in d.branches(repo)}

    def test_branch_delete_refuses_trunk(self, trunk_wc: Path) -> None:
        d = SvnDriver()
        repo = d.detect(trunk_wc)
        from sange.adapters.vcs._protocol import DriverError
        with pytest.raises(DriverError, match="trunk"):
            d.branch_delete(repo, "trunk")

    def test_switch_to_branch_then_back(self, trunk_wc: Path) -> None:
        d = SvnDriver()
        repo = d.detect(trunk_wc)
        # feature-x already exists in the fixture.
        b1 = d.switch(repo, "feature-x")
        assert b1.name == "feature-x"
        # current_branch must reflect the new URL (not the stale detect-cache).
        assert d.current_branch(repo) is not None
        cb = d.current_branch(repo)
        assert cb is not None and cb.name == "feature-x"
        # Switch back.
        b2 = d.switch(repo, "trunk")
        assert b2.name == "trunk"

    def test_push_is_noop_for_svn(self, trunk_wc: Path) -> None:
        d = SvnDriver()
        repo = d.detect(trunk_wc)
        result = d.push(repo)
        assert result.was_no_op is True
        assert result.forced is False
        assert result.remote == "origin"

    def test_push_force_raises(self, trunk_wc: Path) -> None:
        d = SvnDriver()
        repo = d.detect(trunk_wc)
        from sange.adapters.vcs._protocol import DriverError
        with pytest.raises(DriverError, match="history-rewrite"):
            d.push(repo, force=True)
        with pytest.raises(DriverError, match="history-rewrite"):
            d.push(repo, force_with_lease=True)

    def test_fetch_is_noop(self, trunk_wc: Path) -> None:
        # No assertion on side effects — just that it doesn't raise.
        d = SvnDriver()
        repo = d.detect(trunk_wc)
        d.fetch(repo)
        d.fetch(repo, remote="origin")

    def test_pull_runs_svn_update(self, trunk_wc: Path) -> None:
        # The WC is already at HEAD; pull is a documented no-op-equivalent.
        d = SvnDriver()
        repo = d.detect(trunk_wc)
        d.pull(repo)   # must not raise
        d.pull(repo, remote="origin")

    def test_tag_create_with_message(self, trunk_wc: Path) -> None:
        d = SvnDriver()
        repo = d.detect(trunk_wc)
        ti = d.tag_create(repo, "v1.0", message="Initial tag")
        assert ti.name == "v1.0"
        assert ti.is_annotated is False  # SVN tags are dir-copies
        assert ti.is_signed is False
        assert ti.message == "Initial tag"

    def test_tag_create_default_message(self, trunk_wc: Path) -> None:
        d = SvnDriver()
        repo = d.detect(trunk_wc)
        d.tag_create(repo, "v1.1")  # message omitted
        names = {t.name for t in d.tags(repo)}
        assert "v1.1" in names

    def test_tag_create_sign_raises(self, trunk_wc: Path) -> None:
        d = SvnDriver()
        repo = d.detect(trunk_wc)
        from sange.adapters.vcs._protocol import DriverError
        with pytest.raises(DriverError, match="GPG signing"):
            d.tag_create(repo, "v-signed", sign=True)

    def test_tag_create_invalid_name(self, trunk_wc: Path) -> None:
        d = SvnDriver()
        repo = d.detect(trunk_wc)
        from sange.adapters.vcs._protocol import DriverError
        with pytest.raises(DriverError, match="non-empty"):
            d.tag_create(repo, "")
        with pytest.raises(DriverError, match="cannot contain"):
            d.tag_create(repo, "with/slash")

    def test_tag_delete(self, trunk_wc: Path) -> None:
        d = SvnDriver()
        repo = d.detect(trunk_wc)
        d.tag_create(repo, "ephemeral")
        assert "ephemeral" in {t.name for t in d.tags(repo)}
        d.tag_delete(repo, "ephemeral")
        assert "ephemeral" not in {t.name for t in d.tags(repo)}


# --------------------------------------------------------------------------- #
# `_extract_committed_revision` — pure parser of `svn commit` stdout
# --------------------------------------------------------------------------- #


class TestExtractCommittedRevision:
    def test_basic(self) -> None:
        from sange.adapters.vcs.svn.driver import _extract_committed_revision
        out = "Adding         b.txt\nTransmitting file data .done\nCommitting transaction...\nCommitted revision 3.\n"
        assert _extract_committed_revision(out) == 3

    def test_large_revision(self) -> None:
        from sange.adapters.vcs.svn.driver import _extract_committed_revision
        assert _extract_committed_revision("Committed revision 1234567.") == 1234567

    def test_missing_marker_returns_none(self) -> None:
        from sange.adapters.vcs.svn.driver import _extract_committed_revision
        assert _extract_committed_revision("nothing useful here") is None
        assert _extract_committed_revision("") is None

    def test_multiple_lines_picks_first(self) -> None:
        # Defensive: if there are somehow two "Committed revision" lines,
        # use the first match.
        from sange.adapters.vcs.svn.driver import _extract_committed_revision
        out = "Committed revision 5.\nCommitted revision 7.\n"
        assert _extract_committed_revision(out) == 5
