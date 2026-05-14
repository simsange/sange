"""Tests for src/sange/cli/commits.py — `sange commits` sub-app."""

from __future__ import annotations

import datetime as _dt
import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from sange.cli import app
from sange.core.lifecycle import (
    CommitJSON,
    CommitMessage,
    CommitsDirectory,
    CommitStatus,
)


_NOW = _dt.datetime(2026, 1, 1, 12, 0, 0, tzinfo=_dt.timezone.utc)


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def _draft(
    counter: int,
    type_: str = "feat",
    scope: str = "auth",
    subject: str = "subject",
) -> CommitJSON:
    return CommitJSON(
        counter=counter,
        created_at=_NOW,
        updated_at=_NOW,
        message=CommitMessage(
            type=type_,  # type: ignore[arg-type]
            scope=scope,
            subject=subject,
        ),
    )


def _seed(repo_root: Path) -> CommitsDirectory:
    """Plant three DRAFT rows + one APPROVED in <repo_root>/.sange/commits/."""

    cd = CommitsDirectory(repo_root)
    cd.save(_draft(1, "feat", "auth", "add login"))
    cd.save(_draft(2, "fix", "core", "tighten loop"))
    cd.save(_draft(3, "docs", "", "update readme"))
    approved = CommitJSON(
        counter=4,
        created_at=_NOW,
        updated_at=_NOW,
        status=CommitStatus.APPROVED,
        message=CommitMessage(type="chore", scope="deps", subject="bump"),
        approvals=[],
    )
    cd.save(approved)
    return cd


# --------------------------------------------------------------------------- #
# `sange commits list` — basic / empty / multi-row
# --------------------------------------------------------------------------- #


class TestListEmpty:
    def test_empty_queue(self, runner: CliRunner, tmp_path: Path) -> None:
        result = runner.invoke(
            app, ["commits", "list", "--repo", str(tmp_path)]
        )
        assert result.exit_code == 0
        assert "no commits" in result.output.lower()

    def test_empty_queue_json(self, runner: CliRunner, tmp_path: Path) -> None:
        result = runner.invoke(
            app, ["--json", "commits", "list", "--repo", str(tmp_path)]
        )
        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert payload["count"] == 0
        assert payload["commits"] == []


