"""`sange hooks` sub-app — pre-commit / pre-push / etc. (T-102 slice 2).

Five verbs:

  * `sange hooks run EVENT [--repo PATH]`
        — discover + run every hook for `EVENT` in priority order.
          Exits non-zero iff any FAILED hook is reported.
  * `sange hooks list [--event EVENT] [--repo PATH]`
        — show discovered hooks (every event, or a specific one).
  * `sange hooks install [--repo PATH] [--event EVENT ...] [--force]`
        — write `.git/hooks/<event>` shims that delegate to
          `sange hooks run <event>`.
  * `sange hooks uninstall [--repo PATH] [--event EVENT ...]`
        — remove Sange-managed shims (foreign hooks untouched).
  * `sange hooks status [--repo PATH]`
        — quick summary: per-event count + shim install state.

Wraps the engine at `sange.core.hooks` (T-102 slice 1).
"""

from __future__ import annotations

import json
from pathlib import Path

import typer

hooks_app = typer.Typer(
    name="hooks",
    help="Manage pre-commit / pre-push / etc. hooks (T-102).",
    no_args_is_help=True,
)


# --------------------------------------------------------------------------- #
# `sange hooks run`
# --------------------------------------------------------------------------- #


@hooks_app.command(
    "run",
    help="Run every hook for EVENT in priority order.",
)
def run_command(
    event: str = typer.Argument(
        ...,
        help="Lifecycle event (`pre-commit` / `pre-push` / etc.).",
    ),
    repo_root: Path = typer.Option(
        Path("."),
        "--repo",
        help="Repo root (parent of .sange/). Default: cwd.",
    ),
    no_abort: bool = typer.Option(
        False,
        "--no-abort",
        help="Continue after FAILED hooks (collect every result).",
    ),
    timeout_s: float = typer.Option(
        60.0,
        "--timeout",
        help="Per-hook subprocess timeout in seconds.",
    ),
) -> None:
    """Invoke `HookEngine.run_event` + format the report."""

    import click

    from sange.core.hooks import HookEngine, HookError

    ctx = click.get_current_context()
    json_mode = bool(ctx.obj and ctx.obj.get("json"))

    try:
        engine = HookEngine(repo_root.resolve(), hook_timeout_s=timeout_s)
        report = engine.run_event(event, abort_on_failed=not no_abort)
    except HookError as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(code=2) from exc

    if json_mode:
        typer.echo(json.dumps({
            "event": report.event,
            "total": report.total,
            "all_passed": report.all_passed,
            "any_failed": report.any_failed,
            "counts": {s.value: n for s, n in report.counts.items()},
            "results": [
                {
                    "name": r.name,
                    "priority": r.priority,
                    "status": r.status.value,
                    "exit_code": r.exit_code,
                    "duration_ms": r.duration_ms,
                    "timed_out": r.timed_out,
                    "stdout": r.stdout,
                    "stderr": r.stderr,
                }
                for r in report.results
            ],
        }, indent=2))
    elif report.total == 0:
        typer.echo(f"(no hooks for event {event!r})")
    else:
        typer.echo(f"{'STATUS':<10} {'PRI':<5} {'NAME':<30} {'MS':<7} EXIT")
        typer.echo(f"{'-' * 10} {'-' * 5} {'-' * 30} {'-' * 7} {'-' * 5}")
        for r in report.results:
            typer.echo(
                f"{r.status.value:<10} {r.priority:<5d} {r.name:<30} "
                f"{r.duration_ms:<7d} {r.exit_code}"
            )
        typer.echo("")
        typer.echo(
            f"{report.total} hook(s); counts="
            + " ".join(f"{s.value}={n}" for s, n in report.counts.items() if n)
        )

    if report.any_failed:
        raise typer.Exit(code=1)


# --------------------------------------------------------------------------- #
# `sange hooks list`
# --------------------------------------------------------------------------- #


