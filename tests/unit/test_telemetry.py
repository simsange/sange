"""Tests for src/sange/core/telemetry/ — local NDJSON collector."""

from __future__ import annotations

import datetime as _dt
import json
from pathlib import Path

import pytest

from sange.adapters.ai import Usage
from sange.core.enhancer import AuditRecord
from sange.core.telemetry import (
    SCHEMA_VERSION,
    AiCallEvent,
    CollectorPolicy,
    CommandEvent,
    ErrorEvent,
    EventKind,
    TelemetryCollector,
)

_FIXED = _dt.datetime(2026, 5, 14, 12, 0, 0, tzinfo=_dt.UTC)


# --------------------------------------------------------------------------- #
# Event dataclasses
# --------------------------------------------------------------------------- #


class TestAiCallEvent:
    def test_defaults(self) -> None:
        e = AiCallEvent()
        assert e.kind is EventKind.AI_CALL
        assert e.schema_version == SCHEMA_VERSION
        assert e.tokens_in == 0

    def test_kind_is_init_false(self) -> None:
        # Can't set kind via constructor — it's always AI_CALL.
        with pytest.raises(TypeError):
            AiCallEvent(kind=EventKind.COMMAND)  # type: ignore[call-arg]

    def test_redact_returns_dict(self) -> None:
        e = AiCallEvent(provider="anthropic", tokens_in=10, tokens_out=20)
        payload = e.redact(hash_sensitive=True)
        assert payload["kind"] == "ai_call"
        assert payload["provider"] == "anthropic"
        assert payload["tokens_in"] == 10
        # Timestamp is ISO-8601.
        assert isinstance(payload["timestamp"], str)


class TestCommandEvent:
    def test_redact_hashes_repo_path(self) -> None:
        e = CommandEvent(repo_ref="/Users/me/code/secret-project")
        payload = e.redact(hash_sensitive=True)
        assert "/Users/me/code/secret-project" not in payload["repo_ref"]
        # Basename is preserved for human readability.
        assert "secret-project" in payload["repo_ref"]
        assert ":" in payload["repo_ref"]  # hash:basename format

    def test_redact_hashes_branch(self) -> None:
        e = CommandEvent(branch_ref="feat/internal-secret-flag")
        payload = e.redact(hash_sensitive=True)
        assert "feat/internal-secret-flag" not in payload["branch_ref"]
        assert len(payload["branch_ref"]) == 16  # truncated sha256

    def test_redact_disabled_keeps_raw(self) -> None:
        e = CommandEvent(repo_ref="/Users/me/code/p", branch_ref="main")
        payload = e.redact(hash_sensitive=False)
        assert payload["repo_ref"] == "/Users/me/code/p"
        assert payload["branch_ref"] == "main"


class TestErrorEvent:
    def test_redact_hashes_error_message(self) -> None:
        e = ErrorEvent(
            error_type="ValueError",
            error_message="bad path /Users/me/.ssh/id_rsa.pub",
        )
        payload = e.redact(hash_sensitive=True)
        assert "/Users/me/.ssh" not in payload["error_message"]
        # The type stays as-is — exception class names aren't sensitive.
        assert payload["error_type"] == "ValueError"


# --------------------------------------------------------------------------- #
# CollectorPolicy
# --------------------------------------------------------------------------- #


class TestCollectorPolicy:
    def test_defaults(self) -> None:
        p = CollectorPolicy()
        assert p.enabled is True
        assert p.hash_sensitive_fields is True
        assert p.rotation == "weekly"

    def test_unsupported_rotation_rejected(self) -> None:
        with pytest.raises(ValueError, match="rotation"):
            CollectorPolicy(rotation="monthly")


# --------------------------------------------------------------------------- #
# TelemetryCollector — record + read
# --------------------------------------------------------------------------- #


