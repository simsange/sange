"""`sange.core.audit` — hash-chained audit JSONL (T-108).

Public surface:

  * `AuditEvent`           — one chain record.
  * `EventKind`            — recordable event types enum.
  * `make_event()`         — build a record with its `this_hash` populated.
  * `compute_hash()`       — recompute a record's hash (verifier-internal).
  * `AuditChain`           — append-only per-repo writer.
  * `verify_chain()` / `verify_repo()` — chain integrity check.
  * `VerificationReport`   — verifier outcome.

Per §7.0.7: every state-changing operation appends a record; the
chain is tamper-evident via sha256 hash linking; verification
walks the chain and surfaces the first break.

Distinct from `sange.core.enhancer.AuditRecord` — that's
single-AI-call provenance fed into an `EventKind.AI_CALL` payload.
"""

from __future__ import annotations

from sange.core.audit.chain import AuditChain, AuditChainError
from sange.core.audit.event import (
    AuditEvent,
    AuditEventError,
    EventKind,
    compute_hash,
    make_event,
)
from sange.core.audit.verify import (
    VerificationReport,
    verify_chain,
    verify_repo,
)

__all__ = [
    "AuditChain",
    "AuditChainError",
    "AuditEvent",
    "AuditEventError",
    "EventKind",
    "VerificationReport",
    "compute_hash",
    "make_event",
    "verify_chain",
    "verify_repo",
]
