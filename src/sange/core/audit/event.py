"""`AuditEvent` — one entry in the hash-chained audit log (§7.0.7).

The audit chain is the project's tamper-evident surface. Every
state-changing operation in Sange appends an `AuditEvent` to the
per-repo log at `<repo>/.sange/audit/<YYYY>-W<NN>.jsonl`. Each
record carries a sha256 hash of (its content + the previous
record's hash) so rewriting any line invalidates every later one.

This module owns the data model + the hash function only. The
writer lives in `chain.py`; the verifier in `verify.py`.

Distinct from `sange.core.enhancer.AuditRecord` — that's
single-AI-call provenance fed into one event's payload, not a
chain entry on its own.
"""

from __future__ import annotations

import datetime as _dt
import enum
import hashlib
import json
import uuid
from dataclasses import dataclass, field
from typing import Any


class AuditEventError(Exception):
    """Raised when an AuditEvent payload or hash chain is malformed."""


class EventKind(str, enum.Enum):
    """Recordable event types.

    Append new kinds at the bottom of the enum. Removing a kind is
    a breaking change — the chain's historical records may
    reference the old kind, and the verifier walks every record
    regardless of whether the kind still exists.
    """

    AI_CALL = "ai-call"                       # PromptEnhancer round-trip
    COMMIT_DRAFT = "commit-draft"             # new draft saved
    COMMIT_SUBMIT = "commit-submit"           # DRAFT → PENDING_REVIEW
    COMMIT_APPROVE = "commit-approve"         # PENDING_REVIEW → APPROVED
    COMMIT_REJECT = "commit-reject"           # PENDING_REVIEW → REJECTED
    COMMIT_REOPEN = "commit-reopen"           # any → DRAFT
    COMMIT_COMMIT = "commit-commit"           # APPROVED → COMMITTED
    COMMIT_PUSH = "commit-push"               # COMMITTED → PUSHED
    GITIGNORE_SWAP = "gitignore-swap"         # T-101 swap
    HOOK_RUN = "hook-run"                     # T-102 engine event-aggregate
    GATE_ADD = "gate-add"                     # T-103 gate installed
    GATE_REMOVE = "gate-remove"               # T-103 gate removed
    PURGE_PLAN = "purge-plan"                 # T-111 (v0.5 read-only)
    PURGE_EXECUTE = "purge-execute"           # T-203 (v1.0)
    GENERIC = "generic"                       # plugin / manual / fallback

    @classmethod
    def all_values(cls) -> tuple[str, ...]:
        return tuple(k.value for k in cls)


def _utcnow_iso() -> str:
    """ISO 8601 UTC timestamp at second precision (deterministic for tests)."""

    return _dt.datetime.now(tz=_dt.UTC).replace(microsecond=0).isoformat()