class TestListPopulated:
    def test_shows_all_rows(self, runner: CliRunner, tmp_path: Path) -> None:
        _seed(tmp_path)
        result = runner.invoke(
            app, ["commits", "list", "--repo", str(tmp_path)]
        )
        assert result.exit_code == 0
        for expected in ("add login", "tighten loop", "update readme", "bump"):
            assert expected in result.output
        assert "4 commit(s)" in result.output

    def test_counters_in_order(self, runner: CliRunner, tmp_path: Path) -> None:
        _seed(tmp_path)
        result = runner.invoke(
            app, ["--json", "commits", "list", "--repo", str(tmp_path)]
        )
        payload = json.loads(result.output)
        assert [c["counter"] for c in payload["commits"]] == [1, 2, 3, 4]

    def test_breaking_marker_in_output(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        cd = CommitsDirectory(tmp_path)
        cd.save(CommitJSON(
            counter=1,
            created_at=_NOW,
            updated_at=_NOW,
            message=CommitMessage(
                type="feat",
                scope="api",
                subject="remove v1",
                breaking_change=True,
            ),
        ))
        result = runner.invoke(
            app, ["commits", "list", "--repo", str(tmp_path)]
        )
        assert result.exit_code == 0
        # The breaking-change marker `!` follows the counter.
        assert "1!" in result.output

    def test_no_scope_shows_dash(self, runner: CliRunner, tmp_path: Path) -> None:
        cd = CommitsDirectory(tmp_path)
        cd.save(_draft(1, "docs", "", "update readme"))
        result = runner.invoke(
            app, ["commits", "list", "--repo", str(tmp_path)]
        )
        assert " - " in result.output  # scope cell renders as `-`


# --------------------------------------------------------------------------- #
# Filtering
# --------------------------------------------------------------------------- #


class TestListFilter:
    def test_status_draft_filter(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        _seed(tmp_path)
        result = runner.invoke(
            app,
            [
                "--json",
                "commits", "list",
                "--repo", str(tmp_path),
                "--status", "draft",
            ],
        )
        payload = json.loads(result.output)
        assert payload["count"] == 3
        for c in payload["commits"]:
            assert c["status"] == "draft"

    def test_status_approved_filter(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        _seed(tmp_path)
        result = runner.invoke(
            app,
            [
                "--json",
                "commits", "list",
                "--repo", str(tmp_path),
                "--status", "approved",
            ],
        )
        payload = json.loads(result.output)
        assert payload["count"] == 1
        assert payload["commits"][0]["status"] == "approved"

    def test_unknown_status_exits_2(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        result = runner.invoke(
            app,
            ["commits", "list", "--repo", str(tmp_path), "--status", "frobnicate"],
        )
        assert result.exit_code == 2
        assert "unknown status" in result.output

    def test_unknown_status_lists_valid_values(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        result = runner.invoke(
            app,
            ["commits", "list", "--repo", str(tmp_path), "--status", "x"],
        )
        assert "draft" in result.output
        assert "approved" in result.output
        assert "pushed" in result.output


# --------------------------------------------------------------------------- #
# Archive inclusion
# --------------------------------------------------------------------------- #


class TestListArchive:
    def test_archived_excluded_by_default(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        # Plant one row in archive/ directly; CommitsDirectory's archive
        # subdir layout is `.sange/commits/archive/YYYY-MM/NNNN-...json`.
        cd = CommitsDirectory(tmp_path)
        cd.save(_draft(1, "feat", "auth", "live row"))
        archive_dir = cd.commits_dir / "archive" / "2026-01"
        archive_dir.mkdir(parents=True)
        archived = CommitJSON(
            counter=99,
            created_at=_NOW,
            updated_at=_NOW,
            status=CommitStatus.ARCHIVED,
            message=CommitMessage(type="feat", scope="x", subject="archived row"),
            committed_sha="a" * 40,
            pushed_remote="origin",
        )
        (archive_dir / "0099-feat-x-archived-row.json").write_text(
            archived.model_dump_json(), encoding="utf-8"
        )
        # Default list excludes archive.
        result = runner.invoke(
            app, ["--json", "commits", "list", "--repo", str(tmp_path)]
        )
        payload = json.loads(result.output)
        assert payload["count"] == 1
        assert payload["commits"][0]["subject"] == "live row"

    def test_include_archived_flag(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        cd = CommitsDirectory(tmp_path)
        cd.save(_draft(1, "feat", "auth", "live row"))
        archive_dir = cd.commits_dir / "archive" / "2026-01"
        archive_dir.mkdir(parents=True)
        archived = CommitJSON(
            counter=99,
            created_at=_NOW,
            updated_at=_NOW,
            status=CommitStatus.ARCHIVED,
            message=CommitMessage(type="feat", scope="x", subject="archived row"),
            committed_sha="a" * 40,
            pushed_remote="origin",
        )
        (archive_dir / "0099-feat-x-archived-row.json").write_text(
            archived.model_dump_json(), encoding="utf-8"
        )
        result = runner.invoke(
            app,
            [
                "--json", "commits", "list",
                "--repo", str(tmp_path),
                "--include-archived",
            ],
        )
        payload = json.loads(result.output)
        assert payload["count"] == 2


# --------------------------------------------------------------------------- #
# Help + top-level integration
# --------------------------------------------------------------------------- #


# --------------------------------------------------------------------------- #
# `sange commits approve <counter|id>`
# --------------------------------------------------------------------------- #


class TestApprove:
    def test_approve_by_counter(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        cd = CommitsDirectory(tmp_path)
        cd.save(_draft(1, "feat", "auth", "add login"))
        result = runner.invoke(
            app,
            [
                "commits", "approve", "1",
                "--repo", str(tmp_path),
                "--actor", "alice",
            ],
        )
        assert result.exit_code == 0
        assert "approved #0001" in result.output
        assert "feat(auth): add login" in result.output
        assert "alice" in result.output

        # Verify on disk.
        rows = cd.list_all()
        assert rows[0].status is CommitStatus.APPROVED
        assert len(rows[0].approvals) == 1
        assert rows[0].approvals[0].actor == "alice"
        assert rows[0].approvals[0].via == "cli"

    def test_approve_by_id(self, runner: CliRunner, tmp_path: Path) -> None:
        cd = CommitsDirectory(tmp_path)
        commit = _draft(1, "fix", "core", "tighten loop")
        cd.save(commit)
        result = runner.invoke(
            app,
            [
                "commits", "approve", commit.id,
                "--repo", str(tmp_path),
                "--actor", "bob",
            ],
        )
        assert result.exit_code == 0
        assert "approved #0001" in result.output

    def test_approve_zero_padded_counter(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        cd = CommitsDirectory(tmp_path)
        cd.save(_draft(5, "docs", "", "update readme"))
        # The command must accept "0005" as well as "5".
        result = runner.invoke(
            app,
            [
                "commits", "approve", "0005",
                "--repo", str(tmp_path),
                "--actor", "alice",
            ],
        )
        assert result.exit_code == 0

    def test_approve_missing_counter_exits_2(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        result = runner.invoke(
            app,
            ["commits", "approve", "999", "--repo", str(tmp_path)],
        )
        assert result.exit_code == 2
        assert "no commit found" in result.output

    def test_approve_already_approved_refused(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        cd = CommitsDirectory(tmp_path)
        cd.save(_draft(1, "feat", "auth", "x"))
        runner.invoke(
            app,
            ["commits", "approve", "1", "--repo", str(tmp_path), "--actor", "alice"],
        )
        # Second approve must refuse with the state-machine error.
        result = runner.invoke(
            app,
            ["commits", "approve", "1", "--repo", str(tmp_path), "--actor", "bob"],
        )
        assert result.exit_code == 2
        # Error mentions current state + allowed-from set.
        assert "approved" in result.output
        assert "pending_review" in result.output

    def test_approve_json_mode(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        cd = CommitsDirectory(tmp_path)
        cd.save(_draft(1, "chore", "", "tidy"))
        result = runner.invoke(
            app,
            [
                "--json", "commits", "approve", "1",
                "--repo", str(tmp_path),
                "--actor", "alice",
            ],
        )
        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert payload["counter"] == 1
        assert payload["status"] == "approved"
        assert len(payload["approvals"]) == 1
        assert payload["approvals"][0]["actor"] == "alice"
        assert payload["approvals"][0]["via"] == "cli"

    def test_approve_actor_defaults_to_user_env(
        self,
        runner: CliRunner,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("USER", "testuser")
        cd = CommitsDirectory(tmp_path)
        cd.save(_draft(1, "feat", "auth", "x"))
        result = runner.invoke(
            app,
            ["commits", "approve", "1", "--repo", str(tmp_path)],
        )
        assert result.exit_code == 0
        assert "testuser" in result.output

    def test_approve_via_override(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        cd = CommitsDirectory(tmp_path)
        cd.save(_draft(1, "feat", "auth", "x"))
        result = runner.invoke(
            app,
            [
                "--json", "commits", "approve", "1",
                "--repo", str(tmp_path),
                "--actor", "alice",
                "--via", "tui",
            ],
        )
        payload = json.loads(result.output)
        assert payload["approvals"][0]["via"] == "tui"


class TestSubAppIntegration:
    def test_commits_no_args_shows_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["commits"])
        # no_args_is_help=True returns 0 or 2 depending on click version.
        assert result.exit_code in (0, 2)
        assert "list" in result.output

    def test_help_text_mentions_lifecycle(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["commits", "--help"])
        assert result.exit_code == 0
        assert "lifecycle" in result.output.lower() or "queue" in result.output.lower()
