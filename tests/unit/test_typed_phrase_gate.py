"""Tests for `sange.utils.gate.typed_phrase_confirm` — §7.0.5."""

from __future__ import annotations

import datetime as _dt
from collections.abc import Iterable, Iterator

import pytest

from sange.utils import (
    GateError,
    GateResult,
    render_phrase,
    typed_phrase_confirm,
)


class _Inputs:
    """Pop canned answers off a queue. Raises StopIteration if exhausted."""

    def __init__(self, *items: str) -> None:
        self._iter: Iterator[str] = iter(items)

    def __call__(self, _prompt: str) -> str:
        return next(self._iter)


class _Clock:
    """Tick forward by `step` seconds on each call."""

    def __init__(self, *, step: float = 0.0, ticks: Iterable[float] | None = None) -> None:
        self._step = step
        self._fixed = list(ticks) if ticks else None
        self._t = 0.0
        self._calls = 0

    def __call__(self) -> float:
        if self._fixed is not None:
            value = self._fixed[min(self._calls, len(self._fixed) - 1)]
            self._calls += 1
            return value
        cur = self._t
        self._t += self._step
        return cur


def _captured_output() -> tuple[list[str], object]:
    """Collect output_fn calls into a list."""

    out: list[str] = []
    def emit(line: str) -> None:
        out.append(line)
    return out, emit


# --------------------------------------------------------------------------- #
# render_phrase
# --------------------------------------------------------------------------- #


class TestRenderPhrase:
    def test_canonical_format_with_nonce(self) -> None:
        phrase = render_phrase(
            "PURGE",
            clock=_dt.datetime(2026, 5, 18, tzinfo=_dt.UTC),
            nonce_fn=lambda: "deadbeef",
        )
        assert phrase == "PURGE_2026-05-18_deadbeef"

    def test_no_nonce_omits_nonce_segment(self) -> None:
        phrase = render_phrase(
            "PURGE",
            nonce=False,
            clock=_dt.datetime(2026, 5, 18, tzinfo=_dt.UTC),
        )
        assert phrase == "PURGE_2026-05-18"

    def test_action_uppercased(self) -> None:
        phrase = render_phrase(
            "purge",
            nonce=False,
            clock=_dt.datetime(2026, 5, 18, tzinfo=_dt.UTC),
        )
        assert phrase.startswith("PURGE_")

    def test_action_with_underscore(self) -> None:
        phrase = render_phrase(
            "purge_push",
            nonce=False,
            clock=_dt.datetime(2026, 5, 18, tzinfo=_dt.UTC),
        )
        assert phrase == "PURGE_PUSH_2026-05-18"

    def test_empty_action_rejected(self) -> None:
        with pytest.raises(GateError, match="non-empty"):
            render_phrase("")

    def test_whitespace_only_action_rejected(self) -> None:
        with pytest.raises(GateError, match="non-empty"):
            render_phrase("   ")

    def test_illegal_chars_rejected(self) -> None:
        with pytest.raises(GateError, match="illegal character"):
            render_phrase("purge!")
        with pytest.raises(GateError, match="illegal character"):
            render_phrase("purge push")  # space

    def test_default_nonce_is_8_hex(self) -> None:
        phrase = render_phrase(
            "PURGE",
            clock=_dt.datetime(2026, 5, 18, tzinfo=_dt.UTC),
        )
        # PURGE_2026-05-18_<8-hex>
        parts = phrase.rsplit("_", 1)
        assert len(parts[1]) == 8
        int(parts[1], 16)  # valid hex


# --------------------------------------------------------------------------- #
# typed_phrase_confirm — happy paths
# --------------------------------------------------------------------------- #


class TestTypedPhraseConfirmHappyPath:
    def test_correct_phrase_passes_first_try(self) -> None:
        expected = "PURGE_2026-05-18_deadbeef"
        _, emit = _captured_output()
        result = typed_phrase_confirm(
            "PURGE",
            timeout_s=30,
            input_fn=_Inputs(expected),
            output_fn=emit,
            clock_fn=_Clock(step=0.1),
            nonce_fn=lambda: "deadbeef",
            date_fn=lambda: _dt.datetime(2026, 5, 18, tzinfo=_dt.UTC),
        )
        assert result.passed is True
        assert result.outcome == "passed"
        assert result.attempts == 1
        assert result.via == "tty"
        assert result.phrase == expected

    def test_passes_on_second_try(self) -> None:
        expected = "PURGE_2026-05-18_deadbeef"
        _, emit = _captured_output()
        result = typed_phrase_confirm(
            "PURGE",
            timeout_s=30,
            input_fn=_Inputs("wrong typing", expected),
            output_fn=emit,
            clock_fn=_Clock(step=0.1),
            nonce_fn=lambda: "deadbeef",
            date_fn=lambda: _dt.datetime(2026, 5, 18, tzinfo=_dt.UTC),
        )
        assert result.passed is True
        assert result.attempts == 2


