"""Sange CLI — typer-based command surface.

Per §7.0.1 the CLI framework pin is `typer`. This package exposes one
typer app (`app`) that the `[project.scripts]` entry-point invokes.

v0.1 command surface:

  * `sange --version`            — print version and exit.
  * `sange doctor`               — environment health checks (Python
                                    version, git availability, config
                                    validity, AI provider status).
  * `sange ai preview`           — show the prompt that would be sent
                                    for a given task without sending
                                    (§6.7.1 "inspectable").
  * `sange ai providers`         — list registered AI providers + their
                                    declared capabilities.
  * `sange commit`               — one-shot: takes a diff (from a file
                                    or stdin), runs it through the
                                    prompt enhancer, prints the
                                    Conventional Commits message.

§7.0.2 TerminalProfile / glyph swapping is deferred to a future task —
v0.1 just renders plain text. JSON output mode (`--json`) is wired on
every command that surfaces structured data.

Tests use `typer.testing.CliRunner`. The CLI never invokes a real AI
provider in tests; the test fixtures pre-register a `MockProvider`
with canned responses.
"""

from __future__ import annotations

from sange.cli.main import app

__all__ = ["app"]
