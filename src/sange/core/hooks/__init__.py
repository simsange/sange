"""`sange.core.hooks` — pre-commit / pre-push / etc. hooks engine (T-102).

First slice ships discovery + execution + per-hook result aggregation.
The named-gate library (gitleaks / trufflehog / make-test / make-lint
shipping as preconfigured hooks) lands in T-103 as a layer on top.
"""

from __future__ import annotations

from sange.core.hooks.engine import HookDescriptor, HookEngine, HookError
from sange.core.hooks.result import (
    EXIT_PASSED,
    EXIT_SKIPPED,
    EXIT_WARN,
    HookReport,
    HookResult,
    HookStatus,
    status_from_exit_code,
)

__all__ = [
    "EXIT_PASSED",
    "EXIT_SKIPPED",
    "EXIT_WARN",
    "HookDescriptor",
    "HookEngine",
    "HookError",
    "HookReport",
    "HookResult",
    "HookStatus",
    "status_from_exit_code",
]
