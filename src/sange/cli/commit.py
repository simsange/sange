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
    no_telemetry: bool = typer.Option(
        False,
        "--no-telemetry",
        help="Disable local telemetry recording for this invocation.",
    ),
    telemetry_dir: Path = typer.Option(
        Path(".sange/telemetry"),
        "--telemetry-dir",
        help="Where to write the NDJSON telemetry file. "
             "Default: .sange/telemetry in the current directory.",
    ),
    save: bool = typer.Option(
        True,
        "--save/--no-save",
        help="Save the generated commit as a DRAFT in <repo>/.sange/commits/. "
             "Disable for ephemeral one-shot use.",
    ),
) -> None:
    import datetime as _dt

    import click

    from sange.core.enhancer.tasks.commit_message import (
        CommitMessageRequest,
        generate_commit_message,
    )
    from sange.core.telemetry import CollectorPolicy, TelemetryCollector

    ctx = click.get_current_context()
    json_mode = bool(ctx.obj and ctx.obj.get("json"))

    collector = TelemetryCollector(
        CollectorPolicy(enabled=not no_telemetry, log_dir=telemetry_dir)
    )

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
        raise typer.Exit(code=2) from exc

    try:
        result = generate_commit_message(
            request, provider=provider, model=model, collector=collector
        )
    except Exception as exc:
        typer.echo(f"AI provider error: {exc}", err=True)
        raise typer.Exit(code=70) from exc

    saved_path: Path | None = None
    counter: int | None = None
    if save:
        # `--repo` is the lookup-context flag; if absent we save into
        # the current working dir's .sange/commits/.
        save_root = repo_path if repo_path is not None else Path(".")
        try:
            saved_path, counter = _save_draft(
                result=result,
                branch=branch,
                repo_root=save_root,
            )
        except Exception as exc:
            typer.echo(f"warning: failed to save DRAFT row: {exc}", err=True)

    if json_mode:
        payload = {
            "type": result.type,
            "scope": result.scope,
            "subject": result.subject,
            "body": result.body,
            "breaking_change": result.breaking_change,
            "audit_id": result.audit_id,
            "draft_counter": counter,
            "draft_path": str(saved_path) if saved_path else None,
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

    # Surface where the DRAFT was saved (counter + path).
    if saved_path is not None:
        typer.echo("", err=True)
        typer.echo(
            f"saved DRAFT #{counter:04d} to {saved_path}", err=True
        )

    # Surface the telemetry recording path (per §12.1 transparency).
    if not no_telemetry:
        now = _dt.datetime.now(tz=_dt.UTC)
        iso_year, iso_week, _ = now.isocalendar()
        record_path = telemetry_dir / f"events-{iso_year}-W{iso_week:02d}.ndjson"
        if saved_path is None:
            typer.echo("", err=True)
        typer.echo(f"recorded to {record_path}", err=True)


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

        repo = GitDriver.detect(repo_path.resolve())
        driver = GitDriver()

        branch = driver.current_branch(repo)
        commits = driver.log(repo, max_count=5)
        recent = "\n".join(c.subject for c in commits)
        # files_changed is the working-copy status set.
        status = driver.status(repo)
        files = [entry.path for entry in status.entries]
        return branch or "", recent, files
    except Exception:
        return "", "", []


def _save_draft(
    *,
    result,  # type: ignore[no-untyped-def] — CommitMessageResult, lazily-imported above
    branch: str,
    repo_root: Path,
) -> tuple[Path, int]:
    """Build a `CommitJSON` in DRAFT status and write it to disk.

    Returns `(path_written, counter)`. The counter is the per-repo
    monotonic value; the path is `<repo_root>/.sange/commits/NNNN-...json`."""

    import datetime as _dt

    from sange.core.lifecycle import (
        CommitJSON,
        CommitMessage,
        CommitsDirectory,
    )

    cd = CommitsDirectory(repo_root)
    counter = cd.allocate_counter()
    now = _dt.datetime.now(tz=_dt.UTC)

    commit = CommitJSON(
        counter=counter,
        created_at=now,
        updated_at=now,
        message=CommitMessage(
            type=result.type,
            scope=result.scope,
            subject=result.subject,
            body=result.body,
            breaking_change=result.breaking_change,
        ),
        branch=branch,
        repo_path=str(repo_root.resolve()),
        template_id=result.audit_id,
    )
    path = cd.save(commit)
    return path, counter


__all__ = ["commit_command"]
