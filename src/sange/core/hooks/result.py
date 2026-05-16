"""`HookResult` — the typed outcome of one hook invocation.

Per §7.4, every hook returns a `HookResult` that the engine
aggregates into a per-event report. The contract is intentionally
simple — anything that exits 0 passes; anything else fails — so
plugins can ship hooks in any language. Sange-shipped named gates
(gitleaks / trufflehog / make-test / etc.) land in T-103.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field


class HookStatus(str, enum.Enum):
    """The four outcomes a hook can produce.

    * `PASSED`  — exit code 0; no further action.
    * `FAILED`  — exit code 1-127 (excluding the warn band); the
                  engine reports failure and the calling flow
                  aborts (per the `--abort-on` policy the operator
                  configures).
    * `WARN`    — exit code 128 (Sange convention); the engine
                  records a warning but does not abort. Use this
                  for advisory checks (a noisy lint that shouldn't
                  block).
    * `SKIPPED` — the hook chose not to run (exit code 64 by
                  Sange convention) — e.g. the gate's target
                  scope didn't match the staged paths.
    """

    PASSED = "passed"
    FAILED = "failed"
    WARN = "warn"
    SKIPPED = "skipped"


# Convention exit codes. Hooks that exit with these values map to
# the corresponding HookStatus; everything else outside the [0, 128]
# range or non-conventional codes maps to FAILED.
EXIT_PASSED = 0
EXIT_WARN = 128
EXIT_SKIPPED = 64


def status_from_exit_code(code: int) -> HookStatus:
    """Map a hook process exit code to a `HookStatus`."""

    if code == EXIT_PASSED:
        return HookStatus.PASSED
    if code == EXIT_WARN:
        return HookStatus.WARN
    if code == EXIT_SKIPPED:
        return HookStatus.SKIPPED
    return HookStatus.FAILED


@dataclass(frozen=True)
class HookResult:
    """The outcome of one hook invocation.

    Fields:
      * `name`         — the hook's slug (basename minus priority prefix).
      * `event`        — the lifecycle event (`pre-commit` / `pre-push` /
                         …) the hook ran for.
      * `priority`     — the hook's priority number (sort order; lower
                         runs first).
      * `path`         — absolute path to the hook executable on disk.
      * `status`       — one of `HookStatus`.
      * `exit_code`    — the underlying process exit code.
      * `duration_ms`  — wall-clock duration in milliseconds.
      * `stdout`       — captured stdout (truncated to 64 KiB).
      * `stderr`       — captured stderr (truncated to 64 KiB).
      * `timed_out`    — True if the hook hit its timeout (status will
                         be `FAILED`).
    """

    name: str
    event: str
    priority: int
    path: str
    status: HookStatus
    exit_code: int
    duration_ms: int
    stdout: str = ""
    stderr: str = ""
    timed_out: bool = False

    @property
    def passed(self) -> bool:
        return self.status is HookStatus.PASSED

    @property
    def failed(self) -> bool:
        return self.status is HookStatus.FAILED


@dataclass(frozen=True)
class HookReport:
    """Aggregate of every hook that ran for one event.

    Returned by `HookEngine.run_event(event, repo)`. The CLI's
    `sange hooks run` surfaces this as a table + exit code.
    """

    event: str
    results: tuple[HookResult, ...] = field(default_factory=tuple)

    @property
    def all_passed(self) -> bool:
        return all(r.status is HookStatus.PASSED for r in self.results)

    @property
    def any_failed(self) -> bool:
        return any(r.status is HookStatus.FAILED for r in self.results)

    @property
    def counts(self) -> dict[HookStatus, int]:
        out: dict[HookStatus, int] = {s: 0 for s in HookStatus}
        for r in self.results:
            out[r.status] += 1
        return out

    @property
    def total(self) -> int:
        return len(self.results)


__all__ = [
    "EXIT_PASSED",
    "EXIT_SKIPPED",
    "EXIT_WARN",
    "HookReport",
    "HookResult",
    "HookStatus",
    "status_from_exit_code",
]
