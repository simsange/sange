"""Tests for `src/sange/cli/purge.py` — the typer sub-app."""

from __future__ import annotations

import json as _json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from typer.testing import CliRunner

from sange.cli import app
from sange.core.purge import PurgePlanStore, PurgeState

pytestmark = pytest.mark.skipif(
    sys.platform == "win32", reason="POSIX-only — git + tar assumed",
)


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def repo_root(tmp_path: Path) -> Path:
    return tmp_path / "operator"


@pytest.fixture
def source_repo(tmp_path: Path) -> Path:
    """Mini source: 1 commit, 1 file."""

    if shutil.which("git") is None:
        pytest.skip("git not on PATH")

    src = tmp_path / "source"
    src.mkdir()
    env = {
        "PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin",
        "HOME": str(tmp_path),
        "GIT_AUTHOR_NAME": "Test",
        "GIT_AUTHOR_EMAIL": "test@example.invalid",
        "GIT_COMMITTER_NAME": "Test",
        "GIT_COMMITTER_EMAIL": "test@example.invalid",
        "GIT_TERMINAL_PROMPT": "0",
        "LC_ALL": "C",
    }
    for argv in (
        ["git", "init", "--initial-branch=main", "--quiet"],
        ["git", "add", "."],
    ):
        subprocess.run(argv, cwd=src, check=True, env=env, capture_output=True)
    (src / "f.txt").write_text("hi\n")
    subprocess.run(["git", "add", "f.txt"], cwd=src, check=True, env=env, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=src, check=True, env=env, capture_output=True)
    return src


class TestPlanCommand:
    def test_creates_plan(
        self, runner: CliRunner, repo_root: Path,
    ) -> None:
        result = runner.invoke(
            app,
            ["purge", "plan",
             "--path", "secret.txt",
             "--repo", str(repo_root)],
        )
        assert result.exit_code == 0
        assert "created plan" in result.output
        # plan.json was actually written.
        store = PurgePlanStore(repo_root)
        plans = store.list_plans()
        assert len(plans) == 1

    def test_json_mode_returns_plan_id(
        self, runner: CliRunner, repo_root: Path,
    ) -> None:
        result = runner.invoke(
            app,
            ["--json", "purge", "plan",
             "--path", "x.bin",
             "--repo", str(repo_root)],
        )
        assert result.exit_code == 0
        payload = _json.loads(result.output)
        assert payload["plan_id"].startswith("purge-")
        assert payload["state"] == "planned"

    def test_no_filters_rejected(
        self, runner: CliRunner, repo_root: Path,
    ) -> None:
        result = runner.invoke(
            app,
            ["purge", "plan", "--repo", str(repo_root)],
        )
        assert result.exit_code == 2
        assert "at least one" in result.output

    def test_unsupported_vcs_rejected(
        self, runner: CliRunner, repo_root: Path,
    ) -> None:
        result = runner.invoke(
            app,
            ["purge", "plan",
             "--path", "x", "--vcs", "fossil",
             "--repo", str(repo_root)],
        )
        assert result.exit_code == 2

    def test_globs_and_paths_combined(
        self, runner: CliRunner, repo_root: Path,
    ) -> None:
        result = runner.invoke(
            app,
            ["purge", "plan",
             "--path", "secret.txt",
             "--glob", "*.pem",
             "--repo", str(repo_root)],
        )
        assert result.exit_code == 0
        store = PurgePlanStore(repo_root)
        plan = store.load(store.list_plans()[0])
        assert plan.filters.paths == ["secret.txt"]
        assert plan.filters.globs == ["*.pem"]

    def test_audit_chain_records_plan_event(
        self, runner: CliRunner, repo_root: Path,
    ) -> None:
        from sange.core.audit import AuditChain
        result = runner.invoke(
            app,
            ["purge", "plan", "--path", "x", "--repo", str(repo_root)],
        )
        assert result.exit_code == 0
        chain = AuditChain(repo_root)
        events = list(chain.iter_events())
        # Exactly one event: the verb-level purge-plan event.
        assert len(events) == 1
        assert events[0].kind == "purge-plan"
        assert events[0].payload["verb"] == "plan"


