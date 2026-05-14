"""Tests for src/sange/core/models/ — Domain dataclasses."""

from __future__ import annotations

import datetime as _dt
from pathlib import Path

import pytest

from sange.core.models import (
    BranchInfo,
    CommitRef,
    DiffSummary,
    FileEntry,
    FileState,
    RemoteInfo,
    Repo,
    WorkingCopyStatus,
)


# --------------------------------------------------------------------------- #
# Repo
# --------------------------------------------------------------------------- #


class TestRepo:
    def test_basic_construction(self) -> None:
        r = Repo(path=Path("/tmp/example"), vcs="git")
        assert r.vcs == "git"
        assert r.default_branch == "main"
        assert r.remote is None

    def test_slug_is_path_basename(self) -> None:
        r = Repo(path=Path("/tmp/foo-bar"), vcs="git")
        assert r.slug == "foo-bar"

    def test_relative_path_rejected(self) -> None:
        with pytest.raises(ValueError, match="must be absolute"):
            Repo(path=Path("relative/path"), vcs="git")

    def test_unknown_vcs_kind_rejected(self) -> None:
        with pytest.raises(ValueError, match="unknown VCSKind"):
            Repo(path=Path("/tmp/x"), vcs="invented")  # type: ignore[arg-type]

    def test_empty_default_branch_rejected(self) -> None:
        with pytest.raises(ValueError, match="default_branch"):
            Repo(path=Path("/tmp/x"), vcs="git", default_branch="")

    def test_frozen_immutable(self) -> None:
        r = Repo(path=Path("/tmp/x"), vcs="git")
        with pytest.raises(Exception):  # FrozenInstanceError
            r.vcs = "svn"  # type: ignore[misc]


# --------------------------------------------------------------------------- #
# CommitRef
# --------------------------------------------------------------------------- #


class TestCommitRef:
    def test_basic_construction(self) -> None:
        c = CommitRef(sha="a" * 40, subject="feat: add")
        assert c.short_sha == "a" * 12
        assert not c.is_merge

    def test_merge_detected(self) -> None:
        c = CommitRef(
            sha="a" * 40, subject="merge",
            parents=("b" * 40, "c" * 40),
        )
        assert c.is_merge

    def test_empty_sha_rejected(self) -> None:
        with pytest.raises(ValueError, match="sha"):
            CommitRef(sha="", subject="x")

    def test_empty_subject_rejected(self) -> None:
        with pytest.raises(ValueError, match="subject"):
            CommitRef(sha="a", subject="")

    def test_multiline_subject_rejected(self) -> None:
        with pytest.raises(ValueError, match="single line"):
            CommitRef(sha="a", subject="line1\nline2")

    def test_cr_in_subject_rejected(self) -> None:
        with pytest.raises(ValueError, match="single line"):
            CommitRef(sha="a", subject="x\ry")


# --------------------------------------------------------------------------- #
# DiffSummary
# --------------------------------------------------------------------------- #


class TestDiffSummary:
    def test_basic_construction(self) -> None:
        d = DiffSummary(files_changed=3, insertions=10, deletions=2, content_hash="a" * 64)
        assert d.net_lines == 8
        assert not d.is_empty

    def test_empty_when_no_files(self) -> None:
        d = DiffSummary(files_changed=0, insertions=0, deletions=0, content_hash="")
        assert d.is_empty

    def test_negative_counts_rejected(self) -> None:
        with pytest.raises(ValueError, match="non-negative"):
            DiffSummary(files_changed=-1, insertions=0, deletions=0, content_hash="")

    def test_short_hash_rejected(self) -> None:
        with pytest.raises(ValueError, match="64-char"):
            DiffSummary(files_changed=0, insertions=0, deletions=0, content_hash="abc")

    def test_empty_hash_allowed(self) -> None:
        d = DiffSummary(files_changed=0, insertions=0, deletions=0, content_hash="")
        assert d.content_hash == ""


# --------------------------------------------------------------------------- #
# RemoteInfo + BranchInfo
# --------------------------------------------------------------------------- #


class TestRemoteAndBranch:
    def test_remote_basic(self) -> None:
        r = RemoteInfo(name="origin", url="git@github.com:org/repo.git")
        assert r.name == "origin"

    def test_remote_empty_rejected(self) -> None:
        with pytest.raises(ValueError):
            RemoteInfo(name="", url="https://x")
        with pytest.raises(ValueError):
            RemoteInfo(name="origin", url="")

    def test_branch_default_state(self) -> None:
        b = BranchInfo(name="main", tip_sha="a" * 40)
        assert not b.is_tracking
        assert not b.is_up_to_date  # because not tracking

    def test_branch_tracking(self) -> None:
        b = BranchInfo(
            name="main", tip_sha="a" * 40, tracking="origin/main",
            ahead=0, behind=0,
        )
        assert b.is_tracking
        assert b.is_up_to_date

    def test_branch_ahead_only(self) -> None:
        b = BranchInfo(
            name="main", tip_sha="a" * 40, tracking="origin/main",
            ahead=2, behind=0,
        )
        assert not b.is_up_to_date

    def test_ahead_without_behind_rejected(self) -> None:
        with pytest.raises(ValueError, match="both be set or both be None"):
            BranchInfo(name="main", tip_sha="a", ahead=1, behind=None)

    def test_negative_ahead_rejected(self) -> None:
        with pytest.raises(ValueError):
            BranchInfo(name="main", tip_sha="a", ahead=-1, behind=0)

    def test_newline_in_branch_name_rejected(self) -> None:
        with pytest.raises(ValueError):
            BranchInfo(name="bad\nname", tip_sha="a")


