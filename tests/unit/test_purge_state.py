"""Tests for `sange.core.purge.state` — the §6.11.2 state machine."""

from __future__ import annotations

import pytest

from sange.core.purge import (
    TERMINAL_STATES,
    IllegalTransition,
    PurgeState,
    assert_transition,
    can_transition,
    legal_next,
)


class TestPurgeStateEnum:
    def test_ten_states_declared(self) -> None:
        assert len(list(PurgeState)) == 10

    def test_value_is_canonical_kebab(self) -> None:
        assert PurgeState.PLANNED.value == "planned"
        assert PurgeState.PREFLIGHT_PASSED.value == "preflight_passed"
        assert PurgeState.ROLLED_BACK.value == "rolled_back"

    def test_all_values_returns_every_state(self) -> None:
        values = PurgeState.all_values()
        assert "planned" in values
        assert "completed" in values
        assert len(values) == 10


class TestTransitions:
    @pytest.mark.parametrize(
        ("frm", "to"),
        [
            (PurgeState.PLANNED, PurgeState.PREFLIGHT_PASSED),
            (PurgeState.PLANNED, PurgeState.ABORTED),
            (PurgeState.PREFLIGHT_PASSED, PurgeState.ANALYZED),
            (PurgeState.PREFLIGHT_PASSED, PurgeState.ABORTED),
            (PurgeState.ANALYZED, PurgeState.PREVIEWED),
            (PurgeState.ANALYZED, PurgeState.ABORTED),
            (PurgeState.PREVIEWED, PurgeState.CONFIRMED),
            (PurgeState.PREVIEWED, PurgeState.ABORTED),
            (PurgeState.CONFIRMED, PurgeState.EXECUTING),
            (PurgeState.EXECUTING, PurgeState.VERIFIED),
            (PurgeState.EXECUTING, PurgeState.ROLLED_BACK),
            (PurgeState.VERIFIED, PurgeState.COMPLETED),
            (PurgeState.VERIFIED, PurgeState.ROLLED_BACK),
            (PurgeState.ROLLED_BACK, PurgeState.PLANNED),
        ],
    )
    def test_legal_transitions(
        self, frm: PurgeState, to: PurgeState,
    ) -> None:
        assert can_transition(frm, to)
        assert_transition(frm, to)  # does not raise

    @pytest.mark.parametrize(
        ("frm", "to"),
        [
            # Skip-ahead from PLANNED → ANALYZED (must go through PREFLIGHT).
            (PurgeState.PLANNED, PurgeState.ANALYZED),
            # PLANNED → CONFIRMED (skipping every gate).
            (PurgeState.PLANNED, PurgeState.CONFIRMED),
            # Re-entry to PLANNED only from ROLLED_BACK.
            (PurgeState.ABORTED, PurgeState.PLANNED),
            (PurgeState.COMPLETED, PurgeState.PLANNED),
            # Backwards.
            (PurgeState.PREVIEWED, PurgeState.PLANNED),
            (PurgeState.CONFIRMED, PurgeState.PREVIEWED),
            # CONFIRMED can only go to EXECUTING (no abort once confirmed).
            (PurgeState.CONFIRMED, PurgeState.ABORTED),
            # EXECUTING can't abort — only verify or roll back.
            (PurgeState.EXECUTING, PurgeState.ABORTED),
            (PurgeState.EXECUTING, PurgeState.COMPLETED),
        ],
    )
    def test_illegal_transitions_raise(
        self, frm: PurgeState, to: PurgeState,
    ) -> None:
        assert can_transition(frm, to) is False
        with pytest.raises(IllegalTransition) as exc_info:
            assert_transition(frm, to)
        assert exc_info.value.from_state is frm
        assert exc_info.value.to_state is to


class TestTerminalStates:
    def test_completed_is_terminal(self) -> None:
        assert PurgeState.COMPLETED in TERMINAL_STATES
        assert legal_next(PurgeState.COMPLETED) == frozenset()

    def test_aborted_is_terminal(self) -> None:
        assert PurgeState.ABORTED in TERMINAL_STATES
        assert legal_next(PurgeState.ABORTED) == frozenset()

    def test_rolled_back_is_not_terminal(self) -> None:
        # ROLLED_BACK can re-enter PLANNED for retries.
        assert PurgeState.ROLLED_BACK not in TERMINAL_STATES
        assert PurgeState.PLANNED in legal_next(PurgeState.ROLLED_BACK)

    def test_terminal_states_count(self) -> None:
        assert len(TERMINAL_STATES) == 2


class TestLegalNext:
    def test_planned_can_go_to_preflight_or_aborted(self) -> None:
        assert legal_next(PurgeState.PLANNED) == frozenset({
            PurgeState.PREFLIGHT_PASSED,
            PurgeState.ABORTED,
        })

    def test_confirmed_has_one_successor(self) -> None:
        assert legal_next(PurgeState.CONFIRMED) == frozenset({
            PurgeState.EXECUTING,
        })

    def test_rolled_back_only_re_enters_planned(self) -> None:
        assert legal_next(PurgeState.ROLLED_BACK) == frozenset({
            PurgeState.PLANNED,
        })


class TestIllegalTransitionMessage:
    def test_message_lists_legal_alternatives(self) -> None:
        with pytest.raises(IllegalTransition, match="planned → confirmed"):
            assert_transition(PurgeState.PLANNED, PurgeState.CONFIRMED)
        with pytest.raises(IllegalTransition) as exc_info:
            assert_transition(PurgeState.PLANNED, PurgeState.CONFIRMED)
        assert "preflight_passed" in str(exc_info.value)
        assert "aborted" in str(exc_info.value)