@hooks_app.command(
    "list",
    help="Show discovered hooks (every event, or a specific one).",
)
def list_command(
    event: str = typer.Option(
        "",
        "--event",
        help="Filter to one event. Empty = list every known event.",
    ),
    repo_root: Path = typer.Option(
        Path("."),
        "--repo",
        help="Repo root. Default: cwd.",
    ),
) -> None:
    """Discover every hook (or hooks for one event) + print."""

    import click

    from sange.core.hooks import GIT_HOOK_EVENTS, HookEngine

    ctx = click.get_current_context()
    json_mode = bool(ctx.obj and ctx.obj.get("json"))

    engine = HookEngine(repo_root.resolve())
    events_to_check = (event,) if event else GIT_HOOK_EVENTS

    rows: list[dict[str, object]] = []
    for ev in events_to_check:
        descriptors = engine.discover(ev)
        for d in descriptors:
            rows.append({
                "event": ev,
                "priority": d.priority,
                "name": d.name,
                "path": str(d.path),
            })

    if json_mode:
        typer.echo(json.dumps(rows, indent=2))
        return
    if not rows:
        typer.echo("(no hooks discovered)")
        return
    typer.echo(f"{'EVENT':<22} {'PRI':<5} {'NAME':<30} PATH")
    typer.echo(f"{'-' * 22} {'-' * 5} {'-' * 30} {'-' * 30}")
    for row in rows:
        path_str = str(row["path"])
        if len(path_str) > 60:
            path_str = "..." + path_str[-57:]
        # Pull values out and re-narrow types for mypy. `rows` carries
        # `dict[str, object]` because the JSON-serializable form mixes
        # ints + strs; the formatting branch needs them re-typed.
        priority_val = row["priority"]
        priority_int = priority_val if isinstance(priority_val, int) else 0
        name_val = row["name"]
        name_str = name_val if isinstance(name_val, str) else str(name_val)
        event_val = row["event"]
        event_str = event_val if isinstance(event_val, str) else str(event_val)
        typer.echo(
            f"{event_str:<22} {priority_int:<5d} "
            f"{name_str:<30} {path_str}"
        )
    typer.echo(f"\n{len(rows)} hook(s)")


# --------------------------------------------------------------------------- #
# `sange hooks install`
# --------------------------------------------------------------------------- #


@hooks_app.command(
    "install",
    help="Write .git/hooks/<event> shims that delegate to `sange hooks run`.",
)
def install_command(
    events: list[str] = typer.Option(
        [],
        "--event",
        help="Restrict to these events (repeatable). Default: every known event.",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        help="Overwrite pre-existing non-Sange hook files. Use carefully.",
    ),
    repo_root: Path = typer.Option(
        Path("."),
        "--repo",
        help="Repo root (must be a git working tree). Default: cwd.",
    ),
) -> None:
    """Write a shim per event that has any executable hooks."""

    import click

    from sange.core.hooks import ShimError, install_git_shims

    ctx = click.get_current_context()
    json_mode = bool(ctx.obj and ctx.obj.get("json"))

    try:
        results = install_git_shims(
            repo_root.resolve(),
            events=events or None,
            force=force,
        )
    except ShimError as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(code=2) from exc

    if json_mode:
        typer.echo(json.dumps([
            {"event": r.event, "path": str(r.path), "status": r.status}
            for r in results
        ], indent=2))
        return

    counts = {"installed": 0, "updated": 0, "skipped-foreign": 0, "skipped-no-hooks": 0}
    for r in results:
        counts[r.status] = counts.get(r.status, 0) + 1
        marker = {
            "installed": "[+]",
            "updated": "[~]",
            "skipped-foreign": "[!]",
            "skipped-no-hooks": "[ ]",
        }.get(r.status, "[?]")
        # Only print interesting rows by default.
        if r.status not in ("skipped-no-hooks",):
            typer.echo(f"  {marker} {r.event:<22} {r.status}")
    typer.echo("")
    typer.echo(
        f"{counts['installed']} installed, "
        f"{counts['updated']} updated, "
        f"{counts['skipped-foreign']} skipped (foreign), "
        f"{counts['skipped-no-hooks']} skipped (no hooks)"
    )


