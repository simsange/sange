"""`sange.core.hooks` — pre-commit / pre-push / etc. hooks engine (T-102).

First slice ships discovery + execution + per-hook result aggregation.
The named-gate library (gitleaks / trufflehog / make-test / make-lint
shipping as preconfigured hooks) lands in T-103 as a layer on top.
"""

from __future__ import annotations

from sange.core.hooks.engine import HookDescriptor, HookEngine, HookError
from sange.core.hooks.gates import (
    Gate,
    GateActionResult,
    GateError,
    GateEvent,
    GateRegistry,
    add_gate,
    default_gate_roots,
    load_gate,
    remove_gate,
)
from sange.core.hooks.result import (
    EXIT_PASSED,
    EXIT_SKIPPED,
    EXIT_WARN,
    HookReport,
    HookResult,
    HookStatus,
    status_from_exit_code,
)
from sange.core.hooks.shim import (
    GIT_HOOK_EVENTS,
    SHIM_MARKER,
    ShimError,
    ShimInstallResult,
    install_git_shims,
    uninstall_git_shims,
)

__all__ = [
    "EXIT_PASSED",
    "EXIT_SKIPPED",
    "EXIT_WARN",
    "GIT_HOOK_EVENTS",
    "SHIM_MARKER",
    "Gate",
    "GateActionResult",
    "GateError",
    "GateEvent",
    "GateRegistry",
    "HookDescriptor",
    "HookEngine",
    "HookError",
    "HookReport",
    "HookResult",
    "HookStatus",
    "ShimError",
    "ShimInstallResult",
    "add_gate",
    "default_gate_roots",
    "install_git_shims",
    "load_gate",
    "remove_gate",
    "status_from_exit_code",
    "uninstall_git_shims",
]