class TestListCommand:
    def test_empty_repo(
        self, runner: CliRunner, repo_root: Path,
    ) -> None:
        result = runner.invoke(
            app, ["purge", "list", "--repo", str(repo_root)],
        )
        assert result.exit_code == 0
        assert "no purge plans" in result.output

    def test_lists_plans(
        self, runner: CliRunner, repo_root: Path,
    ) -> None:
        # Make 2 plans.
        for path in ("a", "b"):
            runner.invoke(
                app,
                ["purge", "plan", "--path", path, "--repo", str(repo_root)],
            )
        result = runner.invoke(
            app, ["purge", "list", "--repo", str(repo_root)],
        )
        assert result.exit_code == 0
        assert "2 plan(s)" in result.output

    def test_json_mode(
        self, runner: CliRunner, repo_root: Path,
    ) -> None:
        runner.invoke(
            app, ["purge", "plan", "--path", "a", "--repo", str(repo_root)],
        )
        result = runner.invoke(
            app, ["--json", "purge", "list", "--repo", str(repo_root)],
        )
        assert result.exit_code == 0
        payload = _json.loads(result.output)
        assert len(payload) == 1
        assert payload[0]["state"] == "planned"


class TestShowCommand:
    def test_shows_plan_json(
        self, runner: CliRunner, repo_root: Path,
    ) -> None:
        runner.invoke(
            app, ["purge", "plan", "--path", "a", "--repo", str(repo_root)],
        )
        store = PurgePlanStore(repo_root)
        pid = store.list_plans()[0]
        result = runner.invoke(
            app, ["purge", "show", pid, "--repo", str(repo_root)],
        )
        assert result.exit_code == 0
        assert pid in result.output
        assert "planned" in result.output

    def test_missing_plan_exits_2(
        self, runner: CliRunner, repo_root: Path,
    ) -> None:
        result = runner.invoke(
            app,
            ["purge", "show",
             "purge-2026-01-01T00-00-00Z-deadbeef",
             "--repo", str(repo_root)],
        )
        assert result.exit_code == 2

    def test_json_mode_returns_full_plan(
        self, runner: CliRunner, repo_root: Path,
    ) -> None:
        runner.invoke(
            app, ["purge", "plan", "--path", "a", "--repo", str(repo_root)],
        )
        store = PurgePlanStore(repo_root)
        pid = store.list_plans()[0]
        result = runner.invoke(
            app, ["--json", "purge", "show", pid, "--repo", str(repo_root)],
        )
        assert result.exit_code == 0
        payload = _json.loads(result.output)
        assert payload["plan_id"] == pid
        assert payload["state"] == "planned"


class TestMirrorAnalyzeFlow:
    def test_mirror_then_analyze(
        self, runner: CliRunner, repo_root: Path, source_repo: Path,
    ) -> None:
        # Step 1: plan
        runner.invoke(
            app,
            ["purge", "plan",
             "--path", "f.txt",
             "--remote", f"file://{source_repo}",
             "--repo", str(repo_root)],
        )
        store = PurgePlanStore(repo_root)
        pid = store.list_plans()[0]

        # Step 2: mirror
        mirror_result = runner.invoke(
            app,
            ["purge", "mirror", pid, "--repo", str(repo_root)],
        )
        assert mirror_result.exit_code == 0
        assert "mirror created" in mirror_result.output

        # Step 3: analyze
        analyze_result = runner.invoke(
            app,
            ["purge", "analyze", pid, "--repo", str(repo_root)],
        )
        assert analyze_result.exit_code == 0
        assert "deleted objects" in analyze_result.output

        # plan.mirror_path + plan.counts populated.
        plan = store.load(pid)
        assert plan.mirror_path != ""
        assert "deleted_objects" in plan.counts

    def test_analyze_without_mirror_rejected(
        self, runner: CliRunner, repo_root: Path,
    ) -> None:
        runner.invoke(
            app,
            ["purge", "plan", "--path", "a", "--repo", str(repo_root)],
        )
        store = PurgePlanStore(repo_root)
        pid = store.list_plans()[0]
        result = runner.invoke(
            app, ["purge", "analyze", pid, "--repo", str(repo_root)],
        )
        assert result.exit_code == 2
        assert "no mirror_path" in result.output