# --------------------------------------------------------------------------- #
# `sange hooks uninstall`
# --------------------------------------------------------------------------- #


@hooks_app.command(
    "uninstall",
    help="Remove Sange-managed .git/hooks/<event> shims (foreign hooks untouched).",
)
def uninstall_command(
    events: list[str] = typer.Option(
        [],
        "--event",
        help="Restrict to these events (repeatable). Default: every known event.",
    ),
    repo_root: Path = typer.Option(
        Path("."),
        "--repo",
        help="Repo root. Default: cwd.",
    ),
) -> None:
    """Remove Sange shims; leave foreign hook files alone."""

    import click

    from sange.core.hooks import ShimError, uninstall_git_shims

    ctx = click.get_current_context()
    json_mode = bool(ctx.obj and ctx.obj.get("json"))

    try:
        results = uninstall_git_shims(
            repo_root.resolve(),
            events=events or None,
        )
    except ShimError as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(code=2) from exc

    if json_mode:
        typer.echo(json.dumps([
            {"event": r.event, "path": str(r.path), "status": r.status}
            for r in results
        ], indent=2))
        return

    counts = {"removed": 0, "skipped-foreign": 0, "skipped-absent": 0}
    for r in results:
        counts[r.status] = counts.get(r.status, 0) + 1
        if r.status in ("removed", "skipped-foreign"):
            marker = {"removed": "[-]", "skipped-foreign": "[!]"}[r.status]
            typer.echo(f"  {marker} {r.event:<22} {r.status}")
    typer.echo("")
    typer.echo(
        f"{counts['removed']} removed, "
        f"{counts['skipped-foreign']} skipped (foreign), "
        f"{counts['skipped-absent']} skipped (absent)"
    )


# --------------------------------------------------------------------------- #
# `sange hooks status`
# --------------------------------------------------------------------------- #


@hooks_app.command(
    "status",
    help="Per-event summary: hook count + shim install state.",
)
def status_command(
    repo_root: Path = typer.Option(
        Path("."),
        "--repo",
        help="Repo root. Default: cwd.",
    ),
) -> None:
    """Cross-table of (event → hook count, shim installed?, foreign hook?)."""

    import click

    from sange.core.hooks import GIT_HOOK_EVENTS, SHIM_MARKER, HookEngine

    ctx = click.get_current_context()
    json_mode = bool(ctx.obj and ctx.obj.get("json"))

    engine = HookEngine(repo_root.resolve())
    git_hooks_dir = repo_root.resolve() / ".git" / "hooks"

    rows: list[dict[str, object]] = []
    for event in GIT_HOOK_EVENTS:
        descriptors = engine.discover(event)
        shim_path = git_hooks_dir / event
        shim_state = "absent"
        if shim_path.is_file():
            try:
                content = shim_path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                content = ""
            shim_state = "sange" if SHIM_MARKER in content else "foreign"
        rows.append({
            "event": event,
            "hook_count": len(descriptors),
            "shim": shim_state,
        })

    # Filter to rows that have any signal worth showing.
    interesting = [r for r in rows if r["hook_count"] or r["shim"] != "absent"]

    if json_mode:
        typer.echo(json.dumps(interesting, indent=2))
        return
    if not interesting:
        typer.echo("(no hooks or shims; run `sange hooks install` to wire git)")
        return
    typer.echo(f"{'EVENT':<22} {'HOOKS':<8} SHIM")
    typer.echo(f"{'-' * 22} {'-' * 8} {'-' * 10}")
    for r in interesting:
        event_val = r["event"]
        event_str = event_val if isinstance(event_val, str) else str(event_val)
        hook_count_val = r["hook_count"]
        hook_count = hook_count_val if isinstance(hook_count_val, int) else 0
        typer.echo(
            f"{event_str:<22} {hook_count:<8d} {r['shim']}"
        )


__all__ = [
    "hooks_app",
    "install_command",
    "list_command",
    "run_command",
    "status_command",
    "uninstall_command",
]