class TestTypedPhraseConfirmFailures:
    def test_max_attempts_exhausted_fails(self) -> None:
        _, emit = _captured_output()
        result = typed_phrase_confirm(
            "PURGE",
            timeout_s=30,
            max_attempts=3,
            input_fn=_Inputs("a", "b", "c"),
            output_fn=emit,
            clock_fn=_Clock(step=0.1),
            nonce_fn=lambda: "deadbeef",
            date_fn=lambda: _dt.datetime(2026, 5, 18, tzinfo=_dt.UTC),
        )
        assert result.passed is False
        assert result.outcome == "failed"
        assert result.attempts == 3

    def test_eof_on_input_fails_fast(self) -> None:
        def raising(_prompt: str) -> str:
            raise EOFError()

        _, emit = _captured_output()
        result = typed_phrase_confirm(
            "PURGE",
            timeout_s=30,
            input_fn=raising,
            output_fn=emit,
            clock_fn=_Clock(step=0.1),
            nonce_fn=lambda: "deadbeef",
            date_fn=lambda: _dt.datetime(2026, 5, 18, tzinfo=_dt.UTC),
        )
        assert result.passed is False
        assert result.outcome == "failed"
        assert result.attempts == 1


class TestTypedPhraseConfirmTimeout:
    def test_timeout_before_any_attempt(self) -> None:
        # Clock starts at 100s elapsed — immediate deadline hit.
        _, emit = _captured_output()
        result = typed_phrase_confirm(
            "PURGE",
            timeout_s=30,
            input_fn=_Inputs("anything"),
            output_fn=emit,
            clock_fn=_Clock(ticks=[0.0, 100.0, 100.0]),
            nonce_fn=lambda: "deadbeef",
            date_fn=lambda: _dt.datetime(2026, 5, 18, tzinfo=_dt.UTC),
        )
        assert result.passed is False
        assert result.outcome == "timed_out"
        # No attempts because the deadline check fires before input_fn.
        assert result.attempts == 0

    def test_timeout_between_attempts(self) -> None:
        # Clock ticks consumed in order:
        #   1: start_ns = 0.0
        #   2: pre-attempt-1 elapsed = 0.1 (not timed out)
        #   3: post-attempt-1 elapsed_s recorded = 0.5
        #   4: pre-attempt-2 elapsed = 70.0 (TIMED OUT — no second input)
        # So attempts == 1 (only one input call consumed).
        _, emit = _captured_output()
        result = typed_phrase_confirm(
            "PURGE",
            timeout_s=30,
            input_fn=_Inputs("wrong", "wrong-still"),
            output_fn=emit,
            clock_fn=_Clock(ticks=[0.0, 0.1, 70.0, 70.5]),
            nonce_fn=lambda: "deadbeef",
            date_fn=lambda: _dt.datetime(2026, 5, 18, tzinfo=_dt.UTC),
        )
        assert result.passed is False
        assert result.outcome == "timed_out"
        assert result.attempts == 1


class TestBatchMode:
    def test_batch_skips_prompt(self) -> None:
        # input_fn should never be called.
        def must_not_call(_prompt: str) -> str:
            raise AssertionError("input_fn called in batch mode")

        _, emit = _captured_output()
        result = typed_phrase_confirm(
            "PURGE",
            batch=True,
            input_fn=must_not_call,
            output_fn=emit,
            nonce_fn=lambda: "deadbeef",
            date_fn=lambda: _dt.datetime(2026, 5, 18, tzinfo=_dt.UTC),
        )
        assert result.passed is True
        assert result.outcome == "skipped"
        assert result.via == "batch"
        assert result.attempts == 0
        assert result.elapsed_s == 0.0

    def test_batch_still_renders_phrase(self) -> None:
        result = typed_phrase_confirm(
            "PUBLISH",
            batch=True,
            nonce_fn=lambda: "cafef00d",
            date_fn=lambda: _dt.datetime(2026, 5, 18, tzinfo=_dt.UTC),
        )
        # Phrase still produced (for audit payload), just not prompted.
        assert result.phrase == "PUBLISH_2026-05-18_cafef00d"