class TestBackupCommand:
    def test_backup_creates_tarball(
        self, runner: CliRunner, repo_root: Path, source_repo: Path,
    ) -> None:
        runner.invoke(
            app,
            ["purge", "plan",
             "--path", "f.txt",
             "--remote", f"file://{source_repo}",
             "--repo", str(repo_root)],
        )
        store = PurgePlanStore(repo_root)
        pid = store.list_plans()[0]
        runner.invoke(
            app, ["purge", "mirror", pid, "--repo", str(repo_root)],
        )
        result = runner.invoke(
            app, ["purge", "backup", pid, "--repo", str(repo_root)],
        )
        assert result.exit_code == 0
        assert "backup created" in result.output
        plan = store.load(pid)
        assert plan.backup_path.endswith(".tar.gz")

    def test_backup_without_mirror_rejected(
        self, runner: CliRunner, repo_root: Path,
    ) -> None:
        runner.invoke(
            app,
            ["purge", "plan", "--path", "a", "--repo", str(repo_root)],
        )
        store = PurgePlanStore(repo_root)
        pid = store.list_plans()[0]
        result = runner.invoke(
            app, ["purge", "backup", pid, "--repo", str(repo_root)],
        )
        assert result.exit_code == 2


class TestScanCommand:
    def test_scan_without_tools_installed(
        self, runner: CliRunner, repo_root: Path, source_repo: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        runner.invoke(
            app,
            ["purge", "plan",
             "--path", "f.txt",
             "--remote", f"file://{source_repo}",
             "--repo", str(repo_root)],
        )
        store = PurgePlanStore(repo_root)
        pid = store.list_plans()[0]
        runner.invoke(
            app, ["purge", "mirror", pid, "--repo", str(repo_root)],
        )
        # Empty PATH so neither gitleaks nor trufflehog resolve.
        empty_bin = repo_root.parent / "empty-bin-scan"
        empty_bin.mkdir(exist_ok=True)
        monkeypatch.setenv("PATH", str(empty_bin))
        result = runner.invoke(
            app, ["purge", "scan", pid, "--repo", str(repo_root)],
        )
        assert result.exit_code == 0
        assert "not installed" in result.output

    def test_scan_without_mirror_rejected(
        self, runner: CliRunner, repo_root: Path,
    ) -> None:
        runner.invoke(
            app,
            ["purge", "plan", "--path", "a", "--repo", str(repo_root)],
        )
        store = PurgePlanStore(repo_root)
        pid = store.list_plans()[0]
        result = runner.invoke(
            app, ["purge", "scan", pid, "--repo", str(repo_root)],
        )
        assert result.exit_code == 2


class TestAbortCommand:
    def test_abort_transitions(
        self, runner: CliRunner, repo_root: Path,
    ) -> None:
        runner.invoke(
            app,
            ["purge", "plan", "--path", "a", "--repo", str(repo_root)],
        )
        store = PurgePlanStore(repo_root)
        pid = store.list_plans()[0]
        result = runner.invoke(
            app,
            ["purge", "abort", pid,
             "--reason", "user cancelled",
             "--repo", str(repo_root)],
        )
        assert result.exit_code == 0
        assert "aborted" in result.output
        plan = store.load(pid)
        assert plan.state is PurgeState.ABORTED
        assert plan.aborted_reason == "user cancelled"

    def test_abort_already_aborted_rejected(
        self, runner: CliRunner, repo_root: Path,
    ) -> None:
        runner.invoke(
            app,
            ["purge", "plan", "--path", "a", "--repo", str(repo_root)],
        )
        store = PurgePlanStore(repo_root)
        pid = store.list_plans()[0]
        runner.invoke(
            app, ["purge", "abort", pid, "--repo", str(repo_root)],
        )
        # Second abort attempt should fail — aborted is terminal.
        result = runner.invoke(
            app, ["purge", "abort", pid, "--repo", str(repo_root)],
        )
        assert result.exit_code == 1
        assert "illegal" in result.output.lower()
