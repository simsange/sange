"""`sange commit` — one-shot commit-message generation.

v0.1 flow:

  1. Read the diff (from `--diff <path>` or stdin).
  2. Optionally read repo context (current branch via GitDriver if
     `--repo <path>` is given; recent commits limited to 5).
  3. Run the enhancer's commit-message template.
  4. Print the generated message.

This is the v0.1 minimum. The §6.8 lifecycle integration —
`CommitsDirectory.allocate_counter()` → save DRAFT → state machine
transitions → `git commit` — lands in T-013+ once the bundle of CLI +
TUI + interactive approval (questionary) is in place. For v0.1 the
user copies the printed message into `git commit -m`.

JSON output mode emits a `{type, scope, subject, body, breaking_change,
audit}` object that downstream tooling (the §13 web UI, the §15 MCP
endpoint) can consume directly.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import typer


def commit_command(
    diff_path: Path | None = typer.Option(
        None,
        "--diff",
        help="Path to a file containing the staged diff. "
             "When omitted, reads from stdin.",
    ),
    repo_path: Path | None = typer.Option(
        None,
        "--repo",
        help="Repo root for context lookup (branch + recent commits). "
             "When omitted, the prompt receives empty repo context.",
    ),
    provider: str = typer.Option(
        "mock",
        "--provider",
        help="AI provider to call (mock / anthropic / openai / ollama / ...).",
    ),
    model: str = typer.Option(
        "mock-1",
        "--model",
        help="Model identifier passed to the provider.",
    ),
    scope: str = typer.Option(
        "",
        "--scope",
        help="Optional scope hint biasing the generated message.",
    ),
) -> None:
    from sange.core.enhancer.tasks.commit_message import (
        CommitMessageRequest,
        generate_commit_message,
    )

    import click

    ctx = click.get_current_context()
    json_mode = bool(ctx.obj and ctx.obj.get("json"))

    diff_text = _read_diff(diff_path)
    if not diff_text:
        typer.echo("error: diff is empty (use --diff <path> or pipe via stdin)", err=True)
        raise typer.Exit(code=2)

    branch, recent_commits, files_changed = _gather_repo_context(repo_path)

    try:
        request = CommitMessageRequest(
            diff=diff_text,
            branch=branch,
            recent_commits=recent_commits,
            files_changed=tuple(files_changed),
            scope_override=scope,
        )
    except ValueError as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(code=2)

    try:
        result = generate_commit_message(request, provider=provider, model=model)
    except Exception as exc:  # noqa: BLE001 — surface as exit-code-70 AI error.
        typer.echo(f"AI provider error: {exc}", err=True)
        raise typer.Exit(code=70)

    if json_mode:
        payload = {
            "type": result.type,
            "scope": result.scope,
            "subject": result.subject,
            "body": result.body,
            "breaking_change": result.breaking_change,
            "audit_id": result.audit_id,
        }
        typer.echo(json.dumps(payload, indent=2))
        return

    # Plain output: emit the message in Conventional Commits format.
    header = result.type
    if result.scope:
        header += f"({result.scope})"
    if result.breaking_change:
        header += "!"
    header += f": {result.subject}"
    typer.echo(header)
    if result.body:
        typer.echo("")
        typer.echo(result.body)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _read_diff(diff_path: Path | None) -> str:
    if diff_path is not None:
        if not diff_path.is_file():
            typer.echo(f"error: diff file not found: {diff_path}", err=True)
            raise typer.Exit(code=2)
        return diff_path.read_text(encoding="utf-8")
    if sys.stdin.isatty():
        return ""
    return sys.stdin.read()


def _gather_repo_context(
    repo_path: Path | None,
) -> tuple[str, str, list[str]]:
    """Best-effort context lookup. Returns (branch, recent_commits_text,
    files_changed). Failures degrade silently to empty values — the
    prompt fills them with placeholders."""

    if repo_path is None:
        return "", "", []

    try:
        from sange.adapters.vcs.git import GitDriver
        from sange.core.models import Repo, VCSKind

        repo = Repo(path=str(repo_path.resolve()), kind=VCSKind.GIT)
        driver = GitDriver()
        if not driver.detect(repo):
            return "", "", []

        branch = driver.current_branch(repo)
        commits = driver.log(repo, max_count=5)
        recent = "\n".join(c.subject for c in commits)
        # files_changed is the working-copy status set.
        status = driver.status(repo)
        files = [entry.path for entry in status.entries]
        return branch or "", recent, files
    except Exception:  # noqa: BLE001 — best-effort; degrade silently.
        return "", "", []


__all__ = ["commit_command"]
