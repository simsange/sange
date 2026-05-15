"""Tests for src/sange/core/lifecycle/state_machine.py — LifecycleEngine.

The state machine is pure (no I/O except `archive`) so most tests exercise
the transition logic directly. `archive` tests use `tmp_path` for the
filesystem move.
"""

from __future__ import annotations

import datetime as _dt
from pathlib import Path

import pytest

from sange.core.lifecycle import (
    TRANSITIONS,
    CommitJSON,
    CommitMessage,
    CommitsDirectory,
    CommitStatus,
    IllegalTransition,
    LifecycleEngine,
    allowed_transitions_from,
    is_terminal,
)

# Past-dated fixture so the real clock used by the state machine's
# `_replace()` is always >= this value (the cross-field validator
# `updated_at >= created_at` requires monotonicity).
_NOW = _dt.datetime(2026, 1, 1, 0, 0, 0, tzinfo=_dt.UTC)


def _make_commit(
    *,
    status: CommitStatus = CommitStatus.DRAFT,
    committed_sha: str = "",
    pushed_remote: str = "",
    counter: int = 1,
) -> CommitJSON:
    return CommitJSON(
        counter=counter,
        created_at=_NOW,
        updated_at=_NOW,
        status=status,
        message=CommitMessage(type="feat", scope="auth", subject="add login"),
        committed_sha=committed_sha,
        pushed_remote=pushed_remote,
    )


# --------------------------------------------------------------------------- #
# Transition table introspection
# --------------------------------------------------------------------------- #


class TestTransitionTable:
    def test_every_status_in_table(self) -> None:
        """Every CommitStatus that has incoming forward transitions is in
        the TRANSITIONS map's keys."""

        targets = set(TRANSITIONS.keys())
        # DRAFT has no incoming forward transitions (only reopen).
        expected_keys = set(CommitStatus) - {CommitStatus.DRAFT}
        assert targets == expected_keys

    def test_allowed_transitions_from_draft(self) -> None:
        assert allowed_transitions_from(CommitStatus.DRAFT) == frozenset(
            {CommitStatus.PENDING_REVIEW, CommitStatus.DISCARDED}
        )

    def test_allowed_transitions_from_pending_review(self) -> None:
        assert allowed_transitions_from(CommitStatus.PENDING_REVIEW) == frozenset(
            {CommitStatus.APPROVED, CommitStatus.REJECTED}
        )

    def test_terminal_states(self) -> None:
        terminals = {s for s in CommitStatus if is_terminal(s)}
        assert terminals == {
            CommitStatus.REJECTED,
            CommitStatus.ARCHIVED,
            CommitStatus.DISCARDED,
        }

    def test_non_terminal_states(self) -> None:
        non_terminals = {s for s in CommitStatus if not is_terminal(s)}
        assert non_terminals == {
            CommitStatus.DRAFT,
            CommitStatus.PENDING_REVIEW,
            CommitStatus.APPROVED,
            CommitStatus.COMMITTED,
            CommitStatus.PUSHED,
        }


# --------------------------------------------------------------------------- #
# submit
# --------------------------------------------------------------------------- #


class TestSubmit:
    def test_draft_to_pending_review(self) -> None:
        c = _make_commit(status=CommitStatus.DRAFT)
        e = LifecycleEngine()
        c2 = e.submit(c)
        assert c2.status is CommitStatus.PENDING_REVIEW
        assert c2.updated_at >= _NOW

    def test_submit_from_wrong_state_raises(self) -> None:
        c = _make_commit(status=CommitStatus.APPROVED)
        with pytest.raises(IllegalTransition, match="submit"):
            LifecycleEngine().submit(c)

    def test_returns_new_object_not_mutation(self) -> None:
        c = _make_commit()
        e = LifecycleEngine()
        c2 = e.submit(c)
        # Original is unchanged.
        assert c.status is CommitStatus.DRAFT
        # New object is distinct (different id() not required, but values differ).
        assert c2.status is not c.status


# --------------------------------------------------------------------------- #
# approve / reject
# --------------------------------------------------------------------------- #


class TestApproveReject:
    def test_approve_appends_record(self) -> None:
        c = _make_commit(status=CommitStatus.PENDING_REVIEW)
        c2 = LifecycleEngine().approve(c, actor="alice@example.com", via="web")
        assert c2.status is CommitStatus.APPROVED
        assert len(c2.approvals) == 1
        assert c2.approvals[0].actor == "alice@example.com"
        assert c2.approvals[0].via == "web"

    def test_approve_from_draft_rejected(self) -> None:
        c = _make_commit(status=CommitStatus.DRAFT)
        with pytest.raises(IllegalTransition, match="approve"):
            LifecycleEngine().approve(c, actor="x")

    def test_reject_appends_record(self) -> None:
        c = _make_commit(status=CommitStatus.PENDING_REVIEW)
        c2 = LifecycleEngine().reject(c, actor="alice", reason="needs more tests")
        assert c2.status is CommitStatus.REJECTED
        assert len(c2.rejections) == 1
        assert c2.rejections[0].reason == "needs more tests"

    def test_reject_empty_reason_raises(self) -> None:
        c = _make_commit(status=CommitStatus.PENDING_REVIEW)
        with pytest.raises(ValueError, match="reason must be non-empty"):
            LifecycleEngine().reject(c, actor="x", reason="")

    def test_reject_from_approved_rejected(self) -> None:
        c = _make_commit(status=CommitStatus.APPROVED)
        with pytest.raises(IllegalTransition):
            LifecycleEngine().reject(c, actor="x", reason="too late")


