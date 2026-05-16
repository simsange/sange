"""`AuditChain` — append-only writer for the per-repo audit JSONL.

Each repo has one chain stored as ISO-week-sharded files under
`<repo>/.sange/audit/<YYYY>-W<NN>.jsonl`. Records append to the
current week's shard; week rollover happens on the first append
after midnight UTC of the new ISO week.

The writer is **append-only on disk**: appending a new record is
`open(path, "a")` + write + fsync. The chain integrity comes from
each record's `prev_hash` linking to the previous record's
`this_hash`. Tampering with a mid-chain record requires
recomputing every subsequent hash — which a verifier catches
immediately.

Concurrency: file appends on POSIX are atomic at the syscall
level when the data is shorter than PIPE_BUF (typically 4096 bytes).
A normal `AuditEvent.to_json()` line is well under that. The chain
doesn't take a lock — concurrent appenders within the same process
serialize via the GIL; cross-process concurrency would need an
advisory lock (deferred to v0.5 when the Web UI's daemon ships).
"""

from __future__ import annotations

import datetime as _dt
import os
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from sange.core.audit.event import (
    AuditEvent,
    AuditEventError,
    EventKind,
    make_event,
)


class AuditChainError(Exception):
    """Raised when the chain writer can't proceed."""


class AuditChain:
    """Append-only writer for `<repo>/.sange/audit/<ISO-week>.jsonl`."""

    def __init__(self, repo_root: Path, *, clock: _dt.datetime | None = None) -> None:
        self._repo_root = Path(repo_root).resolve()
        self._clock = clock

    @property
    def repo_root(self) -> Path:
        return self._repo_root

    @property
    def audit_dir(self) -> Path:
        return self._repo_root / ".sange" / "audit"

    def shard_path(self, when: _dt.datetime | None = None) -> Path:
        """Return the JSONL shard path for `when` (default: now-UTC).

        Sharding is by ISO calendar week — `<YYYY>-W<NN>.jsonl`.
        Records within the same week land in the same shard.
        """

        moment = when or self._clock or _dt.datetime.now(tz=_dt.UTC)
        iso_year, iso_week, _ = moment.isocalendar()
        return self.audit_dir / f"{iso_year:04d}-W{iso_week:02d}.jsonl"

    def last_hash(self) -> str:
        """Return the most-recent record's `this_hash`, or "" if empty.

        Walks the current week's shard last → first; falls back to
        prior shards in descending order if the current week is empty.
        Useful for chaining a new record onto a partially-written log.
        """

        if not self.audit_dir.is_dir():
            return ""
        shards = sorted(self.audit_dir.glob("*.jsonl"), reverse=True)
        for shard in shards:
            try:
                with shard.open("r", encoding="utf-8") as fp:
                    last_line = ""
                    for line in fp:
                        stripped = line.strip()
                        if stripped:
                            last_line = stripped
                    if not last_line:
                        continue
                    event = AuditEvent.from_json(last_line)
                    return event.this_hash
            except (OSError, AuditEventError):
                continue
        return ""

    def append(
        self,
        kind: EventKind | str,
        *,
        actor: str,
        payload: dict[str, Any] | None = None,
        timestamp: str | None = None,
        event_id: str | None = None,
    ) -> AuditEvent:
        """Build + write one event onto the current shard.

        The new event's `prev_hash` is auto-populated from the
        chain's current head. Returns the written event so callers
        can stash its `this_hash` for cross-references.
        """

        try:
            self.audit_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise AuditChainError(
                f"cannot create {self.audit_dir}: {exc}"
            ) from exc

        prev = self.last_hash()
        event = make_event(
            kind,
            actor=actor,
            payload=payload,
            prev_hash=prev,
            timestamp=timestamp,
            event_id=event_id,
        )

        shard = self.shard_path()
        line = event.to_json() + "\n"
        try:
            # Append-mode write + fsync. POSIX guarantees the append
            # is atomic when the data is shorter than PIPE_BUF; a
            # normal JSONL line is well under that.
            fd = os.open(
                str(shard),
                os.O_WRONLY | os.O_APPEND | os.O_CREAT,
                0o644,
            )
            try:
                os.write(fd, line.encode("utf-8"))
                os.fsync(fd)
            finally:
                os.close(fd)
        except OSError as exc:
            raise AuditChainError(
                f"append failed for {shard}: {exc}"
            ) from exc

        return event

    def shards(self) -> tuple[Path, ...]:
        """Every shard in the chain, sorted by week ascending."""

        if not self.audit_dir.is_dir():
            return ()
        return tuple(sorted(self.audit_dir.glob("*.jsonl")))

    def iter_events(self) -> Iterator[AuditEvent]:
        """Walk every event in every shard in chronological order.

        Malformed lines surface as `AuditEventError` — the iterator
        does NOT swallow them. Verification callers want to know.
        """

        for shard in self.shards():
            try:
                fp = shard.open("r", encoding="utf-8")
            except OSError as exc:
                raise AuditChainError(
                    f"cannot read {shard}: {exc}"
                ) from exc
            with fp:
                for line in fp:
                    stripped = line.strip()
                    if not stripped:
                        continue
                    yield AuditEvent.from_json(stripped)

    def count(self) -> int:
        """Total record count across every shard."""

        return sum(1 for _ in self.iter_events())


__all__ = [
    "AuditChain",
    "AuditChainError",
]
