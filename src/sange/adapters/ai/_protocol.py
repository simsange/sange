"""`AIProvider` Protocol + auxiliary types.

Per §6.7 of the architecture prompt. Defines the structural-subtyping
surface every concrete AI provider implements. Application code depends
on `AIProvider`; concrete providers are selected at runtime via
`SangeConfig.ai.default_provider`.

Design rules:

  * **Structural subtyping** — providers don't inherit from `AIProvider`;
    they just need matching method signatures. Mypy / Pyright enforce
    the contract statically.
  * **Streaming-first** — every provider implements both `complete()`
    and `stream()`. Interactive surfaces (CLI/TUI live preview) use
    `stream()`; batch operations use `complete()`.
  * **No I/O leaks** — providers translate SDK exceptions into `AIError`
    sub-exceptions. The Application layer never sees raw `httpx`/`requests`
    errors.
  * **Cost tracking** — every `CompletionResponse` + final `CompletionChunk`
    carries a `Usage` object with `tokens_in`, `tokens_out`,
    `cost_estimate_usd`. The prompt enhancer (T-010) sums these per-session
    for the §12 telemetry collector.
  * **Capability introspection** — `provider.capabilities` is class-level
    + readable without invoking the provider. `sange doctor` enumerates
    configured providers and surfaces their capabilities.

Redaction is NOT here. The prompt-enhancer (T-010) scrubs input before
calling the provider. Providers see already-clean text.
"""

from __future__ import annotations

import enum
from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol, cast

# --------------------------------------------------------------------------- #
# Exceptions
# --------------------------------------------------------------------------- #


class AIError(Exception):
    """Base exception for AI provider failures.

    Concrete providers subclass for situations like:
      * `AIAuthenticationError` — bad API key.
      * `AIRateLimitError`     — provider rate-limit hit.
      * `AITimeoutError`       — request exceeded the configured timeout.
      * `AIInvalidRequestError` — provider rejected the request shape.

    The Application layer pattern-matches on these for retry / fallback
    decisions; raw SDK exceptions are wrapped and re-raised.
    """


class AIProviderNotInstalled(AIError):
    """A provider was requested but its SDK isn't installed.

    Raised by `get_provider(name)` when e.g. `name="anthropic"` but the
    optional `sange[ai-anthropic]` extra isn't present. Surfaced by
    `sange doctor` so the operator can install the missing extra.
    """


# --------------------------------------------------------------------------- #
# Message + Role
# --------------------------------------------------------------------------- #


class MessageRole(str, enum.Enum):
    """Conversation roles understood by all major providers."""

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


@dataclass(frozen=True)
class Message:
    """A single message in a conversation.

    Fields:
      * `role`    — system / user / assistant / tool.
      * `content` — message text. Multi-modal (image/audio) content lives
                    in the future `parts` field for providers that
                    support it (Claude vision, GPT-4 vision); for v0.1
                    text-only is the contract.
      * `name`    — optional sender name (some providers use this for
                    function-call results or named participants).
    """

    role: MessageRole
    content: str
    name: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.role, MessageRole):
            raise ValueError(f"Message.role must be MessageRole, got {type(self.role).__name__}")
        if not self.content and self.role is not MessageRole.ASSISTANT:
            # Assistant messages may be empty during streaming; user / system
            # / tool messages must be non-empty.
            raise ValueError(f"Message.content must be non-empty for role={self.role.value}")


# --------------------------------------------------------------------------- #
# CompletionRequest + ResponseFormat
# --------------------------------------------------------------------------- #


class ResponseFormat(str, enum.Enum):
    """How the provider should shape its response.

    Most providers support TEXT (default) and JSON_OBJECT (structured
    output). STRUCTURED is JSON_OBJECT + a schema (each provider's own
    schema flavor — handled per-adapter).
    """

    TEXT = "text"
    JSON_OBJECT = "json_object"
    STRUCTURED = "structured"


