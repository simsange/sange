"""Tests for src/sange/core/lifecycle/{store,counter}.py — file-based store + counter."""

from __future__ import annotations

import datetime as _dt
from pathlib import Path

import pytest

from sange.core.lifecycle import (
    CommitCounter,
    CommitJSON,
    CommitMessage,
    CommitsDirectory,
    CommitStatus,
    CommitStore,
    CommitStoreError,
    slugify_subject,
)
from sange.core.lifecycle.store import filename_for

_NOW = _dt.datetime(2026, 5, 15, 12, 0, 0, tzinfo=_dt.UTC)


def _make_commit(
    counter: int = 1,
    *,
    type_: str = "feat",
    scope: str = "auth",
    subject: str = "add passkey support",
    status: CommitStatus = CommitStatus.DRAFT,
    committed_sha: str = "",
    pushed_remote: str = "",
) -> CommitJSON:
    return CommitJSON(
        counter=counter,
        created_at=_NOW,
        updated_at=_NOW,
        status=status,
        message=CommitMessage(type=type_, scope=scope, subject=subject),  # type: ignore[arg-type]
        committed_sha=committed_sha,
        pushed_remote=pushed_remote,
    )


# --------------------------------------------------------------------------- #
# slugify_subject
# --------------------------------------------------------------------------- #


class TestSlugifySubject:
    def test_basic(self) -> None:
        assert slugify_subject("add OAuth login") == "add-oauth-login"

    def test_special_chars_replaced(self) -> None:
        assert slugify_subject("Fix: race in gitignore-swap!") == \
            "fix-race-in-gitignore-swap"

    def test_repeated_dashes_collapsed(self) -> None:
        assert slugify_subject("a -- b -- c") == "a-b-c"

    def test_empty_subject(self) -> None:
        assert slugify_subject("") == "untitled"

    def test_all_special_chars(self) -> None:
        assert slugify_subject("???") == "untitled"

    def test_truncated(self) -> None:
        long = "a" * 200
        assert len(slugify_subject(long)) <= 64

    def test_truncation_strips_trailing_dash(self) -> None:
        # Construct a string that, at the truncation boundary, ends with a dash.
        s = ("x" * 62) + "-" + "y" * 20
        out = slugify_subject(s)
        assert not out.endswith("-")


# --------------------------------------------------------------------------- #
# filename_for
# --------------------------------------------------------------------------- #


class TestFilenameFor:
    def test_with_scope(self) -> None:
        c = _make_commit()
        assert filename_for(c) == "0001-feat-auth-add-passkey-support.json"

    def test_without_scope(self) -> None:
        c = _make_commit(scope="")
        # Per §6.8.1 layout: NNNN-<type>-<subject>.json when no scope.
        assert filename_for(c) == "0001-feat-add-passkey-support.json"

    def test_counter_zero_padded_to_four(self) -> None:
        c = _make_commit(counter=42)
        assert filename_for(c).startswith("0042-")


# --------------------------------------------------------------------------- #
# CommitCounter
# --------------------------------------------------------------------------- #


class TestCommitCounter:
    def test_initial_is_zero(self, tmp_path: Path) -> None:
        c = CommitCounter(tmp_path / "commits")
        assert c.current_number() == 0

    def test_next_monotonic(self, tmp_path: Path) -> None:
        c = CommitCounter(tmp_path / "commits")
        assert c.next_number() == 1
        assert c.next_number() == 2
        assert c.next_number() == 3
        assert c.current_number() == 3

    def test_persists_across_instances(self, tmp_path: Path) -> None:
        d = tmp_path / "commits"
        CommitCounter(d).next_number()  # → 1
        CommitCounter(d).next_number()  # → 2
        assert CommitCounter(d).current_number() == 2

    def test_recovery_from_filesystem(self, tmp_path: Path) -> None:
        # Simulate a missing/corrupted .counter but existing JSON files.
        commits = tmp_path / "commits"
        commits.mkdir(parents=True)
        (commits / "0005-feat-foo.json").write_text("{}\n")
        (commits / "0007-fix-bar.json").write_text("{}\n")
        # No .counter file → must recover from filenames.
        c = CommitCounter(commits)
        assert c.current_number() == 7
        # And persisted now.
        assert (commits / ".counter").is_file()
        assert (commits / ".counter").read_text().strip() == "7"

    def test_corrupt_counter_recovers(self, tmp_path: Path) -> None:
        commits = tmp_path / "commits"
        commits.mkdir(parents=True)
        (commits / ".counter").write_text("not-an-integer\n")
        (commits / "0003-feat-x.json").write_text("{}\n")
        c = CommitCounter(commits)
        assert c.current_number() == 3


# --------------------------------------------------------------------------- #
# CommitStore — read/write/list
# --------------------------------------------------------------------------- #


class TestCommitStoreWriteRead:
    def test_write_then_read(self, tmp_path: Path) -> None:
        store = CommitStore(tmp_path / "commits")
        c = _make_commit()
        path = store.write(c)
        assert path.is_file()
        assert path.name == "0001-feat-auth-add-passkey-support.json"
        replayed = store.read(path)
        assert replayed == c

    def test_read_missing_file_raises(self, tmp_path: Path) -> None:
        store = CommitStore(tmp_path / "commits")
        with pytest.raises(CommitStoreError, match="not found"):
            store.read(tmp_path / "commits" / "nope.json")

    def test_read_malformed_raises(self, tmp_path: Path) -> None:
        d = tmp_path / "commits"
        d.mkdir(parents=True)
        bad = d / "0001-feat-bad.json"
        bad.write_text("not valid json")
        store = CommitStore(d)
        with pytest.raises(CommitStoreError):
            store.read(bad)


