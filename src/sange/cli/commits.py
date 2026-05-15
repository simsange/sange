"""`sange commits` sub-app — lifecycle management commands.

Per §6.8.4: granular lifecycle commands for the §6.8.2 state machine.
v0.1 ships:

  * `sange commits list`     — show pending + recent commits in the queue.
  * `sange commits new`      — write a manual DRAFT commit (no AI).
  * `sange commits ai`       — generate a DRAFT via AI (alias for `sange commit`).
  * `sange commits submit`   — DRAFT → PENDING_REVIEW.
  * `sange commits approve`  — PENDING_REVIEW → APPROVED (auto-submits DRAFT).
  * `sange commits reject`   — PENDING_REVIEW → REJECTED.
  * `sange commits commit`   — APPROVED → COMMITTED (git commit, no push).
  * `sange commits push`     — APPROVED → COMMITTED → PUSHED.

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
        except ValueError as exc:
            valid = ", ".join(s.value for s in CommitStatus)
            typer.echo(
                f"error: unknown status {status!r}; expected one of: {valid}",
                err=True,
            )
            raise typer.Exit(code=2) from exc

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
# `sange commits new`
# --------------------------------------------------------------------------- #


_CONVENTIONAL_TYPES = (
    "feat", "fix", "docs", "style", "refactor",
    "perf", "test", "build", "ci", "chore", "revert",
)


@commits_app.command(
    "new",
    help="Write a manual DRAFT commit to the queue (no AI involved).",
)
def new_command(
    type_: str = typer.Argument(
        ...,
        metavar="TYPE",
        help="Conventional Commits type. One of: "
             + ", ".join(_CONVENTIONAL_TYPES) + ".",
    ),
    subject: str = typer.Argument(
        ...,
        help="Commit subject line (single-line, ≤120 chars, non-empty).",
    ),
    scope: str = typer.Option(
        "",
        "--scope",
        help="Optional scope (lowercase letters/digits/hyphens).",
    ),
    body: str = typer.Option(
        "",
        "--body",
        help="Commit body. Pass `-` to read from stdin.",
    ),
    breaking_change: bool = typer.Option(
        False,
        "--breaking-change",
        help="Mark this commit as introducing a BREAKING CHANGE.",
    ),
    co_author: list[str] = typer.Option(
        [],
        "--co-author",
        help="Co-author (repeatable). Format: `Name <email>`.",
    ),
    reference: list[str] = typer.Option(
        [],
        "--reference",
        help="Issue / ticket reference (repeatable). Format: `#123` or `JIRA-42`.",
    ),
    repo_root: Path = typer.Option(
        Path("."),
        "--repo",
        help="Repo root (the parent of .sange/commits/). Default: cwd.",
    ),
    branch: str = typer.Option(
        "",
        "--branch",
        help="Branch override. Default: auto-detect via GitDriver "
             "(falls back to empty string if not in a git repo).",
    ),
) -> None:
    """Build a DRAFT `CommitJSON` from manually-supplied fields."""

    import datetime as _dt
    import sys

    import click

    from sange.core.lifecycle import (
        CommitJSON,
        CommitMessage,
        CommitsDirectory,
    )

    ctx = click.get_current_context()
    json_mode = bool(ctx.obj and ctx.obj.get("json"))

    if type_ not in _CONVENTIONAL_TYPES:
        typer.echo(
            f"error: unknown type {type_!r}; expected one of: "
            + ", ".join(_CONVENTIONAL_TYPES),
            err=True,
        )
        raise typer.Exit(code=2)

    if body == "-":
        body = sys.stdin.read()

    detected_branch = branch or _detect_branch(repo_root)

    try:
        message = CommitMessage(
            type=type_,  # type: ignore[arg-type]
            scope=scope,
            subject=subject,
            body=body,
            breaking_change=breaking_change,
            co_authors=list(co_author),
            references=list(reference),
        )
    except ValueError as exc:
        # Pydantic surfaces validation failures as ValueError subclasses;
        # `.errors()` gives the structured detail.
        typer.echo(f"error: invalid commit message: {exc}", err=True)
        raise typer.Exit(code=2) from exc

    cd = CommitsDirectory(repo_root)
    counter = cd.allocate_counter()
    now = _dt.datetime.now(tz=_dt.UTC)

    commit = CommitJSON(
        counter=counter,
        created_at=now,
        updated_at=now,
        message=message,
        branch=detected_branch,
        repo_path=str(repo_root.resolve()),
    )
    path = cd.save(commit)

    if json_mode:
        payload = {
            "counter": commit.counter,
            "id": commit.id,
            "status": commit.status.value,
            "path": str(path),
            "type": commit.message.type,
            "scope": commit.message.scope,
            "subject": commit.message.subject,
            "branch": commit.branch,
            "breaking_change": commit.message.breaking_change,
        }
        typer.echo(json.dumps(payload, indent=2))
        return

    rendered = f"{commit.message.type}"
    if commit.message.scope:
        rendered += f"({commit.message.scope})"
    if commit.message.breaking_change:
        rendered += "!"
    rendered += f": {commit.message.subject}"
    typer.echo(f"drafted #{commit.counter:04d}: {rendered}")
    typer.echo(f"saved to {path}")


def _detect_branch(repo_root: Path) -> str:
    """Best-effort current-branch lookup; empty string on any failure."""

    try:
        from sange.adapters.vcs.git import GitDriver

        driver = GitDriver()
        repo = driver.detect(repo_root)
        branch = driver.current_branch(repo)
        return branch.name if branch else ""
    except Exception:
        return ""


# --------------------------------------------------------------------------- #
# `sange commits ai` — alias for the top-level `sange commit` happy path
# --------------------------------------------------------------------------- #
#
# T-043. The AI-driven DRAFT-creation flow is implemented in
# `sange/cli/commit.py::commit_command` (it's also the top-level `sange
# commit` happy path). Registering it here under the `commits` sub-app
# gives the granular surface a complete parallel:
#
#     sange commits new   — manual draft (you supply type/subject/body).
#     sange commits ai    — AI draft     (you supply diff; AI fills the rest).
#
# Both produce a DRAFT row in `.sange/commits/`; downstream verbs
# (submit / approve / reject / commit / push) work identically on
# either.

from sange.cli.commit import commit_command as _commit_command  # noqa: E402

commits_app.command(
    "ai",
    help="Generate a commit message via AI and save as DRAFT.",
)(_commit_command)


# --------------------------------------------------------------------------- #
# `sange commits submit <counter|id>`
# --------------------------------------------------------------------------- #


@commits_app.command(
    "submit",
    help="Submit a DRAFT for review (DRAFT → PENDING_REVIEW).",
)
def submit_command(
    target: str = typer.Argument(
        ...,
        help="Counter (e.g. `1` or `0001`) or full commit id.",
    ),
    repo_root: Path = typer.Option(
        Path("."),
        "--repo",
        help="Repo root (the parent of .sange/commits/). Default: cwd.",
    ),
) -> None:
    """Resolve the commit and run the DRAFT → PENDING_REVIEW transition."""

    import click

    from sange.core.lifecycle import (
        CommitsDirectory,
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

    engine = LifecycleEngine()
    try:
        submitted = engine.submit(commit)
    except IllegalTransition as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(code=2) from exc

    path = cd.save(submitted)

    if json_mode:
        payload = {
            "counter": submitted.counter,
            "id": submitted.id,
            "status": submitted.status.value,
            "path": str(path),
        }
        typer.echo(json.dumps(payload, indent=2))
        return

    typer.echo(
        f"submitted #{submitted.counter:04d}: "
        f"{submitted.message.type}"
        + (f"({submitted.message.scope})" if submitted.message.scope else "")
        + f": {submitted.message.subject}"
    )


# --------------------------------------------------------------------------- #
# `sange commits reject <counter|id>`
# --------------------------------------------------------------------------- #


@commits_app.command(
    "reject",
    help="Reject a PENDING_REVIEW commit (PENDING_REVIEW → REJECTED).",
)
def reject_command(
    target: str = typer.Argument(
        ...,
        help="Counter (e.g. `1` or `0001`) or full commit id.",
    ),
    reason: str = typer.Option(
        ...,
        "--reason",
        help="Non-empty rejection reason (≤480 chars).",
    ),
    repo_root: Path = typer.Option(
        Path("."),
        "--repo",
        help="Repo root (the parent of .sange/commits/). Default: cwd.",
    ),
    actor: str = typer.Option(
        "",
        "--actor",
        help="Rejector name. Default: $USER environment variable.",
    ),
    via: str = typer.Option(
        "cli",
        "--via",
        help="Surface the rejection came through (cli / tui / web / mcp).",
    ),
) -> None:
    """Resolve the commit, optionally auto-submit a DRAFT, then run the
    PENDING_REVIEW → REJECTED transition. Mirrors the solo-dev UX in
    `commits approve` where DRAFT goes through PENDING_REVIEW transparently."""

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
        if commit.status is CommitStatus.DRAFT:
            commit = engine.submit(commit)
        rejected = engine.reject(
            commit, actor=actor_name, reason=reason, via=via,  # type: ignore[arg-type]
        )
    except IllegalTransition as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(code=2) from exc
    except ValueError as exc:
        # engine.reject raises ValueError on empty reason — but typer's
        # required-option enforcement already prevents that; defensive.
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(code=2) from exc

    path = cd.save(rejected)

    if json_mode:
        payload = {
            "counter": rejected.counter,
            "id": rejected.id,
            "status": rejected.status.value,
            "rejections": [
                {"actor": r.actor, "via": r.via, "at": r.at.isoformat(), "reason": r.reason}
                for r in rejected.rejections
            ],
            "path": str(path),
        }
        typer.echo(json.dumps(payload, indent=2))
        return

    typer.echo(f"rejected #{rejected.counter:04d}: {reason}")
    typer.echo(f"rejected by {actor_name} via {via} at {rejected.rejections[-1].at.isoformat()}")


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
    interactive: bool = typer.Option(
        False,
        "--interactive/--no-interactive",
        "-i",
        help="Show the rendered message + prompt approve / reject / skip. "
             "Default: non-interactive (approve immediately).",
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

    # Interactive mode: render the commit + prompt approve/reject/skip.
    if interactive:
        decision = _interactive_decision(commit)
        if decision == "skip":
            typer.echo("skipped (no transition)")
            return
        if decision == "reject":
            reason = _interactive_reject_reason()
            if not reason:
                typer.echo("rejection cancelled (no reason provided)")
                return
            try:
                if commit.status is CommitStatus.DRAFT:
                    commit = engine.submit(commit)
                rejected = engine.reject(
                    commit, actor=actor_name, reason=reason, via=via,  # type: ignore[arg-type]
                )
            except IllegalTransition as exc:
                typer.echo(f"error: {exc}", err=True)
                raise typer.Exit(code=2) from exc
            cd.save(rejected)
            typer.echo(f"rejected #{rejected.counter:04d}: {reason}")
            return
        # decision == "approve" → fall through to the non-interactive path.

    try:
        # Solo-dev UX: DRAFT goes through the PENDING_REVIEW intermediate
        # transparently. If the commit is already PENDING_REVIEW, skip
        # the submit step.
        if commit.status is CommitStatus.DRAFT:
            commit = engine.submit(commit)
        approved = engine.approve(commit, actor=actor_name, via=via)  # type: ignore[arg-type]
    except IllegalTransition as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(code=2) from exc

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
# `sange commits commit <counter|id>`
# --------------------------------------------------------------------------- #


@commits_app.command(
    "commit",
    help="Land an APPROVED commit locally (git commit, no push).",
)
def commit_command(
    target: str = typer.Argument(
        ...,
        help="Counter (e.g. `1` or `0001`) or full commit id.",
    ),
    repo_root: Path = typer.Option(
        Path("."),
        "--repo",
        help="Repo root (must be a working git checkout). Default: cwd.",
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
    """Resolve the commit, run `git commit`, mark COMMITTED. No push."""

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
            f"{commit.status.value!r}; must be 'approved' before commit. "
            "Run `sange commits approve` first.",
            err=True,
        )
        raise typer.Exit(code=2)

    try:
        repo = GitDriver.detect(repo_root.resolve())
    except GitRepoNotFound as exc:
        typer.echo(f"error: {repo_root} is not a git working tree", err=True)
        raise typer.Exit(code=65) from exc
    driver = GitDriver()

    message = _render_message(commit)

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
        raise typer.Exit(code=65) from exc

    engine = LifecycleEngine()
    try:
        committed = engine.mark_committed(commit, sha=commit_ref.sha)
    except IllegalTransition as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(code=2) from exc

    path = cd.save(committed)

    if json_mode:
        payload = {
            "counter": committed.counter,
            "id": committed.id,
            "status": committed.status.value,
            "committed_sha": committed.committed_sha,
            "path": str(path),
        }
        typer.echo(json.dumps(payload, indent=2))
        return

    typer.echo(
        f"committed #{committed.counter:04d} as {commit_ref.short_sha} "
        f"(local only — run `sange commits push` to publish)"
    )


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
    except GitRepoNotFound as exc:
        typer.echo(
            f"error: {repo_root} is not a git working tree",
            err=True,
        )
        raise typer.Exit(code=65) from exc  # VCS-not-detected per §16
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
        raise typer.Exit(code=65) from exc

    engine = LifecycleEngine()
    try:
        committed = engine.mark_committed(commit, sha=commit_ref.sha)
    except IllegalTransition as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(code=2) from exc

    cd.save(committed)

    push_status = "(--no-push)"
    push_result_payload: dict[str, object] | None = None
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
                raise typer.Exit(code=2) from exc
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
# Interactive helpers — questionary-based prompts
# --------------------------------------------------------------------------- #


def _interactive_decision(commit) -> str:  # type: ignore[no-untyped-def]
    """Render the commit, then prompt approve / reject / skip.

    Returns the literal choice value: `"approve"`, `"reject"`, or
    `"skip"`. Falls back to `"skip"` on Ctrl-C / empty input."""

    import questionary

    # Display the rendered Conventional Commits message above the prompt.
    rendered = _render_message(commit)
    typer.echo("")
    typer.echo(f"=== commit #{commit.counter:04d} ({commit.status.value}) ===")
    typer.echo(rendered)
    typer.echo("")

    answer = questionary.select(
        "What would you like to do?",
        choices=[
            questionary.Choice(title="Approve", value="approve"),
            questionary.Choice(title="Reject (with reason)", value="reject"),
            questionary.Choice(title="Skip (no change)", value="skip"),
        ],
        default="approve",
    ).ask()

    if answer is None:
        # Ctrl-C / EOF.
        return "skip"
    # questionary's stubs return Any; we know the value is one of the
    # registered choices (approve/reject/skip), all strings.
    return str(answer)


def _interactive_reject_reason() -> str:
    """Prompt for a rejection reason. Returns the text or `""` on cancel."""

    import questionary

    answer = questionary.text(
        "Reason for rejection:",
        validate=lambda v: True if v.strip() else "reason cannot be empty",
    ).ask()
    return (answer or "").strip()


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
    "commit_command",
    "commits_app",
    "list_command",
    "new_command",
    "push_command",
    "reject_command",
    "submit_command",
]