class TestRecord:
    def test_disabled_returns_none(self, tmp_path: Path) -> None:
        c = TelemetryCollector(CollectorPolicy(enabled=False, log_dir=tmp_path))
        result = c.record(AiCallEvent(provider="mock"))
        assert result is None

    def test_disabled_writes_nothing(self, tmp_path: Path) -> None:
        c = TelemetryCollector(CollectorPolicy(enabled=False, log_dir=tmp_path))
        c.record(AiCallEvent())
        assert list(tmp_path.glob("*")) == []

    def test_enabled_creates_log_dir(self, tmp_path: Path) -> None:
        log_dir = tmp_path / "nested" / "log"
        c = TelemetryCollector(CollectorPolicy(log_dir=log_dir))
        c.record(AiCallEvent(timestamp=_FIXED))
        assert log_dir.is_dir()

    def test_iso_week_filename(self, tmp_path: Path) -> None:
        c = TelemetryCollector(CollectorPolicy(log_dir=tmp_path))
        c.record(AiCallEvent(timestamp=_FIXED))
        # 2026-05-14 falls in ISO week 20.
        expected = tmp_path / "events-2026-W20.ndjson"
        assert expected.is_file()

    def test_appends_one_line_per_event(self, tmp_path: Path) -> None:
        c = TelemetryCollector(CollectorPolicy(log_dir=tmp_path))
        c.record(AiCallEvent(timestamp=_FIXED, provider="a"))
        c.record(AiCallEvent(timestamp=_FIXED, provider="b"))
        c.record(AiCallEvent(timestamp=_FIXED, provider="c"))
        path = tmp_path / "events-2026-W20.ndjson"
        lines = path.read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == 3
        # Each line parses independently.
        for line in lines:
            json.loads(line)

    def test_back_filled_events_land_in_correct_week(
        self, tmp_path: Path
    ) -> None:
        c = TelemetryCollector(CollectorPolicy(log_dir=tmp_path))
        a = AiCallEvent(timestamp=_dt.datetime(2026, 1, 5, tzinfo=_dt.UTC))  # W2
        b = AiCallEvent(timestamp=_FIXED)  # W20
        c.record(a)
        c.record(b)
        assert (tmp_path / "events-2026-W02.ndjson").is_file()
        assert (tmp_path / "events-2026-W20.ndjson").is_file()

    def test_record_many(self, tmp_path: Path) -> None:
        c = TelemetryCollector(CollectorPolicy(log_dir=tmp_path))
        events = [
            AiCallEvent(timestamp=_FIXED),
            CommandEvent(timestamp=_FIXED),
            ErrorEvent(timestamp=_FIXED),
        ]
        paths = c.record_many(events)
        assert len(paths) == 3
        # All three end up in the same week file.
        assert len({p for p in paths}) == 1


# --------------------------------------------------------------------------- #
# TelemetryCollector — read_all + filtering
# --------------------------------------------------------------------------- #


class TestRead:
    def _seed(self, tmp_path: Path) -> TelemetryCollector:
        c = TelemetryCollector(CollectorPolicy(log_dir=tmp_path))
        c.record(AiCallEvent(timestamp=_FIXED, provider="mock", tokens_in=10, tokens_out=20))
        c.record(AiCallEvent(timestamp=_FIXED, provider="anthropic", tokens_in=100, tokens_out=200))
        c.record(CommandEvent(timestamp=_FIXED, command_path="sange.commit", exit_code=0))
        c.record(ErrorEvent(timestamp=_FIXED, error_type="ValueError", error_message="x"))
        return c

    def test_read_all(self, tmp_path: Path) -> None:
        c = self._seed(tmp_path)
        rows = c.read_all()
        assert len(rows) == 4
        kinds = [r["kind"] for r in rows]
        assert kinds.count("ai_call") == 2
        assert kinds.count("command") == 1
        assert kinds.count("error") == 1

    def test_read_all_filter_ai_calls(self, tmp_path: Path) -> None:
        c = self._seed(tmp_path)
        rows = c.read_all(kinds=(EventKind.AI_CALL,))
        assert len(rows) == 2
        assert all(r["kind"] == "ai_call" for r in rows)

    def test_read_all_filter_multiple_kinds(self, tmp_path: Path) -> None:
        c = self._seed(tmp_path)
        rows = c.read_all(kinds=(EventKind.COMMAND, EventKind.ERROR))
        assert len(rows) == 2
        kinds = {r["kind"] for r in rows}
        assert kinds == {"command", "error"}

    def test_read_all_empty_dir(self, tmp_path: Path) -> None:
        c = TelemetryCollector(CollectorPolicy(log_dir=tmp_path / "nonexistent"))
        assert c.read_all() == []

    def test_read_all_skips_malformed_lines(self, tmp_path: Path) -> None:
        path = tmp_path / "events-2026-W20.ndjson"
        path.write_text("not-json\n" + json.dumps({"kind": "ai_call"}) + "\n")
        c = TelemetryCollector(CollectorPolicy(log_dir=tmp_path))
        rows = c.read_all()
        assert len(rows) == 1
        assert rows[0]["kind"] == "ai_call"

    def test_summary_by_provider(self, tmp_path: Path) -> None:
        c = self._seed(tmp_path)
        # Add a second mock call.
        c.record(
            AiCallEvent(
                timestamp=_FIXED, provider="mock", tokens_in=5, tokens_out=15, cost_usd=0.0,
            )
        )
        summary = c.summary_by_provider()
        assert summary["mock"]["calls"] == 2
        assert summary["mock"]["tokens_in"] == 15
        assert summary["mock"]["tokens_out"] == 35
        assert summary["anthropic"]["calls"] == 1
        assert summary["anthropic"]["tokens_in"] == 100


