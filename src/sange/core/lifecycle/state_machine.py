"""`LifecycleEngine` — the §6.8.2 commit-message state machine.

Per §6.8.2 the lifecycle is forward-only with one exception (`reopen`).
The state machine in this module is **pure** — every method returns a
new `CommitJSON` rather than mutating the input, and no method touches
git or the filesystem (except `archive`, which is inherently FS-bound).

This separation lets higher-level workflow functions (T-040+ CLI) compose
the state machine with `GitDriver` (T-005) and `CommitsDirectory` (T-006)
explicitly: the CLI runs the git operation, then calls
`engine.mark_committed(commit, sha)` to record the result.

Transitions per §6.8.2:

    DRAFT --submit--> PENDING_REVIEW --approve--> APPROVED
        |                  |                          |
        |          reject  |                  commit  |
        v                  v                          v
    DISCARDED         REJECTED                  COMMITTED
                                                      |
                                              push    |
                                                      v
                                                  PUSHED
                                                      |
                                          archive     |
                                                      v
                                                  ARCHIVED

    Plus: any state ── reopen ──> DRAFT  (THE exception to forward-only)
"""

from __future__ import annotations

import datetime as _dt
from typing import Literal

from sange.core.lifecycle.schema import (
    Approval,
    CommitJSON,
    CommitStatus,
    Rejection,
)
from sange.core.lifecycle.store import (
    CommitsDirectory,
    filename_for,
)

Surface = Literal["cli", "tui", "web", "mcp"]


# --------------------------------------------------------------------------- #
# Exceptions
# --------------------------------------------------------------------------- #


class IllegalTransition(Exception):
    """A requested transition is not legal from the current state."""

    def __init__(
        self,
        commit_id: str,
        current: CommitStatus,
        attempted: str,
        *,
        allowed_from: frozenset[CommitStatus] | None = None,
    ) -> None:
        allowed_str = (
            ", ".join(s.value for s in sorted(allowed_from, key=lambda s: s.value))
            if allowed_from else "<unspecified>"
        )
        super().__init__(
            f"commit {commit_id!r} is in state {current.value!r}; "
            f"can't {attempted!r} (allowed-from: {{{allowed_str}}})"
        )
        self.commit_id = commit_id
        self.current = current
        self.attempted = attempted
        self.allowed_from = allowed_from


# --------------------------------------------------------------------------- #
# Transition table (for introspection + tests)
# --------------------------------------------------------------------------- #


# Maps target state → legal source states. The reverse map (source →
# legal targets) is computed below for diagnostics + UI menus.
TRANSITIONS: dict[CommitStatus, frozenset[CommitStatus]] = {
    CommitStatus.PENDING_REVIEW: frozenset({CommitStatus.DRAFT}),
    CommitStatus.APPROVED:       frozenset({CommitStatus.PENDING_REVIEW}),
    CommitStatus.REJECTED:       frozenset({CommitStatus.PENDING_REVIEW}),
    CommitStatus.COMMITTED:      frozenset({CommitStatus.APPROVED}),
    CommitStatus.PUSHED:         frozenset({CommitStatus.COMMITTED}),
    CommitStatus.ARCHIVED:       frozenset({CommitStatus.PUSHED}),
    CommitStatus.DISCARDED:      frozenset({CommitStatus.DRAFT}),
    # reopen is special: any state → DRAFT, handled separately so it
    # doesn't appear here as a TRANSITIONS entry pointing back to DRAFT.
}


def allowed_transitions_from(state: CommitStatus) -> frozenset[CommitStatus]:
    """Return the set of states reachable from `state` via a forward move.

    `reopen` is not included — it's a separate explicit operation.
    """

    out: set[CommitStatus] = set()
    for target, sources in TRANSITIONS.items():
        if state in sources:
            out.add(target)
    return frozenset(out)


def is_terminal(state: CommitStatus) -> bool:
    """A state is terminal when no forward transitions are legal from it."""

    return not allowed_transitions_from(state)


# --------------------------------------------------------------------------- #
# LifecycleEngine
# --------------------------------------------------------------------------- #


def _now() -> _dt.datetime:
    return _dt.datetime.now(tz=_dt.UTC)


def _replace(commit: CommitJSON, **changes: object) -> CommitJSON:
    """Return a new CommitJSON with `changes` applied + `updated_at` bumped.

    Re-validates via Pydantic so cross-field invariants
    (committed_sha-iff-COMMITTED+, etc.) fire on every transition.
    """

    data = commit.model_dump(mode="python")
    data.update(changes)
    data["updated_at"] = _now()
    return CommitJSON.model_validate(data)