# --------------------------------------------------------------------------- #
# FileEntry + WorkingCopyStatus
# --------------------------------------------------------------------------- #


class TestFileEntry:
    def test_basic(self) -> None:
        e = FileEntry(path=Path("a/b.txt"), state=FileState.MODIFIED)
        assert e.state is FileState.MODIFIED

    def test_absolute_path_rejected(self) -> None:
        with pytest.raises(ValueError, match="relative"):
            FileEntry(path=Path("/abs/x"), state=FileState.MODIFIED)

    def test_renamed_requires_previous(self) -> None:
        with pytest.raises(ValueError, match="previous_path required"):
            FileEntry(path=Path("new"), state=FileState.RENAMED)

    def test_non_renamed_with_previous_rejected(self) -> None:
        with pytest.raises(ValueError, match="only valid for RENAMED/COPIED"):
            FileEntry(
                path=Path("new"), state=FileState.MODIFIED,
                previous_path=Path("old"),
            )

    def test_copied_with_previous_ok(self) -> None:
        e = FileEntry(
            path=Path("new"), state=FileState.COPIED,
            previous_path=Path("old"),
        )
        assert e.previous_path == Path("old")


class TestWorkingCopyStatus:
    def test_entries_sorted_by_path(self) -> None:
        ws = WorkingCopyStatus(
            entries=(
                FileEntry(path=Path("z.txt"), state=FileState.MODIFIED),
                FileEntry(path=Path("a.txt"), state=FileState.ADDED),
                FileEntry(path=Path("m.txt"), state=FileState.UNTRACKED),
            ),
        )
        assert [str(e.path) for e in ws.entries] == ["a.txt", "m.txt", "z.txt"]

    def test_accepts_list_or_tuple(self) -> None:
        ws = WorkingCopyStatus(
            entries=[FileEntry(path=Path("a"), state=FileState.MODIFIED)],
        )
        assert isinstance(ws.entries, tuple)

    def test_is_clean_when_only_ignored(self) -> None:
        ws = WorkingCopyStatus(
            entries=(FileEntry(path=Path(".pyc"), state=FileState.IGNORED),),
        )
        assert ws.is_clean  # No dirty states
        assert not ws.is_pristine  # But not pristine (has IGNORED entries)

    def test_is_pristine(self) -> None:
        ws = WorkingCopyStatus(entries=())
        assert ws.is_pristine
        assert ws.is_clean

    def test_dirty_entries_excludes_ignored_and_unchanged(self) -> None:
        ws = WorkingCopyStatus(entries=(
            FileEntry(path=Path("dirty"), state=FileState.MODIFIED),
            FileEntry(path=Path("noise.pyc"), state=FileState.IGNORED),
            FileEntry(path=Path("clean"), state=FileState.UNCHANGED),
            FileEntry(path=Path("new"), state=FileState.UNTRACKED),
        ))
        dirty = ws.dirty_entries()
        assert {str(e.path) for e in dirty} == {"dirty", "new"}

    def test_by_state_filters_correctly(self) -> None:
        ws = WorkingCopyStatus(entries=(
            FileEntry(path=Path("a"), state=FileState.MODIFIED),
            FileEntry(path=Path("b"), state=FileState.ADDED),
            FileEntry(path=Path("c"), state=FileState.MODIFIED),
        ))
        modified = ws.by_state(FileState.MODIFIED)
        assert len(modified) == 2
        assert all(e.state is FileState.MODIFIED for e in modified)

    def test_count_and_total(self) -> None:
        ws = WorkingCopyStatus(entries=(
            FileEntry(path=Path("a"), state=FileState.MODIFIED),
            FileEntry(path=Path("b"), state=FileState.ADDED),
            FileEntry(path=Path("c"), state=FileState.MODIFIED),
        ))
        assert ws.count(FileState.MODIFIED) == 2
        assert ws.count(FileState.ADDED) == 1
        assert ws.total() == 3


# --------------------------------------------------------------------------- #
# FileState convenience
# --------------------------------------------------------------------------- #


class TestFileState:
    def test_all_dirty_excludes_clean_states(self) -> None:
        dirty = set(FileState.all_dirty())
        assert FileState.UNCHANGED not in dirty
        assert FileState.IGNORED not in dirty
        # Sanity: every other state is in there.
        assert FileState.MODIFIED in dirty
        assert FileState.UNTRACKED in dirty
        assert FileState.ADDED in dirty
