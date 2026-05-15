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

    def test_not_yet_implemented_surfaces_raise(self, svn_wc: Path) -> None:
        d = SvnDriver()
        repo = d.detect(svn_wc)
        for verb in ("log", "diff", "branches", "current_branch",
                     "remotes", "tags", "show_commit"):
            with pytest.raises(NotImplementedError, match="T-100b"):
                getattr(d, verb)(repo)
        for verb in ("add", "remove", "revert_working_copy", "commit",
                     "branch_create", "branch_delete", "switch",
                     "fetch", "pull", "push", "tag_create", "tag_delete"):
            with pytest.raises(NotImplementedError, match="T-100c"):
                getattr(d, verb)(repo)
