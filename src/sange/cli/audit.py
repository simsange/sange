"""`sange audit` sub-app — hash-chained audit JSONL (T-108c).

Four verbs:

  * `sange audit verify [--repo]`     — verify the chain end-to-end.
  * `sange audit list [--week] [--kind]` — print records.
  * `sange audit tail [--n N]`        — print the most recent N records.
  * `sange audit append KIND --actor A [--payload JSON]`
                                      — manually append a record (testing
                                        + plugin entry-point).

Exit codes from `verify`:
  * 0 — chain verified clean.
  * 1 — chain tampered or broken (verifier surfaced the break).
  * 2 — usage error.

The engine surface is `sange.core.audit`; this module is a thin
typer wrapper.
"""

from __future__ import annotations

import json as _json
from pathlib import Path

import typer

audit_app = typer.Typer(
    name="audit",
    help="Inspect + verify the hash-chained audit JSONL (T-108).",
    no_args_is_help=True,
)


# --------------------------------------------------------------------------- #
# `sange audit verify`
# --------------------------------------------------------------------------- #


@audit_app.command(
    "verify",
    help="Walk the chain + recompute every hash. Exit 0 clean / 1 tampered.",
)
def verify_command(
    repo_root: Path = typer.Option(
        Path("."),
        "--repo",
        help="Repo root (parent of .sange/). Default: cwd.",
    ),
) -> None:
    """Invoke `verify_repo` + format the report."""

    import click

    from sange.core.audit import verify_repo

    ctx = click.get_current_context()
    json_mode = bool(ctx.obj and ctx.obj.get("json"))

    report = verify_repo(repo_root.resolve())

    if json_mode:
        typer.echo(_json.dumps(report.to_dict(), indent=2))
    elif report.verified:
        typer.echo(
            f"✓ chain verified: {report.records_checked} record(s) "
            f"across {report.shards_checked} shard(s)"
        )
    else:
        typer.echo(
            f"✗ chain FAILED ({report.failure_kind}): {report.failure_message}",
            err=True,
        )
        if report.failure_shard:
            typer.echo(
                f"  shard:  {report.failure_shard}", err=True,
            )
        if report.failure_index >= 0:
            typer.echo(
                f"  record: index={report.failure_index} "
                f"id={report.failure_event_id}",
                err=True,
            )

    if not report.verified:
        raise typer.Exit(code=1)


# --------------------------------------------------------------------------- #
# `sange audit list`
# --------------------------------------------------------------------------- #


@audit_app.command(
    "list",
    help="List audit records (every shard, or filtered).",
)
def list_command(
    week: str = typer.Option(
        "",
        "--week",
        help="ISO week filter `YYYY-WNN` (e.g. 2026-W20). Empty = all.",
    ),
    kind: str = typer.Option(
        "",
        "--kind",
        help="Filter by event kind (e.g. `commit-push`).",
    ),
    repo_root: Path = typer.Option(
        Path("."),
        "--repo",
        help="Repo root. Default: cwd.",
    ),
) -> None:
    """Walk the chain + print rows matching the filters."""

    import click

    from sange.core.audit import AuditChain

    ctx = click.get_current_context()
    json_mode = bool(ctx.obj and ctx.obj.get("json"))

    chain = AuditChain(repo_root.resolve())
    events = list(chain.iter_events())

    # Filter by week + kind.
    if week:
        # Match the shard's basename minus `.jsonl`.
        events = [
            e for e in events
            if e.timestamp.startswith(_iso_week_prefix(week))
        ]
    if kind:
        events = [e for e in events if e.kind == kind]

    if json_mode:
        typer.echo(_json.dumps(
            [e.to_dict() for e in events],
            indent=2,
        ))
        return
    if not events:
        typer.echo("(no audit records)")
        return
    typer.echo(f"{'TIMESTAMP':<26} {'KIND':<22} {'ACTOR':<20} ID")
    typer.echo(f"{'-' * 26} {'-' * 22} {'-' * 20} {'-' * 12}")
    for e in events:
        short_id = e.id[:8]
        typer.echo(
            f"{e.timestamp[:25]:<26} {e.kind:<22} {e.actor[:20]:<20} {short_id}"
        )
    typer.echo(f"\n{len(events)} record(s)")


