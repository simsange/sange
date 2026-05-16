"""`sange purge` sub-app — v0.5 read-only purge surface (§6.11).

Eight typer verbs cover the v0.5 detection/analysis/preview lifecycle.
Destructive transitions (`confirm` / `execute` / `push`) land in
v1.0 + T-203.

  * `sange purge plan --paths ... [--globs ...] [--vcs git] [--remote URL]
                      [--repo PATH] [--dry-run] [--batch]`
       Create a new `PurgePlan`, save to
       `.sange/purge/<plan-id>/plan.json`, append an audit chain event
       (kind=`purge-plan`). Prints the plan_id.

  * `sange purge list [--repo PATH]`
       Enumerate every saved plan with id + state + target_vcs +
       brief filter summary. Honors `--json` for machine consumption.

  * `sange purge show PLAN_ID [--repo PATH]`
       Print the full `plan.json` contents (pretty-printed by default,
       raw JSON under `--json`).

  * `sange purge mirror PLAN_ID [--source-url URL] [--repo PATH]`
       Run `create_mirror` against the plan, updating `plan.mirror_path`.

  * `sange purge analyze PLAN_ID [--repo PATH]`
       Run `analyze_mirror`, merge result into `plan.counts`, save.

  * `sange purge backup PLAN_ID [--repo PATH]`
       Tarball the mirror + sha256 sidecar, update `plan.backup_path`.

  * `sange purge scan PLAN_ID [--repo PATH]`
       Run gitleaks + trufflehog against the mirror, merge into
       `plan.scanner_results`.

  * `sange purge abort PLAN_ID [--reason TEXT] [--repo PATH]`
       Transition the plan to `aborted`, recording the reason.

Every state-changing verb appends one PURGE_PLAN event with a
`verb` payload key + the plan_id; the corresponding library call's
own audit events (clone / fsck / analyze / tar / scanners) thread
onto the chain inline as separate entries. The plan-level event is
the boundary marker; the library events are the leaf ops.
"""

from __future__ import annotations

import json as _json
import socket
from pathlib import Path
from typing import Annotated

import typer

from sange.core.audit import AuditChain, EventKind
from sange.core.purge import (
    AnalysisError,
    BackupError,
    IllegalTransition,
    MirrorError,
    PurgeFilters,
    PurgePlan,
    PurgePlanNotFound,
    PurgePlanStore,
    PurgeState,
    RepoMeta,
    ScannerError,
    analyze_mirror,
    create_backup,
    create_mirror,
    run_scanners,
)

purge_app = typer.Typer(
    name="purge",
    help="VCS history purge — v0.5 read-only (detection / analyze / dry-run).",
    no_args_is_help=True,
)


# --------------------------------------------------------------------------- #
# Shared helpers
# --------------------------------------------------------------------------- #


def _actor() -> str:
    """Best-effort operator identity for audit entries."""

    try:
        import getpass
        user = getpass.getuser()
    except Exception:
        user = "unknown"
    try:
        host = socket.gethostname()
    except Exception:
        host = "unknown"
    return f"{user}@{host}"


def _json_mode() -> bool:
    import click
    ctx = click.get_current_context()
    return bool(ctx.obj and ctx.obj.get("json"))


def _load_plan(store: PurgePlanStore, plan_id: str) -> PurgePlan:
    try:
        return store.load(plan_id)
    except PurgePlanNotFound as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(code=2) from exc


def _record_verb_event(
    chain: AuditChain,
    *,
    actor: str,
    plan_id: str,
    verb: str,
    extra: dict[str, object] | None = None,
) -> str:
    payload: dict[str, object] = {"verb": verb, "plan_id": plan_id}
    if extra:
        payload.update(extra)
    event = chain.append(EventKind.PURGE_PLAN, actor=actor, payload=payload)
    return event.id


# --------------------------------------------------------------------------- #
# sange purge plan
# --------------------------------------------------------------------------- #


