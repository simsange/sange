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
