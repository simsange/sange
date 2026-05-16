"""Tests for src/sange/cli/gitignore.py — the typer sub-app."""

from __future__ import annotations

import json as _json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from sange.cli import app


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def python_repo(tmp_path: Path) -> Path:
    (tmp_path / "pyproject.toml").write_text("", encoding="utf-8")
    return tmp_path


class TestGitignoreListCommand:
    def test_lists_shipped_profiles(self, runner: CliRunner, tmp_path: Path) -> None:
        result = runner.invoke(app, ["gitignore", "list", "--repo", str(tmp_path)])
        assert result.exit_code == 0
        assert "lang/python" in result.output
        assert "lang/node" in result.output

    def test_category_filter(self, runner: CliRunner, tmp_path: Path) -> None:
        result = runner.invoke(
            app, ["gitignore", "list", "--category", "framework", "--repo", str(tmp_path)],
        )
        assert result.exit_code == 0
        assert "framework/django" in result.output
        # lang/python should NOT appear under the framework filter.
        assert "lang/python" not in result.output

    def test_json_output(self, runner: CliRunner, tmp_path: Path) -> None:
        result = runner.invoke(
            app, ["--json", "gitignore", "list", "--repo", str(tmp_path)],
        )
        assert result.exit_code == 0
        payload = _json.loads(result.output)
        assert isinstance(payload, list)
        names = [p["name"] for p in payload]
        assert "lang/python" in names


class TestGitignoreDetectCommand:
    def test_detects_python_repo(
        self, runner: CliRunner, python_repo: Path,
    ) -> None:
        result = runner.invoke(
            app, ["gitignore", "detect", "--repo", str(python_repo)],
        )
        assert result.exit_code == 0
        assert "lang/python" in result.output

    def test_empty_repo_says_no_candidates(
        self, runner: CliRunner, tmp_path: Path,
    ) -> None:
        result = runner.invoke(
            app, ["gitignore", "detect", "--repo", str(tmp_path)],
        )
        assert result.exit_code == 0
        assert "no profile candidates" in result.output

    def test_json_output(
        self, runner: CliRunner, python_repo: Path,
    ) -> None:
        result = runner.invoke(
            app, ["--json", "gitignore", "detect", "--repo", str(python_repo)],
        )
        assert result.exit_code == 0
        payload = _json.loads(result.output)
        assert isinstance(payload, list)
        names = [p["profile"] for p in payload]
        assert "lang/python" in names


class TestGitignoreSwapCommand:
    def test_swap_writes_gitignore(
        self, runner: CliRunner, python_repo: Path,
    ) -> None:
        result = runner.invoke(
            app,
            ["gitignore", "swap", "lang/python", "--repo", str(python_repo)],
        )
        assert result.exit_code == 0, result.output
        assert "swapped" in result.output
        assert (python_repo / ".gitignore").is_file()
        assert (python_repo / ".sange" / ".active-profile").is_file()

    def test_swap_unknown_profile_exits_2(
        self, runner: CliRunner, python_repo: Path,
    ) -> None:
        result = runner.invoke(
            app,
            ["gitignore", "swap", "lang/nonexistent", "--repo", str(python_repo)],
        )
        assert result.exit_code == 2
        assert "not found" in result.output

    def test_swap_unknown_stage_exits_2(
        self, runner: CliRunner, python_repo: Path,
    ) -> None:
        result = runner.invoke(
            app,
            ["gitignore", "swap", "lang/python",
             "--stage", "weekend",
             "--repo", str(python_repo)],
        )
        # `compose()` validates against the binary VALID_STAGES
        # ("dev" / "prod") and raises CompositionError for anything
        # else. The CLI surfaces that as exit 2.
        # (The variant-aware `compose_variant()` accepts custom
        # stage names that profiles declare under
        # [patterns.stages.<stage>] — that's the path forward for
        # extended stages.)
        assert result.exit_code == 2
        assert "stage must be one of" in result.output

    def test_swap_json_output(
        self, runner: CliRunner, python_repo: Path,
    ) -> None:
        result = runner.invoke(
            app,
            ["--json", "gitignore", "swap", "lang/python",
             "--repo", str(python_repo)],
        )
        assert result.exit_code == 0
        payload = _json.loads(result.output)
        assert payload["profiles"] == ["lang/python"]
        assert payload["stage"] == "dev"
        assert payload["bytes_written"] > 0


class TestGitignoreCurrentCommand:
    def test_no_active_profile(
        self, runner: CliRunner, tmp_path: Path,
    ) -> None:
        result = runner.invoke(
            app, ["gitignore", "current", "--repo", str(tmp_path)],
        )
        assert result.exit_code == 0
        assert "no active profile" in result.output

    def test_reads_active_profile(
        self, runner: CliRunner, python_repo: Path,
    ) -> None:
        # First swap to set a profile.
        runner.invoke(
            app,
            ["gitignore", "swap", "lang/python", "--repo", str(python_repo)],
        )
        result = runner.invoke(
            app, ["gitignore", "current", "--repo", str(python_repo)],
        )
        assert result.exit_code == 0
        assert "lang/python" in result.output
        assert "dev" in result.output

    def test_json_output(
        self, runner: CliRunner, python_repo: Path,
    ) -> None:
        runner.invoke(
            app,
            ["gitignore", "swap", "lang/python", "--repo", str(python_repo)],
        )
        result = runner.invoke(
            app, ["--json", "gitignore", "current", "--repo", str(python_repo)],
        )
        assert result.exit_code == 0
        payload = _json.loads(result.output)
        assert payload["active"]["profiles"] == ["lang/python"]
        assert payload["active"]["stage"] == "dev"


class TestGitignoreRecoverCommand:
    def test_no_journals(self, runner: CliRunner, tmp_path: Path) -> None:
        result = runner.invoke(
            app, ["gitignore", "recover", "--repo", str(tmp_path)],
        )
        assert result.exit_code == 0
        assert "no in-progress" in result.output

    def test_recovers_planted_journal(
        self, runner: CliRunner, python_repo: Path,
    ) -> None:
        # Plant a journal at phase=prepared.
        from sange.core.gitignore import (
            ProfileRegistry,
            compose,
            default_registry_roots,
        )
        reg = ProfileRegistry(default_registry_roots(python_repo))
        planned = compose(["lang/python"], stage="dev", registry=reg)
        import hashlib
        journal_dir = python_repo / ".sange" / ".recovery"
        journal_dir.mkdir(parents=True, exist_ok=True)
        (journal_dir / "swap-20260516T120000Z.json").write_text(_json.dumps({
            "journal_id": "swap-20260516T120000Z",
            "profiles": ["lang/python"],
            "stage": "dev",
            "planned_sha256": hashlib.sha256(planned.encode("utf-8")).hexdigest(),
            "old_gitignore_content": None,
            "old_active_profile_content": None,
            "phase": "prepared",
            "started_at": "2026-05-16T12:00:00+00:00",
            "planned_content": planned,
        }))

        result = runner.invoke(
            app, ["gitignore", "recover", "--repo", str(python_repo)],
        )
        assert result.exit_code == 0
        assert "recovered" in result.output
        # Artifacts now exist.
        assert (python_repo / ".gitignore").is_file()
        assert (python_repo / ".sange" / ".active-profile").is_file()