@purge_app.command("plan", help="Create a new purge plan + save it.")
def plan_command(
    paths: Annotated[
        list[str] | None,
        typer.Option("--path", help="Exact path to purge. Repeat for multiple."),
    ] = None,
    globs: Annotated[
        list[str] | None,
        typer.Option("--glob", help="Glob pattern. Repeat for multiple."),
    ] = None,
    vcs: Annotated[
        str,
        typer.Option("--vcs", help="Target VCS: git / svn / hg / p4."),
    ] = "git",
    remote: Annotated[
        str,
        typer.Option("--remote", help="Remote URL for the target repo."),
    ] = "",
    slug: Annotated[
        str,
        typer.Option("--slug", help="Short repo identifier (e.g. `owner/name`)."),
    ] = "",
    repo_root: Annotated[
        Path,
        typer.Option(
            "--repo",
            help="Repo root (parent of `.sange/`). Default: cwd.",
        ),
    ] = Path("."),
    dry_run: Annotated[bool, typer.Option("--dry-run")] = False,
    batch: Annotated[bool, typer.Option("--batch")] = False,
) -> None:
    paths = paths or []
    globs = globs or []
    if not paths and not globs:
        typer.echo("error: at least one --path or --glob required", err=True)
        raise typer.Exit(code=2)

    if vcs not in {"git", "svn", "hg", "p4"}:
        typer.echo(f"error: unsupported --vcs {vcs!r}", err=True)
        raise typer.Exit(code=2)

    repo = repo_root.resolve()
    actor = _actor()
    try:
        filters = PurgeFilters(paths=list(paths), globs=list(globs))
        plan = PurgePlan(
            created_by=actor,
            target_vcs=vcs,  # type: ignore[arg-type]
            target_repo=RepoMeta(path=str(repo), remote=remote, slug=slug),
            filters=filters,
            dry_run=dry_run,
            batch=batch,
        )
    except Exception as exc:  # pydantic ValidationError + downstream
        typer.echo(f"error: invalid plan: {exc}", err=True)
        raise typer.Exit(code=2) from exc

    store = PurgePlanStore(repo)
    store.save(plan)

    chain = AuditChain(repo)
    _record_verb_event(
        chain, actor=actor, plan_id=plan.plan_id, verb="plan",
        extra={"target_vcs": vcs, "filter_count": len(paths) + len(globs)},
    )

    if _json_mode():
        typer.echo(_json.dumps({"plan_id": plan.plan_id, "state": plan.state.value}))
        return
    typer.echo(f"created plan {plan.plan_id}")
    typer.echo(f"  state:  {plan.state.value}")
    typer.echo(f"  paths:  {paths or '(none)'}")
    typer.echo(f"  globs:  {globs or '(none)'}")
    typer.echo(f"  saved:  {store.plan_path(plan.plan_id)}")


# --------------------------------------------------------------------------- #
# sange purge list
# --------------------------------------------------------------------------- #


@purge_app.command("list", help="Enumerate every saved purge plan.")
def list_command(
    repo_root: Annotated[
        Path, typer.Option("--repo"),
    ] = Path("."),
) -> None:
    store = PurgePlanStore(repo_root.resolve())
    plan_ids = store.list_plans()
    if _json_mode():
        rows = [
            {
                "plan_id": pid,
                "state": store.load(pid).state.value,
            }
            for pid in plan_ids
        ]
        typer.echo(_json.dumps(rows, indent=2))
        return
    if not plan_ids:
        typer.echo("(no purge plans)")
        return
    typer.echo(f"{'PLAN_ID':<46} STATE")
    typer.echo(f"{'-' * 46} {'-' * 18}")
    for pid in plan_ids:
        plan = store.load(pid)
        typer.echo(f"{pid:<46} {plan.state.value}")
    typer.echo(f"\n{len(plan_ids)} plan(s)")


# --------------------------------------------------------------------------- #
# sange purge show
# --------------------------------------------------------------------------- #


@purge_app.command("show", help="Print a plan's full JSON.")
def show_command(
    plan_id: Annotated[str, typer.Argument(help="Plan id to display.")],
    repo_root: Annotated[
        Path, typer.Option("--repo"),
    ] = Path("."),
) -> None:
    store = PurgePlanStore(repo_root.resolve())
    plan = _load_plan(store, plan_id)
    if _json_mode():
        typer.echo(plan.model_dump_json(indent=2))
        return
    # Pretty form: same JSON, with a banner.
    typer.echo(f"plan: {plan.plan_id}")
    typer.echo(f"state: {plan.state.value}")
    typer.echo(f"target_vcs: {plan.target_vcs}")
    typer.echo(plan.model_dump_json(indent=2))


