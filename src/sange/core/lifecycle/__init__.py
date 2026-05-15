"""Commit message lifecycle — the §6.8 headline Sange feature.

Per §6.8 the lifecycle is a file-based store at
`${repo}/.sange/commits/NNNN-<type>-<scope>-<short-subject>.json`
plus a durable monotonic counter at `.sange/commits/.counter`.

State machine (per §6.8.2):

    [draft] --submit--> [pending_review] --approve--> [approved]
        |                     |                            |
        |              reject |                     commit |
        v                     v                            v
    [discarded]          [rejected]                   [committed]
                                                          |
                                                     push |
                                                          v
                                                      [pushed]
                                                          |
                                                  archive |
                                                          v
                                                      [archived]

Public surface (T-006 — this module):

  * `CommitJSON`       — Pydantic v2 model matching §6.8.3 verbatim.
  * `CommitStatus`     — the 8-state enum.
  * `CommitMessage`    — the structured commit-message sub-model.
  * `CommitDiff`       — diff-summary sub-model (linked to §6.2 DiffSummary).
  * `AIProvenance`     — per-commit AI metadata (provider, model, cost).
  * `Approval`         — single approval record.
  * `CommitStore`      — file-based read/write/list operations.
  * `CommitCounter`    — durable monotonic per-repo counter.
  * `CommitsDirectory` — high-level façade combining store + counter.

T-007 (state machine) builds on this; the state-transition logic
lives there. The model here only declares valid states; transitions
are not enforced at the model level.
"""

from __future__ import annotations

from sange.core.lifecycle.counter import CommitCounter, CounterError
from sange.core.lifecycle.schema import (
    SCHEMA_VERSION,
    AIProvenance,
    Approval,
    Author,
    CommitDiff,
    CommitJSON,
    CommitMessage,
    CommitStatus,
    Rejection,
)
from sange.core.lifecycle.state_machine import (
    TRANSITIONS,
    IllegalTransition,
    LifecycleEngine,
    Surface,
    allowed_transitions_from,
    is_terminal,
)
from sange.core.lifecycle.store import (
    CommitsDirectory,
    CommitStore,
    CommitStoreError,
    slugify_subject,
)

__all__ = [
    "SCHEMA_VERSION",
    "TRANSITIONS",
    "AIProvenance",
    "Approval",
    "Author",
    "CommitCounter",
    "CommitDiff",
    "CommitJSON",
    "CommitMessage",
    "CommitStatus",
    "CommitStore",
    "CommitStoreError",
    "CommitsDirectory",
    "CounterError",
    "IllegalTransition",
    "LifecycleEngine",
    "Rejection",
    "Surface",
    "allowed_transitions_from",
    "is_terminal",
    "slugify_subject",
]
