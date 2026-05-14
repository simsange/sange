"""AI provider abstraction — Protocol + per-provider implementations.

Per §6.7 of the architecture prompt the AI subsystem is provider-agnostic.
Application code depends on the `AIProvider` Protocol; concrete providers
(Anthropic, OpenAI, Ollama, Gemini, Bedrock, Azure OpenAI, MCP) are
selected at runtime via the `SangeConfig.ai.providers` block.

Public surface:

  * `AIProvider`           — the structural-typing Protocol.
  * `CompletionRequest`    — input shape for a completion call.
  * `CompletionResponse`   — non-streaming response shape.
  * `CompletionChunk`      — streaming response shape.
  * `ProviderCapabilities` — declarative descriptor each provider exposes.
  * `AIError`              — base exception for provider failures.
  * `MockProvider`         — deterministic test surface (no API key needed).
  * `get_provider(name, config)` — factory that returns a concrete provider.

Provider implementation modules:

  * `mock`     — fully-deterministic; the default test surface.
  * `anthropic` — Anthropic Claude (requires `sange[ai-anthropic]` extra).
  * `openai`   — OpenAI / Azure OpenAI (requires `sange[ai-openai]` extra).
  * `ollama`   — Local Ollama (requires `sange[ai-ollama]` extra).
  * `gemini`   — Google Gemini (requires `sange[ai-google]` extra).
  * `bedrock`  — AWS Bedrock (requires `sange[ai-bedrock]` extra).

Streaming-first design per §6.7: every provider implements both
`complete()` (single-shot) AND `stream()` (incremental chunks). The
prompt-enhancer (T-010) chooses streaming for interactive surfaces and
single-shot for batch operations.

Redaction (per §11 threat model T-030) is NOT in the provider — it
lives one layer up in the prompt-enhancer (T-010). Providers receive
already-scrubbed input.
"""

from __future__ import annotations

from sange.adapters.ai._protocol import (
    AIError,
    AIProvider,
    AIProviderNotInstalled,
    CompletionChunk,
    CompletionRequest,
    CompletionResponse,
    FinishReason,
    Message,
    MessageRole,
    ProviderCapabilities,
    ResponseFormat,
    Usage,
    get_provider,
)
from sange.adapters.ai.mock import MockProvider

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
    "MockProvider",
    "ProviderCapabilities",
    "ResponseFormat",
    "Usage",
    "get_provider",
]