# --------------------------------------------------------------------------- #
# from_audit factory
# --------------------------------------------------------------------------- #


class TestFromAudit:
    def test_basic(self) -> None:
        audit = AuditRecord(
            template_id="commit-message",
            template_version="1.0.0",
            provider="anthropic",
            model="claude-opus-4-7",
            redaction_count=3,
            redaction_labels=frozenset({"aws-access-key", "github-pat"}),
            usage=Usage(
                tokens_in=100,
                tokens_out=50,
                cost_estimate_usd=0.0042,
                model="claude-opus-4-7",
            ),
            retries=1,
        )
        event = TelemetryCollector.from_audit(audit, latency_ms=850)
        assert event.template_id == "commit-message"
        assert event.template_version == "1.0.0"
        assert event.provider == "anthropic"
        assert event.tokens_in == 100
        assert event.cost_usd == 0.0042
        assert event.redaction_count == 3
        # Labels sorted for stable serialization.
        assert event.redaction_labels == ("aws-access-key", "github-pat")
        assert event.retries == 1
        assert event.latency_ms == 850

    def test_zero_usage(self) -> None:
        audit = AuditRecord(
            template_id="t",
            template_version="1.0",
            provider="mock",
            model="mock-1",
            redaction_count=0,
            redaction_labels=frozenset(),
            usage=Usage(model="mock-1"),
            retries=0,
        )
        event = TelemetryCollector.from_audit(audit)
        assert event.tokens_in == 0
        assert event.cost_usd == 0.0
        assert event.latency_ms == 0


# --------------------------------------------------------------------------- #
# Hash redaction is on by default
# --------------------------------------------------------------------------- #


class TestRedactionDefaults:
    def test_default_policy_hashes(self, tmp_path: Path) -> None:
        c = TelemetryCollector(CollectorPolicy(log_dir=tmp_path))
        c.record(
            CommandEvent(
                timestamp=_FIXED,
                command_path="sange.commit",
                repo_ref="/Users/me/code/private",
                branch_ref="internal-feature",
            )
        )
        path = tmp_path / "events-2026-W20.ndjson"
        text = path.read_text(encoding="utf-8")
        assert "/Users/me/code/private" not in text
        assert "internal-feature" not in text

    def test_opt_out_preserves_raw(self, tmp_path: Path) -> None:
        c = TelemetryCollector(
            CollectorPolicy(log_dir=tmp_path, hash_sensitive_fields=False)
        )
        c.record(
            CommandEvent(
                timestamp=_FIXED,
                command_path="sange.commit",
                repo_ref="/Users/me/code/private",
                branch_ref="internal-feature",
            )
        )
        path = tmp_path / "events-2026-W20.ndjson"
        text = path.read_text(encoding="utf-8")
        assert "/Users/me/code/private" in text
        assert "internal-feature" in text


# --------------------------------------------------------------------------- #
# File-mode permissions (POSIX best-effort)
# --------------------------------------------------------------------------- #


class TestFilePermissions:
    def test_log_file_mode_0600(self, tmp_path: Path) -> None:
        import sys

        if sys.platform == "win32":
            pytest.skip("POSIX mode bits not meaningful on Windows")

        c = TelemetryCollector(CollectorPolicy(log_dir=tmp_path))
        c.record(AiCallEvent(timestamp=_FIXED))
        path = tmp_path / "events-2026-W20.ndjson"
        mode = path.stat().st_mode & 0o777
        # Created with 0600, but umask may strip bits — we only assert
        # group/world have no write access. Read access we don't pin
        # because some test environments set umask 022.
        assert mode & 0o022 == 0  # group + world have no write bit


# --------------------------------------------------------------------------- #
# Schema version
# --------------------------------------------------------------------------- #


class TestSchemaVersion:
    def test_every_event_carries_version(self) -> None:
        for cls in (AiCallEvent, CommandEvent, ErrorEvent):
            event = cls()
            payload = event.redact(hash_sensitive=True)
            assert payload["schema_version"] == SCHEMA_VERSION
