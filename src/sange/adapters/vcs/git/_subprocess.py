"""Env-disciplined `git` subprocess wrapper.

Reuses the lesson learned from `tools/generators/_lib/manpage.py::_run`
(the PATH+HOME bug caught when SVN at `/Applications/ServBay/bin/svn`
failed): preserve `PATH` + `HOME` so the child process can find the
binary and read its config, while still forcing C locale + no-pager
for reproducible output parsing.

Surface:

  * `run_git(args, cwd, *, allow_failure=False) -> str`
      Returns stdout. Raises `GitCommandFailed` on non-zero exit
      (unless `allow_failure=True`, which returns the empty string).
  * `run_git_lines(args, cwd) -> list[str]`
      Convenience: returns stdout split by lines (terminator stripped).
  * `GitNotInstalled`, `GitCommandFailed` — concrete sub-exceptions of
      `DriverError` for fine-grained handling.

Subprocess discipline:
  * Locale: `LC_ALL=C` + `LANG=C` so output is en_US-with-no-translation.
  * Pager: `GIT_PAGER=cat` + `PAGER=cat` so `git log` doesn't try to spawn
    `less`.
  * Auth: `GIT_TERMINAL_PROMPT=0` so a credential prompt fails fast
    instead of hanging the test runner.
  * PATH + HOME: inherited from parent process (the §6.10 secrets resolver
    consults `HOME` for `~/.gitconfig` keys).
  * Timeout: `default 30s`. Long-running operations (clone of a huge repo)
    pass an explicit override; the §7.0.6 streaming helper takes over for
    operations that don't fit a single string return.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from collections.abc import Sequence
from pathlib import Path

from sange.adapters.vcs._protocol import DriverError


class GitNotInstalled(DriverError):
    """`git` binary is not on PATH."""


class GitCommandFailed(DriverError):
    """`git` exited non-zero. Carries the `returncode`, `args`, and `stderr` so
    callers can pattern-match on common failures.
    """

    def __init__(
        self,
        message: str,
        *,
        returncode: int,
        args: Sequence[str],
        stderr: str,
    ) -> None:
        super().__init__(message)
        self.returncode = returncode
        self.args = tuple(args)
        self.stderr = stderr


# Default subprocess timeout (seconds). Operations that need more time
# pass an explicit override; the streaming helper (§7.0.6) is the path
# for operations that don't fit a single buffered return.
_DEFAULT_TIMEOUT_S = 30.0


def _build_env() -> dict[str, str]:
    """Construct the locked-down environment for `git` child processes."""

    return {
        # Preserve PATH so the child can find git + any helpers it shells
        # out to (e.g. `git-lfs`, credential helpers).
        "PATH": os.environ.get("PATH", ""),
        # Preserve HOME so `~/.gitconfig` resolves correctly.
        "HOME": os.environ.get("HOME", ""),
        # Force C locale for parseable output.
        "LC_ALL": "C",
        "LANG": "C",
        # No pager — we want raw stdout.
        "PAGER": "cat",
        "GIT_PAGER": "cat",
        # No interactive auth prompts.
        "GIT_TERMINAL_PROMPT": "0",
        # No commit-msg editor invocation (we always pass -m or --file).
        "GIT_EDITOR": "true",
    }


def run_git(
    args: Sequence[str],
    cwd: Path | None = None,
    *,
    allow_failure: bool = False,
    timeout_s: float = _DEFAULT_TIMEOUT_S,
    stdin: str | None = None,
) -> str:
    """Run `git <args>` and return stdout as a string.

    Args:
      args:   git's arguments (without the leading `"git"`).
      cwd:    working directory; defaults to `os.getcwd()`.
      allow_failure: when True, non-zero exit returns `""` instead of raising.
      timeout_s: kill the process if it runs longer than this.
      stdin:  optional input passed via stdin.

    Raises:
      GitNotInstalled: `git` is not on PATH.
      GitCommandFailed: non-zero exit (unless `allow_failure=True`).
    """

    if shutil.which("git") is None:
        raise GitNotInstalled(
            "git binary not found on PATH; install git or supply a fake driver"
        )

    try:
        result = subprocess.run(
            ["git", *args],
            cwd=str(cwd) if cwd is not None else None,
            env=_build_env(),
            input=stdin,
            capture_output=True,
            text=True,
            timeout=timeout_s,
            check=False,
            encoding="utf-8",
            errors="replace",
        )
    except FileNotFoundError as exc:
        # Race: which() found git but it disappeared before we could exec it.
        raise GitNotInstalled(str(exc)) from exc
    except subprocess.TimeoutExpired as exc:
        raise GitCommandFailed(
            f"git {args[0] if args else '<no-args>'} timed out after {timeout_s}s",
            returncode=-1,
            args=args,
            stderr=exc.stderr.decode("utf-8", errors="replace") if exc.stderr else "",
        ) from exc

    if result.returncode != 0:
        if allow_failure:
            return ""
        raise GitCommandFailed(
            f"git {' '.join(args)} exited {result.returncode}: "
            f"{result.stderr.strip() or '<no stderr>'}",
            returncode=result.returncode,
            args=args,
            stderr=result.stderr,
        )

    return result.stdout


def run_git_lines(
    args: Sequence[str],
    cwd: Path | None = None,
    *,
    allow_failure: bool = False,
) -> list[str]:
    """Convenience wrapper — return stdout split by lines (no trailing empty)."""

    out = run_git(args, cwd=cwd, allow_failure=allow_failure)
    lines = out.splitlines()
    # Strip a trailing empty line introduced by a final `\n` in stdout.
    while lines and not lines[-1]:
        lines.pop()
    return lines


__all__ = [
    "GitCommandFailed",
    "GitNotInstalled",
    "run_git",
    "run_git_lines",
]
