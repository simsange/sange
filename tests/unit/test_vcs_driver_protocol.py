"""Tests for src/sange/adapters/vcs/_protocol.py — VCSDriver Protocol.

Protocols are static-typing constructs; the run-time tests here verify:
  * The expected types are importable + have the documented attributes.
  * `DriverCapabilities` + `PushResult` + `TagInfo` dataclasses round-trip.
  * A stub driver that implements every method type-checks structurally
    against `VCSDriver` (via the static type checker — these tests just
    instantiate the stub to verify the shape).
"""

from __future__ import annotations

import datetime as _dt
from collections.abc import Sequence
from pathlib import Path
from typing import get_args

import pytest

from sange.adapters.vcs import (
    DriverCapabilities,
    DriverError,
    PushResult,
    SupportsBisect,
    SupportsLFS,
    SupportsRebase,
    SupportsStash,
    TagInfo,
    VCSDriver,
)
from sange.core.models import (
    BranchInfo,
    CommitRef,
    DiffSummary,
    RemoteInfo,
    Repo,
    WorkingCopyStatus,
)

# --------------------------------------------------------------------------- #
# Auxiliary shapes
# --------------------------------------------------------------------------- #


class TestPushResult:
    def test_default_is_no_op(self) -> None:
        r = PushResult(remote="origin")
        assert r.was_no_op is False
        assert r.refs_updated == ()
        assert r.forced is False

    def test_with_refs(self) -> None:
        r = PushResult(
            remote="origin",
            refs_updated=(("refs/heads/main", "refs/heads/main"),),
        )
        assert len(r.refs_updated) == 1


class TestTagInfo:
    def test_lightweight(self) -> None:
        t = TagInfo(name="v0.1.0", target_sha="a" * 40)
        assert not t.is_annotated
        assert not t.is_signed

    def test_signed_annotated(self) -> None:
        t = TagInfo(
            name="v0.1.0", target_sha="a" * 40,
            is_annotated=True, is_signed=True, message="Initial release",
        )
        assert t.is_annotated and t.is_signed
        assert t.message == "Initial release"


class TestDriverCapabilities:
    def test_minimal(self) -> None:
        caps = DriverCapabilities(vcs="git", vcs_version="git 2.51.0")
        assert caps.vcs == "git"
        # Defaults
        assert not caps.supports_stash
        assert caps.supports_signed_tags  # Default True
        assert not caps.supports_history_rewrite

    def test_with_capabilities(self) -> None:
        caps = DriverCapabilities(
            vcs="git", vcs_version="git 2.51.0",
            supports_stash=True, supports_bisect=True, supports_rebase=True,
            supports_lfs=True, supports_history_rewrite=True,
            notes=("git-filter-repo installed", "BFG available"),
        )
        assert all((caps.supports_stash, caps.supports_bisect,
                    caps.supports_rebase, caps.supports_lfs))
        assert len(caps.notes) == 2


# --------------------------------------------------------------------------- #
# DriverError
# --------------------------------------------------------------------------- #


class TestDriverError:
    def test_is_exception(self) -> None:
        with pytest.raises(DriverError, match="something failed"):
            raise DriverError("something failed")


# --------------------------------------------------------------------------- #
# Structural compliance — a stub driver implements every Protocol method
# --------------------------------------------------------------------------- #