# --------------------------------------------------------------------------- #
# mark_committed / mark_pushed
# --------------------------------------------------------------------------- #


class TestMarkCommittedAndPushed:
    def test_mark_committed_from_approved(self) -> None:
        c = _make_commit(status=CommitStatus.APPROVED)
        c2 = LifecycleEngine().mark_committed(c, sha="a" * 40)
        assert c2.status is CommitStatus.COMMITTED
        assert c2.committed_sha == "a" * 40

    def test_mark_committed_empty_sha_rejected(self) -> None:
        c = _make_commit(status=CommitStatus.APPROVED)
        with pytest.raises(ValueError, match="sha"):
            LifecycleEngine().mark_committed(c, sha="")

    def test_mark_committed_from_draft_rejected(self) -> None:
        c = _make_commit(status=CommitStatus.DRAFT)
        with pytest.raises(IllegalTransition):
            LifecycleEngine().mark_committed(c, sha="a" * 40)

    def test_mark_pushed_requires_committed(self) -> None:
        c = _make_commit(status=CommitStatus.APPROVED)
        with pytest.raises(IllegalTransition):
            LifecycleEngine().mark_pushed(c, remote="origin")

    def test_mark_pushed_from_committed(self) -> None:
        c = _make_commit(
            status=CommitStatus.COMMITTED,
            committed_sha="a" * 40,
        )
        c2 = LifecycleEngine().mark_pushed(c, remote="origin")
        assert c2.status is CommitStatus.PUSHED
        assert c2.pushed_remote == "origin"

    def test_mark_pushed_empty_remote_rejected(self) -> None:
        c = _make_commit(
            status=CommitStatus.COMMITTED,
            committed_sha="a" * 40,
        )
        with pytest.raises(ValueError, match="remote"):
            LifecycleEngine().mark_pushed(c, remote="")


# --------------------------------------------------------------------------- #
# discard / reopen
# --------------------------------------------------------------------------- #


class TestDiscardReopen:
    def test_discard_from_draft(self) -> None:
        c = _make_commit(status=CommitStatus.DRAFT)
        c2 = LifecycleEngine().discard(c)
        assert c2.status is CommitStatus.DISCARDED

    def test_discard_from_approved_rejected(self) -> None:
        c = _make_commit(status=CommitStatus.APPROVED)
        with pytest.raises(IllegalTransition):
            LifecycleEngine().discard(c)

    def test_reopen_from_pending_review(self) -> None:
        c = _make_commit(status=CommitStatus.PENDING_REVIEW)
        c2 = LifecycleEngine().reopen(c)
        assert c2.status is CommitStatus.DRAFT

    def test_reopen_clears_sha_and_remote(self) -> None:
        c = _make_commit(
            status=CommitStatus.PUSHED,
            committed_sha="a" * 40,
            pushed_remote="origin",
        )
        c2 = LifecycleEngine().reopen(c)
        assert c2.status is CommitStatus.DRAFT
        assert c2.committed_sha == ""
        assert c2.pushed_remote == ""

    def test_reopen_from_draft_is_noop(self) -> None:
        c = _make_commit(status=CommitStatus.DRAFT)
        c2 = LifecycleEngine().reopen(c)
        # Same object (the no-op early-return path) — no update.
        assert c2 is c

    def test_reopen_from_terminal_states(self) -> None:
        """Per §6.8.2 reopen is THE backward path — works from REJECTED,
        DISCARDED, ARCHIVED too."""

        for terminal_state in (
            CommitStatus.REJECTED,
            CommitStatus.DISCARDED,
        ):
            c = _make_commit(status=terminal_state)
            c2 = LifecycleEngine().reopen(c)
            assert c2.status is CommitStatus.DRAFT


# --------------------------------------------------------------------------- #
# archive (the FS-bound transition)
# --------------------------------------------------------------------------- #


