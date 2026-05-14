"""Local-only telemetry subsystem — §12.1.

Per §12.1 + ADR-008:

  * Nothing leaves the machine in v0.1. External send (§12.2) is a
    v2+ feature; the on-disk format is forward-compatible.
  * Storage is `.sange/telemetry/` (per-repo) and `~/.sange/telemetry/`
    (global), as NDJSON with weekly rotation by ISO week.
  * Sensitive fields (repo path, branch name, file names, error
    messages) are hashed before storage by default. Opt-out via
    `CollectorPolicy.hash_sensitive_fields=False`.

Public surface:

  * `TelemetryCollector` — append + read API.
  * `CollectorPolicy`    — enabled / log_dir / hash_sensitive_fields.
  * `AiCallEvent`        — built from a `PromptEnhancer` AuditRecord.
  * `CommandEvent`       — a CLI invocation.
  * `ErrorEvent`         — a surfaced error.
  * `EventKind`          — discriminator enum.
"""

from __future__ import annotations

from sange.core.telemetry.collector import (
    CollectorPolicy,
    TelemetryCollector,
)
from sange.core.telemetry.events import (
    AiCallEvent,
    CommandEvent,
    ErrorEvent,
    EventKind,
    SCHEMA_VERSION,
)

__all__ = [
    "AiCallEvent",
    "CollectorPolicy",
    "CommandEvent",
    "ErrorEvent",
    "EventKind",
    "SCHEMA_VERSION",
    "TelemetryCollector",
]
