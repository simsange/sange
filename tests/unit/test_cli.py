"""Tests for src/sange/cli/ — typer-based CLI entry-point."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from sange._version import __version__
from sange.cli import app


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


# --------------------------------------------------------------------------- #
# --version
# --------------------------------------------------------------------------- #


class TestVersion:
    def test_prints_version_and_exits(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert __version__ in result.output
        assert "sange" in result.output.lower()


# --------------------------------------------------------------------------- #
# doctor
# --------------------------------------------------------------------------- #


class TestDoctor:
    def test_doctor_basic(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["doctor"])
        assert result.exit_code == 0
        # Each check must appear at least once.
        assert "python:" in result.output
        assert "git:" in result.output
        assert "config:" in result.output
        assert "ai-providers:" in result.output

    def test_doctor_json(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["--json", "doctor"])
        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert payload["ok"] in (True, False)
        names = [c["name"] for c in payload["checks"]]
        assert "python" in names
        assert "git" in names
        assert "config" in names
        assert "ai-providers" in names

    def test_doctor_reports_mock_provider_installed(
        self, runner: CliRunner
    ) -> None:
        result = runner.invoke(app, ["--json", "doctor"])
        payload = json.loads(result.output)
        ai_check = next(c for c in payload["checks"] if c["name"] == "ai-providers")
        assert ai_check["details"]["mock"] == "installed"


# --------------------------------------------------------------------------- #
# ai providers
# --------------------------------------------------------------------------- #


class TestAiProviders:
    def test_lists_providers(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["ai", "providers"])
        assert result.exit_code == 0
        assert "mock" in result.output
        assert "PROVIDER" in result.output  # table header

    def test_providers_json(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["--json", "ai", "providers"])
        assert result.exit_code == 0
        payload = json.loads(result.output)
        names = [p["name"] for p in payload["providers"]]
        assert "mock" in names
        mock_row = next(p for p in payload["providers"] if p["name"] == "mock")
        assert mock_row["sdk"] == "installed"
        assert mock_row["supports_streaming"] is True

    def test_providers_reports_missing_sdks(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["--json", "ai", "providers"])
        payload = json.loads(result.output)
        names_to_sdk = {p["name"]: p["sdk"] for p in payload["providers"]}
        # Anthropic / OpenAI / Ollama not installed in test env.
        assert names_to_sdk["anthropic"] in ("missing", "error")
        assert names_to_sdk["openai"] in ("missing", "error")


# --------------------------------------------------------------------------- #
# ai preview
# --------------------------------------------------------------------------- #


class TestAiPreview:
    def test_preview_from_file(self, runner: CliRunner, tmp_path: Path) -> None:
        diff = tmp_path / "patch.diff"
        diff.write_text("+ added a thing\n")
        result = runner.invoke(
            app, ["ai", "preview", "--diff", str(diff), "--branch", "main"]
        )
        assert result.exit_code == 0
        assert "SYSTEM" in result.output or "USER" in result.output
        assert "added a thing" in result.output

    def test_preview_from_stdin(self, runner: CliRunner) -> None:
        result = runner.invoke(
            app, ["ai", "preview"], input="+ from stdin\n"
        )
        assert result.exit_code == 0
        assert "from stdin" in result.output

    def test_preview_empty_diff_errors(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["ai", "preview"])
        # No stdin + no --diff → exit 2 (usage error).
        assert result.exit_code == 2

    def test_preview_unknown_task_errors(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        diff = tmp_path / "p.diff"
        diff.write_text("x")
        result = runner.invoke(
            app, ["ai", "preview", "--task", "nope", "--diff", str(diff)]
        )
        assert result.exit_code == 2
        assert "unknown task" in result.output.lower()

    def test_preview_missing_file_errors(self, runner: CliRunner) -> None:
        result = runner.invoke(
            app, ["ai", "preview", "--diff", "/nonexistent/path/diff"]
        )
        assert result.exit_code == 2

    def test_preview_anthropic_provider_uses_xml(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        diff = tmp_path / "p.diff"
        diff.write_text("+ change\n")
        result = runner.invoke(
            app,
            ["ai", "preview", "--diff", str(diff), "--provider", "anthropic"],
        )
        assert result.exit_code == 0
        assert "<task>" in result.output  # XML strategy fires

    def test_preview_json_mode(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        diff = tmp_path / "p.diff"
        diff.write_text("+ change\n")
        result = runner.invoke(
            app, ["--json", "ai", "preview", "--diff", str(diff)]
        )
        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert payload["task"] == "commit-msg"
        assert payload["provider"] == "mock"
        assert isinstance(payload["messages"], list)


# --------------------------------------------------------------------------- #
# commit
# --------------------------------------------------------------------------- #


class TestCommit:
    def test_commit_with_default_mock_fails_validation(
        self, runner: CliRunner
    ) -> None:
        # MockProvider can't synthesize valid JSON → exit 70.
        result = runner.invoke(app, ["commit"], input="+ change\n")
        assert result.exit_code == 70
        assert "AI provider error" in result.output

    def test_commit_empty_diff_exits_2(self, runner: CliRunner) -> None:
        # Send empty stdin → empty diff → usage error.
        result = runner.invoke(app, ["commit"], input="")
        assert result.exit_code == 2
        assert "diff is empty" in result.output

    def test_commit_missing_diff_file_exits_2(
        self, runner: CliRunner
    ) -> None:
        result = runner.invoke(
            app, ["commit", "--diff", "/nonexistent/diff"]
        )
        assert result.exit_code == 2

    def test_commit_with_canned_response(
        self, runner: CliRunner, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Inject a custom mock that returns valid JSON so the
        end-to-end CLI → enhancer → provider path succeeds."""

        from sange.adapters.ai import (
            CompletionResponse,
            FinishReason,
            MockProvider,
            Usage,
        )

        class _ValidJsonMock(MockProvider):
            def complete(self, request):  # type: ignore[override]
                return CompletionResponse(
                    text=json.dumps({
                        "type": "feat",
                        "scope": "auth",
                        "subject": "add login flow",
                        "body": "Wires the new handler.",
                        "breaking_change": False,
                    }),
                    finish_reason=FinishReason.STOP,
                    usage=Usage(tokens_in=5, tokens_out=5, model=request.model),
                    provider="mock",
                    model=request.model,
                )

        # Patch get_provider so it returns our mock for 'mock'.
        from sange.adapters.ai import _protocol

        original = _protocol.get_provider

        def _patched(name: str, **kwargs):
            if name == "mock":
                return _ValidJsonMock()
            return original(name, **kwargs)

        monkeypatch.setattr(_protocol, "get_provider", _patched)
        # Also patch the symbol that the enhancer imports directly.
        from sange.core.enhancer import enhancer as enhancer_mod

        monkeypatch.setattr(enhancer_mod, "get_provider", _patched)

        result = runner.invoke(app, ["commit"], input="+ change\n")
        assert result.exit_code == 0, result.output
        # Conventional Commits format: type(scope): subject
        assert "feat(auth): add login flow" in result.output
        assert "Wires the new handler" in result.output

    def test_commit_json_mode(
        self, runner: CliRunner, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from sange.adapters.ai import (
            CompletionResponse,
            FinishReason,
            MockProvider,
            Usage,
        )

        class _Mock(MockProvider):
            def complete(self, request):  # type: ignore[override]
                return CompletionResponse(
                    text=json.dumps({
                        "type": "fix",
                        "scope": "",
                        "subject": "correct rounding",
                        "body": "",
                        "breaking_change": False,
                    }),
                    finish_reason=FinishReason.STOP,
                    usage=Usage(model=request.model),
                    provider="mock",
                    model=request.model,
                )

        from sange.adapters.ai import _protocol
        from sange.core.enhancer import enhancer as enhancer_mod

        def _patched(name: str, **kwargs):
            return _Mock() if name == "mock" else _protocol.get_provider(name, **kwargs)

        monkeypatch.setattr(_protocol, "get_provider", _patched)
        monkeypatch.setattr(enhancer_mod, "get_provider", _patched)

        result = runner.invoke(app, ["--json", "commit"], input="+ change\n")
        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert payload["type"] == "fix"
        assert payload["subject"] == "correct rounding"
        assert payload["scope"] == ""
        assert payload["breaking_change"] is False

    def test_commit_with_breaking_change(
        self, runner: CliRunner, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from sange.adapters.ai import (
            CompletionResponse,
            FinishReason,
            MockProvider,
            Usage,
        )

        class _Mock(MockProvider):
            def complete(self, request):  # type: ignore[override]
                return CompletionResponse(
                    text=json.dumps({
                        "type": "feat",
                        "scope": "api",
                        "subject": "remove v1 endpoints",
                        "body": "",
                        "breaking_change": True,
                    }),
                    finish_reason=FinishReason.STOP,
                    usage=Usage(model=request.model),
                    provider="mock",
                    model=request.model,
                )

        from sange.adapters.ai import _protocol
        from sange.core.enhancer import enhancer as enhancer_mod

        def _patched(name: str, **kwargs):
            return _Mock() if name == "mock" else _protocol.get_provider(name, **kwargs)

        monkeypatch.setattr(_protocol, "get_provider", _patched)
        monkeypatch.setattr(enhancer_mod, "get_provider", _patched)

        result = runner.invoke(app, ["commit"], input="+ change\n")
        assert result.exit_code == 0
        # Breaking change marker `!` between scope and colon.
        assert "feat(api)!: remove v1 endpoints" in result.output


# --------------------------------------------------------------------------- #
# Top-level / help
# --------------------------------------------------------------------------- #


class TestTopLevel:
    def test_help_lists_commands(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        # The three top-level commands must appear.
        for cmd in ("ai", "doctor", "commit"):
            assert cmd in result.output

    def test_no_args_shows_help(self, runner: CliRunner) -> None:
        # `no_args_is_help=True` on the app — invoking with no args
        # surfaces help and exits with click's default usage-error code 2.
        result = runner.invoke(app, [])
        # Typer returns 0 with help text when no_args_is_help fires;
        # accept either 0 or 2 for portability.
        assert result.exit_code in (0, 2)
        assert "sange" in result.output.lower()

    def test_ai_no_args_shows_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["ai"])
        assert result.exit_code in (0, 2)
        assert "preview" in result.output or "providers" in result.output
