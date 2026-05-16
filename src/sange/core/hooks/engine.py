"""`HookEngine` — discovers + runs hooks under `.sange/hooks/`.

Per §7.4: hooks live at `<repo>/.sange/hooks/<event>/<priority>-<name>`
where `<event>` is `pre-commit` / `pre-push` / `pre-merge-commit` /
etc., `<priority>` is a 2-digit integer (`00` runs first), and
`<name>` is a filesystem-safe slug. Any executable in that path
becomes a hook for that event.

The discipline:

  * Hooks are append-only files in the repo (committable). Sange
    never installs into `.git/hooks/` directly — instead, `sange
    init` writes shims into `.git/hooks/<event>` that delegate to
    `sange hooks run <event>`. That keeps the hook content
    visible in git history.
  * Each hook is a self-contained executable. Bash, Python, Ruby,
    Go — any language. The convention is exit code 0/128/64/other
    maps to PASSED/WARN/SKIPPED/FAILED per `result.py`.
  * The engine doesn't know what the hooks do. It runs them in
    priority order and aggregates the results.
  * Per-event timeout is configurable; defaults to 5 minutes for
    `pre-commit` (caller can override). Each hook also has its
    own subprocess timeout that defaults to 60s.

The first slice (T-102 in this commit) ships discovery + run.
The named-gate library (gitleaks / trufflehog / `make test` /
`make lint` shipping as named hooks) lands in T-103 as a separate
subsystem layered on top of this engine.
"""

from __future__ import annotations

import os
import re
import subprocess
import time
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from sange.core.hooks.result import (
    HookReport,
    HookResult,
    HookStatus,
    status_from_exit_code,
)

_HOOKS_DIR_NAME = ".sange/hooks"
_PRIORITY_RE = re.compile(r"^(\d{2})-(.+)$")
_DEFAULT_HOOK_TIMEOUT_S = 60.0
_STDOUT_MAX = 64 * 1024
_STDERR_MAX = 64 * 1024


class HookError(Exception):
    """Raised when hook discovery or invocation can't proceed."""


@dataclass(frozen=True)
class HookDescriptor:
    """A discovered hook on disk, not yet executed."""

    name: str
    event: str
    priority: int
    path: Path

    def __post_init__(self) -> None:
        if not 0 <= self.priority <= 99:
            raise HookError(
                f"hook priority must be 0..99; got {self.priority} for {self.name!r}"
            )


