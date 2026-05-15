"""`sange ai` sub-app — provider preview + introspection.

v0.1 commands:
  * `sange ai providers`  — list known provider names + SDK status.
  * `sange ai preview --task commit-msg --diff <path>` — render the
                            prompt that would be sent, without sending.
"""

from __future__ import annotations

import json
from pathlib import Path

import typer

ai_app = typer.Typer(
    name="ai",
    help="AI provider preview + introspection.",
    no_args_is_help=True,
)


# --------------------------------------------------------------------------- #
# `sange ai providers`
# --------------------------------------------------------------------------- #


@ai_app.command("providers", help="List registered AI providers + capabilities.")
def providers_command() -> None:
    import click

    from sange.adapters.ai import AIProviderNotInstalled, get_provider

    ctx = click.get_current_context()
    json_mode = bool(ctx.obj and ctx.obj.get("json"))

    rows: list[dict] = []
    for name in ("mock", "anthropic", "openai", "ollama", "gemini", "bedrock"):
        try:
            provider = get_provider(name)
            caps = provider.capabilities
            rows.append(
                {
                    "name": name,
                    "sdk": "installed",
                    "supports_streaming": caps.supports_streaming,
                    "supports_json_mode": caps.supports_json_mode,
                    "supports_tool_use": caps.supports_tool_use,
                    "default_model": caps.default_model,
                }
            )
        except AIProviderNotInstalled:
            rows.append({"name": name, "sdk": "missing"})
        except Exception as exc:
            rows.append({"name": name, "sdk": "error", "error": str(exc)})

    if json_mode:
        typer.echo(json.dumps({"providers": rows}, indent=2))
        return

    # Plain-text table.
    typer.echo(f"{'PROVIDER':<14} {'SDK':<10} {'STREAM':<8} {'JSON':<6} {'TOOLS':<6} DEFAULT-MODEL")
    typer.echo(f"{'-' * 14} {'-' * 10} {'-' * 8} {'-' * 6} {'-' * 6} {'-' * 20}")
    for row in rows:
        if row["sdk"] == "installed":
            typer.echo(
                f"{row['name']:<14} {'installed':<10} "
                f"{('yes' if row['supports_streaming'] else 'no'):<8} "
                f"{('yes' if row['supports_json_mode'] else 'no'):<6} "
                f"{('yes' if row['supports_tool_use'] else 'no'):<6} "
                f"{row['default_model']}"
            )
        else:
            extra = f" — {row['error']}" if "error" in row else ""
            typer.echo(f"{row['name']:<14} {row['sdk']:<10}{extra}")


# --------------------------------------------------------------------------- #
# `sange ai preview`
# --------------------------------------------------------------------------- #


@ai_app.command("preview", help="Render the prompt for a task without sending.")
def preview_command(
    task: str = typer.Option(
        "commit-msg",
        "--task",
        help="Task to preview. v0.1 supports: commit-msg.",
    ),
    diff_path: Path | None = typer.Option(
        None,
        "--diff",
        help="Path to a file containing the staged diff. "
             "When omitted, reads from stdin.",
        exists=False,
    ),
    provider: str = typer.Option(
        "mock",
        "--provider",
        help="Provider whose formatting to preview (anthropic / openai / mock / ...).",
    ),
    branch: str = typer.Option("", "--branch", help="Current branch name."),
    files_changed: list[str] = typer.Option(
        [],
        "--file",
        help="Files changed by the diff. Repeat for multiple. "
             "(`--file a.py --file b.py`)",
    ),
) -> None:
    from sange.core.enhancer import PromptEnhancer, TemplateRegistry
    from sange.core.enhancer.tasks.commit_message import (
        TEMPLATE_ID,
        build_commit_message_template,
    )

    if task != "commit-msg":
        typer.echo(f"unknown task {task!r}; v0.1 supports: commit-msg", err=True)
        raise typer.Exit(code=2)

    import click

    ctx = click.get_current_context()
    json_mode = bool(ctx.obj and ctx.obj.get("json"))

    diff_text = _read_diff(diff_path)
    if not diff_text:
        typer.echo("error: diff is empty (use --diff <path> or pipe via stdin)", err=True)
        raise typer.Exit(code=2)

    registry = TemplateRegistry([build_commit_message_template()])
    enhancer = PromptEnhancer(templates=registry)

    files = tuple(files_changed)
    files_summary = (
        "\n".join(f"- {p}" for p in files) if files else "(no files listed)"
    )

    formatted = enhancer.preview(
        TEMPLATE_ID,
        {
            "diff": diff_text,
            "branch": branch or "(unknown)",
            "recent_commits": "(none)",
            "files_changed_count": str(len(files)),
            "files_changed_summary": files_summary,
        },
        provider=provider,
        trusted_vars={
            "branch", "recent_commits",
            "files_changed_count", "files_changed_summary",
        },
    )

    if json_mode:
        payload = {
            "task": task,
            "provider": provider,
            "requires_json": formatted.requires_json,
            "messages": [
                {"role": m.role.value, "content": m.content}
                for m in formatted.messages
            ],
        }
        typer.echo(json.dumps(payload, indent=2))
        return

    for m in formatted.messages:
        typer.echo(f"=== {m.role.value.upper()} ===")
        typer.echo(m.content)
        typer.echo("")


def _read_diff(diff_path: Path | None) -> str:
    import sys

    if diff_path is not None:
        if not diff_path.is_file():
            typer.echo(f"error: diff file not found: {diff_path}", err=True)
            raise typer.Exit(code=2)
        return diff_path.read_text(encoding="utf-8")
    if sys.stdin.isatty():
        return ""
    return sys.stdin.read()


__all__ = ["ai_app", "preview_command", "providers_command"]