# --------------------------------------------------------------------------- #
# sange purge mirror
# --------------------------------------------------------------------------- #


@purge_app.command("mirror", help="Create the mirror clone (§6.11.4 gate 2).")
def mirror_command(
    plan_id: Annotated[str, typer.Argument()],
    source_url: Annotated[
        str,
        typer.Option("--source-url", help="Override the plan's remote URL."),
    ] = "",
    repo_root: Annotated[
        Path, typer.Option("--repo"),
    ] = Path("."),
) -> None:
    repo = repo_root.resolve()
    store = PurgePlanStore(repo)
    plan = _load_plan(store, plan_id)
    chain = AuditChain(repo)
    actor = _actor()

    try:
        result = create_mirror(
            plan, repo,
            audit_chain=chain, actor=actor,
            source_url=source_url or None,
        )
    except MirrorError as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    plan.mirror_path = str(result.path)
    store.save(plan)
    _record_verb_event(
        chain, actor=actor, plan_id=plan.plan_id, verb="mirror",
        extra={"mirror_path": str(result.path), "ref_count": result.ref_count},
    )

    if _json_mode():
        typer.echo(_json.dumps({
            "plan_id": plan.plan_id,
            "mirror_path": str(result.path),
            "ref_count": result.ref_count,
            "fsck_passed": result.fsck_passed,
        }))
        return
    typer.echo(f"mirror created: {result.path}")
    typer.echo(f"  refs:        {result.ref_count}")
    typer.echo(f"  fsck:        {'green' if result.fsck_passed else 'red'}")
    typer.echo(f"  source URL:  {result.source_url}")


# --------------------------------------------------------------------------- #
# sange purge analyze
# --------------------------------------------------------------------------- #


@purge_app.command("analyze", help="Compute what would be purged (read-only).")
def analyze_command(
    plan_id: Annotated[str, typer.Argument()],
    repo_root: Annotated[
        Path, typer.Option("--repo"),
    ] = Path("."),
) -> None:
    repo = repo_root.resolve()
    store = PurgePlanStore(repo)
    plan = _load_plan(store, plan_id)
    if not plan.mirror_path:
        typer.echo(
            "error: plan has no mirror_path — run `sange purge mirror` first",
            err=True,
        )
        raise typer.Exit(code=2)
    chain = AuditChain(repo)
    actor = _actor()

    try:
        result = analyze_mirror(
            plan, Path(plan.mirror_path),
            audit_chain=chain, actor=actor,
        )
    except AnalysisError as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    counts = result.as_counts()
    plan.counts.update({k: int(v) for k, v in counts.items()})
    store.save(plan)
    _record_verb_event(
        chain, actor=actor, plan_id=plan.plan_id, verb="analyze",
        extra={
            "affected_commits": counts["affected_commits"],
            "deleted_objects": counts["deleted_objects"],
            "size_delta_bytes": counts["size_delta_bytes"],
        },
    )

    if _json_mode():
        typer.echo(_json.dumps(counts, indent=2))
        return
    typer.echo(f"analysis for {plan.plan_id}:")
    typer.echo(f"  matched paths:    {len(result.matched_paths)}")
    typer.echo(f"  affected commits: {counts['affected_commits']}")
    typer.echo(f"  deleted objects:  {counts['deleted_objects']}")
    typer.echo(f"  size delta:       {counts['size_delta_bytes']} bytes")


# --------------------------------------------------------------------------- #
# sange purge backup
# --------------------------------------------------------------------------- #