class TestValidation:
    def test_negative_timeout_rejected(self) -> None:
        with pytest.raises(GateError, match="positive"):
            typed_phrase_confirm("PURGE", timeout_s=-1)

    def test_zero_timeout_rejected(self) -> None:
        with pytest.raises(GateError, match="positive"):
            typed_phrase_confirm("PURGE", timeout_s=0)

    def test_timeout_above_max_rejected(self) -> None:
        with pytest.raises(GateError, match="max"):
            typed_phrase_confirm("PURGE", timeout_s=601)

    def test_zero_max_attempts_rejected(self) -> None:
        with pytest.raises(GateError, match="max_attempts"):
            typed_phrase_confirm("PURGE", timeout_s=30, max_attempts=0)


class TestAuditPayload:
    def test_passed_payload_shape(self) -> None:
        result = typed_phrase_confirm(
            "PURGE",
            timeout_s=30,
            input_fn=_Inputs("PURGE_2026-05-18_x"),
            output_fn=lambda _: None,
            clock_fn=_Clock(step=0.1),
            nonce_fn=lambda: "x",
            date_fn=lambda: _dt.datetime(2026, 5, 18, tzinfo=_dt.UTC),
        )
        payload = result.as_audit_payload()
        assert payload["gate_passed"] is True
        assert payload["gate_outcome"] == "passed"
        assert payload["attempts"] == 1
        assert payload["via"] == "tty"
        assert payload["phrase"] == "PURGE_2026-05-18_x"
        assert isinstance(payload["elapsed_s"], float)

    def test_failed_payload_shape(self) -> None:
        result = typed_phrase_confirm(
            "PURGE",
            timeout_s=30,
            max_attempts=2,
            input_fn=_Inputs("nope", "nope-2"),
            output_fn=lambda _: None,
            clock_fn=_Clock(step=0.1),
            nonce_fn=lambda: "x",
            date_fn=lambda: _dt.datetime(2026, 5, 18, tzinfo=_dt.UTC),
        )
        payload = result.as_audit_payload()
        assert payload["gate_passed"] is False
        assert payload["gate_outcome"] == "failed"
        assert payload["attempts"] == 2

    def test_batch_payload_shape(self) -> None:
        result = typed_phrase_confirm(
            "PURGE",
            batch=True,
            nonce_fn=lambda: "x",
            date_fn=lambda: _dt.datetime(2026, 5, 18, tzinfo=_dt.UTC),
        )
        payload = result.as_audit_payload()
        assert payload["gate_passed"] is True
        assert payload["gate_outcome"] == "skipped"
        assert payload["via"] == "batch"
        assert payload["elapsed_s"] == 0.0


class TestPromptOutput:
    def test_phrase_appears_in_prompt(self) -> None:
        seen, emit = _captured_output()
        typed_phrase_confirm(
            "PURGE",
            timeout_s=30,
            input_fn=_Inputs("PURGE_2026-05-18_x"),
            output_fn=emit,
            clock_fn=_Clock(step=0.1),
            nonce_fn=lambda: "x",
            date_fn=lambda: _dt.datetime(2026, 5, 18, tzinfo=_dt.UTC),
        )
        all_output = "\n".join(seen)
        assert "PURGE_2026-05-18_x" in all_output
        assert "30 seconds" in all_output or "30 second" in all_output

    def test_mismatch_does_not_echo_typed_input(self) -> None:
        seen, emit = _captured_output()
        typed_phrase_confirm(
            "PURGE",
            timeout_s=30,
            max_attempts=2,
            input_fn=_Inputs("MY-LEAKED-SECRET", "PURGE_2026-05-18_x"),
            output_fn=emit,
            clock_fn=_Clock(step=0.1),
            nonce_fn=lambda: "x",
            date_fn=lambda: _dt.datetime(2026, 5, 18, tzinfo=_dt.UTC),
        )
        # The operator's mistyped input should NEVER appear in output —
        # they might be in the middle of typing a real secret.
        all_output = "\n".join(seen)
        assert "MY-LEAKED-SECRET" not in all_output
        assert "phrase mismatch" in all_output


class TestGateResultImmutability:
    def test_frozen(self) -> None:
        result = GateResult(
            passed=True, outcome="passed", attempts=1, elapsed_s=0.5,
            via="tty", phrase="X",
        )
        with pytest.raises(Exception):
            result.passed = False  # type: ignore[misc]
