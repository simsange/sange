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


# --------------------------------------------------------------------------- #
# `sange commits approve <counter|id>`
# --------------------------------------------------------------------------- #


@commits_app.command("approve", help="Approve a commit (DRAFT → APPROVED).")
def approve_command(
    target: str = typer.Argument(
        ...,
        help="Counter (e.g. `1` or `0001`) or full commit id.",
    ),
    repo_root: Path = typer.Option(
        Path("."),
        "--repo",
        help="Repo root (the parent of .sange/commits/). Default: cwd.",
    ),
    actor: str = typer.Option(
        "",
        "--actor",
        help="Approver name. Default: $USER environment variable.",
    ),
    via: str = typer.Option(
        "cli",
        "--via",
        help="Surface the approval came through (cli / tui / web / mcp).",
    ),
) -> None:
    """Resolve the commit, transition DRAFT → PENDING_REVIEW → APPROVED,
    write back to disk."""

    import os

    import click

    from sange.core.lifecycle import (
        CommitsDirectory,
        CommitStatus,
        IllegalTransition,
        LifecycleEngine,
    )

    ctx = click.get_current_context()
    json_mode = bool(ctx.obj and ctx.obj.get("json"))

    cd = CommitsDirectory(repo_root)
    commit = _resolve_target(cd, target)
    if commit is None:
        typer.echo(f"error: no commit found matching {target!r}", err=True)
        raise typer.Exit(code=2)

    actor_name = actor or os.environ.get("USER", "") or "unknown"
    engine = LifecycleEngine()

    try:
        # Solo-dev UX: DRAFT goes through the PENDING_REVIEW intermediate
        # transparently. If the commit is already PENDING_REVIEW, skip
        # the submit step.
        if commit.status is CommitStatus.DRAFT:
            commit = engine.submit(commit)
        approved = engine.approve(commit, actor=actor_name, via=via)  # type: ignore[arg-type]
    except IllegalTransition as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(code=2)

    path = cd.save(approved)

    if json_mode:
        payload = {
            "counter": approved.counter,
            "id": approved.id,
            "status": approved.status.value,
            "approvals": [
                {"actor": a.actor, "via": a.via, "at": a.at.isoformat()}
                for a in approved.approvals
            ],
            "path": str(path),
        }
        typer.echo(json.dumps(payload, indent=2))
        return

    typer.echo(
        f"approved #{approved.counter:04d}: {approved.message.type}"
        + (f"({approved.message.scope})" if approved.message.scope else "")
        + f": {approved.message.subject}"
    )
    typer.echo(f"approved by {actor_name} via {via} at {approved.approvals[-1].at.isoformat()}")


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _resolve_target(cd, target: str):  # type: ignore[no-untyped-def]
    """Resolve a CLI target (counter int or hex id) to a CommitJSON."""

    if target.isdigit() or (target.startswith("0") and target.lstrip("0").isdigit()):
        # Counter form (1, 0001, 42, etc.).
        try:
            counter = int(target)
        except ValueError:
            return None
        return cd.by_counter(counter)
    # Otherwise treat as an id.
    return cd.store.find_by_id(target)


__all__ = ["commits_app", "approve_command", "list_command"]
