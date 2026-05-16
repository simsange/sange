"""Chain integrity verification.

Given a JSONL audit shard (or a whole repo's audit dir), walks
records front-to-back and recomputes each event's `this_hash`,
checks that each record's `prev_hash` matches the previous
record's `this_hash`, and surfaces the first break.

Three failure modes:

  * **Malformed line**       — a record doesn't deserialize.
                               `verified=False`, kind=`"malformed"`.
  * **Hash mismatch**        — the record's `this_hash` doesn't
                               match `compute_hash(record)`.
                               kind=`"hash-mismatch"`.
  * **Chain break**          — a record's `prev_hash` doesn't
                               equal the previous record's
                               `this_hash`.
                               kind=`"chain-break"`.

`verified=True` means every record is internally consistent AND
the chain links cleanly from first to last.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sange.core.audit.event import (
    AuditEvent,
    AuditEventError,
    compute_hash,
)


@dataclass(frozen=True)
class VerificationReport:
    """The outcome of `verify_chain` / `verify_repo`."""

    verified: bool
    records_checked: int
    shards_checked: int = 0
    failure_kind: str = ""        # "" | "malformed" | "hash-mismatch" | "chain-break"
    failure_shard: str = ""
    failure_index: int = -1       # 0-based index within the shard
    failure_event_id: str = ""
    failure_message: str = ""
    shard_paths: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return {
            "verified": self.verified,
            "records_checked": self.records_checked,
            "shards_checked": self.shards_checked,
            "failure_kind": self.failure_kind,
            "failure_shard": self.failure_shard,
            "failure_index": self.failure_index,
            "failure_event_id": self.failure_event_id,
            "failure_message": self.failure_message,
            "shard_paths": list(self.shard_paths),
        }


def verify_chain(
    shard_path: Path,
    *,
    starting_prev_hash: str = "",
) -> VerificationReport:
    """Verify one JSONL shard.

    `starting_prev_hash` lets the caller chain-verify across
    multiple shards by feeding the previous shard's last
    `this_hash` as the seed. Default "" means "this shard is
    the start of the chain".
    """

    prev_hash = starting_prev_hash
    index = -1

    try:
        with Path(shard_path).open("r", encoding="utf-8") as fp:
            for raw_line in fp:
                stripped = raw_line.strip()
                if not stripped:
                    continue
                index += 1
                try:
                    event = AuditEvent.from_json(stripped)
                except AuditEventError as exc:
                    return VerificationReport(
                        verified=False,
                        records_checked=index,   # records BEFORE the break
                        failure_kind="malformed",
                        failure_shard=str(shard_path),
                        failure_index=index,
                        failure_message=str(exc),
                    )

                if event.prev_hash != prev_hash:
                    return VerificationReport(
                        verified=False,
                        records_checked=index,
                        failure_kind="chain-break",
                        failure_shard=str(shard_path),
                        failure_index=index,
                        failure_event_id=event.id,
                        failure_message=(
                            f"record {index} prev_hash {event.prev_hash[:12]}.. "
                            f"does not match previous this_hash {prev_hash[:12]}.."
                        ),
                    )

                expected = compute_hash(event)
                if event.this_hash != expected:
                    return VerificationReport(
                        verified=False,
                        records_checked=index,
                        failure_kind="hash-mismatch",
                        failure_shard=str(shard_path),
                        failure_index=index,
                        failure_event_id=event.id,
                        failure_message=(
                            f"record {index} this_hash {event.this_hash[:12]}.. "
                            f"!= recomputed {expected[:12]}.. (tampered or stale)"
                        ),
                    )

                prev_hash = event.this_hash
    except FileNotFoundError:
        return VerificationReport(
            verified=False,
            records_checked=0,
            failure_kind="malformed",
            failure_shard=str(shard_path),
            failure_message="shard file not found",
        )

    total = index + 1
    return VerificationReport(
        verified=True,
        records_checked=total,
        shards_checked=1,
        shard_paths=(str(shard_path),),
    )


def verify_repo(repo_root: Path) -> VerificationReport:
    """Verify the entire `<repo>/.sange/audit/*.jsonl` tree.

    Walks shards in ISO-week ascending order, threading each
    shard's final `this_hash` as the seed for the next shard's
    verification. Returns a single `VerificationReport` summarizing
    every record.

    Empty audit dir → `verified=True` (vacuous), `records_checked=0`.
    """

    audit_dir = Path(repo_root).resolve() / ".sange" / "audit"
    if not audit_dir.is_dir():
        return VerificationReport(verified=True, records_checked=0)

    shards = sorted(audit_dir.glob("*.jsonl"))
    if not shards:
        return VerificationReport(verified=True, records_checked=0)

    total = 0
    prev_hash = ""
    last_seen_hash = ""
    for shard in shards:
        report = verify_chain(shard, starting_prev_hash=prev_hash)
        total += report.records_checked
        if not report.verified:
            return VerificationReport(
                verified=False,
                records_checked=total,
                shards_checked=shards.index(shard) + 1,
                failure_kind=report.failure_kind,
                failure_shard=report.failure_shard,
                failure_index=report.failure_index,
                failure_event_id=report.failure_event_id,
                failure_message=report.failure_message,
                shard_paths=tuple(str(s) for s in shards[: shards.index(shard) + 1]),
            )
        # The verified shard's tail-hash threads into the next shard.
        # We need to re-read the last record to learn it (verify_chain
        # doesn't expose the tail hash); easier to just read it here.
        last_seen_hash = _read_tail_hash(shard) or last_seen_hash
        prev_hash = last_seen_hash

    return VerificationReport(
        verified=True,
        records_checked=total,
        shards_checked=len(shards),
        shard_paths=tuple(str(s) for s in shards),
    )


def _read_tail_hash(shard: Path) -> str:
    """Return the last record's `this_hash` in `shard`, or "" on failure."""

    last_line = ""
    try:
        with shard.open("r", encoding="utf-8") as fp:
            for line in fp:
                stripped = line.strip()
                if stripped:
                    last_line = stripped
    except OSError:
        return ""
    if not last_line:
        return ""
    try:
        return AuditEvent.from_json(last_line).this_hash
    except AuditEventError:
        return ""


__all__ = [
    "VerificationReport",
    "verify_chain",
    "verify_repo",
]
