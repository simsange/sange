"""`sange.core.purge` — VCS history purge subsystem (§6.11).

This first slice (T-111a) ships the data model + state machine +
persistence layer only — every higher-level concern (mirror clones,
analyzers, gates, CLI surface) layers on top.

Public surface:

  * `PurgeState`            — the 10 lifecycle states per §6.11.2.
  * `IllegalTransition`     — raised when a forward-only constraint is violated.
  * `can_transition()` /    — pure query/assert helpers over the state graph.
    `assert_transition()`
  * `PurgePlan`             — the persistent plan model (Pydantic v2).
  * `PurgeFilters`,         — sub-models nested inside `PurgePlan`.
    `RepoMeta`,
    `ToolMeta`,
    `PreflightCheck`
  * `PurgePlanStore`        — atomic read/write at
                              `<repo>/.sange/purge/<plan-id>/plan.json`.
  * `PurgePlanNotFound`     — raised by `load()` on missing plan.
  * `new_plan_id()`         — generate a canonical
                              `purge-<UTC-ISO>-<8-hex>` id.

Audit-chain integration (`EventKind.PURGE_PLAN` / `EventKind.PURGE_EXECUTE`)
is intentionally NOT in this layer — the CLI layer pairs each
`plan.transition(...)` with `chain.append(...)` so the audit + plan
concerns stay independent.
"""

from __future__ import annotations

from sange.core.purge.mirror import (
    MirrorError,
    MirrorResult,
    MirrorVerification,
    create_mirror,
    verify_mirror,
)
from sange.core.purge.plan import (
    SCHEMA_VERSION,
    PreflightCheck,
    PurgeFilters,
    PurgePlan,
    PurgePlanNotFound,
    PurgePlanStore,
    RepoMeta,
    ToolMeta,
    new_plan_id,
)
from sange.core.purge.state import (
    TERMINAL_STATES,
    IllegalTransition,
    PurgeState,
    assert_transition,
    can_transition,
    legal_next,
)

__all__ = [
    "SCHEMA_VERSION",
    "TERMINAL_STATES",
    "IllegalTransition",
    "MirrorError",
    "MirrorResult",
    "MirrorVerification",
    "PreflightCheck",
    "PurgeFilters",
    "PurgePlan",
    "PurgePlanNotFound",
    "PurgePlanStore",
    "PurgeState",
    "RepoMeta",
    "ToolMeta",
    "assert_transition",
    "can_transition",
    "create_mirror",
    "legal_next",
    "new_plan_id",
    "verify_mirror",
]
