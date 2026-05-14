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
# `sange commits push <counter|id>`
# --------------------------------------------------------------------------- #


@commits_app.command(
    "push",
    help="Land an APPROVED commit (git commit + optionally git push).",
)
def push_command(
    target: str = typer.Argument(
        ...,
        help="Counter (e.g. `1` or `0001`) or full commit id.",
    ),
    repo_root: Path = typer.Option(
        Path("."),
        "--repo",
        help="Repo root (must be a working git checkout). Default: cwd.",
    ),
    push: bool = typer.Option(
        True,
        "--push/--no-push",
        help="After the local commit lands, also `git push` to the remote.",
    ),
    remote: str = typer.Option(
        "origin",
        "--remote",
        help="Remote name when --push is on. Default: origin.",
    ),
    branch: str = typer.Option(
        "",
        "--branch",
        help="Branch to push. Default: current branch.",
    ),
    author_name: str = typer.Option(
        "",
        "--author-name",
        help="Override the author name (otherwise git config user.name).",
    ),
    author_email: str = typer.Option(
        "",
        "--author-email",
        help="Override the author email (otherwise git config user.email).",
    ),
    sign: bool = typer.Option(
        False,
        "--sign",
        help="GPG-sign the commit (`git commit -S`).",
    ),
) -> None:
    """Resolve the commit, build the Conventional Commits message,
    run `git commit`, record the SHA, optionally push, and write
    the updated CommitJSON back to disk."""

    import click

    from sange.adapters.vcs._protocol import DriverError
    from sange.adapters.vcs.git import GitDriver, GitRepoNotFound
    from sange.core.lifecycle import (
        CommitsDirectory,
        CommitStatus,
        IllegalTransition,
        LifecycleEngine,
    )

    ctx = click.get_current_context()
    json_mode = bool(ctx.obj and ctx.obj.get("json"))

    # Pre-flight: author name + email must be both-or-neither.
    if bool(author_name) != bool(author_email):
        typer.echo(
            "error: --author-name and --author-email must be supplied together",
            err=True,
        )
        raise typer.Exit(code=2)

    cd = CommitsDirectory(repo_root)
    commit = _resolve_target(cd, target)
    if commit is None:
        typer.echo(f"error: no commit found matching {target!r}", err=True)
        raise typer.Exit(code=2)

    if commit.status is not CommitStatus.APPROVED:
        typer.echo(
            f"error: commit #{commit.counter} is in state "
            f"{commit.status.value!r}; must be 'approved' before push. "
            "Run `sange commits approve` first.",
            err=True,
        )
        raise typer.Exit(code=2)

    # Resolve the repo (validates that path is inside a git working tree).
    try:
        repo = GitDriver.detect(repo_root.resolve())
    except GitRepoNotFound:
        typer.echo(
            f"error: {repo_root} is not a git working tree",
            err=True,
        )
        raise typer.Exit(code=65)  # VCS-not-detected per §16
    driver = GitDriver()

    # Render the commit message.
    message = _render_message(commit)

    # Run git commit.
    try:
        commit_ref = driver.commit(
            repo,
            message=message,
            author_name=author_name,
            author_email=author_email,
            sign=sign,
        )
    except DriverError as exc:
        typer.echo(f"git commit failed: {exc}", err=True)
        raise typer.Exit(code=65)

    engine = LifecycleEngine()
    try:
        committed = engine.mark_committed(commit, sha=commit_ref.sha)
    except IllegalTransition as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(code=2)

    cd.save(committed)

    push_status = "(--no-push)"
    push_result_payload: dict | None = None
    if push:
        try:
            push_result = driver.push(repo, remote=remote, branch=branch or "")
        except DriverError as exc:
            typer.echo(
                f"warning: git commit landed but push failed: {exc}", err=True
            )
            push_status = f"FAILED: {exc}"
        else:
            try:
                pushed = engine.mark_pushed(committed, remote=remote)
            except IllegalTransition as exc:
                typer.echo(f"error: {exc}", err=True)
                raise typer.Exit(code=2)
            cd.save(pushed)
            committed = pushed
            push_status = f"pushed to {remote}"
            push_result_payload = {
                "remote": push_result.remote,
                "was_no_op": push_result.was_no_op,
                "forced": push_result.forced,
                "refs_updated": [
                    {"local": local, "remote": rem}
                    for local, rem in push_result.refs_updated
                ],
            }

    if json_mode:
        payload = {
            "counter": committed.counter,
            "id": committed.id,
            "status": committed.status.value,
            "committed_sha": committed.committed_sha,
            "pushed_remote": committed.pushed_remote,
            "push": push_result_payload,
        }
        typer.echo(json.dumps(payload, indent=2))
        return

    typer.echo(f"committed #{committed.counter:04d} as {commit_ref.short_sha} ({push_status})")


# --------------------------------------------------------------------------- #
# Message rendering
# --------------------------------------------------------------------------- #


def _render_message(commit) -> str:  # type: ignore[no-untyped-def]
    """Render a `CommitMessage` into Conventional Commits text."""

    msg = commit.message
    header = msg.type
    if msg.scope:
        header += f"({msg.scope})"
    if msg.breaking_change:
        header += "!"
    header += f": {msg.subject}"

    parts: list[str] = [header]
    if msg.body:
        parts.append("")
        parts.append(msg.body)
    if msg.breaking_change and "BREAKING CHANGE" not in msg.body:
        parts.append("")
        parts.append("BREAKING CHANGE: see scope above")
    if msg.footer:
        parts.append("")
        parts.append(msg.footer)
    for co_author in msg.co_authors:
        parts.append(f"Co-authored-by: {co_author}")
    return "\n".join(parts)


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


__all__ = [
    "approve_command",
    "commits_app",
    "list_command",
    "push_command",
]
