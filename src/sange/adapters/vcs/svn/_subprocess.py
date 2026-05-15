"""Subprocess wrapper for `svn` invocations.

Mirrors `sange.adapters.vcs.git._subprocess` — same env-discipline
(LC_ALL=C, LANG=C, PAGER=cat, SVN_EDITOR=true), same structured
errors, same timeout default. Adapter callers use `run_svn()`
exclusively; they never `subprocess.run(['svn', ...])` directly.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from collections.abc import Sequence
from pathlib import Path

from sange.adapters.vcs._protocol import DriverError

_DEFAULT_TIMEOUT_S = 30.0


class SvnNotInstalled(DriverError):
    """Raised when the `svn` binary is not on PATH."""


class SvnCommandFailed(DriverError):
    """Raised when `svn` exits non-zero (and `allow_failure=False`)."""

    def __init__(
        self,
        msg: str,
        *,
        returncode: int,
        args: Sequence[str],
        stderr: str,
    ) -> None:
        super().__init__(msg)
        self.returncode = returncode
        self.args = tuple(args)
        self.stderr = stderr


def _build_env() -> dict[str, str]:
    """Construct the locked-down environment for `svn` child processes."""

    return {
        # Preserve PATH so the child can find svn + helpers.
        "PATH": os.environ.get("PATH", ""),
        # Preserve HOME so `~/.subversion/` resolves correctly (auth + config).
        "HOME": os.environ.get("HOME", ""),
        # Force C locale for parseable output — svn's `--xml` is already
        # locale-independent, but human-readable output (errors, log messages
        # in `--non-interactive` mode) isn't.
        "LC_ALL": "C",
        "LANG": "C",
        "LC_MESSAGES": "C",
        # No pager — we want raw stdout.
        "PAGER": "cat",
        # No interactive auth prompts; the caller passes credentials
        # explicitly or fails fast.
        # (`svn` honors `--non-interactive` per-invocation; this env knob
        # is belt-and-braces.)
        "SVN_EDITOR": "true",
    }


def run_svn(
    args: Sequence[str],
    cwd: Path | None = None,
    *,
    allow_failure: bool = False,
    timeout_s: float = _DEFAULT_TIMEOUT_S,
    stdin: str | None = None,
) -> str:
    """Run `svn <args>` and return stdout as a string.

    Args:
      args:   svn's arguments (without the leading `"svn"`).
      cwd:    working directory; defaults to `os.getcwd()`.
      allow_failure: when True, non-zero exit returns `""` instead of raising.
      timeout_s: kill the process if it runs longer than this.
      stdin:  optional input passed via stdin.

    Raises:
      SvnNotInstalled: `svn` is not on PATH.
      SvnCommandFailed: non-zero exit (unless `allow_failure=True`).
    """

    if shutil.which("svn") is None:
        raise SvnNotInstalled(
            "svn binary not found on PATH; install Subversion (1.10+ recommended)"
        )

    try:
        result = subprocess.run(
            ["svn", *args],
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
        raise SvnNotInstalled(str(exc)) from exc
    except subprocess.TimeoutExpired as exc:
        raise SvnCommandFailed(
            f"svn {args[0] if args else '<no-args>'} timed out after {timeout_s}s",
            returncode=-1,
            args=args,
            stderr=exc.stderr.decode("utf-8", errors="replace") if exc.stderr else "",
        ) from exc

    if result.returncode != 0:
        if allow_failure:
            return ""
        raise SvnCommandFailed(
            f"svn {' '.join(args)} exited {result.returncode}: "
            f"{result.stderr.strip() or '<no stderr>'}",
            returncode=result.returncode,
            args=args,
            stderr=result.stderr,
        )

    return result.stdout


__all__ = [
    "SvnCommandFailed",
    "SvnNotInstalled",
    "run_svn",
]
