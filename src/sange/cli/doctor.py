"""`sange doctor` — minimal health checks for v0.1.

Surfaces actionable diagnostics:

  * Python version — must be ≥ 3.10 (we test on 3.10; pyproject pins ≥ 3.12 long-term).
  * Git availability + version.
  * SangeConfig load attempt — surfaces parse / validation errors.
  * AI provider state — which SDK extras are installed.

The full §11.2 audit-chain probe and §6.10 container-secret audit
land in later tasks. v0.1 keeps the scope tight: report what we can
verify, hedge what we can't.

Exit codes:
  * 0 — all checks passed.
  * 1 — one or more checks failed; details on stderr.
"""

from __future__ import annotations

import json
import platform
import shutil
import subprocess
import sys
from dataclasses import dataclass, field

import typer


@dataclass
class CheckResult:
    name: str
    ok: bool
    message: str
    details: dict = field(default_factory=dict)


def _check_python() -> CheckResult:
    v = sys.version_info
    ok = v >= (3, 10)
    return CheckResult(
        name="python",
        ok=ok,
        message=f"Python {v.major}.{v.minor}.{v.micro}"
        + ("" if ok else " (need ≥ 3.10)"),
        details={"major": v.major, "minor": v.minor, "patch": v.micro},
    )


def _check_git() -> CheckResult:
    path = shutil.which("git")
    if path is None:
        return CheckResult(
            name="git",
            ok=False,
            message="git not found on PATH",
        )
    try:
        out = subprocess.run(
            [path, "--version"],
            capture_output=True,
            check=True,
            text=True,
            timeout=5,
        )
        return CheckResult(
            name="git",
            ok=True,
            message=out.stdout.strip(),
            details={"path": path, "version": out.stdout.strip()},
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        return CheckResult(
            name="git",
            ok=False,
            message=f"git --version failed: {exc}",
        )


def _check_config() -> CheckResult:
    # We only try to load the default; a missing repo-config is fine.
    try:
        from sange.core.config import SangeConfig

        SangeConfig()  # default-minimal must always validate.
        return CheckResult(
            name="config",
            ok=True,
            message="SangeConfig default-minimal validates",
        )
    except Exception as exc:  # pragma: no cover — sanity net.
        return CheckResult(
            name="config",
            ok=False,
            message=f"SangeConfig default failed to validate: {exc}",
        )


def _check_ai_providers() -> CheckResult:
    """Report which provider SDKs are installed.

    Mock is always available (no SDK). Other providers report
    installed/missing — missing is informational, not a failure.
    """

    statuses: dict[str, str] = {}
    for name in ("mock", "anthropic", "openai", "ollama"):
        try:
            from sange.adapters.ai import AIProviderNotInstalled, get_provider

            get_provider(name)
            statuses[name] = "installed"
        except AIProviderNotInstalled:
            statuses[name] = "missing-sdk (install sange[ai-" + name + "])"
        except Exception as exc:  # noqa: BLE001 — informational only.
            statuses[name] = f"error: {exc}"

    ok = statuses.get("mock") == "installed"
    message = ", ".join(f"{n}={s}" for n, s in statuses.items())
    return CheckResult(
        name="ai-providers",
        ok=ok,
        message=message,
        details=statuses,
    )


def doctor_command() -> None:
    """Run all v0.1 health checks; print results; exit non-zero on failure."""

    import click

    ctx = click.get_current_context()
    json_mode = bool(ctx.obj and ctx.obj.get("json"))

    checks = [
        _check_python(),
        _check_git(),
        _check_config(),
        _check_ai_providers(),
    ]

    all_ok = all(c.ok for c in checks)

    if json_mode:
        payload = {
            "ok": all_ok,
            "checks": [
                {
                    "name": c.name,
                    "ok": c.ok,
                    "message": c.message,
                    "details": c.details,
                }
                for c in checks
            ],
            "platform": platform.platform(),
        }
        typer.echo(json.dumps(payload, indent=2))
    else:
        for c in checks:
            marker = "[OK]  " if c.ok else "[FAIL]"
            typer.echo(f"{marker} {c.name}: {c.message}")
        typer.echo("")
        if all_ok:
            typer.echo("All checks passed.")
        else:
            typer.echo("One or more checks failed.", err=True)

    raise typer.Exit(code=0 if all_ok else 1)


__all__ = ["CheckResult", "doctor_command"]
