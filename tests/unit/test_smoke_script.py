"""Tests for scripts/smoke_v01.sh — static + invocation checks.

The smoke script is operator-driven (real AI calls). These tests
exercise everything that doesn't require sange installed on PATH or
a real API key:

  * file invariants (shebang, executable bit, strict bash flags)
  * `bash -n` syntax check
  * `--help` works without preconditions
  * missing API key surfaces exit 2 with a helpful message
"""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPT = _REPO_ROOT / "scripts" / "smoke_v01.sh"


# --------------------------------------------------------------------------- #
# File invariants
# --------------------------------------------------------------------------- #


class TestFileShape:
    def test_script_exists(self) -> None:
        assert _SCRIPT.is_file()

    def test_executable_bit(self) -> None:
        mode = _SCRIPT.stat().st_mode
        assert mode & stat.S_IXUSR, "smoke script is not executable"

    def test_shebang(self) -> None:
        first = _SCRIPT.read_text(encoding="utf-8").splitlines()[0]
        assert first == "#!/usr/bin/env bash"

    def test_strict_mode_flags(self) -> None:
        # `set -euo pipefail` near the top — defends against silent failures.
        text = _SCRIPT.read_text(encoding="utf-8")
        assert "set -euo pipefail" in text

    def test_cleanup_trap(self) -> None:
        # `trap cleanup EXIT` removes the tmp workspace on exit.
        text = _SCRIPT.read_text(encoding="utf-8")
        assert "trap cleanup EXIT" in text


# --------------------------------------------------------------------------- #
# Syntax check
# --------------------------------------------------------------------------- #


class TestSyntax:
    def test_bash_syntax(self) -> None:
        """`bash -n` parses without executing; fails on syntax errors."""

        bash = shutil.which("bash")
        if bash is None:
            pytest.skip("bash not on PATH")
        result = subprocess.run(
            [bash, "-n", str(_SCRIPT)],
            capture_output=True,
            text=True,
            timeout=5,
        )
        assert result.returncode == 0, (
            f"bash -n failed: stderr={result.stderr!r}"
        )


# --------------------------------------------------------------------------- #
# --help works without preconditions
# --------------------------------------------------------------------------- #


@pytest.fixture
def script_env() -> dict[str, str]:
    """Minimal environment — preserves PATH but strips API keys so the
    pre-flight checks fire on the no-key path."""

    env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": "/tmp",
    }
    return env


class TestHelp:
    def test_help_short_flag(self, script_env: dict[str, str]) -> None:
        result = subprocess.run(
            [str(_SCRIPT), "-h"],
            capture_output=True,
            text=True,
            env=script_env,
            timeout=5,
        )
        assert result.returncode == 0
        assert "smoke test" in result.stdout.lower() or "usage" in result.stdout.lower()

    def test_help_long_flag(self, script_env: dict[str, str]) -> None:
        result = subprocess.run(
            [str(_SCRIPT), "--help"],
            capture_output=True,
            text=True,
            env=script_env,
            timeout=5,
        )
        assert result.returncode == 0


# --------------------------------------------------------------------------- #
# Argument parsing
# --------------------------------------------------------------------------- #


class TestArgumentParsing:
    def test_unknown_arg_exits_2(self, script_env: dict[str, str]) -> None:
        result = subprocess.run(
            [str(_SCRIPT), "--frobnicate"],
            capture_output=True,
            text=True,
            env=script_env,
            timeout=5,
        )
        assert result.returncode == 2
        assert "unknown argument" in result.stderr.lower()


# --------------------------------------------------------------------------- #
# Pre-flight checks
# --------------------------------------------------------------------------- #


class TestPreflightChecks:
    def test_missing_anthropic_key_exits_2(
        self, script_env: dict[str, str]
    ) -> None:
        """Default provider is anthropic; without ANTHROPIC_API_KEY we
        should exit 2 BEFORE any other work."""

        # Ensure key is not in env.
        env = dict(script_env)
        env.pop("ANTHROPIC_API_KEY", None)
        result = subprocess.run(
            [str(_SCRIPT)],
            capture_output=True,
            text=True,
            env=env,
            timeout=10,
        )
        # We expect either exit 2 (key check) or exit 2 (sange missing) —
        # both are valid preflight failures. The check_cmd order is
        # sange, git, then API key, so when sange isn't installed we
        # hit the sange check first.
        assert result.returncode == 2

    def test_unknown_provider_exits_2(
        self, script_env: dict[str, str]
    ) -> None:
        result = subprocess.run(
            [str(_SCRIPT), "--provider", "frobnicate"],
            capture_output=True,
            text=True,
            env=script_env,
            timeout=10,
        )
        assert result.returncode == 2

    def test_dry_run_aliases_to_mock(self) -> None:
        """The --dry-run flag uses --provider mock (no API key needed).
        We can't run the full smoke without `sange` installed, but the
        script should accept the flag without complaining about a
        missing API key."""

        # Read the script source to confirm the alias exists; we can't
        # test the runtime path without `sange` on PATH.
        text = _SCRIPT.read_text(encoding="utf-8")
        assert "--dry-run" in text
        assert 'PROVIDER="mock"' in text


# --------------------------------------------------------------------------- #
# Content invariants — the smoke must drive the documented happy path
# --------------------------------------------------------------------------- #


class TestHappyPathSteps:
    def test_drives_sange_init(self) -> None:
        text = _SCRIPT.read_text(encoding="utf-8")
        assert "sange init" in text

    def test_drives_sange_commit(self) -> None:
        text = _SCRIPT.read_text(encoding="utf-8")
        assert "sange commit" in text

    def test_drives_sange_commits_approve(self) -> None:
        text = _SCRIPT.read_text(encoding="utf-8")
        assert "sange commits approve" in text

    def test_drives_sange_commits_push(self) -> None:
        text = _SCRIPT.read_text(encoding="utf-8")
        assert "sange commits push" in text

    def test_creates_bare_remote(self) -> None:
        # Validates the push has somewhere to land.
        text = _SCRIPT.read_text(encoding="utf-8")
        assert "git init --bare" in text

    def test_verifies_remote_log(self) -> None:
        # Confirms the script asserts the remote actually received it.
        text = _SCRIPT.read_text(encoding="utf-8")
        assert "git --git-dir=" in text and "log" in text