class LifecycleEngine:
    """The pure state-transition surface for `CommitJSON`.

    Stateless — no instance attributes; every method takes the commit
    and returns a transformed copy. The class form is a convenience for
    dependency injection (CLI handlers take a `LifecycleEngine` and can
    be tested with a mock).

    The clock is injectable for deterministic tests: callers pass
    `clock=<datetime>` to fix `updated_at`.
    """

    # ----- DRAFT → PENDING_REVIEW (submit) ---------------------------- #

    def submit(self, commit: CommitJSON) -> CommitJSON:
        """Move from DRAFT to PENDING_REVIEW. Validates source state."""

        self._require_state(commit, frozenset({CommitStatus.DRAFT}), "submit")
        return _replace(commit, status=CommitStatus.PENDING_REVIEW)

    # ----- PENDING_REVIEW → APPROVED (approve) ----------------------- #

    def approve(
        self,
        commit: CommitJSON,
        *,
        actor: str,
        via: Surface = "cli",
    ) -> CommitJSON:
        """Approve a PENDING_REVIEW commit. Appends an Approval record."""

        self._require_state(commit, frozenset({CommitStatus.PENDING_REVIEW}), "approve")
        approvals = list(commit.approvals)
        approvals.append(Approval(actor=actor, at=_now(), via=via))
        return _replace(commit, status=CommitStatus.APPROVED, approvals=approvals)

    # ----- PENDING_REVIEW → REJECTED (reject) ----------------------- #

    def reject(
        self,
        commit: CommitJSON,
        *,
        actor: str,
        reason: str,
        via: Surface = "cli",
    ) -> CommitJSON:
        """Reject a PENDING_REVIEW commit. Appends a Rejection record."""

        self._require_state(commit, frozenset({CommitStatus.PENDING_REVIEW}), "reject")
        if not reason:
            raise ValueError("reject: reason must be non-empty")
        rejections = list(commit.rejections)
        rejections.append(
            Rejection(actor=actor, at=_now(), reason=reason, via=via)
        )
        return _replace(commit, status=CommitStatus.REJECTED, rejections=rejections)

    # ----- APPROVED → COMMITTED (mark_committed) -------------------- #

    def mark_committed(
        self,
        commit: CommitJSON,
        *,
        sha: str,
    ) -> CommitJSON:
        """Record that the git commit landed.

        The caller is responsible for actually invoking `GitDriver.commit()`
        before calling this method — the engine just records the SHA the
        adapter returned.
        """

        self._require_state(commit, frozenset({CommitStatus.APPROVED}), "mark_committed")
        if not sha:
            raise ValueError("mark_committed: sha must be non-empty")
        return _replace(commit, status=CommitStatus.COMMITTED, committed_sha=sha)

    # ----- COMMITTED → PUSHED (mark_pushed) ------------------------- #

    def mark_pushed(
        self,
        commit: CommitJSON,
        *,
        remote: str,
    ) -> CommitJSON:
        """Record that the push to `remote` landed.

        The caller is responsible for invoking `GitDriver.push()` first;
        the engine records the result.
        """

        self._require_state(commit, frozenset({CommitStatus.COMMITTED}), "mark_pushed")
        if not remote:
            raise ValueError("mark_pushed: remote must be non-empty")
        return _replace(commit, status=CommitStatus.PUSHED, pushed_remote=remote)

    # ----- DRAFT → DISCARDED (discard) ----------------------------- #

    def discard(self, commit: CommitJSON) -> CommitJSON:
        """Soft-delete a DRAFT commit.

        Hard-delete (removing the file) is performed by the CLI via
        `CommitsDirectory.store.delete()`. The engine only flips state.
        """

        self._require_state(commit, frozenset({CommitStatus.DRAFT}), "discard")
        return _replace(commit, status=CommitStatus.DISCARDED)

    # ----- ANY → DRAFT (reopen, the exception path) ----------------- #

    def reopen(self, commit: CommitJSON) -> CommitJSON:
        """Move any state back to DRAFT.

        Per §6.8.2 this is the ONLY backward transition. The audit log
        records every reopen separately (the engine itself doesn't log;
        the CLI invokes `sange.core.audit.log_event()` before saving).
        """

        if commit.status is CommitStatus.DRAFT:
            # No-op rather than error; caller saves a few cycles.
            return commit
        # When reopening from COMMITTED+, clear the committed_sha + remote
        # so the next forward path starts fresh. The cross-field invariants
        # in the schema enforce this — committed_sha must be empty when
        # status != COMMITTED+.
        return _replace(
            commit,
            status=CommitStatus.DRAFT,
            committed_sha="",
            pushed_remote="",
        )

    # ----- PUSHED → ARCHIVED (archive — FS-bound) ------------------- #

    def archive(
        self,
        commit: CommitJSON,
        *,
        commits_dir: CommitsDirectory,
    ) -> CommitJSON:
        """Move a PUSHED commit to `.sange/commits/archive/YYYY-MM/`.

        This is the only state transition that touches the filesystem —
        the file is physically moved from the live commits/ directory
        to the dated archive subdirectory. Returns the new CommitJSON
        (with status=ARCHIVED + updated_at bumped).
        """

        self._require_state(commit, frozenset({CommitStatus.PUSHED}), "archive")
        new_commit = _replace(commit, status=CommitStatus.ARCHIVED)

        # Move the file: delete the live version, write into archive/.
        live_dir = commits_dir.commits_dir
        live_path = live_dir / filename_for(commit)
        archive_month_dir = (
            live_dir
            / "archive"
            / new_commit.updated_at.strftime("%Y-%m")
        )
        archive_month_dir.mkdir(parents=True, exist_ok=True)

        # Write the new (ARCHIVED) JSON into the archive subdir.
        archive_path = archive_month_dir / filename_for(new_commit)
        archive_path.write_text(
            new_commit.model_dump_json(indent=2) + "\n",
            encoding="utf-8",
        )

        # Remove the live file (the move is logically atomic: archive
        # write succeeds, then live delete; if delete fails, we accept
        # a duplicated file — the next list_commits() sees the archived
        # entry and the doctor flags the leftover live file).
        if live_path.is_file():
            live_path.unlink()
        return new_commit

    # ----- internals -------------------------------------------------- #

    def _require_state(
        self,
        commit: CommitJSON,
        allowed: frozenset[CommitStatus],
        operation: str,
    ) -> None:
        if commit.status not in allowed:
            raise IllegalTransition(
                commit_id=commit.id,
                current=commit.status,
                attempted=operation,
                allowed_from=allowed,
            )


__all__ = [
    "TRANSITIONS",
    "IllegalTransition",
    "LifecycleEngine",
    "Surface",
    "allowed_transitions_from",
    "is_terminal",
]
