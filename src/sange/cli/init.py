"""`sange init` — materialize the .sange/ skeleton in a target repo.

Bootstrap UX per §6.4 + §6.5 + §10:

  1. Create `<repo>/.sange/commits/` and `<repo>/.sange/telemetry/` so
     `sange commit` lands without pre-creating directories.
  2. Copy `templates/Makefile.template` → `<repo>/Makefile` (the §10.1
     shim).
  3. Copy `templates/makefiles/<category>/<frag>.mk` → `<repo>/.sange/
     makefiles/<category>/<frag>.mk` (the §10.2 fragments).
  4. Append `/Makefile` + `/.sange/` to `<repo>/.gitignore` per §10.3
     (the §6.4 `.sange/` is partially gitignored — `.sange/commits/`
     and `.sange/telemetry/` are; `.sange/config.toml` is checked in;
     this v0.1 sub-command writes the minimal entries).

Idempotency: re-running `sange init` is safe and minimal — existing
files are left untouched unless `--force` is passed. Missing files
are filled in (partial-skeleton repair). Gitignore lines are added
only when not already present.

Per §10.3 the Makefile is **always gitignored**. The user can review
the diff before committing; T-013's doctor check will surface any
slip.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import typer

# Source roots — resolved relative to the installed package.
_PACKAGE_ROOT = Path(__file__).resolve().parent.parent  # src/sange/
_REPO_ROOT = _PACKAGE_ROOT.parent.parent                # repo root
_TEMPLATES_DIR = _REPO_ROOT / "templates"


def init_command(
    repo_root: Path = typer.Option(
        Path("."),
        "--repo",
        help="Target repo root. Default: the current directory.",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        help="Overwrite existing files. Default: keep existing untouched.",
    ),
    install_makefile: bool = typer.Option(
        True,
        "--makefile/--no-makefile",
        help="Install the top-level Makefile + .sange/makefiles/ tree.",
    ),
    update_gitignore: bool = typer.Option(
        True,
        "--gitignore/--no-gitignore",
        help="Append /Makefile + /.sange/ entries to .gitignore.",
    ),
) -> None:
    """Materialize `.sange/` skeleton + (optionally) the Makefile shim."""

    import click

    ctx = click.get_current_context()
    json_mode = bool(ctx.obj and ctx.obj.get("json"))

    actions: list[dict] = []

    repo = repo_root.resolve()
    if not repo.is_dir():
        typer.echo(f"error: --repo {repo_root} is not a directory", err=True)
        raise typer.Exit(code=2)

    # Always create the .sange/ skeleton.
    for sub in ("commits", "telemetry"):
        target = repo / ".sange" / sub
        existed = target.exists()
        target.mkdir(parents=True, exist_ok=True)
        actions.append(
            {
                "kind": "mkdir",
                "path": str(target.relative_to(repo)),
                "status": "exists" if existed else "created",
            }
        )

    # Install Makefile + .sange/makefiles/ tree if requested.
    if install_makefile:
        actions.extend(_install_makefile_kit(repo, force=force))

    # Update .gitignore if requested.
    if update_gitignore:
        actions.append(_update_gitignore(repo))

    if json_mode:
        typer.echo(
            json.dumps(
                {
                    "repo": str(repo),
                    "actions": actions,
                },
                indent=2,
            )
        )
        return

    typer.echo(f"initialized .sange at {repo}")
    for a in actions:
        marker = {
            "created": "[+]",
            "exists": "[=]",
            "skipped": "[ ]",
            "updated": "[~]",
            "overwritten": "[!]",
            "appended": "[+]",
            "already-present": "[=]",
        }.get(a.get("status", ""), "[?]")
        typer.echo(f"  {marker} {a.get('path', a.get('kind', '?'))}: {a.get('status', '')}")


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _install_makefile_kit(repo: Path, *, force: bool) -> list[dict]:
    """Copy templates/Makefile.template → <repo>/Makefile + every .mk
    fragment under templates/makefiles/ to <repo>/.sange/makefiles/."""

    actions: list[dict] = []

    shim_src = _TEMPLATES_DIR / "Makefile.template"
    shim_dst = repo / "Makefile"
    actions.append(_copy_file(shim_src, shim_dst, repo, force=force))

    makefiles_src = _TEMPLATES_DIR / "makefiles"
    if makefiles_src.is_dir():
        for source in sorted(makefiles_src.rglob("*.mk")):
            rel = source.relative_to(makefiles_src)
            dest = repo / ".sange" / "makefiles" / rel
            actions.append(_copy_file(source, dest, repo, force=force))

    return actions


def _copy_file(src: Path, dst: Path, repo: Path, *, force: bool) -> dict:
    """Copy `src` → `dst`. Returns an action record."""

    rel = str(dst.relative_to(repo))
    if not src.is_file():
        return {"kind": "copy", "path": rel, "status": f"missing-source:{src}"}

    if dst.exists() and not force:
        return {"kind": "copy", "path": rel, "status": "skipped"}

    dst.parent.mkdir(parents=True, exist_ok=True)
    existed = dst.exists()
    shutil.copy2(src, dst)
    return {
        "kind": "copy",
        "path": rel,
        "status": "overwritten" if existed else "created",
    }


_GITIGNORE_ENTRIES = ("/Makefile", "/.sange/commits/", "/.sange/telemetry/")
_GITIGNORE_HEADER = "# Sange-managed entries (sange init)"


def _update_gitignore(repo: Path) -> dict:
    """Append the §10.3 + §6.4 entries to `.gitignore` (idempotent)."""

    gitignore = repo / ".gitignore"
    if gitignore.exists():
        existing = gitignore.read_text(encoding="utf-8")
    else:
        existing = ""

    existing_lines = {line.rstrip() for line in existing.splitlines()}
    missing = [e for e in _GITIGNORE_ENTRIES if e not in existing_lines]

    if not missing:
        return {
            "kind": "gitignore",
            "path": ".gitignore",
            "status": "already-present",
        }

    block = ""
    if existing and not existing.endswith("\n"):
        block += "\n"
    if _GITIGNORE_HEADER not in existing:
        block += f"\n{_GITIGNORE_HEADER}\n"
    block += "\n".join(missing) + "\n"

    with gitignore.open("a", encoding="utf-8") as handle:
        handle.write(block)

    return {
        "kind": "gitignore",
        "path": ".gitignore",
        "status": "appended",
        "added_lines": missing,
    }


__all__ = ["init_command"]