@dataclass(frozen=True)
class AuditEvent:
    """One entry in the audit chain.

    Fields:
      * `id`         — UUID4 string.
      * `kind`       — `EventKind` value (stored as string for JSON-ability).
      * `timestamp`  — ISO 8601 UTC second-precision.
      * `actor`      — username / role / surface ("alice@cli", "ci/main", …).
      * `payload`    — kind-specific JSON-serializable dict.
      * `prev_hash`  — sha256 hex of the previous record's `this_hash`,
                       or "" for the first record in the chain.
      * `this_hash`  — sha256 hex of this record's deterministic
                       serialization (id|kind|timestamp|actor|payload|prev_hash).
                       Populated by `compute_hash()`; verified by
                       `verify_chain()`.

    Construction is via `make_event()` for new records (auto-fills id +
    timestamp + this_hash). The constructor is exposed for loaders +
    the verifier reading existing records from disk.
    """

    id: str
    kind: str
    timestamp: str
    actor: str
    payload: dict[str, Any] = field(default_factory=dict)
    prev_hash: str = ""
    this_hash: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Dict shape used for JSONL serialization."""

        return {
            "id": self.id,
            "kind": self.kind,
            "timestamp": self.timestamp,
            "actor": self.actor,
            "payload": self.payload,
            "prev_hash": self.prev_hash,
            "this_hash": self.this_hash,
        }

    def to_json(self) -> str:
        """One-line JSON for the JSONL file."""

        return json.dumps(
            self.to_dict(),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AuditEvent:
        for required in ("id", "kind", "timestamp", "actor"):
            if required not in data:
                raise AuditEventError(f"missing required field {required!r}")
        return cls(
            id=str(data["id"]),
            kind=str(data["kind"]),
            timestamp=str(data["timestamp"]),
            actor=str(data["actor"]),
            payload=dict(data.get("payload") or {}),
            prev_hash=str(data.get("prev_hash", "") or ""),
            this_hash=str(data.get("this_hash", "") or ""),
        )

    @classmethod
    def from_json(cls, line: str) -> AuditEvent:
        try:
            data = json.loads(line)
        except json.JSONDecodeError as exc:
            raise AuditEventError(f"invalid JSON: {exc}") from exc
        if not isinstance(data, dict):
            raise AuditEventError("expected JSON object, got " + type(data).__name__)
        return cls.from_dict(data)


# --------------------------------------------------------------------------- #
# Hash function
# --------------------------------------------------------------------------- #


def compute_hash(event: AuditEvent) -> str:
    """Return sha256 hex of an event's content (excluding `this_hash`).

    The hashing payload is the JSON serialization of the event with
    `this_hash` field stripped — sort-keys, no-whitespace, UTF-8.
    Deterministic given the same input.

    Two events that differ only in `this_hash` produce identical
    inputs to this function (that's the whole point — `this_hash`
    is an output, not an input).
    """

    body = {
        "id": event.id,
        "kind": event.kind,
        "timestamp": event.timestamp,
        "actor": event.actor,
        "payload": event.payload,
        "prev_hash": event.prev_hash,
    }
    text = json.dumps(
        body,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def make_event(
    kind: EventKind | str,
    *,
    actor: str,
    payload: dict[str, Any] | None = None,
    prev_hash: str = "",
    timestamp: str | None = None,
    event_id: str | None = None,
) -> AuditEvent:
    """Build a fresh `AuditEvent` with its `this_hash` populated.

    Args:
      kind:       `EventKind` or any string (plugins can ship custom
                  kinds; the verifier doesn't care, only the operator
                  filtering does).
      actor:      identifier for the actor responsible. Required.
      payload:    kind-specific dict; serialized as-is into the JSON.
                  Must be JSON-serializable (no datetimes, no Paths
                  — coerce to strings before passing).
      prev_hash:  the previous record's `this_hash`, or "" for the
                  first record in a chain.
      timestamp:  override the default `now(UTC)` (useful for tests).
      event_id:   override the default UUID4 (useful for tests).
    """

    if not actor:
        raise AuditEventError("AuditEvent.actor must be non-empty")
    kind_str = kind.value if isinstance(kind, EventKind) else str(kind)
    if not kind_str:
        raise AuditEventError("AuditEvent.kind must be non-empty")

    skeleton = AuditEvent(
        id=event_id or str(uuid.uuid4()),
        kind=kind_str,
        timestamp=timestamp or _utcnow_iso(),
        actor=actor,
        payload=dict(payload or {}),
        prev_hash=prev_hash,
        this_hash="",
    )
    digest = compute_hash(skeleton)
    return AuditEvent(
        id=skeleton.id,
        kind=skeleton.kind,
        timestamp=skeleton.timestamp,
        actor=skeleton.actor,
        payload=skeleton.payload,
        prev_hash=skeleton.prev_hash,
        this_hash=digest,
    )


__all__ = [
    "AuditEvent",
    "AuditEventError",
    "EventKind",
    "compute_hash",
    "make_event",
]
