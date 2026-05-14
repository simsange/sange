"""`sange commits` sub-app — lifecycle management commands.

Per §6.8.4: granular lifecycle commands for the §6.8.2 state machine.
v0.1 ships:

  * `sange commits list`     — show pending + recent commits in the queue.
  * `sange commits approve <id>` — DRAFT → APPROVED transition (T-72+).
  * `sange commits push <id>`    — APPROVED → COMMITTED → PUSHED (T-73+).

This module exposes the typer sub-app; individual commands live in
their own modules so they remain easy to extend.
"""

from __future__ import annotations

import json
from pathlib import Path

import typer


commits_app = typer.Typer(
    name="commits",
    help="Manage the commit lifecycle queue (DRAFT → APPROVED → COMMITTED → PUSHED).",
    no_args_is_help=True,
)


# --------------------------------------------------------------------------- #
# `sange commits list`
# --------------------------------------------------------------------------- #


@commits_app.command("list", help="Show the commit queue.")
def list_command(
    repo_root: Path = typer.Option(
        Path("."),
        "--repo",
        help="Repo root (the parent of .sange/commits/). Default: cwd.",
    ),
    status: str = typer.Option(
        "",
        "--status",
        help="Filter by status (draft / pending_review / approved / committed / "
             "pushed / archived / rejected / discarded). Empty = all.",
    ),
    include_archived: bool = typer.Option(
        False,
        "--include-archived",
        help="Include rows in .sange/commits/archive/.",
    ),
) -> None:
    """List commits in the queue."""

    import click

    from sange.core.lifecycle import CommitsDirectory, CommitStatus

    ctx = click.get_current_context()
    json_mode = bool(ctx.obj and ctx.obj.get("json"))

    cd = CommitsDirectory(repo_root)
    # Empty .sange/commits/ returns []; that's fine.
    status_filter: CommitStatus | None = None
    if status:
        try:
            status_filter = CommitStatus(status.lower())
        except ValueError:
            valid = ", ".join(s.value for s in CommitStatus)
            typer.echo(
                f"error: unknown status {status!r}; expected one of: {valid}",
                err=True,
            )
            raise typer.Exit(code=2)

    rows = cd.list_all(
        status=status_filter,
        include_archived=include_archived,
    )

    if json_mode:
        payload = {
            "count": len(rows),
            "commits": [
                {
                    "counter": c.counter,
                    "id": c.id,
                    "status": c.status.value,
                    "type": c.message.type,
                    "scope": c.message.scope,
                    "subject": c.message.subject,
                    "breaking_change": c.message.breaking_change,
                    "branch": c.branch,
                    "created_at": c.created_at.isoformat(),
                    "updated_at": c.updated_at.isoformat(),
                    "committed_sha": c.committed_sha,
                    "pushed_remote": c.pushed_remote,
                }
                for c in rows
            ],
        }
        typer.echo(json.dumps(payload, indent=2))
        return

    if not rows:
        typer.echo("(no commits in queue)")
        return

    # Plain-text table.
    typer.echo(
        f"{'#':>5}  {'STATUS':<14} {'TYPE':<9} {'SCOPE':<14} SUBJECT"
    )
    typer.echo(
        f"{'-' * 5}  {'-' * 14} {'-' * 9} {'-' * 14} {'-' * 40}"
    )
    for c in rows:
        marker = "!" if c.message.breaking_change else " "
        scope = c.message.scope or "-"
        subject = c.message.subject
        if len(subject) > 60:
            subject = subject[:57] + "..."
        typer.echo(
            f"{c.counter:>4}{marker}  "
            f"{c.status.value:<14} "
            f"{c.message.type:<9} "
            f"{scope:<14} "
            f"{subject}"
        )

    typer.echo("")
    typer.echo(
        f"{len(rows)} commit(s)"
        + (f" with status={status!r}" if status else "")
        + (" (including archived)" if include_archived else "")
    )


__all__ = ["commits_app", "list_command"]