@dataclass(frozen=True)
class CompletionRequest:
    """Input to a `complete()` or `stream()` call.

    Fields:
      * `model`           — provider-specific model identifier
                            (`"claude-opus-4-7"`, `"gpt-4o"`, etc.).
      * `messages`        — the conversation. First message MAY be a
                            system message; the rest alternate user /
                            assistant / tool.
      * `max_tokens`      — soft cap on output tokens. Provider-dependent
                            interpretation.
      * `temperature`     — sampling temperature (0.0 = deterministic).
      * `response_format` — TEXT / JSON_OBJECT / STRUCTURED.
      * `schema`          — JSON Schema dict for STRUCTURED requests; the
                            provider validates the response against this.
      * `metadata`        — opaque dict the provider attaches for billing
                            / observability (Anthropic's `metadata.user_id`,
                            OpenAI's `user`).
      * `stop`            — explicit stop sequences.
      * `timeout_s`       — per-request timeout (provider-dependent).
    """

    model: str
    messages: Sequence[Message]
    max_tokens: int | None = None
    temperature: float = 0.0
    response_format: ResponseFormat = ResponseFormat.TEXT
    schema: dict[str, Any] | None = None
    metadata: dict[str, str] = field(default_factory=dict)
    stop: tuple[str, ...] = field(default_factory=tuple)
    timeout_s: float = 60.0

    def __post_init__(self) -> None:
        if not self.model:
            raise ValueError("CompletionRequest.model must be non-empty")
        if not self.messages:
            raise ValueError("CompletionRequest.messages must be non-empty")
        if not 0.0 <= self.temperature <= 2.0:
            raise ValueError(
                f"CompletionRequest.temperature must be 0.0..2.0; got {self.temperature}"
            )
        if self.max_tokens is not None and self.max_tokens < 1:
            raise ValueError(
                f"CompletionRequest.max_tokens must be ≥ 1 or None; got {self.max_tokens}"
            )
        if self.response_format is ResponseFormat.STRUCTURED and self.schema is None:
            raise ValueError(
                "CompletionRequest.response_format=STRUCTURED requires a `schema`"
            )


# --------------------------------------------------------------------------- #
# Usage + CompletionResponse + CompletionChunk
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Usage:
    """Token + cost accounting for one completion call.

    Fields:
      * `tokens_in`         — prompt tokens charged (provider-counted).
      * `tokens_out`        — completion tokens charged.
      * `cost_estimate_usd` — total cost in USD; computed by the provider
                              from its pricing table. Always non-negative.
      * `model`             — model that actually served the request
                              (may differ from request when a provider
                              auto-routes — Bedrock, MCP-routed).
    """

    tokens_in: int = 0
    tokens_out: int = 0
    cost_estimate_usd: float = 0.0
    model: str = ""

    def __post_init__(self) -> None:
        if self.tokens_in < 0 or self.tokens_out < 0:
            raise ValueError(
                f"Usage tokens must be ≥ 0; got in={self.tokens_in} out={self.tokens_out}"
            )
        if self.cost_estimate_usd < 0.0:
            raise ValueError(
                f"Usage.cost_estimate_usd must be ≥ 0; got {self.cost_estimate_usd}"
            )

    @property
    def total_tokens(self) -> int:
        return self.tokens_in + self.tokens_out


class FinishReason(str, enum.Enum):
    """Why the provider stopped generating."""

    STOP = "stop"                 # Natural end-of-turn or stop sequence.
    MAX_TOKENS = "max_tokens"     # max_tokens cap hit.
    TOOL_CALL = "tool_call"       # The assistant wants to invoke a tool.
    CONTENT_FILTER = "content_filter"  # Provider's safety filter.
    ERROR = "error"               # Mid-stream provider error.


