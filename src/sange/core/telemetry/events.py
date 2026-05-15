"""Event dataclasses — the things the collector writes to NDJSON.

Per §12.1: local-only telemetry from v1 covers operation counts,
latencies, error rates, AI cost trends, and feature usage. Each event
type lives in its own dataclass with a frozen / declarative shape so
serialization is just `asdict()`.

Event types:

  * `AiCallEvent`   — one AI provider invocation. Built from the
                       `AuditRecord` that `PromptEnhancer.enhance()`
                       emits. Carries provider/model/template,
                       token+cost accounting, redaction metrics, and
                       retry count.
  * `CommandEvent`  — one CLI command invocation. Records the command
                       path, latency, exit code, whether the user
                       supplied flags that mark special modes (--json,
                       --provider, etc.).
  * `ErrorEvent`    — an unhandled / surfaced error. The error
                       message itself is recorded BUT hashed when
                       hashing is enabled (so reading a telemetry
                       feed can't leak repo content embedded in
                       exception strings).

Per §12.1 sensitive fields (repo paths, branch names, commit
messages, file names) are **hashed before storage** by default. The
hashing is done at the collector layer via a per-event `redact()`
hook each event type implements; the raw event passed to
`TelemetryCollector.record()` is what the caller has — sensitive or
not — and the collector takes responsibility for normalizing it.

Schema versioning is explicit (`schema_version` field). v1 events
are forward-compatible: the reader skips unknown fields and tolerates
new event kinds appearing in the feed.
"""

from __future__ import annotations

import datetime as _dt
import enum
import hashlib
from dataclasses import asdict, dataclass, field
from typing import Any

SCHEMA_VERSION = 1


class EventKind(str, enum.Enum):
    AI_CALL = "ai_call"
    COMMAND = "command"
    ERROR = "error"


# --------------------------------------------------------------------------- #
# Shared helpers
# --------------------------------------------------------------------------- #


def _utcnow() -> _dt.datetime:
    return _dt.datetime.now(tz=_dt.UTC)


def _hash(text: str) -> str:
    """Stable SHA-256 of the input string, truncated to 16 hex chars.

    Truncation keeps NDJSON rows compact; 64-bit collision resistance
    is plenty for telemetry-feed bucketing."""

    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _redact_path(path: str) -> str:
    """Hash a repo path while keeping the basename for human readability."""

    if not path:
        return ""
    parts = path.replace("\\", "/").rsplit("/", 1)
    basename = parts[-1] if parts else ""
    return f"{_hash(path)}:{basename}" if basename else _hash(path)


def _redact_name(name: str) -> str:
    """Hash a branch / file name to a 16-char digest."""

    return _hash(name) if name else ""


# --------------------------------------------------------------------------- #
# AI call event
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class AiCallEvent:
    """One AI provider invocation.

    Built from a `PromptEnhancer` `AuditRecord`. Mirrors the
    audit-record fields plus a timestamp + latency. Cost tracking is
    rolled up across the per-week NDJSON file for the trend view.
    """

    kind: EventKind = field(default=EventKind.AI_CALL, init=False)
    schema_version: int = field(default=SCHEMA_VERSION, init=False)
    timestamp: _dt.datetime = field(default_factory=_utcnow)
    template_id: str = ""
    template_version: str = ""
    provider: str = ""
    model: str = ""
    tokens_in: int = 0
    tokens_out: int = 0
    cost_usd: float = 0.0
    redaction_count: int = 0
    redaction_labels: tuple[str, ...] = ()
    retries: int = 0
    latency_ms: int = 0
    exit_code: int = 0

    def redact(self, *, hash_sensitive: bool) -> dict[str, Any]:
        # Template / provider / model are non-sensitive identifiers.
        # Only the redaction_labels list could leak which kinds of
        # secrets were present in the diff; we keep that as-is because
        # the label set is finite + known. The other fields are pure
        # counters / opaque ids.
        return _serialize(self)


# --------------------------------------------------------------------------- #
# Command event
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class CommandEvent:
    """One CLI command invocation.

    `command_path` is the dotted invocation (`sange.commit`,
    `sange.ai.preview`). `repo_ref` is the repo identifier — the
    collector hashes the actual path before writing.
    """

    kind: EventKind = field(default=EventKind.COMMAND, init=False)
    schema_version: int = field(default=SCHEMA_VERSION, init=False)
    timestamp: _dt.datetime = field(default_factory=_utcnow)
    command_path: str = ""
    exit_code: int = 0
    latency_ms: int = 0
    repo_ref: str = ""
    branch_ref: str = ""
    flags: tuple[str, ...] = ()  # the --foo flag names the user passed (no values).

    def redact(self, *, hash_sensitive: bool) -> dict[str, Any]:
        payload = _serialize(self)
        if hash_sensitive:
            payload["repo_ref"] = _redact_path(self.repo_ref) if self.repo_ref else ""
            payload["branch_ref"] = _redact_name(self.branch_ref) if self.branch_ref else ""
        return payload


# --------------------------------------------------------------------------- #
# Error event
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class ErrorEvent:
    """A surfaced error.

    `error_type` is the exception class name (always safe to log).
    `error_message` may carry repo content (file paths in tracebacks)
    so the collector hashes it when hashing is enabled.
    """

    kind: EventKind = field(default=EventKind.ERROR, init=False)
    schema_version: int = field(default=SCHEMA_VERSION, init=False)
    timestamp: _dt.datetime = field(default_factory=_utcnow)
    command_path: str = ""
    error_type: str = ""
    error_message: str = ""
    repo_ref: str = ""

    def redact(self, *, hash_sensitive: bool) -> dict[str, Any]:
        payload = _serialize(self)
        if hash_sensitive:
            payload["error_message"] = _redact_name(self.error_message)
            payload["repo_ref"] = _redact_path(self.repo_ref) if self.repo_ref else ""
        return payload


# --------------------------------------------------------------------------- #
# Serialization helper
# --------------------------------------------------------------------------- #


def _serialize(event: Any) -> dict[str, Any]:
    """`asdict()` + ISO-8601 timestamps + EventKind values."""

    payload = asdict(event)
    if isinstance(payload.get("timestamp"), _dt.datetime):
        payload["timestamp"] = payload["timestamp"].isoformat()
    if isinstance(payload.get("kind"), EventKind):
        payload["kind"] = payload["kind"].value
    # Tuples become lists for JSON.
    for k, v in list(payload.items()):
        if isinstance(v, tuple):
            payload[k] = list(v)
    return payload


__all__ = [
    "SCHEMA_VERSION",
    "AiCallEvent",
    "CommandEvent",
    "ErrorEvent",
    "EventKind",
]
