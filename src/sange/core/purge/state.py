"""`PurgeState` — the §6.11.2 purge lifecycle state machine.

The graph is forward-only with one exception: `rolled_back` re-enters
`planned` so a failed purge can be retried after the operator
addresses what went wrong.

```
                                ┌── abort ──┐
                                ▼           │
[planned] ─→ [preflight_passed] ─→ [analyzed] ─→ [previewed] ─→ [confirmed]
                                                                    │
                                                                  execute
                                                                    │
                                                                    ▼
                                                              [executing]
                                                                ┌─────┴─────┐
                                                                ▼           ▼
                                                          [verified]  [rolled_back] ─→ [planned] (retry)
                                                              │
                                                            push
                                                              │
                                                              ▼
                                                          [completed]   (terminal)
                                                          [aborted]     (terminal)
```

This module is pure — no I/O, no audit chain, no plan persistence.
Higher layers compose this with the store + chain as needed.
"""

from __future__ import annotations

import enum
from typing import Final


class PurgeState(str, enum.Enum):
    """The 10 lifecycle states per §6.11.2."""

    PLANNED = "planned"
    PREFLIGHT_PASSED = "preflight_passed"
    ANALYZED = "analyzed"
    PREVIEWED = "previewed"
    CONFIRMED = "confirmed"
    EXECUTING = "executing"
    VERIFIED = "verified"
    COMPLETED = "completed"
    ABORTED = "aborted"
    ROLLED_BACK = "rolled_back"

    @classmethod
    def all_values(cls) -> tuple[str, ...]:
        return tuple(s.value for s in cls)


# Adjacency map per §6.11.2. Forward-only with one re-entry edge.
# `aborted` is reachable from every pre-execution state; `rolled_back`
# from `executing` or `verified` (post-execution failure modes).
_TRANSITIONS: Final[dict[PurgeState, frozenset[PurgeState]]] = {
    PurgeState.PLANNED: frozenset({
        PurgeState.PREFLIGHT_PASSED,
        PurgeState.ABORTED,
    }),
    PurgeState.PREFLIGHT_PASSED: frozenset({
        PurgeState.ANALYZED,
        PurgeState.ABORTED,
    }),
    PurgeState.ANALYZED: frozenset({
        PurgeState.PREVIEWED,
        PurgeState.ABORTED,
    }),
    PurgeState.PREVIEWED: frozenset({
        PurgeState.CONFIRMED,
        PurgeState.ABORTED,
    }),
    PurgeState.CONFIRMED: frozenset({
        PurgeState.EXECUTING,
    }),
    PurgeState.EXECUTING: frozenset({
        PurgeState.VERIFIED,
        PurgeState.ROLLED_BACK,
    }),
    PurgeState.VERIFIED: frozenset({
        PurgeState.COMPLETED,
        PurgeState.ROLLED_BACK,
    }),
    PurgeState.COMPLETED: frozenset(),  # terminal
    PurgeState.ABORTED: frozenset(),    # terminal
    PurgeState.ROLLED_BACK: frozenset({
        PurgeState.PLANNED,  # the only re-entry edge — retry path
    }),
}


# States that have no outgoing transitions — operations against these
# require a fresh plan_id.
TERMINAL_STATES: Final[frozenset[PurgeState]] = frozenset({
    PurgeState.COMPLETED,
    PurgeState.ABORTED,
})


class IllegalTransition(Exception):
    """Raised when a requested transition isn't legal from the current state.

    Carries `from_state` + `to_state` so callers can format precise
    remediation messages (`docs/reference/exit-codes.md` exit 66).
    """

    def __init__(self, from_state: PurgeState, to_state: PurgeState) -> None:
        legal = sorted(s.value for s in _TRANSITIONS[from_state])
        super().__init__(
            f"illegal purge transition: {from_state.value} → {to_state.value} "
            f"(legal from {from_state.value}: {legal})"
        )
        self.from_state = from_state
        self.to_state = to_state


def legal_next(state: PurgeState) -> frozenset[PurgeState]:
    """The set of states reachable from `state` in one transition."""

    return _TRANSITIONS[state]


def can_transition(from_state: PurgeState, to_state: PurgeState) -> bool:
    """Pure predicate — does the graph permit `from_state → to_state`?"""

    return to_state in _TRANSITIONS[from_state]


def assert_transition(from_state: PurgeState, to_state: PurgeState) -> None:
    """Raise IllegalTransition if `from_state → to_state` isn't legal."""

    if not can_transition(from_state, to_state):
        raise IllegalTransition(from_state, to_state)


__all__ = [
    "TERMINAL_STATES",
    "IllegalTransition",
    "PurgeState",
    "assert_transition",
    "can_transition",
    "legal_next",
]