@dataclass(frozen=True)
class CompletionResponse:
    """Non-streaming completion result.

    Fields:
      * `text`           — the assistant's complete reply text.
      * `finish_reason`  — why generation stopped.
      * `usage`          — token + cost accounting.
      * `latency_ms`     — wall-clock time the provider took to respond.
      * `model`          — model that served the request (echoed for audit).
      * `provider`       — provider name (`"anthropic"`, `"openai"`, …).
      * `tool_calls`     — when `finish_reason=TOOL_CALL`, the list of
                            tool invocations the assistant requested.
                            Empty otherwise.
    """

    text: str
    finish_reason: FinishReason
    usage: Usage
    latency_ms: int = 0
    model: str = ""
    provider: str = ""
    tool_calls: tuple[dict[str, Any], ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if self.latency_ms < 0:
            raise ValueError(f"latency_ms must be ≥ 0; got {self.latency_ms}")


@dataclass(frozen=True)
class CompletionChunk:
    """One incremental piece of a streaming completion.

    Streams produce a sequence of `CompletionChunk` objects, each
    carrying either a text delta OR a final marker:

      * Mid-stream chunks: `text` populated, `is_final=False`, `usage=None`.
      * Final chunk:       `text=""`, `is_final=True`, `usage` populated.

    Consumers can keep concatenating `text` until they see `is_final=True`,
    or join + observe `usage` for cost accounting.
    """

    text: str = ""
    is_final: bool = False
    finish_reason: FinishReason | None = None
    usage: Usage | None = None
    model: str = ""

    def __post_init__(self) -> None:
        # Final chunks must populate finish_reason + usage; non-final
        # chunks must not.
        if self.is_final:
            if self.finish_reason is None:
                raise ValueError("final CompletionChunk must populate finish_reason")
            if self.usage is None:
                raise ValueError("final CompletionChunk must populate usage")
        else:
            if self.finish_reason is not None:
                raise ValueError(
                    "non-final CompletionChunk must not populate finish_reason"
                )


# --------------------------------------------------------------------------- #
# ProviderCapabilities
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class ProviderCapabilities:
    """Declarative descriptor each provider exposes for `sange doctor`.

    Fields document what the provider can do; the Application layer
    queries these before sending features-not-supported requests.
    """

    name: str                       # `"anthropic"`, `"openai"`, ...
    supports_streaming: bool = True
    supports_json_mode: bool = False
    supports_structured_output: bool = False
    supports_tool_use: bool = False
    supports_vision: bool = False
    supports_audio: bool = False
    sdk_installed: bool = True
    default_model: str = ""
    notes: tuple[str, ...] = field(default_factory=tuple)


# --------------------------------------------------------------------------- #
# AIProvider Protocol
# --------------------------------------------------------------------------- #


class AIProvider(Protocol):
    """The structural-typing contract every AI adapter implements."""

    # Class-level capability descriptor.
    capabilities: ProviderCapabilities

    def complete(self, request: CompletionRequest) -> CompletionResponse:
        """Single-shot completion. Blocks until done."""
        ...

    def stream(self, request: CompletionRequest) -> Iterator[CompletionChunk]:
        """Streaming completion. Yields chunks; last one has `is_final=True`."""
        ...


# --------------------------------------------------------------------------- #
# Factory — name → concrete provider
# --------------------------------------------------------------------------- #


def get_provider(
    name: str,
    *,
    api_key: str = "",
    base_url: str = "",
    **kwargs: Any,
) -> AIProvider:
    """Return an `AIProvider` instance for `name`.

    Args:
      name:     `"mock"` / `"anthropic"` / `"openai"` / `"ollama"` / etc.
      api_key:  bearer token. Empty for providers that don't need one
                (`"mock"`, `"ollama"` running locally).
      base_url: optional API base URL override (Ollama / Azure OpenAI /
                self-hosted endpoints).
      **kwargs: provider-specific extras passed through to the adapter.

    Raises:
      `AIProviderNotInstalled` if the requested provider's SDK extra
      isn't present.
      `AIError` for an unknown `name`.
    """

    if name == "mock":
        from sange.adapters.ai.mock import MockProvider
        return MockProvider(**kwargs)

    # Optional-extra providers — the modules live under sange.adapters.ai.*
    # but only when the matching pip extra is installed. mypy resolves their
    # types as `Any` (ignore_missing_imports), so the constructor calls need
    # an explicit cast to satisfy the AIProvider return type.
    if name == "anthropic":
        try:
            from sange.adapters.ai.anthropic import AnthropicProvider
        except ImportError as exc:
            raise AIProviderNotInstalled(
                "anthropic SDK not installed — run `pip install sange[ai-anthropic]`"
            ) from exc
        return cast(
            AIProvider,
            AnthropicProvider(api_key=api_key, base_url=base_url, **kwargs),
        )

    if name == "openai":
        try:
            from sange.adapters.ai.openai import OpenAIProvider
        except ImportError as exc:
            raise AIProviderNotInstalled(
                "openai SDK not installed — run `pip install sange[ai-openai]`"
            ) from exc
        return cast(
            AIProvider,
            OpenAIProvider(api_key=api_key, base_url=base_url, **kwargs),
        )

    if name == "ollama":
        try:
            from sange.adapters.ai.ollama import OllamaProvider
        except ImportError as exc:
            raise AIProviderNotInstalled(
                "ollama SDK not installed — run `pip install sange[ai-ollama]`"
            ) from exc
        return cast(AIProvider, OllamaProvider(base_url=base_url, **kwargs))

    raise AIError(
        f"unknown AI provider {name!r}; "
        "expected one of: mock, anthropic, openai, ollama, gemini, bedrock, azure-openai, mcp"
    )


__all__ = [
    "AIError",
    "AIProvider",
    "AIProviderNotInstalled",
    "CompletionChunk",
    "CompletionRequest",
    "CompletionResponse",
    "FinishReason",
    "Message",
    "MessageRole",
    "ProviderCapabilities",
    "ResponseFormat",
    "Usage",
    "get_provider",
]