class HookEngine:
    """Discovers + runs hooks for a repo.

    Instances are cheap — no caching across events; `discover()`
    re-walks `.sange/hooks/` on every call. The CLI surface is
    `sange hooks run <event>` (lands in a follow-up commit).
    """

    def __init__(
        self,
        repo_root: Path,
        *,
        hook_timeout_s: float = _DEFAULT_HOOK_TIMEOUT_S,
        env_extra: Mapping[str, str] | None = None,
    ) -> None:
        self._repo_root = Path(repo_root).resolve()
        self._hook_timeout_s = hook_timeout_s
        self._env_extra = dict(env_extra or {})

    @property
    def repo_root(self) -> Path:
        return self._repo_root

    @property
    def hooks_dir(self) -> Path:
        return self._repo_root / _HOOKS_DIR_NAME

    # ---- discovery ------------------------------------------------ #

    def discover(self, event: str) -> tuple[HookDescriptor, ...]:
        """Return every executable hook for `event` in priority order.

        Files under `<repo>/.sange/hooks/<event>/` whose name matches
        `NN-<slug>` are included. The `NN` is the priority (00 first);
        files that don't match the priority pattern are skipped.
        Non-executable files are also skipped — they're considered
        templates, not active hooks.
        """

        if not event:
            raise HookError("discover: event must be non-empty")

        event_dir = self.hooks_dir / event
        if not event_dir.is_dir():
            return ()

        out: list[HookDescriptor] = []
        for child in sorted(event_dir.iterdir(), key=lambda p: p.name):
            if not child.is_file():
                continue
            m = _PRIORITY_RE.match(child.name)
            if m is None:
                continue
            # POSIX: executable bit for the user. Windows: we trust the
            # extension or run `python <file>` — but the v0.5-alpha
            # boundary is POSIX-only.
            if not os.access(child, os.X_OK):
                continue
            priority = int(m.group(1))
            name = m.group(2)
            out.append(HookDescriptor(
                name=name,
                event=event,
                priority=priority,
                path=child.resolve(),
            ))
        return tuple(out)

    # ---- execution ----------------------------------------------- #

    def run_event(
        self,
        event: str,
        *,
        cwd: Path | None = None,
        env: Mapping[str, str] | None = None,
        abort_on_failed: bool = True,
    ) -> HookReport:
        """Run every hook for `event` in priority order.

        Args:
          event:            the lifecycle event (`pre-commit`, etc.).
          cwd:              working directory for each hook process.
                            Default: `repo_root`.
          env:              additional env vars to set. The engine
                            preserves PATH + HOME + any operator-supplied
                            `env_extra` from `__init__`, then layers `env`
                            on top.
          abort_on_failed:  when True (default), the first FAILED hook
                            short-circuits the remaining hooks. WARN /
                            SKIPPED never short-circuit. Set False to
                            collect every hook's result regardless.

        Returns a `HookReport` with one `HookResult` per hook that ran.
        Hooks that were short-circuited do not appear in the report.
        """

        descriptors = self.discover(event)
        if not descriptors:
            return HookReport(event=event, results=())

        target_cwd = (cwd or self._repo_root).resolve()
        results: list[HookResult] = []
        for d in descriptors:
            result = self._run_one(d, cwd=target_cwd, env=env)
            results.append(result)
            if abort_on_failed and result.status is HookStatus.FAILED:
                break
        return HookReport(event=event, results=tuple(results))

    def run_one(
        self,
        descriptor: HookDescriptor,
        *,
        cwd: Path | None = None,
        env: Mapping[str, str] | None = None,
    ) -> HookResult:
        """Run a single hook (no abort-on-failed semantics)."""

        return self._run_one(
            descriptor,
            cwd=(cwd or self._repo_root).resolve(),
            env=env,
        )

    # ---- internals ----------------------------------------------- #

    def _run_one(
        self,
        descriptor: HookDescriptor,
        *,
        cwd: Path,
        env: Mapping[str, str] | None,
    ) -> HookResult:
        full_env = self._build_env(env)
        start_ns = time.monotonic_ns()
        timed_out = False
        try:
            proc = subprocess.run(
                [str(descriptor.path)],
                cwd=str(cwd),
                env=full_env,
                capture_output=True,
                text=True,
                timeout=self._hook_timeout_s,
                check=False,
                encoding="utf-8",
                errors="replace",
            )
            exit_code = proc.returncode
            stdout = proc.stdout
            stderr = proc.stderr
        except subprocess.TimeoutExpired as exc:
            exit_code = -1
            stdout = exc.stdout.decode("utf-8", errors="replace") if exc.stdout else ""
            stderr = exc.stderr.decode("utf-8", errors="replace") if exc.stderr else ""
            stderr = (
                f"hook timed out after {self._hook_timeout_s}s\n{stderr}"
            )
            timed_out = True
        except (PermissionError, FileNotFoundError) as exc:
            exit_code = -1
            stdout = ""
            stderr = f"hook invocation failed: {exc}"
        duration_ms = int((time.monotonic_ns() - start_ns) / 1_000_000)

        status = HookStatus.FAILED if timed_out else status_from_exit_code(exit_code)

        return HookResult(
            name=descriptor.name,
            event=descriptor.event,
            priority=descriptor.priority,
            path=str(descriptor.path),
            status=status,
            exit_code=exit_code,
            duration_ms=duration_ms,
            stdout=stdout[:_STDOUT_MAX],
            stderr=stderr[:_STDERR_MAX],
            timed_out=timed_out,
        )

    def _build_env(self, override: Mapping[str, str] | None) -> dict[str, str]:
        env: dict[str, str] = {
            "PATH": os.environ.get("PATH", ""),
            "HOME": os.environ.get("HOME", ""),
            "SANGE_HOOKS_REPO_ROOT": str(self._repo_root),
        }
        env.update(self._env_extra)
        if override:
            env.update(override)
        return env


__all__ = [
    "HookDescriptor",
    "HookEngine",
    "HookError",
]
