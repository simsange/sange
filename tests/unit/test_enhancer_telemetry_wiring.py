"""Tests for the PromptEnhancer ↔ TelemetryCollector wiring.

Verifies that:
  * Successful enhance() calls record an AiCallEvent.
  * Failed enhance() calls record an ErrorEvent.
  * latency_ms is populated (non-zero in real timing).
  * `generate_commit_message()` passes the collector through.
  * Telemetry failures NEVER break the call path.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from sange.adapters.ai import (
    CompletionResponse,
    FinishReason,
    MockProvider,
    Usage,
)
from sange.core.enhancer import (
    EnhancerValidationError,
    PromptEnhancer,
    PromptTemplate,
    TemplateRegistry,
    build_commit_message_template,
)
from sange.core.enhancer.tasks.commit_message import (
    CommitMessageRequest,
    generate_commit_message,
)
from sange.core.telemetry import (
    CollectorPolicy,
    EventKind,
    TelemetryCollector,
)


def _registry() -> TemplateRegistry:
    return TemplateRegistry(
        [
            build_commit_message_template(),
            PromptTemplate(
                id="free-form",
                version="1.0",
                task="free-form",
                user_template="Echo {text}",
                required_vars=("text",),
            ),
        ]
    )


def _valid_json_mock() -> MockProvider:
    class _M(MockProvider):
        def complete(self, request):  # type: ignore[override]
            return CompletionResponse(
                text=json.dumps(
                    {
                        "type": "feat",
                        "scope": "auth",
                        "subject": "add login",
                        "body": "",
                        "breaking_change": False,
                    }
                ),
                finish_reason=FinishReason.STOP,
                usage=Usage(
                    tokens_in=20, tokens_out=10, cost_estimate_usd=0.001, model=request.model
                ),
                provider="mock",
                model=request.model,
            )

    return _M()


# --------------------------------------------------------------------------- #
# Successful enhance() auto-records
# --------------------------------------------------------------------------- #


class TestSuccessfulRecord:
    def test_records_ai_call_event(self, tmp_path: Path) -> None:
        collector = TelemetryCollector(CollectorPolicy(log_dir=tmp_path))
        e = PromptEnhancer(
            templates=_registry(),
            providers={"mock": _valid_json_mock()},
            collector=collector,
        )
        result = generate_commit_message(
            CommitMessageRequest(diff="+ change"), enhancer=e
        )
        assert result.type == "feat"

        rows = collector.read_all(kinds=(EventKind.AI_CALL,))
        assert len(rows) == 1
        row = rows[0]
        assert row["provider"] == "mock"
        assert row["template_id"] == "commit-message"
        assert row["tokens_in"] == 20
        assert row["tokens_out"] == 10
        assert row["cost_usd"] == 0.001
        assert row["retries"] == 0

    def test_records_latency(self, tmp_path: Path) -> None:
        collector = TelemetryCollector(CollectorPolicy(log_dir=tmp_path))
        e = PromptEnhancer(
            templates=_registry(),
            providers={"mock": _valid_json_mock()},
            collector=collector,
        )
        generate_commit_message(
            CommitMessageRequest(diff="+ change"), enhancer=e
        )
        row = collector.read_all(kinds=(EventKind.AI_CALL,))[0]
        # latency_ms is wall-clock — must be a non-negative integer.
        assert isinstance(row["latency_ms"], int)
        assert row["latency_ms"] >= 0

    def test_records_redaction_labels(self, tmp_path: Path) -> None:
        """Redaction labels propagate from AuditRecord → event."""

        collector = TelemetryCollector(CollectorPolicy(log_dir=tmp_path))
        e = PromptEnhancer(
            templates=_registry(),
            providers={"mock": _valid_json_mock()},
            collector=collector,
        )
        secret_diff = "+ AKIAIOSFODNN7EXAMPLE = \"aws\"\n"
        generate_commit_message(
            CommitMessageRequest(diff=secret_diff), enhancer=e
        )
        row = collector.read_all(kinds=(EventKind.AI_CALL,))[0]
        assert "aws-access-key" in row["redaction_labels"]
        assert row["redaction_count"] >= 1


# --------------------------------------------------------------------------- #
# Failed enhance() records ErrorEvent
# --------------------------------------------------------------------------- #


class TestFailureRecord:
    def test_validation_failure_records_error(self, tmp_path: Path) -> None:
        # Default MockProvider returns echo text → fails JSON validation.
        collector = TelemetryCollector(CollectorPolicy(log_dir=tmp_path))
        e = PromptEnhancer(
            templates=_registry(),
            collector=collector,
            max_retries=1,
        )
        with pytest.raises(EnhancerValidationError):
            generate_commit_message(
                CommitMessageRequest(diff="+ change"), enhancer=e
            )

        errors = collector.read_all(kinds=(EventKind.ERROR,))
        assert len(errors) == 1
        err = errors[0]
        assert err["error_type"] == "EnhancerValidationError"
        assert err["command_path"] == "enhance.commit-message"


# --------------------------------------------------------------------------- #
# No-collector path
# --------------------------------------------------------------------------- #


class TestNoCollector:
    def test_no_collector_no_recording(self) -> None:
        # PromptEnhancer with collector=None must not crash.
        e = PromptEnhancer(
            templates=_registry(),
            providers={"mock": _valid_json_mock()},
        )
        result = generate_commit_message(
            CommitMessageRequest(diff="+ change"), enhancer=e
        )
        assert result.type == "feat"

    def test_disabled_collector_doesnt_write(self, tmp_path: Path) -> None:
        collector = TelemetryCollector(
            CollectorPolicy(enabled=False, log_dir=tmp_path)
        )
        e = PromptEnhancer(
            templates=_registry(),
            providers={"mock": _valid_json_mock()},
            collector=collector,
        )
        generate_commit_message(
            CommitMessageRequest(diff="+ change"), enhancer=e
        )
        # No NDJSON files written.
        assert list(tmp_path.glob("*.ndjson")) == []


# --------------------------------------------------------------------------- #
# Telemetry failure must not break the call path
# --------------------------------------------------------------------------- #


class TestTelemetryIsolation:
    def test_collector_record_failure_swallowed(self, tmp_path: Path) -> None:
        """A buggy collector must not propagate exceptions to the
        caller. Telemetry is fire-and-forget."""

        class _BrokenCollector:
            def record(self, _event):
                raise RuntimeError("disk full")

            @staticmethod
            def from_audit(audit, *, latency_ms=0):
                # Real method — must work so the bug surfaces only at
                # record() time.
                return TelemetryCollector.from_audit(audit, latency_ms=latency_ms)

        broken = _BrokenCollector()
        e = PromptEnhancer(
            templates=_registry(),
            providers={"mock": _valid_json_mock()},
            collector=broken,  # type: ignore[arg-type]
        )
        # Must NOT raise.
        result = generate_commit_message(
            CommitMessageRequest(diff="+ change"), enhancer=e
        )
        assert result.type == "feat"


# --------------------------------------------------------------------------- #
# generate_commit_message() — collector pass-through when no enhancer
# --------------------------------------------------------------------------- #


class TestGenerateCommitMessageCollector:
    def test_collector_passed_to_auto_built_enhancer(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from sange.adapters.ai import _protocol
        from sange.core.enhancer import enhancer as enhancer_mod

        mock = _valid_json_mock()

        def _patched(name: str, **kwargs):
            return mock if name == "mock" else _protocol.get_provider(name, **kwargs)

        monkeypatch.setattr(_protocol, "get_provider", _patched)
        monkeypatch.setattr(enhancer_mod, "get_provider", _patched)

        collector = TelemetryCollector(CollectorPolicy(log_dir=tmp_path))
        # No enhancer arg → auto-built enhancer must still record.
        result = generate_commit_message(
            CommitMessageRequest(diff="+ change"), collector=collector
        )
        assert result.type == "feat"
        rows = collector.read_all(kinds=(EventKind.AI_CALL,))
        assert len(rows) == 1
