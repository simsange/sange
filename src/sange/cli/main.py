"""`sange` — top-level typer app.

Composes the per-feature command groups: `ai` (preview, providers),
`doctor`, `commit`. Top-level options:

  * `--version`  — print version and exit.
  * `--json`     — JSON output mode (machine-readable). Each command
                   chooses what to emit.

Exit codes follow the §16 / `docs/reference/exit-codes.md` table:
  * 0  — success.
  * 1  — generic failure.
  * 2  — usage error (typer's default for bad args).
  * 64 — config invalid.
  * 65 — VCS not detected / git not installed.
  * 70 — AI provider error.
"""

from __future__ import annotations

import typer

from sange._version import __version__

# Sub-command apps imported lazily inside the factory so that
# `sange --version` doesn't pay the cost of importing the AI subsystem.


app = typer.Typer(
    name="sange",
    help="Polyglot VCS automation toolkit (Git/SVN/Hg/P4).",
    no_args_is_help=True,
    add_completion=False,  # Defer shell-completion to a v0.5 task.
    rich_markup_mode=None,  # Plain output for v0.1 — §7.0.2 deferred.
)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"sange {__version__}")
        raise typer.Exit(code=0)


@app.callback()
def _root(
    version: bool = typer.Option(
        False,
        "--version",
        callback=_version_callback,
        is_eager=True,
        help="Show version and exit.",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Emit machine-readable JSON output where supported.",
    ),
) -> None:
    """Sange — polyglot VCS automation."""

    # `json_output` is read by individual commands via the typer
    # context. Stored on the app's user-data slot when a real command
    # runs; not needed for `--version`.
    import click

    ctx = click.get_current_context()
    ctx.obj = {"json": json_output}


# --------------------------------------------------------------------------- #
# Sub-command registration
# --------------------------------------------------------------------------- #


# Lazy import keeps `sange --version` fast and prevents an AI-package
# import error (e.g. broken extra) from breaking the entire CLI.
from sange.cli.ai import ai_app  # noqa: E402
from sange.cli.audit import audit_app  # noqa: E402
from sange.cli.commit import commit_command  # noqa: E402
from sange.cli.commits import commits_app  # noqa: E402
from sange.cli.doctor import doctor_command  # noqa: E402
from sange.cli.gitignore import gitignore_app  # noqa: E402
from sange.cli.hooks import hooks_app  # noqa: E402
from sange.cli.init import init_command  # noqa: E402
from sange.cli.purge import purge_app  # noqa: E402

app.add_typer(ai_app, name="ai", help="AI provider preview + introspection.")
app.add_typer(
    audit_app, name="audit",
    help="Inspect + verify the hash-chained audit JSONL (T-108).",
)
app.add_typer(commits_app, name="commits", help="Manage the commit lifecycle queue.")
app.add_typer(
    gitignore_app, name="gitignore",
    help="Manage the active gitignore profile (T-101).",
)
app.add_typer(
    hooks_app, name="hooks",
    help="Manage pre-commit / pre-push / etc. hooks (T-102).",
)
app.add_typer(
    purge_app, name="purge",
    help="VCS history purge (read-only v0.5; destructive v1.0+) (T-111).",
)
app.command("doctor", help="Environment health checks.")(doctor_command)
app.command("commit", help="Generate a commit message from a diff.")(commit_command)
app.command("init", help="Bootstrap .sange/ skeleton in the target repo.")(init_command)


__all__ = ["app"]