class _StubDriver:
    """A no-op `VCSDriver` implementation used to verify the Protocol shape.

    If `VCSDriver` adds or renames a method, the stub here breaks the
    static type-check (in CI's mypy step). Run-time the stub just needs
    to be instantiable.
    """

    capabilities = DriverCapabilities(
        vcs="git",
        vcs_version="stub",
        supports_stash=False,
    )

    @classmethod
    def detect(cls, path: Path) -> Repo:
        return Repo(path=path.resolve(), vcs="git")

    def status(self, repo: Repo) -> WorkingCopyStatus:
        return WorkingCopyStatus(entries=(), branch="main")

    def log(
        self, repo: Repo, *, revision_range: str = "", max_count: int | None = None,
    ) -> tuple[CommitRef, ...]:
        return ()

    def diff(
        self, repo: Repo, *, paths: Sequence[Path] = (), revision_range: str = "",
    ) -> DiffSummary:
        return DiffSummary(files_changed=0, insertions=0, deletions=0, content_hash="")

    def branches(self, repo: Repo) -> tuple[BranchInfo, ...]:
        return ()

    def current_branch(self, repo: Repo) -> BranchInfo | None:
        return None

    def remotes(self, repo: Repo) -> tuple[RemoteInfo, ...]:
        return ()

    def tags(self, repo: Repo) -> tuple[TagInfo, ...]:
        return ()

    def show_commit(self, repo: Repo, sha: str) -> CommitRef:
        raise DriverError(f"stub: commit {sha} not found")

    def add(self, repo: Repo, paths: Sequence[Path]) -> None:
        pass

    def remove(self, repo: Repo, paths: Sequence[Path], *, force: bool = False) -> None:
        pass

    def revert_working_copy(self, repo: Repo, paths: Sequence[Path]) -> None:
        pass

    def commit(
        self,
        repo: Repo,
        *,
        message: str,
        author_name: str = "",
        author_email: str = "",
        allow_empty: bool = False,
        sign: bool = False,
    ) -> CommitRef:
        return CommitRef(sha="0" * 40, subject=message.split("\n", 1)[0])

    def branch_create(self, repo: Repo, name: str, *, base: str = "") -> BranchInfo:
        return BranchInfo(name=name, tip_sha="0" * 40)

    def branch_delete(self, repo: Repo, name: str, *, force: bool = False) -> None:
        pass

    def switch(self, repo: Repo, branch: str) -> BranchInfo:
        return BranchInfo(name=branch, tip_sha="0" * 40, is_current=True)

    def fetch(self, repo: Repo, remote: str = "") -> None:
        pass

    def pull(self, repo: Repo, remote: str = "") -> None:
        pass

    def push(
        self,
        repo: Repo,
        *,
        remote: str = "",
        branch: str = "",
        force: bool = False,
        force_with_lease: bool = False,
    ) -> PushResult:
        return PushResult(remote=remote or "origin", was_no_op=True)

    def tag_create(
        self,
        repo: Repo,
        name: str,
        *,
        target_sha: str = "",
        message: str = "",
        sign: bool = False,
    ) -> TagInfo:
        return TagInfo(name=name, target_sha=target_sha or "0" * 40)

    def tag_delete(self, repo: Repo, name: str) -> None:
        pass


class TestStubDriverCompliance:
    def test_stub_instantiates(self) -> None:
        d = _StubDriver()
        assert d.capabilities.vcs == "git"

    def test_stub_satisfies_vcsdriver_structurally(self) -> None:
        """The static checker enforces this; at run-time we just probe key methods."""

        d: VCSDriver = _StubDriver()  # static-type assignment proves the shape
        # Probe a few methods to make sure they're callable + return the right shape.
        repo = d.detect(Path("/tmp/example"))
        assert isinstance(repo, Repo)
        ws = d.status(repo)
        assert isinstance(ws, WorkingCopyStatus)
        diff = d.diff(repo)
        assert isinstance(diff, DiffSummary)
        commit = d.commit(repo, message="test commit")
        assert isinstance(commit, CommitRef)
        push = d.push(repo)
        assert isinstance(push, PushResult)
        tag = d.tag_create(repo, "v0.0.0")
        assert isinstance(tag, TagInfo)

    def test_capability_descriptor_exposed(self) -> None:
        d = _StubDriver()
        assert isinstance(d.capabilities, DriverCapabilities)
        assert d.capabilities.vcs in {"git", "svn", "hg", "p4", "fossil", "pijul"}


# --------------------------------------------------------------------------- #
# Sub-Protocols are Protocols
# --------------------------------------------------------------------------- #


class TestSubProtocols:
    """The four optional sub-Protocols are importable + have the right methods.

    A driver that satisfies them is statically annotated; here we just
    sanity-check the surface exists.
    """

    @pytest.mark.parametrize("proto", [SupportsStash, SupportsBisect,
                                       SupportsRebase, SupportsLFS])
    def test_protocol_is_a_protocol(self, proto: type) -> None:
        # typing.Protocol metaclass — we can't easily probe this at runtime
        # without internals, but we can confirm the class object exists +
        # has the documented method names.
        if proto is SupportsStash:
            for name in ("stash_push", "stash_pop", "stash_list"):
                assert hasattr(proto, name), f"SupportsStash missing {name}"
        if proto is SupportsBisect:
            for name in ("bisect_start", "bisect_good", "bisect_bad", "bisect_reset"):
                assert hasattr(proto, name), f"SupportsBisect missing {name}"
        if proto is SupportsRebase:
            for name in ("rebase", "rebase_abort"):
                assert hasattr(proto, name), f"SupportsRebase missing {name}"
        if proto is SupportsLFS:
            for name in ("lfs_track", "lfs_untrack", "lfs_status"):
                assert hasattr(proto, name), f"SupportsLFS missing {name}"
