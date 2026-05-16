"""Tests for src/sange/cli/audit.py — the typer sub-app."""

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
def repo_with_chain(tmp_path: Path) -> Path:
    """Repo with 3 appended audit events."""

    from sange.core.audit import AuditChain, EventKind

    repo = tmp_path / "repo"
    repo.mkdir()
    chain = AuditChain(repo)
    chain.append(EventKind.COMMIT_DRAFT, actor="alice", payload={"counter": 1})
    chain.append(EventKind.COMMIT_APPROVE, actor="alice", payload={"counter": 1})
    chain.append(EventKind.COMMIT_PUSH, actor="alice", payload={"counter": 1})
    return repo


class TestAuditVerifyCommand:
    def test_empty_repo_passes(self, runner: CliRunner, tmp_path: Path) -> None:
        result = runner.invoke(app, ["audit", "verify", "--repo", str(tmp_path)])
        assert result.exit_code == 0
        assert "0 record" in result.output

    def test_clean_chain_passes(
        self, runner: CliRunner, repo_with_chain: Path,
    ) -> None:
        result = runner.invoke(
            app, ["audit", "verify", "--repo", str(repo_with_chain)],
        )
        assert result.exit_code == 0
        assert "3 record" in result.output

    def test_tampered_chain_fails(
        self, runner: CliRunner, repo_with_chain: Path,
    ) -> None:
        # Mutate a mid-chain record on disk.
        shard = next((repo_with_chain / ".sange" / "audit").glob("*.jsonl"))
        lines = shard.read_text(encoding="utf-8").splitlines()
        rec = _json.loads(lines[1])
        rec["actor"] = "attacker"
        lines[1] = _json.dumps(rec, sort_keys=True, separators=(",", ":"))
        shard.write_text("\n".join(lines) + "\n", encoding="utf-8")

        result = runner.invoke(
            app, ["audit", "verify", "--repo", str(repo_with_chain)],
        )
        assert result.exit_code == 1
        assert "FAILED" in result.output

    def test_json_output(self, runner: CliRunner, repo_with_chain: Path) -> None:
        result = runner.invoke(
            app,
            ["--json", "audit", "verify", "--repo", str(repo_with_chain)],
        )
        assert result.exit_code == 0
        payload = _json.loads(result.output)
        assert payload["verified"] is True
        assert payload["records_checked"] == 3


class TestAuditListCommand:
    def test_empty_repo(self, runner: CliRunner, tmp_path: Path) -> None:
        result = runner.invoke(app, ["audit", "list", "--repo", str(tmp_path)])
        assert result.exit_code == 0
        assert "no audit records" in result.output

    def test_lists_records(
        self, runner: CliRunner, repo_with_chain: Path,
    ) -> None:
        result = runner.invoke(
            app, ["audit", "list", "--repo", str(repo_with_chain)],
        )
        assert result.exit_code == 0
        assert "commit-draft" in result.output
        assert "commit-approve" in result.output
        assert "commit-push" in result.output
        assert "3 record(s)" in result.output

    def test_kind_filter(
        self, runner: CliRunner, repo_with_chain: Path,
    ) -> None:
        result = runner.invoke(
            app,
            ["audit", "list", "--kind", "commit-push",
             "--repo", str(repo_with_chain)],
        )
        assert result.exit_code == 0
        assert "commit-push" in result.output
        assert "commit-draft" not in result.output

    def test_json_output(
        self, runner: CliRunner, repo_with_chain: Path,
    ) -> None:
        result = runner.invoke(
            app, ["--json", "audit", "list", "--repo", str(repo_with_chain)],
        )
        assert result.exit_code == 0
        payload = _json.loads(result.output)
        assert len(payload) == 3
        assert payload[0]["kind"] == "commit-draft"


class TestAuditTailCommand:
    def test_tail_returns_last_n(
        self, runner: CliRunner, repo_with_chain: Path,
    ) -> None:
        result = runner.invoke(
            app, ["audit", "tail", "--n", "2", "--repo", str(repo_with_chain)],
        )
        assert result.exit_code == 0
        assert "commit-approve" in result.output
        assert "commit-push" in result.output
        assert "commit-draft" not in result.output

    def test_tail_zero(
        self, runner: CliRunner, repo_with_chain: Path,
    ) -> None:
        result = runner.invoke(
            app, ["audit", "tail", "--n", "0", "--repo", str(repo_with_chain)],
        )
        assert result.exit_code == 0
        assert "no audit records" in result.output

    def test_negative_n_rejected(
        self, runner: CliRunner, tmp_path: Path,
    ) -> None:
        result = runner.invoke(
            app, ["audit", "tail", "--n", "-1", "--repo", str(tmp_path)],
        )
        assert result.exit_code == 2


class TestAuditAppendCommand:
    def test_basic_append(self, runner: CliRunner, tmp_path: Path) -> None:
        result = runner.invoke(
            app,
            ["audit", "append", "generic",
             "--actor", "alice",
             "--repo", str(tmp_path)],
        )
        assert result.exit_code == 0
        assert "appended generic" in result.output
        # Shard exists.
        shards = list((tmp_path / ".sange" / "audit").glob("*.jsonl"))
        assert len(shards) == 1

    def test_payload(self, runner: CliRunner, tmp_path: Path) -> None:
        result = runner.invoke(
            app,
            ["--json", "audit", "append", "ai-call",
             "--actor", "alice",
             "--payload", '{"provider": "mock", "tokens": 42}',
             "--repo", str(tmp_path)],
        )
        assert result.exit_code == 0
        payload = _json.loads(result.output)
        assert payload["kind"] == "ai-call"
        assert payload["payload"]["provider"] == "mock"
        assert payload["payload"]["tokens"] == 42

    def test_invalid_payload_exits_2(
        self, runner: CliRunner, tmp_path: Path,
    ) -> None:
        result = runner.invoke(
            app,
            ["audit", "append", "generic",
             "--actor", "alice",
             "--payload", "{not valid json",
             "--repo", str(tmp_path)],
        )
        assert result.exit_code == 2
        assert "not valid JSON" in result.output

    def test_non_dict_payload_rejected(
        self, runner: CliRunner, tmp_path: Path,
    ) -> None:
        result = runner.invoke(
            app,
            ["audit", "append", "generic",
             "--actor", "alice",
             "--payload", "[1, 2, 3]",
             "--repo", str(tmp_path)],
        )
        assert result.exit_code == 2
        assert "JSON object" in result.output
