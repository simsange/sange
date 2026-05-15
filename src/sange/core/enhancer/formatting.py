"""Model-specific prompt formatting strategies.

Per §6.7.1 "model-specific formatting (Claude prefers XML delimiters;
GPT prefers JSON; local models often prefer plain markdown)".

A `FormattingStrategy` wraps a `RenderedPrompt` into the exact
`Message`s that go to a given provider. Each provider family gets one:

  * `XmlFormattingStrategy`      — Anthropic/Claude (XML-tagged sections).
  * `JsonFormattingStrategy`     — OpenAI/Azure-OpenAI (JSON-mode-friendly).
  * `MarkdownFormattingStrategy` — Ollama/Gemini/Bedrock/Mock (plain
                                    markdown with headers).

The Application layer's enhancer queries `for_provider(name)` and
applies it. New providers can register their own strategy via
`register_strategy()`.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass

from sange.adapters.ai._protocol import Message, MessageRole
from sange.core.enhancer.templates import RenderedPrompt

# --------------------------------------------------------------------------- #
# Strategy interface (Protocol-ish — kept as a regular class for v0.1)
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class FormattedRequest:
    """The output of `format()` — a list of `Message`s plus the
    structured-output hint (if any). The enhancer feeds these directly
    into `CompletionRequest`."""

    messages: tuple[Message, ...]
    requires_json: bool = False


class FormattingStrategy:
    """Base interface. Subclasses override `format()`."""

    name: str = "base"

    def format(self, rendered: RenderedPrompt) -> FormattedRequest:  # pragma: no cover
        raise NotImplementedError


# --------------------------------------------------------------------------- #
# Concrete strategies
# --------------------------------------------------------------------------- #


class XmlFormattingStrategy(FormattingStrategy):
    """Claude-style XML delimiters.

    Claude consistently performs better when sections of the prompt
    are XML-tagged (Anthropic's documented best practice). The system
    message carries general instructions; the user message wraps the
    task content in `<task>`, `<context>`, `<output_schema>` tags.
    """

    name = "xml"

    def format(self, rendered: RenderedPrompt) -> FormattedRequest:
        messages: list[Message] = []
        if rendered.system:
            messages.append(Message(role=MessageRole.SYSTEM, content=rendered.system))

        user_parts = [f"<task>\n{rendered.user}\n</task>"]
        if rendered.output_schema is not None:
            schema_json = json.dumps(rendered.output_schema, indent=2)
            user_parts.append(f"<output_schema>\n{schema_json}\n</output_schema>")
            user_parts.append(
                "<instructions>Respond with valid JSON matching the schema. "
                "Output ONLY the JSON; no prose, no fences.</instructions>"
            )
        messages.append(Message(role=MessageRole.USER, content="\n\n".join(user_parts)))

        return FormattedRequest(
            messages=tuple(messages),
            requires_json=rendered.output_schema is not None,
        )


class JsonFormattingStrategy(FormattingStrategy):
    """OpenAI-style strategy.

    The provider gets `response_format=JSON_OBJECT` when a schema is
    present (OpenAI honors this natively); otherwise it falls back to
    markdown structuring. The system message states the contract; the
    schema is appended to the user message as a JSON block.
    """

    name = "json"

    def format(self, rendered: RenderedPrompt) -> FormattedRequest:
        messages: list[Message] = []
        if rendered.system:
            messages.append(Message(role=MessageRole.SYSTEM, content=rendered.system))

        user_parts = [rendered.user]
        if rendered.output_schema is not None:
            schema_json = json.dumps(rendered.output_schema, indent=2)
            user_parts.append(
                "\nOutput must be valid JSON matching this schema:\n\n"
                f"```json\n{schema_json}\n```"
            )
        messages.append(Message(role=MessageRole.USER, content="\n".join(user_parts)))

        return FormattedRequest(
            messages=tuple(messages),
            requires_json=rendered.output_schema is not None,
        )


class MarkdownFormattingStrategy(FormattingStrategy):
    """Plain-markdown strategy.

    Used for local models (Ollama) and providers without strong
    structured-output support. Schema (if any) is inlined as a fenced
    `json` block with a "respond in JSON" directive.
    """

    name = "markdown"

    def format(self, rendered: RenderedPrompt) -> FormattedRequest:
        messages: list[Message] = []
        if rendered.system:
            messages.append(Message(role=MessageRole.SYSTEM, content=rendered.system))

        user_parts = [f"## Task\n\n{rendered.user}"]
        if rendered.output_schema is not None:
            schema_json = json.dumps(rendered.output_schema, indent=2)
            user_parts.append(
                "## Output format\n\n"
                "Respond ONLY with valid JSON matching:\n\n"
                f"```json\n{schema_json}\n```"
            )
        messages.append(Message(role=MessageRole.USER, content="\n\n".join(user_parts)))

        return FormattedRequest(
            messages=tuple(messages),
            requires_json=rendered.output_schema is not None,
        )


# --------------------------------------------------------------------------- #
# Provider → strategy mapping
# --------------------------------------------------------------------------- #


_STRATEGY_REGISTRY: dict[str, FormattingStrategy] = {
    "anthropic": XmlFormattingStrategy(),
    "openai": JsonFormattingStrategy(),
    "azure-openai": JsonFormattingStrategy(),
    "ollama": MarkdownFormattingStrategy(),
    "gemini": MarkdownFormattingStrategy(),
    "bedrock": MarkdownFormattingStrategy(),
    "mock": MarkdownFormattingStrategy(),
}


def for_provider(name: str) -> FormattingStrategy:
    """Return the strategy registered for `name`. Unknown providers
    fall back to markdown (the safest least-common-denominator)."""

    return _STRATEGY_REGISTRY.get(name, MarkdownFormattingStrategy())


def register_strategy(name: str, strategy: FormattingStrategy) -> None:
    """Plug-in point — third-party providers register their strategy."""

    _STRATEGY_REGISTRY[name] = strategy


def registered_providers() -> Sequence[str]:
    """Snapshot of registered provider names (sorted, for stable output)."""

    return tuple(sorted(_STRATEGY_REGISTRY.keys()))


__all__ = [
    "FormattedRequest",
    "FormattingStrategy",
    "JsonFormattingStrategy",
    "MarkdownFormattingStrategy",
    "XmlFormattingStrategy",
    "for_provider",
    "register_strategy",
    "registered_providers",
]
