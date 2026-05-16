"""Tests for src/sange/cli/hooks.py — the typer sub-app."""

from __future__ import annotations

import json as _json
import stat
import sys
from pathlib import Path

import pytest
from typer.testing import CliRunner

from sange.cli import app


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """Working repo with `.git/` skeleton + a passing pre-commit hook."""

    r = tmp_path / "repo"
    (r / ".git" / "hooks").mkdir(parents=True)
    hook = r / ".sange" / "hooks" / "pre-commit" / "10-ok.sh"
    hook.parent.mkdir(parents=True, exist_ok=True)
    hook.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    hook.chmod(hook.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return r


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX-only shell hooks")
class TestHooksRunCommand:
    def test_no_hooks(self, runner: CliRunner, tmp_path: Path) -> None:
        result = runner.invoke(
            app, ["hooks", "run", "pre-commit", "--repo", str(tmp_path)],
        )
        assert result.exit_code == 0
        assert "no hooks" in result.output

    def test_passing_hook(self, runner: CliRunner, repo: Path) -> None:
        result = runner.invoke(
            app, ["hooks", "run", "pre-commit", "--repo", str(repo)],
        )
        assert result.exit_code == 0, result.output
        assert "passed" in result.output
        assert "ok.sh" in result.output

    def test_failing_hook_exits_1(
        self, runner: CliRunner, repo: Path,
    ) -> None:
        fail = repo / ".sange" / "hooks" / "pre-commit" / "20-fail.sh"
        fail.write_text("#!/usr/bin/env bash\nexit 1\n", encoding="utf-8")
        fail.chmod(fail.stat().st_mode | stat.S_IXUSR)
        result = runner.invoke(
            app, ["hooks", "run", "pre-commit", "--repo", str(repo)],
        )
        # First hook passed, second failed → exit 1.
        assert result.exit_code == 1
        assert "failed" in result.output

    def test_json_output(self, runner: CliRunner, repo: Path) -> None:
        result = runner.invoke(
            app, ["--json", "hooks", "run", "pre-commit", "--repo", str(repo)],
        )
        assert result.exit_code == 0
        payload = _json.loads(result.output)
        assert payload["event"] == "pre-commit"
        assert payload["all_passed"] is True
        assert payload["counts"]["passed"] == 1


class TestHooksListCommand:
    def test_no_hooks(self, runner: CliRunner, tmp_path: Path) -> None:
        result = runner.invoke(
            app, ["hooks", "list", "--repo", str(tmp_path)],
        )
        assert result.exit_code == 0
        assert "no hooks" in result.output

    def test_lists_discovered(self, runner: CliRunner, repo: Path) -> None:
        result = runner.invoke(
            app, ["hooks", "list", "--repo", str(repo)],
        )
        assert result.exit_code == 0
        assert "pre-commit" in result.output
        assert "ok.sh" in result.output

    def test_event_filter(self, runner: CliRunner, repo: Path) -> None:
        # Add another event so we can verify the filter.
        pp = repo / ".sange" / "hooks" / "pre-push" / "10-z.sh"
        pp.parent.mkdir(parents=True, exist_ok=True)
        pp.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
        pp.chmod(pp.stat().st_mode | stat.S_IXUSR)
        result = runner.invoke(
            app, ["hooks", "list", "--event", "pre-commit", "--repo", str(repo)],
        )
        assert "pre-commit" in result.output
        assert "z.sh" not in result.output

    def test_json_output(self, runner: CliRunner, repo: Path) -> None:
        result = runner.invoke(
            app, ["--json", "hooks", "list", "--repo", str(repo)],
        )
        assert result.exit_code == 0
        payload = _json.loads(result.output)
        assert isinstance(payload, list)
        assert payload[0]["event"] == "pre-commit"
        assert payload[0]["name"] == "ok.sh"


class TestHooksInstallCommand:
    def test_installs_shim_when_hook_exists(
        self, runner: CliRunner, repo: Path,
    ) -> None:
        result = runner.invoke(
            app, ["hooks", "install", "--repo", str(repo)],
        )
        assert result.exit_code == 0, result.output
        shim = repo / ".git" / "hooks" / "pre-commit"
        assert shim.is_file()
        # Marker present.
        assert "SANGE-HOOK-SHIM" in shim.read_text(encoding="utf-8")

    def test_non_git_repo_exits_2(
        self, runner: CliRunner, tmp_path: Path,
    ) -> None:
        result = runner.invoke(
            app, ["hooks", "install", "--repo", str(tmp_path)],
        )
        assert result.exit_code == 2

    def test_json_output(self, runner: CliRunner, repo: Path) -> None:
        result = runner.invoke(
            app, ["--json", "hooks", "install", "--repo", str(repo)],
        )
        assert result.exit_code == 0
        payload = _json.loads(result.output)
        installed = [r for r in payload if r["status"] == "installed"]
        assert len(installed) == 1
        assert installed[0]["event"] == "pre-commit"


class TestHooksUninstallCommand:
    def test_removes_sange_shim(self, runner: CliRunner, repo: Path) -> None:
        runner.invoke(app, ["hooks", "install", "--repo", str(repo)])
        assert (repo / ".git" / "hooks" / "pre-commit").is_file()
        result = runner.invoke(
            app, ["hooks", "uninstall", "--repo", str(repo)],
        )
        assert result.exit_code == 0
        assert "removed" in result.output
        assert not (repo / ".git" / "hooks" / "pre-commit").exists()


class TestHooksStatusCommand:
    def test_summary(self, runner: CliRunner, repo: Path) -> None:
        runner.invoke(app, ["hooks", "install", "--repo", str(repo)])
        result = runner.invoke(
            app, ["hooks", "status", "--repo", str(repo)],
        )
        assert result.exit_code == 0
        assert "pre-commit" in result.output
        assert "sange" in result.output  # the shim install state

    def test_empty_repo(self, runner: CliRunner, tmp_path: Path) -> None:
        result = runner.invoke(
            app, ["hooks", "status", "--repo", str(tmp_path)],
        )
        assert result.exit_code == 0
        assert "no hooks or shims" in result.output


# --------------------------------------------------------------------------- #
# T-103 — `sange hooks gates / add / remove`
# --------------------------------------------------------------------------- #


class TestHooksGatesCommand:
    def test_lists_shipped(self, runner: CliRunner, tmp_path: Path) -> None:
        result = runner.invoke(
            app, ["hooks", "gates", "--repo", str(tmp_path)],
        )
        assert result.exit_code == 0
        # Every shipped gate appears.
        for name in ("gitleaks", "trufflehog", "make-test", "make-lint"):
            assert name in result.output

    def test_json_output(self, runner: CliRunner, tmp_path: Path) -> None:
        result = runner.invoke(
            app, ["--json", "hooks", "gates", "--repo", str(tmp_path)],
        )
        assert result.exit_code == 0
        payload = _json.loads(result.output)
        names = [g["name"] for g in payload]
        assert "gitleaks" in names


class TestHooksAddCommand:
    def test_add_unknown_gate_exits_2(
        self, runner: CliRunner, tmp_path: Path,
    ) -> None:
        result = runner.invoke(
            app, ["hooks", "add", "no-such-gate", "--repo", str(tmp_path)],
        )
        assert result.exit_code == 2
        assert "not found" in result.output

    def test_add_gitleaks(self, runner: CliRunner, tmp_path: Path) -> None:
        result = runner.invoke(
            app, ["hooks", "add", "gitleaks", "--repo", str(tmp_path)],
        )
        assert result.exit_code == 0, result.output
        target = tmp_path / ".sange" / "hooks" / "pre-commit" / "05-gitleaks.sh"
        assert target.is_file()
        # The install-hint note prints below the action.
        assert "Install hint" in result.output

    def test_add_event_filter(self, runner: CliRunner, tmp_path: Path) -> None:
        # gitleaks only has pre-commit, so this filter is a no-op for it.
        result = runner.invoke(
            app,
            ["hooks", "add", "gitleaks",
             "--event", "pre-commit", "--repo", str(tmp_path)],
        )
        assert result.exit_code == 0
        assert (tmp_path / ".sange" / "hooks" / "pre-commit" / "05-gitleaks.sh").is_file()


class TestHooksRemoveCommand:
    def test_remove_after_add(self, runner: CliRunner, tmp_path: Path) -> None:
        runner.invoke(
            app, ["hooks", "add", "gitleaks", "--repo", str(tmp_path)],
        )
        result = runner.invoke(
            app, ["hooks", "remove", "gitleaks", "--repo", str(tmp_path)],
        )
        assert result.exit_code == 0
        # Human-readable output uses the `[-]` marker, not the word "removed".
        assert "[-]" in result.output
        assert not (tmp_path / ".sange" / "hooks" / "pre-commit" / "05-gitleaks.sh").exists()

    def test_remove_unknown_gate_exits_2(
        self, runner: CliRunner, tmp_path: Path,
    ) -> None:
        result = runner.invoke(
            app, ["hooks", "remove", "no-such", "--repo", str(tmp_path)],
        )
        assert result.exit_code == 2
