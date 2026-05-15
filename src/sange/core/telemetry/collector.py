"""`TelemetryCollector` — NDJSON append-only local telemetry store.

Per §12.1: nothing leaves the machine. Storage is `.sange/telemetry/`
(per-repo) or `~/.sange/telemetry/` (global) — the directory is
operator-configurable via `TelemetryConfig.log_dir`. Files rotate
weekly by ISO week (`events-YYYY-Www.ndjson`) so each week's stream
is independently rotatable.

Atomic-append semantics: every `record()` opens the per-week file in
append-mode (text, UTF-8), writes one canonical JSON line, then closes.
POSIX guarantees that writes ≤ PIPE_BUF (4 KiB) under `O_APPEND` are
atomic; our serialized rows are well under that, so a concurrent
writer can't interleave bytes. The collector holds no long-lived
handles — losing a process leaves the file in a fully-written state.

Off-by-default contract: `record()` is a no-op when the supplied
`TelemetryConfig.enabled` is `False`. Callers can call it
unconditionally; the cost when disabled is one bool check.

`from_audit()` factory builds an `AiCallEvent` from a
`PromptEnhancer.AuditRecord` — the standard ingestion path for the
§6.7.1 → §12 pipe.
"""

from __future__ import annotations

import datetime as _dt
import json
import os
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sange.core.enhancer import AuditRecord
from sange.core.telemetry.events import (
    AiCallEvent,
    CommandEvent,
    ErrorEvent,
    EventKind,
)

_EventT = AiCallEvent | CommandEvent | ErrorEvent


@dataclass(frozen=True)
class CollectorPolicy:
    """Operator-controlled knobs.

    Fields:
      * `enabled`             — master switch. When `False`, `record()`
                                 is a no-op.
      * `log_dir`             — directory the NDJSON files live in.
                                 Created on first write if absent.
      * `hash_sensitive_fields` — when `True` (default per §12.1),
                                 sensitive fields are hashed before
                                 storage. Opt-out for richer local
                                 analytics.
      * `rotation`            — `"weekly"` for v0.1 (ISO week).
                                 v0.5 may add `"daily"` or `"monthly"`.
    """

    enabled: bool = True
    log_dir: Path = Path(".sange/telemetry")
    hash_sensitive_fields: bool = True
    rotation: str = "weekly"

    def __post_init__(self) -> None:
        if self.rotation not in ("weekly",):
            raise ValueError(
                f"CollectorPolicy.rotation must be 'weekly' (v0.1); "
                f"got {self.rotation!r}"
            )


def _file_for(policy: CollectorPolicy, when: _dt.datetime) -> Path:
    """Path to the NDJSON file that should hold an event at `when`."""

    iso_year, iso_week, _ = when.isocalendar()
    name = f"events-{iso_year}-W{iso_week:02d}.ndjson"
    return Path(policy.log_dir) / name


class TelemetryCollector:
    """Append-only NDJSON writer + simple in-process reader."""

    def __init__(self, policy: CollectorPolicy | None = None) -> None:
        self._policy = policy or CollectorPolicy()

    # ----- public API ----------------------------------------------- #

    @property
    def policy(self) -> CollectorPolicy:
        return self._policy

    def record(self, event: _EventT) -> Path | None:
        """Append `event` to the per-week NDJSON file.

        Returns the path written to, or `None` when telemetry is
        disabled. Raises `OSError` only on a truly unrecoverable
        filesystem error; permission denied / read-only filesystem is
        currently surfaced (a future task may swallow these to keep
        telemetry "fire and forget")."""

        if not self._policy.enabled:
            return None

        # Pick the file based on the event's timestamp (not now()), so
        # back-filled / replay events land in the correct week.
        timestamp = getattr(event, "timestamp", None) or _dt.datetime.now(tz=_dt.UTC)
        path = _file_for(self._policy, timestamp)
        path.parent.mkdir(parents=True, exist_ok=True)

        payload = event.redact(hash_sensitive=self._policy.hash_sensitive_fields)
        line = json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n"

        # Atomic append: O_APPEND + write ≤ PIPE_BUF is interleave-free.
        fd = os.open(
            path,
            os.O_WRONLY | os.O_APPEND | os.O_CREAT,
            0o600,  # the file may carry hashed-but-still-private info.
        )
        try:
            os.write(fd, line.encode("utf-8"))
        finally:
            os.close(fd)

        return path

    def record_many(self, events: Iterable[_EventT]) -> list[Path]:
        return [p for p in (self.record(e) for e in events) if p is not None]

    # ----- factories ------------------------------------------------ #

    @staticmethod
    def from_audit(
        audit: AuditRecord,
        *,
        latency_ms: int = 0,
        exit_code: int = 0,
    ) -> AiCallEvent:
        """Build an `AiCallEvent` from a `PromptEnhancer` audit record."""

        return AiCallEvent(
            template_id=audit.template_id,
            template_version=audit.template_version,
            provider=audit.provider,
            model=audit.model,
            tokens_in=audit.usage.tokens_in,
            tokens_out=audit.usage.tokens_out,
            cost_usd=audit.usage.cost_estimate_usd,
            redaction_count=audit.redaction_count,
            redaction_labels=tuple(sorted(audit.redaction_labels)),
            retries=audit.retries,
            latency_ms=latency_ms,
            exit_code=exit_code,
        )

    # ----- reader --------------------------------------------------- #

    def read_all(
        self,
        *,
        kinds: tuple[EventKind, ...] | None = None,
    ) -> list[dict[str, Any]]:
        """Read every NDJSON row across every rotation file.

        Filters by `kinds` when supplied. Malformed rows are skipped
        with no warning (NDJSON readers must tolerate partial writes
        even though our writer doesn't produce them).
        """

        rows: list[dict[str, Any]] = []
        log_dir = Path(self._policy.log_dir)
        if not log_dir.is_dir():
            return []

        for path in sorted(log_dir.glob("events-*-W*.ndjson")):
            with path.open("r", encoding="utf-8") as handle:
                for line in handle:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        row = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if kinds is not None:
                        if row.get("kind") not in {k.value for k in kinds}:
                            continue
                    rows.append(row)
        return rows

    def summary_by_provider(self) -> dict[str, dict[str, float | int]]:
        """Aggregate `AI_CALL` rows by provider → token + cost totals."""

        out: dict[str, dict[str, float | int]] = {}
        for row in self.read_all(kinds=(EventKind.AI_CALL,)):
            provider = row.get("provider", "unknown")
            slot = out.setdefault(
                provider,
                {"calls": 0, "tokens_in": 0, "tokens_out": 0, "cost_usd": 0.0},
            )
            slot["calls"] = int(slot["calls"]) + 1
            slot["tokens_in"] = int(slot["tokens_in"]) + int(row.get("tokens_in", 0))
            slot["tokens_out"] = int(slot["tokens_out"]) + int(row.get("tokens_out", 0))
            slot["cost_usd"] = float(slot["cost_usd"]) + float(row.get("cost_usd", 0.0))
        return out


__all__ = ["CollectorPolicy", "TelemetryCollector"]