@purge_app.command("backup", help="Tarball the mirror + sha256 (§6.11.4 gate 3).")
def backup_command(
    plan_id: Annotated[str, typer.Argument()],
    repo_root: Annotated[
        Path, typer.Option("--repo"),
    ] = Path("."),
) -> None:
    repo = repo_root.resolve()
    store = PurgePlanStore(repo)
    plan = _load_plan(store, plan_id)
    if not plan.mirror_path:
        typer.echo(
            "error: plan has no mirror_path — run `sange purge mirror` first",
            err=True,
        )
        raise typer.Exit(code=2)
    chain = AuditChain(repo)
    actor = _actor()

    try:
        result = create_backup(
            plan, Path(plan.mirror_path),
            audit_chain=chain, actor=actor,
        )
    except BackupError as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    plan.backup_path = str(result.tarball_path)
    store.save(plan)
    _record_verb_event(
        chain, actor=actor, plan_id=plan.plan_id, verb="backup",
        extra={
            "tarball": str(result.tarball_path),
            "sha256": result.sha256_hex,
            "size_bytes": result.size_bytes,
        },
    )

    if _json_mode():
        typer.echo(_json.dumps({
            "plan_id": plan.plan_id,
            "tarball": str(result.tarball_path),
            "sha256": result.sha256_hex,
            "size_bytes": result.size_bytes,
        }))
        return
    typer.echo(f"backup created: {result.tarball_path}")
    typer.echo(f"  sha256: {result.sha256_hex}")
    typer.echo(f"  size:   {result.size_bytes} bytes")


# --------------------------------------------------------------------------- #
# sange purge scan
# --------------------------------------------------------------------------- #


@purge_app.command("scan", help="Run gitleaks + trufflehog (§6.11.4 gate 8).")
def scan_command(
    plan_id: Annotated[str, typer.Argument()],
    repo_root: Annotated[
        Path, typer.Option("--repo"),
    ] = Path("."),
) -> None:
    repo = repo_root.resolve()
    store = PurgePlanStore(repo)
    plan = _load_plan(store, plan_id)
    if not plan.mirror_path:
        typer.echo(
            "error: plan has no mirror_path — run `sange purge mirror` first",
            err=True,
        )
        raise typer.Exit(code=2)
    chain = AuditChain(repo)
    actor = _actor()

    try:
        gl, th = run_scanners(
            plan, Path(plan.mirror_path),
            audit_chain=chain, actor=actor,
        )
    except ScannerError as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    plan.scanner_results.update({
        "gitleaks": gl.findings_count,
        "trufflehog": th.findings_count,
    })
    store.save(plan)
    _record_verb_event(
        chain, actor=actor, plan_id=plan.plan_id, verb="scan",
        extra={
            "gitleaks_available": gl.available,
            "trufflehog_available": th.available,
            "gitleaks_findings": gl.findings_count,
            "trufflehog_findings": th.findings_count,
        },
    )

    if _json_mode():
        typer.echo(_json.dumps({
            "plan_id": plan.plan_id,
            "gitleaks": {
                "available": gl.available,
                "findings": gl.findings_count,
                "returncode": gl.returncode,
            },
            "trufflehog": {
                "available": th.available,
                "findings": th.findings_count,
                "returncode": th.returncode,
            },
        }, indent=2))
        return
    typer.echo(f"scan results for {plan.plan_id}:")
    for tool in (gl, th):
        status = "ok" if tool.available else "not installed"
        typer.echo(
            f"  {tool.name:<12} {status:<14} findings={tool.findings_count}"
        )


# --------------------------------------------------------------------------- #
# sange purge abort
# --------------------------------------------------------------------------- #


@purge_app.command("abort", help="Transition the plan to `aborted`.")
def abort_command(
    plan_id: Annotated[str, typer.Argument()],
    reason: Annotated[
        str,
        typer.Option("--reason", help="Explanation recorded on the plan + audit chain."),
    ] = "",
    repo_root: Annotated[
        Path, typer.Option("--repo"),
    ] = Path("."),
) -> None:
    repo = repo_root.resolve()
    store = PurgePlanStore(repo)
    plan = _load_plan(store, plan_id)
    actor = _actor()

    try:
        plan.transition(PurgeState.ABORTED, reason=reason)
    except IllegalTransition as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    store.save(plan)
    chain = AuditChain(repo)
    _record_verb_event(
        chain, actor=actor, plan_id=plan.plan_id, verb="abort",
        extra={"reason": reason or "(none)"},
    )

    if _json_mode():
        typer.echo(_json.dumps({
            "plan_id": plan.plan_id, "state": "aborted", "reason": reason,
        }))
        return
    typer.echo(f"aborted {plan.plan_id}")
    if reason:
        typer.echo(f"  reason: {reason}")


__all__ = [
    "abort_command",
    "analyze_command",
    "backup_command",
    "list_command",
    "mirror_command",
    "plan_command",
    "purge_app",
    "scan_command",
    "show_command",
]