class TestCommitStoreList:
    def _seed_three(self, tmp_path: Path) -> CommitStore:
        store = CommitStore(tmp_path / "commits")
        store.write(_make_commit(counter=1, subject="first"))
        store.write(_make_commit(counter=2, subject="second", status=CommitStatus.PENDING_REVIEW))
        store.write(_make_commit(counter=3, subject="third", status=CommitStatus.APPROVED))
        return store

    def test_list_all(self, tmp_path: Path) -> None:
        store = self._seed_three(tmp_path)
        out = store.list_commits()
        assert len(out) == 3
        # Sorted by counter ascending.
        assert [c.counter for c in out] == [1, 2, 3]

    def test_list_by_status(self, tmp_path: Path) -> None:
        store = self._seed_three(tmp_path)
        approved = store.list_commits(status=CommitStatus.APPROVED)
        assert len(approved) == 1
        assert approved[0].counter == 3

    def test_archive_excluded_by_default(self, tmp_path: Path) -> None:
        store = self._seed_three(tmp_path)
        # Plant an archived file in archive/2026-05/
        archive_dir = tmp_path / "commits" / "archive" / "2026-05"
        archive_dir.mkdir(parents=True)
        old = _make_commit(
            counter=100,
            subject="archived",
            status=CommitStatus.ARCHIVED,
            committed_sha="b" * 40,
            pushed_remote="origin",
        )
        (archive_dir / "0100-feat-auth-archived.json").write_text(
            old.model_dump_json(),
        )
        # Default list excludes archive.
        live = store.list_commits()
        assert all(c.counter < 100 for c in live)
        # With include_archived=True it appears.
        full = store.list_commits(include_archived=True)
        assert any(c.counter == 100 for c in full)

    def test_skip_files_starting_with_dot(self, tmp_path: Path) -> None:
        d = tmp_path / "commits"
        d.mkdir(parents=True)
        (d / ".counter").write_text("1\n")  # Not a commit JSON.
        (d / ".hidden.json").write_text("{}")
        store = CommitStore(d)
        out = store.list_commits()
        assert out == []


class TestCommitStoreFind:
    def test_find_by_counter(self, tmp_path: Path) -> None:
        store = CommitStore(tmp_path / "commits")
        c = _make_commit(counter=42, subject="answer")
        store.write(c)
        found = store.find_by_counter(42)
        assert found is not None
        assert found.counter == 42

    def test_find_by_counter_missing(self, tmp_path: Path) -> None:
        store = CommitStore(tmp_path / "commits")
        store.write(_make_commit())
        assert store.find_by_counter(999) is None

    def test_find_by_id(self, tmp_path: Path) -> None:
        store = CommitStore(tmp_path / "commits")
        c = _make_commit()
        store.write(c)
        found = store.find_by_id(c.id)
        assert found is not None
        assert found.id == c.id

    def test_find_by_id_unknown(self, tmp_path: Path) -> None:
        store = CommitStore(tmp_path / "commits")
        store.write(_make_commit())
        assert store.find_by_id("nope") is None


class TestCommitStoreDelete:
    def test_delete_existing(self, tmp_path: Path) -> None:
        store = CommitStore(tmp_path / "commits")
        c = _make_commit()
        path = store.write(c)
        assert path.is_file()
        assert store.delete(c)
        assert not path.is_file()

    def test_delete_missing(self, tmp_path: Path) -> None:
        store = CommitStore(tmp_path / "commits")
        c = _make_commit()
        assert not store.delete(c)


# --------------------------------------------------------------------------- #
# CommitsDirectory — high-level façade
# --------------------------------------------------------------------------- #


class TestCommitsDirectory:
    def test_allocate_and_save_round_trip(self, tmp_path: Path) -> None:
        cd = CommitsDirectory(tmp_path)
        n = cd.allocate_counter()
        c = _make_commit(counter=n)
        path = cd.save(c)
        assert path.is_file()
        replayed = cd.read(path)
        assert replayed == c

    def test_monotonic_across_saves(self, tmp_path: Path) -> None:
        cd = CommitsDirectory(tmp_path)
        n1 = cd.allocate_counter()
        n2 = cd.allocate_counter()
        n3 = cd.allocate_counter()
        assert (n1, n2, n3) == (1, 2, 3)

    def test_list_all_returns_saved_commits(self, tmp_path: Path) -> None:
        cd = CommitsDirectory(tmp_path)
        for i in range(3):
            cd.save(_make_commit(counter=cd.allocate_counter(), subject=f"c{i}"))
        all_ = cd.list_all()
        assert len(all_) == 3

    def test_by_counter_lookup(self, tmp_path: Path) -> None:
        cd = CommitsDirectory(tmp_path)
        n = cd.allocate_counter()
        c = _make_commit(counter=n)
        cd.save(c)
        found = cd.by_counter(n)
        assert found is not None
        assert found.id == c.id

    def test_atomic_write_no_partial_file(self, tmp_path: Path) -> None:
        """Atomic write: after a successful save, the file is fully on disk
        (no `.tmp` artifact remaining)."""

        cd = CommitsDirectory(tmp_path)
        n = cd.allocate_counter()
        cd.save(_make_commit(counter=n))
        # No .tmp- prefixed files left around.
        for f in cd.commits_dir.iterdir():
            assert ".tmp" not in f.name