def _iso_week_prefix(week: str) -> str:
    """Convert `2026-W20` to a year-prefix usable for timestamp filtering.

    Returns just the year part — we filter on `event.timestamp` which
    is ISO-8601 (YYYY-MM-DD...), so we'd need the actual date range
    for an exact ISO-week match. For v0.5-alpha the simple year-prefix
    works for "find me events in 2026"; the full ISO-week-to-date-range
    converter lands in v0.5 when the Web UI needs precise filtering.
    """

    if "-W" in week:
        return week.split("-W")[0]
    return week


# --------------------------------------------------------------------------- #
# `sange audit tail`
# --------------------------------------------------------------------------- #


@audit_app.command(
    "tail",
    help="Print the most recent N audit records.",
)
def tail_command(
    n: int = typer.Option(
        10,
        "--n",
        help="Number of records to show. Default: 10.",
    ),
    repo_root: Path = typer.Option(
        Path("."),
        "--repo",
        help="Repo root. Default: cwd.",
    ),
) -> None:
    """Print the last N records in chronological order."""

    import click

    from sange.core.audit import AuditChain

    ctx = click.get_current_context()
    json_mode = bool(ctx.obj and ctx.obj.get("json"))

    if n < 0:
        typer.echo("error: --n must be non-negative", err=True)
        raise typer.Exit(code=2)

    chain = AuditChain(repo_root.resolve())
    events = list(chain.iter_events())
    tail = events[-n:] if n > 0 else []

    if json_mode:
        typer.echo(_json.dumps(
            [e.to_dict() for e in tail],
            indent=2,
        ))
        return
    if not tail:
        typer.echo("(no audit records)")
        return
    for e in tail:
        typer.echo(
            f"{e.timestamp[:25]}  {e.kind:<22} {e.actor[:20]:<20} "
            f"{e.id[:8]} prev={e.prev_hash[:8] if e.prev_hash else '----'}"
        )


# --------------------------------------------------------------------------- #
# `sange audit append`
# --------------------------------------------------------------------------- #


@audit_app.command(
    "append",
    help="Append a record (mainly for plugins + manual testing).",
)
def append_command(
    kind: str = typer.Argument(
        ...,
        help="Event kind (`ai-call` / `commit-push` / `generic` / etc.).",
    ),
    actor: str = typer.Option(
        ...,
        "--actor",
        help="Identifier for the actor responsible. Required.",
    ),
    payload: str = typer.Option(
        "",
        "--payload",
        help="JSON-encoded payload dict. Default: empty `{}`.",
    ),
    repo_root: Path = typer.Option(
        Path("."),
        "--repo",
        help="Repo root. Default: cwd.",
    ),
) -> None:
    """Build + append one event onto the chain."""

    import click

    from sange.core.audit import AuditChain, AuditChainError

    ctx = click.get_current_context()
    json_mode = bool(ctx.obj and ctx.obj.get("json"))

    payload_dict: dict[str, object] = {}
    if payload:
        try:
            decoded = _json.loads(payload)
        except _json.JSONDecodeError as exc:
            typer.echo(f"error: --payload not valid JSON: {exc}", err=True)
            raise typer.Exit(code=2) from exc
        if not isinstance(decoded, dict):
            typer.echo(
                "error: --payload must be a JSON object (got "
                f"{type(decoded).__name__})",
                err=True,
            )
            raise typer.Exit(code=2)
        payload_dict = decoded

    chain = AuditChain(repo_root.resolve())
    try:
        event = chain.append(kind, actor=actor, payload=payload_dict)
    except AuditChainError as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(code=2) from exc

    if json_mode:
        typer.echo(_json.dumps(event.to_dict(), indent=2))
        return
    typer.echo(
        f"appended {event.kind}  id={event.id[:8]}  "
        f"this_hash={event.this_hash[:12]}"
    )


__all__ = [
    "append_command",
    "audit_app",
    "list_command",
    "tail_command",
    "verify_command",
]
