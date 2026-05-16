"""`sange gitignore` sub-app — gitignore profile management (T-101e).

Verbs:

  * `sange gitignore swap PROFILES… [--stage STAGE] [--variant SLUG] [--repo PATH]`
                                        — atomic swap to a new profile + stage.
  * `sange gitignore list [--category CAT] [--repo PATH]`
                                        — list discoverable profiles.
  * `sange gitignore current [--repo PATH]`
                                        — show the currently active profile.
  * `sange gitignore detect [--repo PATH]`
                                        — auto-detect profile candidates.
  * `sange gitignore recover [--repo PATH]`
                                        — replay any crashed-in-progress
                                          swap journal.

The engine surface is `sange.core.gitignore` (T-101a/b/c/d/f); this
module is a thin typer wrapper.
"""

from __future__ import annotations

import json
from pathlib import Path

import typer

gitignore_app = typer.Typer(
    name="gitignore",
    help="Manage the active gitignore profile (T-101).",
    no_args_is_help=True,
)


# --------------------------------------------------------------------------- #
# `sange gitignore swap`
# --------------------------------------------------------------------------- #


@gitignore_app.command(
    "swap",
    help="Atomic swap to a new gitignore composition.",
)
def swap_command(
    profiles: list[str] = typer.Argument(
        ...,
        metavar="PROFILES...",
        help="One or more profile names (e.g. `lang/python framework/django`).",
    ),
    stage: str = typer.Option(
        "dev",
        "--stage",
        help="Stage to compose for. One of: dev / prod / "
             "(any custom stage your profile declares).",
    ),
    repo_root: Path = typer.Option(
        Path("."),
        "--repo",
        help="Repo root (the parent of .sange/). Default: cwd.",
    ),
) -> None:
    """Compose `profiles` + `stage` and atomically replace `.gitignore`."""

    import click

    from sange.core.gitignore import (
        GitignoreSwap,
        ProfileError,
        ProfileRegistry,
        SwapError,
        default_registry_roots,
    )
    from sange.core.gitignore.compose import CompositionError

    ctx = click.get_current_context()
    json_mode = bool(ctx.obj and ctx.obj.get("json"))

    registry = ProfileRegistry(default_registry_roots(repo_root))
    swap = GitignoreSwap(repo_root.resolve(), registry=registry)

    try:
        result = swap.swap(profiles, stage=stage)
    except (ProfileError, CompositionError) as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(code=2) from exc
    except SwapError as exc:
        typer.echo(f"error: swap failed: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    if json_mode:
        typer.echo(json.dumps({
            "profiles": list(result.profiles),
            "stage": result.stage,
            "gitignore_path": str(result.gitignore_path),
            "active_profile_path": str(result.active_profile_path),
            "bytes_written": result.bytes_written,
            "journal_id": result.journal_id,
            "was_recovered": result.was_recovered,
        }, indent=2))
        return

    typer.echo(
        f"swapped: profiles=[{', '.join(result.profiles)}]  "
        f"stage={result.stage}  bytes={result.bytes_written}"
    )
    typer.echo(f"wrote {result.gitignore_path}")


# --------------------------------------------------------------------------- #
# `sange gitignore list`
# --------------------------------------------------------------------------- #


@gitignore_app.command(
    "list",
    help="List discoverable gitignore profiles.",
)
def list_command(
    category: str = typer.Option(
        "",
        "--category",
        help="Filter by category (lang / framework / infra / editor / os / _core). "
             "Empty = all.",
    ),
    repo_root: Path = typer.Option(
        Path("."),
        "--repo",
        help="Repo root for per-repo profile overrides. Default: cwd.",
    ),
) -> None:
    """Print every profile the registry sees, optionally filtered by category."""

    import click

    from sange.core.gitignore import ProfileRegistry, default_registry_roots

    ctx = click.get_current_context()
    json_mode = bool(ctx.obj and ctx.obj.get("json"))

    registry = ProfileRegistry(default_registry_roots(repo_root))
    if category:
        profiles = registry.by_category(category)
    else:
        profiles = registry.all_profiles()

    if json_mode:
        typer.echo(json.dumps([
            {
                "name": p.name,
                "category": p.category,
                "display_name": p.display_name,
                "version": p.version,
                "source_path": str(p.source_path),
            }
            for p in profiles
        ], indent=2))
        return

    if not profiles:
        typer.echo("(no profiles)")
        return
    typer.echo(f"{'CATEGORY':<14} {'NAME':<32} DISPLAY")
    typer.echo(f"{'-' * 14} {'-' * 32} {'-' * 30}")
    for p in profiles:
        typer.echo(f"{p.category:<14} {p.name:<32} {p.display_name}")
    typer.echo(f"\n{len(profiles)} profile(s)")


# --------------------------------------------------------------------------- #
# `sange gitignore current`
# --------------------------------------------------------------------------- #


@gitignore_app.command(
    "current",
    help="Show the currently active gitignore profile.",
)
def current_command(
    repo_root: Path = typer.Option(
        Path("."),
        "--repo",
        help="Repo root. Default: cwd.",
    ),
) -> None:
    """Read `.sange/.active-profile` and surface its content."""

    import click

    ctx = click.get_current_context()
    json_mode = bool(ctx.obj and ctx.obj.get("json"))

    active_path = repo_root.resolve() / ".sange" / ".active-profile"
    if not active_path.is_file():
        if json_mode:
            typer.echo(json.dumps({"active": None}, indent=2))
            return
        typer.echo("(no active profile — run `sange gitignore swap` to set one)")
        raise typer.Exit(code=0)

    text = active_path.read_text(encoding="utf-8")

    # The active-profile file format is two KV lines:
    #   profiles=<csv>
    #   stage=<stage>
    profiles: list[str] = []
    stage = ""
    for line in text.splitlines():
        if line.startswith("#") or not line.strip():
            continue
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        if key == "profiles":
            profiles = [p for p in value.split(",") if p]
        elif key == "stage":
            stage = value

    if json_mode:
        typer.echo(json.dumps({
            "active": {"profiles": profiles, "stage": stage},
            "path": str(active_path),
        }, indent=2))
        return

    typer.echo(f"profiles: {', '.join(profiles)}")
    typer.echo(f"stage:    {stage}")


# --------------------------------------------------------------------------- #
# `sange gitignore detect`
# --------------------------------------------------------------------------- #


@gitignore_app.command(
    "detect",
    help="Auto-detect profile candidates for the repo.",
)
def detect_command(
    repo_root: Path = typer.Option(
        Path("."),
        "--repo",
        help="Repo root to inspect. Default: cwd.",
    ),
    walk_depth: int = typer.Option(
        1,
        "--depth",
        help="How deep to look for marker files. 0 = root only.",
    ),
) -> None:
    """Walk `repo` looking for files that match each profile's `required_any`."""

    import click

    from sange.core.gitignore import (
        ProfileRegistry,
        default_registry_roots,
        detect_profiles,
    )

    ctx = click.get_current_context()
    json_mode = bool(ctx.obj and ctx.obj.get("json"))

    registry = ProfileRegistry(default_registry_roots(repo_root))
    results = detect_profiles(
        repo_root.resolve(),
        registry,
        walk_depth=walk_depth,
    )

    if json_mode:
        typer.echo(json.dumps([
            {
                "profile": r.profile.name,
                "category": r.profile.category,
                "confidence": r.confidence,
                "matched_required": list(r.matched_required),
                "matched_boost": list(r.matched_boost),
            }
            for r in results
        ], indent=2))
        return

    if not results:
        typer.echo(
            "(no profile candidates — try `sange gitignore list` for the full set)"
        )
        return
    typer.echo(f"{'CONFIDENCE':<12} {'PROFILE':<32} EVIDENCE")
    typer.echo(f"{'-' * 12} {'-' * 32} {'-' * 30}")
    for r in results:
        evidence = ", ".join(
            list(r.matched_required) + [f"+{b}" for b in r.matched_boost]
        )
        typer.echo(f"{r.confidence:<12} {r.profile.name:<32} {evidence}")
    typer.echo(f"\n{len(results)} candidate(s)")


# --------------------------------------------------------------------------- #
# `sange gitignore recover`
# --------------------------------------------------------------------------- #


@gitignore_app.command(
    "recover",
    help="Roll forward any crashed-in-progress swap journals.",
)
def recover_command(
    repo_root: Path = typer.Option(
        Path("."),
        "--repo",
        help="Repo root. Default: cwd.",
    ),
) -> None:
    """Walk `.sange/.recovery/` and complete any pending swap."""

    import click

    from sange.core.gitignore import (
        GitignoreSwap,
        ProfileRegistry,
        SwapError,
        default_registry_roots,
    )

    ctx = click.get_current_context()
    json_mode = bool(ctx.obj and ctx.obj.get("json"))

    registry = ProfileRegistry(default_registry_roots(repo_root))
    swap = GitignoreSwap(repo_root.resolve(), registry=registry)

    try:
        results = swap.recover()
    except SwapError as exc:
        typer.echo(f"error: recover failed: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    if json_mode:
        typer.echo(json.dumps([
            {
                "journal_id": r.journal_id,
                "profiles": list(r.profiles),
                "stage": r.stage,
                "was_recovered": r.was_recovered,
            }
            for r in results
        ], indent=2))
        return

    if not results:
        typer.echo("(no in-progress swaps to recover)")
        return
    for r in results:
        typer.echo(
            f"recovered {r.journal_id}: profiles=[{', '.join(r.profiles)}] "
            f"stage={r.stage}"
        )


__all__ = [
    "current_command",
    "detect_command",
    "gitignore_app",
    "list_command",
    "recover_command",
    "swap_command",
]