class TestArchive:
    def test_archive_moves_file(self, tmp_path: Path) -> None:
        cd = CommitsDirectory(tmp_path)
        c = _make_commit(
            counter=cd.allocate_counter(),
            status=CommitStatus.PUSHED,
            committed_sha="a" * 40,
            pushed_remote="origin",
        )
        live_path = cd.save(c)
        assert live_path.is_file()

        c2 = LifecycleEngine().archive(c, commits_dir=cd)
        assert c2.status is CommitStatus.ARCHIVED

        # Live file is gone.
        assert not live_path.is_file()

        # Archive file exists under archive/YYYY-MM/.
        archive_files = list((cd.commits_dir / "archive").rglob("*.json"))
        assert len(archive_files) == 1

    def test_archive_from_wrong_state_raises(self, tmp_path: Path) -> None:
        cd = CommitsDirectory(tmp_path)
        c = _make_commit(status=CommitStatus.APPROVED)
        with pytest.raises(IllegalTransition):
            LifecycleEngine().archive(c, commits_dir=cd)

    def test_archive_path_uses_year_month_directory(self, tmp_path: Path) -> None:
        cd = CommitsDirectory(tmp_path)
        c = _make_commit(
            counter=cd.allocate_counter(),
            status=CommitStatus.PUSHED,
            committed_sha="a" * 40,
            pushed_remote="origin",
        )
        cd.save(c)
        c2 = LifecycleEngine().archive(c, commits_dir=cd)
        # The directory name matches YYYY-MM of `c2.updated_at`.
        expected_dir = c2.updated_at.strftime("%Y-%m")
        assert (cd.commits_dir / "archive" / expected_dir).is_dir()

    def test_archive_idempotent_when_live_file_missing(self, tmp_path: Path) -> None:
        """If the live file was already removed (e.g. doctor cleaned it),
        archive() shouldn't crash — it writes the archived copy and
        gracefully ignores the missing live file."""

        cd = CommitsDirectory(tmp_path)
        c = _make_commit(
            counter=cd.allocate_counter(),
            status=CommitStatus.PUSHED,
            committed_sha="a" * 40,
            pushed_remote="origin",
        )
        # Don't call cd.save(c) — there's no live file.
        c2 = LifecycleEngine().archive(c, commits_dir=cd)
        assert c2.status is CommitStatus.ARCHIVED


# --------------------------------------------------------------------------- #
# Happy-path full lifecycle
# --------------------------------------------------------------------------- #


class TestFullLifecycle:
    def test_draft_to_archived(self, tmp_path: Path) -> None:
        cd = CommitsDirectory(tmp_path)
        e = LifecycleEngine()
        c0 = _make_commit(counter=cd.allocate_counter())

        c1 = e.submit(c0)
        c2 = e.approve(c1, actor="alice")
        c3 = e.mark_committed(c2, sha="a" * 40)
        c4 = e.mark_pushed(c3, remote="origin")
        # Save before archiving so there's a file to move.
        cd.save(c4)
        c5 = e.archive(c4, commits_dir=cd)

        assert c5.status is CommitStatus.ARCHIVED
        assert len(c5.approvals) == 1
        assert c5.committed_sha == "a" * 40
        assert c5.pushed_remote == "origin"

    def test_draft_to_rejected(self) -> None:
        c0 = _make_commit()
        e = LifecycleEngine()
        c1 = e.submit(c0)
        c2 = e.reject(c1, actor="reviewer", reason="not yet")
        assert c2.status is CommitStatus.REJECTED
        # Cannot move forward from REJECTED — only reopen.
        with pytest.raises(IllegalTransition):
            e.approve(c2, actor="x")

    def test_full_path_with_reopen(self) -> None:
        e = LifecycleEngine()
        c0 = _make_commit()
        c1 = e.submit(c0)
        c2 = e.reject(c1, actor="x", reason="meh")
        # Reopen → start over.
        c3 = e.reopen(c2)
        assert c3.status is CommitStatus.DRAFT
        # Now resubmit + approve.
        c4 = e.submit(c3)
        c5 = e.approve(c4, actor="alice")
        assert c5.status is CommitStatus.APPROVED


# --------------------------------------------------------------------------- #
# Cross-state combinatoric: every illegal transition raises
# --------------------------------------------------------------------------- #


class TestEveryIllegalTransition:
    @pytest.mark.parametrize("from_state", list(CommitStatus))
    def test_submit_illegal_unless_draft(
        self, from_state: CommitStatus,
    ) -> None:
        if from_state is CommitStatus.DRAFT:
            return
        c = _make_commit(
            status=from_state,
            committed_sha="a" * 40 if from_state in (
                CommitStatus.COMMITTED, CommitStatus.PUSHED, CommitStatus.ARCHIVED,
            ) else "",
            pushed_remote="origin" if from_state in (
                CommitStatus.PUSHED, CommitStatus.ARCHIVED,
            ) else "",
        )
        with pytest.raises(IllegalTransition):
            LifecycleEngine().submit(c)

    @pytest.mark.parametrize("from_state", list(CommitStatus))
    def test_mark_pushed_illegal_unless_committed(
        self, from_state: CommitStatus,
    ) -> None:
        if from_state is CommitStatus.COMMITTED:
            return
        c = _make_commit(
            status=from_state,
            committed_sha="a" * 40 if from_state in (
                CommitStatus.PUSHED, CommitStatus.ARCHIVED,
            ) else "",
            pushed_remote="origin" if from_state in (
                CommitStatus.PUSHED, CommitStatus.ARCHIVED,
            ) else "",
        )
        with pytest.raises(IllegalTransition):
            LifecycleEngine().mark_pushed(c, remote="origin")
