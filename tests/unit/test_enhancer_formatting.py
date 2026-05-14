"""Tests for src/sange/core/enhancer/formatting.py — model-specific strategies."""

from __future__ import annotations

from sange.adapters.ai import MessageRole
from sange.core.enhancer.formatting import (
    FormattedRequest,
    JsonFormattingStrategy,
    MarkdownFormattingStrategy,
    XmlFormattingStrategy,
    for_provider,
    register_strategy,
    registered_providers,
)
from sange.core.enhancer.templates import RenderedPrompt


def _rendered(
    system: str = "You are helpful.",
    user: str = "Hi there",
    schema: dict | None = None,
) -> RenderedPrompt:
    return RenderedPrompt(
        system=system,
        user=user,
        template_id="t",
        template_version="1.0",
        output_schema=schema,
    )


# --------------------------------------------------------------------------- #
# XML strategy
# --------------------------------------------------------------------------- #


class TestXmlStrategy:
    def test_no_schema(self) -> None:
        out = XmlFormattingStrategy().format(_rendered())
        assert isinstance(out, FormattedRequest)
        assert out.requires_json is False
        roles = [m.role for m in out.messages]
        assert MessageRole.SYSTEM in roles
        assert MessageRole.USER in roles
        user_msg = next(m for m in out.messages if m.role is MessageRole.USER)
        assert "<task>" in user_msg.content
        assert "Hi there" in user_msg.content
        assert "</task>" in user_msg.content

    def test_with_schema(self) -> None:
        schema = {"type": "object", "required": ["x"]}
        out = XmlFormattingStrategy().format(_rendered(schema=schema))
        assert out.requires_json is True
        user_msg = next(m for m in out.messages if m.role is MessageRole.USER)
        assert "<output_schema>" in user_msg.content
        assert '"type": "object"' in user_msg.content
        assert "<instructions>" in user_msg.content

    def test_no_system(self) -> None:
        out = XmlFormattingStrategy().format(_rendered(system=""))
        roles = [m.role for m in out.messages]
        assert MessageRole.SYSTEM not in roles
        assert MessageRole.USER in roles


# --------------------------------------------------------------------------- #
# JSON strategy
# --------------------------------------------------------------------------- #


class TestJsonStrategy:
    def test_no_schema(self) -> None:
        out = JsonFormattingStrategy().format(_rendered())
        assert out.requires_json is False
        user_msg = next(m for m in out.messages if m.role is MessageRole.USER)
        assert "Hi there" in user_msg.content

    def test_with_schema(self) -> None:
        schema = {"type": "object", "required": ["x"]}
        out = JsonFormattingStrategy().format(_rendered(schema=schema))
        assert out.requires_json is True
        user_msg = next(m for m in out.messages if m.role is MessageRole.USER)
        assert "```json" in user_msg.content
        assert '"type": "object"' in user_msg.content


# --------------------------------------------------------------------------- #
# Markdown strategy
# --------------------------------------------------------------------------- #


class TestMarkdownStrategy:
    def test_basic(self) -> None:
        out = MarkdownFormattingStrategy().format(_rendered())
        user_msg = next(m for m in out.messages if m.role is MessageRole.USER)
        assert "## Task" in user_msg.content
        assert "Hi there" in user_msg.content

    def test_with_schema(self) -> None:
        schema = {"type": "object", "required": ["x"]}
        out = MarkdownFormattingStrategy().format(_rendered(schema=schema))
        assert out.requires_json is True
        user_msg = next(m for m in out.messages if m.role is MessageRole.USER)
        assert "## Output format" in user_msg.content


# --------------------------------------------------------------------------- #
# Provider → strategy mapping
# --------------------------------------------------------------------------- #


class TestProviderMapping:
    def test_anthropic_uses_xml(self) -> None:
        s = for_provider("anthropic")
        assert isinstance(s, XmlFormattingStrategy)

    def test_openai_uses_json(self) -> None:
        s = for_provider("openai")
        assert isinstance(s, JsonFormattingStrategy)

    def test_azure_uses_json(self) -> None:
        s = for_provider("azure-openai")
        assert isinstance(s, JsonFormattingStrategy)

    def test_ollama_uses_markdown(self) -> None:
        assert isinstance(for_provider("ollama"), MarkdownFormattingStrategy)

    def test_mock_uses_markdown(self) -> None:
        assert isinstance(for_provider("mock"), MarkdownFormattingStrategy)

    def test_unknown_falls_back_to_markdown(self) -> None:
        s = for_provider("not-a-real-provider")
        assert isinstance(s, MarkdownFormattingStrategy)

    def test_registered_providers_includes_known(self) -> None:
        names = registered_providers()
        for expected in ("anthropic", "openai", "ollama", "mock"):
            assert expected in names

    def test_register_custom_strategy(self) -> None:
        register_strategy("my-custom-provider", JsonFormattingStrategy())
        try:
            s = for_provider("my-custom-provider")
            assert isinstance(s, JsonFormattingStrategy)
        finally:
            # Don't leak registration to other tests.
            from sange.core.enhancer.formatting import _STRATEGY_REGISTRY

            _STRATEGY_REGISTRY.pop("my-custom-provider", None)
