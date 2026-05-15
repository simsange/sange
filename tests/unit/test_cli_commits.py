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

_NOW = _dt.datetime(2026, 1, 1, 12, 0, 0, tzinfo=_dt.UTC)


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
# `sange commits new` — manual draft creation (T-042)
# --------------------------------------------------------------------------- #


class TestCommitsNew:
    def test_minimal_invocation(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        result = runner.invoke(
            app,
            ["commits", "new", "docs", "tweak readme", "--repo", str(tmp_path)],
        )
        assert result.exit_code == 0
        assert "drafted #0001" in result.output
        assert "docs: tweak readme" in result.output

        rows = CommitsDirectory(tmp_path).list_all()
        assert len(rows) == 1
        assert rows[0].status is CommitStatus.DRAFT
        assert rows[0].message.type == "docs"
        assert rows[0].message.subject == "tweak readme"
        assert rows[0].message.scope == ""
        assert rows[0].message.breaking_change is False
        assert rows[0].counter == 1

    def test_all_options(self, runner: CliRunner, tmp_path: Path) -> None:
        result = runner.invoke(
            app,
            [
                "commits", "new", "feat", "add SSO",
                "--repo", str(tmp_path),
                "--scope", "auth",
                "--body", "Body line.",
                "--breaking-change",
                "--co-author", "Bob <bob@example.com>",
                "--co-author", "Cathy <cathy@example.com>",
                "--reference", "#42",
                "--reference", "JIRA-7",
                "--branch", "release/v2",
            ],
        )
        assert result.exit_code == 0
        assert "feat(auth)!: add SSO" in result.output

        rows = CommitsDirectory(tmp_path).list_all()
        c = rows[0]
        assert c.message.type == "feat"
        assert c.message.scope == "auth"
        assert c.message.subject == "add SSO"
        assert c.message.body == "Body line."
        assert c.message.breaking_change is True
        assert c.message.co_authors == [
            "Bob <bob@example.com>",
            "Cathy <cathy@example.com>",
        ]
        assert c.message.references == ["#42", "JIRA-7"]
        assert c.branch == "release/v2"

    def test_stdin_body(self, runner: CliRunner, tmp_path: Path) -> None:
        result = runner.invoke(
            app,
            [
                "commits", "new", "chore", "from stdin",
                "--repo", str(tmp_path),
                "--body", "-",
            ],
            input="Line one.\nLine two.\n",
        )
        assert result.exit_code == 0
        rows = CommitsDirectory(tmp_path).list_all()
        assert rows[0].message.body == "Line one.\nLine two.\n"

    def test_json_output(self, runner: CliRunner, tmp_path: Path) -> None:
        result = runner.invoke(
            app,
            [
                "--json",
                "commits", "new", "fix", "patch a bug",
                "--repo", str(tmp_path),
                "--scope", "core",
            ],
        )
        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert payload["counter"] == 1
        assert payload["status"] == "draft"
        assert payload["type"] == "fix"
        assert payload["scope"] == "core"
        assert payload["subject"] == "patch a bug"
        assert payload["breaking_change"] is False
        assert payload["path"].endswith(".json")
        assert "id" in payload and len(payload["id"]) == 32

    def test_invalid_type_exits_2(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        result = runner.invoke(
            app,
            [
                "commits", "new", "wibble", "should fail",
                "--repo", str(tmp_path),
            ],
        )
        assert result.exit_code == 2
        assert "unknown type" in result.output

    def test_invalid_scope_exits_2(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        # Scope must be slug-like (lowercase / digits / hyphens) per
        # CommitMessage._SCOPE_RE. Underscore violates the regex.
        result = runner.invoke(
            app,
            [
                "commits", "new", "feat", "bad scope",
                "--repo", str(tmp_path),
                "--scope", "BAD_SCOPE",
            ],
        )
        assert result.exit_code == 2
        assert "invalid commit message" in result.output

    def test_counter_monotonic(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        # Two back-to-back invocations should produce counters 1 + 2.
        first = runner.invoke(
            app,
            ["commits", "new", "feat", "first", "--repo", str(tmp_path)],
        )
        second = runner.invoke(
            app,
            ["commits", "new", "fix", "second", "--repo", str(tmp_path)],
        )
        assert first.exit_code == 0
        assert second.exit_code == 0
        assert "drafted #0001" in first.output
        assert "drafted #0002" in second.output

        rows = CommitsDirectory(tmp_path).list_all()
        assert {r.counter for r in rows} == {1, 2}


# --------------------------------------------------------------------------- #
# `sange commits ai` — AI-driven draft creation (T-043)
# --------------------------------------------------------------------------- #


def _patch_mock_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    """Inject a MockProvider that returns valid CommitMessageResult JSON.

    Mirrors the pattern in tests/unit/test_cli.py::test_commit_records_telemetry.
    The default MockProvider's echo-mode produces invalid JSON; this override
    returns a fixed canned response."""

    from sange.adapters.ai import (
        CompletionResponse,
        FinishReason,
        MockProvider,
        Usage,
        _protocol,
    )
    from sange.core.enhancer import enhancer as enhancer_mod

    class _Mock(MockProvider):
        def complete(self, request):  # type: ignore[override]
            return CompletionResponse(
                text=json.dumps({
                    "type": "feat", "scope": "ai", "subject": "from-mock",
                    "body": "Body from canned mock.", "breaking_change": False,
                }),
                finish_reason=FinishReason.STOP,
                usage=Usage(model=request.model),
                provider="mock",
                model=request.model,
            )

    def _patched(name: str, **kwargs):
        return _Mock() if name == "mock" else _protocol.get_provider(name, **kwargs)

    monkeypatch.setattr(_protocol, "get_provider", _patched)
    monkeypatch.setattr(enhancer_mod, "get_provider", _patched)


class TestCommitsAi:
    def test_help_shows_ai_verb(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["commits", "--help"])
        assert result.exit_code == 0
        assert "ai" in result.output
        assert "Generate a commit message via AI" in result.output

    def test_ai_saves_draft_by_default(
        self,
        runner: CliRunner,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        _patch_mock_provider(monkeypatch)

        result = runner.invoke(
            app,
            [
                "commits", "ai",
                "--repo", str(tmp_path),
                "--no-telemetry",
            ],
            input="+ added a flow\n",
        )
        assert result.exit_code == 0, result.output
        assert "feat(ai): from-mock" in result.output

        # The DRAFT row should exist on disk.
        rows = CommitsDirectory(tmp_path).list_all()
        assert len(rows) == 1
        assert rows[0].status is CommitStatus.DRAFT
        assert rows[0].message.subject == "from-mock"
        assert rows[0].message.body == "Body from canned mock."

    def test_ai_no_save(
        self,
        runner: CliRunner,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        _patch_mock_provider(monkeypatch)

        result = runner.invoke(
            app,
            [
                "commits", "ai",
                "--repo", str(tmp_path),
                "--no-save",
                "--no-telemetry",
            ],
            input="+ added a flow\n",
        )
        assert result.exit_code == 0, result.output
        assert "feat(ai): from-mock" in result.output

        # --no-save → no DRAFT row written.
        assert list(CommitsDirectory(tmp_path).list_all()) == []

    def test_ai_empty_diff_exits_2(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        # An empty stdin pipe yields an empty diff → exit 2.
        result = runner.invoke(
            app,
            [
                "commits", "ai",
                "--repo", str(tmp_path),
                "--no-telemetry",
                "--no-save",
            ],
            input="",
        )
        assert result.exit_code == 2
        assert "diff is empty" in result.output

    def test_ai_json_mode(
        self,
        runner: CliRunner,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        _patch_mock_provider(monkeypatch)

        result = runner.invoke(
            app,
            [
                "--json",
                "commits", "ai",
                "--repo", str(tmp_path),
                "--no-telemetry",
            ],
            input="+ change\n",
        )
        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert payload["type"] == "feat"
        assert payload["scope"] == "ai"
        assert payload["subject"] == "from-mock"
        assert payload["draft_counter"] == 1
        assert payload["draft_path"]


# --------------------------------------------------------------------------- #
# `sange commits reopen <counter|id>` — the only backward transition
# --------------------------------------------------------------------------- #


class TestCommitsReopen:
    def test_reopen_approved_to_draft(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        cd = CommitsDirectory(tmp_path)
        cd.save(
            CommitJSON(
                counter=1,
                created_at=_NOW,
                updated_at=_NOW,
                status=CommitStatus.APPROVED,
                message=CommitMessage(type="feat", scope="auth", subject="x"),
            )
        )
        result = runner.invoke(
            app,
            ["commits", "reopen", "1", "--repo", str(tmp_path)],
        )
        assert result.exit_code == 0
        assert "reopened #0001" in result.output
        assert "approved → draft" in result.output

        rows = cd.list_all()
        assert rows[0].status is CommitStatus.DRAFT

    def test_reopen_draft_is_no_op(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        cd = CommitsDirectory(tmp_path)
        cd.save(_draft(1, "feat", "auth", "x"))
        result = runner.invoke(
            app,
            ["commits", "reopen", "1", "--repo", str(tmp_path)],
        )
        assert result.exit_code == 0
        assert "no-op" in result.output

        rows = cd.list_all()
        assert rows[0].status is CommitStatus.DRAFT

    def test_reopen_clears_committed_sha_and_remote(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        # COMMITTED commit gets reopened — committed_sha must clear.
        cd = CommitsDirectory(tmp_path)
        cd.save(
            CommitJSON(
                counter=1,
                created_at=_NOW,
                updated_at=_NOW,
                status=CommitStatus.COMMITTED,
                message=CommitMessage(type="feat", scope="", subject="x"),
                committed_sha="abc123def456",
            )
        )
        result = runner.invoke(
            app,
            ["commits", "reopen", "1", "--repo", str(tmp_path)],
        )
        assert result.exit_code == 0

        rows = cd.list_all()
        assert rows[0].status is CommitStatus.DRAFT
        assert rows[0].committed_sha == ""
        assert rows[0].pushed_remote == ""

    def test_reopen_json(self, runner: CliRunner, tmp_path: Path) -> None:
        cd = CommitsDirectory(tmp_path)
        cd.save(
            CommitJSON(
                counter=1,
                created_at=_NOW,
                updated_at=_NOW,
                status=CommitStatus.APPROVED,
                message=CommitMessage(type="fix", scope="", subject="x"),
            )
        )
        result = runner.invoke(
            app,
            ["--json", "commits", "reopen", "1", "--repo", str(tmp_path)],
        )
        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert payload["status"] == "draft"
        assert payload["previous_status"] == "approved"
        assert payload["no_op"] is False

    def test_reopen_missing_target_exits_2(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        result = runner.invoke(
            app,
            ["commits", "reopen", "999", "--repo", str(tmp_path)],
        )
        assert result.exit_code == 2
        assert "no commit found" in result.output


# --------------------------------------------------------------------------- #
# `sange commits submit <counter|id>` (T-044a)
# --------------------------------------------------------------------------- #


class TestCommitsSubmit:
    def test_submit_draft(self, runner: CliRunner, tmp_path: Path) -> None:
        cd = CommitsDirectory(tmp_path)
        cd.save(_draft(1, "feat", "auth", "add login"))
        result = runner.invoke(
            app,
            ["commits", "submit", "1", "--repo", str(tmp_path)],
        )
        assert result.exit_code == 0
        assert "submitted #0001" in result.output
        assert "feat(auth): add login" in result.output

        rows = cd.list_all()
        assert rows[0].status is CommitStatus.PENDING_REVIEW

    def test_submit_json(self, runner: CliRunner, tmp_path: Path) -> None:
        cd = CommitsDirectory(tmp_path)
        cd.save(_draft(1, "fix", "core", "tighten"))
        result = runner.invoke(
            app,
            ["--json", "commits", "submit", "1", "--repo", str(tmp_path)],
        )
        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert payload["counter"] == 1
        assert payload["status"] == "pending_review"
        assert payload["path"].endswith(".json")

    def test_submit_missing_target_exits_2(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        result = runner.invoke(
            app,
            ["commits", "submit", "999", "--repo", str(tmp_path)],
        )
        assert result.exit_code == 2
        assert "no commit found" in result.output

    def test_submit_non_draft_exits_2(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        # Already-approved commit can't be re-submitted.
        cd = CommitsDirectory(tmp_path)
        cd.save(
            CommitJSON(
                counter=1,
                created_at=_NOW,
                updated_at=_NOW,
                status=CommitStatus.APPROVED,
                message=CommitMessage(type="feat", scope="", subject="x"),
            )
        )
        result = runner.invoke(
            app,
            ["commits", "submit", "1", "--repo", str(tmp_path)],
        )
        assert result.exit_code == 2


# --------------------------------------------------------------------------- #
# `sange commits reject <counter|id>` (T-044b)
# --------------------------------------------------------------------------- #


class TestCommitsReject:
    def test_reject_pending_review(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        cd = CommitsDirectory(tmp_path)
        cd.save(
            CommitJSON(
                counter=1,
                created_at=_NOW,
                updated_at=_NOW,
                status=CommitStatus.PENDING_REVIEW,
                message=CommitMessage(type="feat", scope="auth", subject="add login"),
            )
        )
        result = runner.invoke(
            app,
            [
                "commits", "reject", "1",
                "--reason", "scope creep",
                "--repo", str(tmp_path),
                "--actor", "alice",
            ],
        )
        assert result.exit_code == 0
        assert "rejected #0001: scope creep" in result.output
        assert "alice" in result.output

        rows = cd.list_all()
        c = rows[0]
        assert c.status is CommitStatus.REJECTED
        assert len(c.rejections) == 1
        assert c.rejections[0].actor == "alice"
        assert c.rejections[0].reason == "scope creep"

    def test_reject_draft_auto_submits(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        # DRAFT goes through PENDING_REVIEW transparently — same UX as approve.
        cd = CommitsDirectory(tmp_path)
        cd.save(_draft(1, "fix", "cli", "bad idea"))
        result = runner.invoke(
            app,
            [
                "commits", "reject", "1",
                "--reason", "wrong fix",
                "--repo", str(tmp_path),
                "--actor", "bob",
            ],
        )
        assert result.exit_code == 0
        rows = cd.list_all()
        assert rows[0].status is CommitStatus.REJECTED

    def test_reject_json(self, runner: CliRunner, tmp_path: Path) -> None:
        cd = CommitsDirectory(tmp_path)
        cd.save(_draft(1, "chore", "deps", "bump"))
        result = runner.invoke(
            app,
            [
                "--json", "commits", "reject", "1",
                "--reason", "deferred",
                "--repo", str(tmp_path),
                "--actor", "alice",
            ],
        )
        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert payload["status"] == "rejected"
        assert len(payload["rejections"]) == 1
        assert payload["rejections"][0]["reason"] == "deferred"
        assert payload["rejections"][0]["actor"] == "alice"

    def test_reject_already_approved_exits_2(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        cd = CommitsDirectory(tmp_path)
        cd.save(
            CommitJSON(
                counter=1,
                created_at=_NOW,
                updated_at=_NOW,
                status=CommitStatus.APPROVED,
                message=CommitMessage(type="feat", scope="", subject="x"),
            )
        )
        result = runner.invoke(
            app,
            [
                "commits", "reject", "1",
                "--reason", "too late",
                "--repo", str(tmp_path),
            ],
        )
        assert result.exit_code == 2

    def test_reject_requires_reason(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        # --reason has no default; omitting it must fail at typer's level.
        result = runner.invoke(
            app,
            ["commits", "reject", "1", "--repo", str(tmp_path)],
        )
        assert result.exit_code != 0


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


# --------------------------------------------------------------------------- #
# `sange commits push <counter|id>` — requires real git
# --------------------------------------------------------------------------- #


import shutil  # noqa: E402
import subprocess  # noqa: E402

_GIT = shutil.which("git")


def _setup_git_repo(tmp_path: Path) -> Path:
    """Init a bare-remote + working-tree pair under tmp_path. Returns the
    working-tree path with one initial commit + a staged change ready for
    the next commit."""

    remote = tmp_path / "remote.git"
    repo = tmp_path / "repo"
    repo.mkdir()
    env = {
        "GIT_AUTHOR_NAME": "Test",
        "GIT_AUTHOR_EMAIL": "t@t",
        "GIT_COMMITTER_NAME": "Test",
        "GIT_COMMITTER_EMAIL": "t@t",
        "PATH": "/usr/bin:/usr/local/bin:/opt/homebrew/bin",
        "HOME": str(tmp_path),
    }
    subprocess.run(
        ["git", "init", "--bare", "-q", "-b", "main", str(remote)],
        env=env, check=True,
    )
    for cmd in (
        ["git", "init", "-q", "-b", "main"],
        ["git", "config", "user.email", "t@t"],
        ["git", "config", "user.name", "Test"],
    ):
        subprocess.run(cmd, cwd=repo, env=env, check=True)
    (repo / "README.md").write_text("x\n")
    subprocess.run(["git", "add", "README.md"], cwd=repo, env=env, check=True)
    subprocess.run(
        ["git", "commit", "-q", "-m", "initial"], cwd=repo, env=env, check=True
    )
    subprocess.run(
        ["git", "remote", "add", "origin", str(remote)],
        cwd=repo, env=env, check=True,
    )
    subprocess.run(
        # `-u` sets upstream so newer git accepts subsequent `git push origin`
        # without explicit branch argument (which is what GitDriver.push() does
        # when no branch override is supplied).
        ["git", "push", "-q", "-u", "origin", "main"], cwd=repo, env=env, check=True
    )
    # Stage a change for the next commit.
    (repo / "README.md").write_text("y\n")
    subprocess.run(["git", "add", "README.md"], cwd=repo, env=env, check=True)
    return repo


def _seed_approved(repo: Path, *, counter: int = 1) -> None:
    """Plant one APPROVED commit row in <repo>/.sange/commits/."""

    from sange.core.lifecycle import LifecycleEngine

    cd = CommitsDirectory(repo)
    engine = LifecycleEngine()
    draft = CommitJSON(
        counter=counter,
        created_at=_NOW,
        updated_at=_NOW,
        message=CommitMessage(
            type="docs", scope="readme", subject="update README"
        ),
    )
    cd.save(engine.approve(engine.submit(draft), actor="alice", via="cli"))


@pytest.mark.skipif(_GIT is None, reason="git not on PATH")
class TestPush:
    def test_push_with_no_push_flag(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        repo = _setup_git_repo(tmp_path)
        _seed_approved(repo)
        result = runner.invoke(
            app,
            [
                "commits", "push", "1",
                "--repo", str(repo),
                "--no-push",
            ],
        )
        assert result.exit_code == 0, result.output
        assert "committed #0001" in result.output
        assert "(--no-push)" in result.output

        # Lifecycle row transitioned to COMMITTED with a real SHA.
        rows = CommitsDirectory(repo).list_all()
        assert rows[0].status is CommitStatus.COMMITTED
        assert len(rows[0].committed_sha) == 40

        # And git really did create the commit.
        env = {"PATH": "/usr/bin:/usr/local/bin:/opt/homebrew/bin", "HOME": str(tmp_path)}
        out = subprocess.run(
            ["git", "log", "--oneline", "-2"],
            cwd=repo, env=env, capture_output=True, text=True,
        )
        assert "docs(readme): update README" in out.stdout

    def test_push_full_with_remote(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        repo = _setup_git_repo(tmp_path)
        _seed_approved(repo)
        result = runner.invoke(
            app,
            ["commits", "push", "1", "--repo", str(repo)],
        )
        assert result.exit_code == 0, result.output
        assert "pushed to origin" in result.output

        rows = CommitsDirectory(repo).list_all()
        assert rows[0].status is CommitStatus.PUSHED
        assert rows[0].pushed_remote == "origin"

    def test_push_json_mode(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        repo = _setup_git_repo(tmp_path)
        _seed_approved(repo)
        result = runner.invoke(
            app,
            ["--json", "commits", "push", "1", "--repo", str(repo)],
        )
        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert payload["counter"] == 1
        assert payload["status"] == "pushed"
        assert len(payload["committed_sha"]) == 40
        assert payload["pushed_remote"] == "origin"
        assert payload["push"]["remote"] == "origin"

    def test_push_refuses_non_approved(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        repo = _setup_git_repo(tmp_path)
        # Save a DRAFT (not APPROVED).
        cd = CommitsDirectory(repo)
        cd.save(_draft(1, "docs", "readme", "x"))
        result = runner.invoke(
            app, ["commits", "push", "1", "--repo", str(repo)]
        )
        assert result.exit_code == 2
        assert "draft" in result.output.lower()
        assert "approve" in result.output.lower()

    def test_push_missing_counter_exits_2(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        repo = _setup_git_repo(tmp_path)
        result = runner.invoke(
            app, ["commits", "push", "99", "--repo", str(repo)]
        )
        assert result.exit_code == 2
        assert "no commit found" in result.output

    def test_push_non_git_dir_exits_65(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        from sange.core.lifecycle import LifecycleEngine

        # No git repo at tmp_path.
        cd = CommitsDirectory(tmp_path)
        cd.save(
            LifecycleEngine().approve(
                LifecycleEngine().submit(
                    CommitJSON(
                        counter=1, created_at=_NOW, updated_at=_NOW,
                        message=CommitMessage(
                            type="docs", scope="x", subject="y"
                        ),
                    )
                ),
                actor="alice", via="cli",
            )
        )
        result = runner.invoke(
            app, ["commits", "push", "1", "--repo", str(tmp_path)]
        )
        assert result.exit_code == 65
        assert "not a git working tree" in result.output

    def test_push_author_mismatch_exits_2(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        repo = _setup_git_repo(tmp_path)
        _seed_approved(repo)
        # Only --author-name without --author-email.
        result = runner.invoke(
            app,
            [
                "commits", "push", "1", "--repo", str(repo),
                "--author-name", "Bob",
            ],
        )
        assert result.exit_code == 2
        assert "author" in result.output.lower()

    def test_push_author_override(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        repo = _setup_git_repo(tmp_path)
        _seed_approved(repo)
        result = runner.invoke(
            app,
            [
                "commits", "push", "1", "--repo", str(repo), "--no-push",
                "--author-name", "Override User",
                "--author-email", "override@example.com",
            ],
        )
        assert result.exit_code == 0, result.output

        # git log shows the override.
        env = {"PATH": "/usr/bin:/usr/local/bin:/opt/homebrew/bin", "HOME": str(tmp_path)}
        out = subprocess.run(
            ["git", "log", "-1", "--format=%an <%ae>"],
            cwd=repo, env=env, capture_output=True, text=True,
        )
        assert "Override User" in out.stdout
        assert "override@example.com" in out.stdout


# --------------------------------------------------------------------------- #
# `sange commits commit <counter|id>` — APPROVED → COMMITTED (no push) (T-044c)
# --------------------------------------------------------------------------- #


@pytest.mark.skipif(_GIT is None, reason="git not on PATH")
class TestCommitsCommit:
    def test_commit_no_push(self, runner: CliRunner, tmp_path: Path) -> None:
        repo = _setup_git_repo(tmp_path)
        _seed_approved(repo)
        result = runner.invoke(
            app,
            ["commits", "commit", "1", "--repo", str(repo)],
        )
        assert result.exit_code == 0
        assert "committed #0001" in result.output
        assert "local only" in result.output

        rows = CommitsDirectory(repo).list_all()
        assert rows[0].status is CommitStatus.COMMITTED
        assert rows[0].committed_sha
        # No push happened — pushed_remote must stay empty.
        assert rows[0].pushed_remote == ""

    def test_commit_json(self, runner: CliRunner, tmp_path: Path) -> None:
        repo = _setup_git_repo(tmp_path)
        _seed_approved(repo)
        result = runner.invoke(
            app,
            ["--json", "commits", "commit", "1", "--repo", str(repo)],
        )
        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert payload["status"] == "committed"
        assert payload["committed_sha"]
        assert "pushed_remote" not in payload or payload.get("pushed_remote") == ""

    def test_commit_non_approved_exits_2(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        repo = _setup_git_repo(tmp_path)
        cd = CommitsDirectory(repo)
        cd.save(_draft(1, "feat", "auth", "add login"))
        result = runner.invoke(
            app,
            ["commits", "commit", "1", "--repo", str(repo)],
        )
        assert result.exit_code == 2
        assert "must be 'approved'" in result.output

    def test_commit_not_git_repo_exits_65(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        # tmp_path is not a git working tree.
        _seed_approved(tmp_path)
        result = runner.invoke(
            app,
            ["commits", "commit", "1", "--repo", str(tmp_path)],
        )
        assert result.exit_code == 65

    def test_commit_partial_author_exits_2(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        repo = _setup_git_repo(tmp_path)
        _seed_approved(repo)
        result = runner.invoke(
            app,
            [
                "commits", "commit", "1",
                "--repo", str(repo),
                "--author-name", "Solo",
                # No --author-email — must reject.
            ],
        )
        assert result.exit_code == 2
        assert "must be supplied together" in result.output


# --------------------------------------------------------------------------- #
# _render_message
# --------------------------------------------------------------------------- #


class TestRenderMessage:
    def test_basic_message(self) -> None:
        from sange.cli.commits import _render_message

        commit = _draft(1, "feat", "auth", "add login")
        text = _render_message(commit)
        assert text == "feat(auth): add login"

    def test_no_scope(self) -> None:
        from sange.cli.commits import _render_message

        commit = _draft(1, "chore", "", "tidy")
        text = _render_message(commit)
        assert text == "chore: tidy"

    def test_breaking_change_marker(self) -> None:
        from sange.cli.commits import _render_message

        commit = CommitJSON(
            counter=1, created_at=_NOW, updated_at=_NOW,
            message=CommitMessage(
                type="feat", scope="api", subject="remove v1",
                body="v1 retired.", breaking_change=True,
            ),
        )
        text = _render_message(commit)
        assert text.startswith("feat(api)!: remove v1")
        assert "BREAKING CHANGE" in text

    def test_body_appended(self) -> None:
        from sange.cli.commits import _render_message

        commit = CommitJSON(
            counter=1, created_at=_NOW, updated_at=_NOW,
            message=CommitMessage(
                type="docs", scope="readme", subject="update",
                body="Two-paragraph body.\n\nWith details.",
            ),
        )
        text = _render_message(commit)
        assert "docs(readme): update" in text
        assert "Two-paragraph body" in text
        assert "With details" in text


# --------------------------------------------------------------------------- #
# Interactive approval (questionary-mediated)
# --------------------------------------------------------------------------- #


class TestInteractiveApprove:
    def _patch_questionary(
        self,
        monkeypatch: pytest.MonkeyPatch,
        decision: str,
        reason: str = "",
    ) -> None:
        """Stub the two interactive helpers so tests never touch a TTY."""

        import sange.cli.commits as cmod

        monkeypatch.setattr(cmod, "_interactive_decision", lambda _c: decision)
        monkeypatch.setattr(cmod, "_interactive_reject_reason", lambda: reason)

    def test_interactive_approve(
        self,
        runner: CliRunner,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        self._patch_questionary(monkeypatch, decision="approve")
        cd = CommitsDirectory(tmp_path)
        cd.save(_draft(1, "feat", "auth", "add login"))

        result = runner.invoke(
            app,
            [
                "commits", "approve", "1",
                "-i",
                "--repo", str(tmp_path),
                "--actor", "alice",
            ],
        )
        assert result.exit_code == 0
        assert "approved #0001" in result.output

        rows = cd.list_all()
        assert rows[0].status is CommitStatus.APPROVED

    def test_interactive_reject(
        self,
        runner: CliRunner,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        self._patch_questionary(
            monkeypatch, decision="reject", reason="message too vague"
        )
        cd = CommitsDirectory(tmp_path)
        cd.save(_draft(1, "fix", "core", "x"))

        result = runner.invoke(
            app,
            [
                "commits", "approve", "1",
                "-i",
                "--repo", str(tmp_path),
                "--actor", "alice",
            ],
        )
        assert result.exit_code == 0
        assert "rejected #0001" in result.output
        assert "message too vague" in result.output

        rows = cd.list_all()
        assert rows[0].status is CommitStatus.REJECTED
        assert len(rows[0].rejections) == 1
        assert rows[0].rejections[0].reason == "message too vague"
        assert rows[0].rejections[0].actor == "alice"

    def test_interactive_skip(
        self,
        runner: CliRunner,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        self._patch_questionary(monkeypatch, decision="skip")
        cd = CommitsDirectory(tmp_path)
        cd.save(_draft(1, "chore", "", "tidy"))

        result = runner.invoke(
            app,
            [
                "commits", "approve", "1",
                "-i",
                "--repo", str(tmp_path),
                "--actor", "alice",
            ],
        )
        assert result.exit_code == 0
        assert "skipped" in result.output.lower()

        rows = cd.list_all()
        # Still DRAFT — no transition fired.
        assert rows[0].status is CommitStatus.DRAFT

    def test_interactive_reject_with_empty_reason_cancels(
        self,
        runner: CliRunner,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # User selects "reject" but then aborts at the reason prompt
        # (empty string returned).
        self._patch_questionary(monkeypatch, decision="reject", reason="")
        cd = CommitsDirectory(tmp_path)
        cd.save(_draft(1, "feat", "auth", "x"))

        result = runner.invoke(
            app,
            ["commits", "approve", "1", "-i", "--repo", str(tmp_path)],
        )
        assert result.exit_code == 0
        assert "cancelled" in result.output.lower()
        rows = cd.list_all()
        assert rows[0].status is CommitStatus.DRAFT

    def test_interactive_default_off(
        self,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        """Without `-i` or `--interactive`, no questionary call happens
        (proven by the test not hanging on stdin)."""

        cd = CommitsDirectory(tmp_path)
        cd.save(_draft(1, "feat", "auth", "x"))
        result = runner.invoke(
            app,
            ["commits", "approve", "1", "--repo", str(tmp_path), "--actor", "a"],
        )
        assert result.exit_code == 0
        rows = cd.list_all()
        assert rows[0].status is CommitStatus.APPROVED


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
