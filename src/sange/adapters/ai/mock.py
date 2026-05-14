"""`MockProvider` — deterministic test surface for the AI subsystem.

Used by:
  * Test suites that need an `AIProvider` without burning real API tokens.
  * The prompt-enhancer's (T-010) development cycle.
  * `sange ai preview` when no real provider is configured.

Determinism contract:

  * `complete()` returns a canned response derived from the input via
    `_canned_response(request)` (a pure function). Same input → same
    response.
  * `stream()` chunks the same response over `chunk_count` (default 4)
    deltas + emits a final marker. The text concatenated across all
    chunks exactly equals `complete()`'s text.
  * `usage` is computed deterministically from input/output character
    counts (4 chars ≈ 1 token, no fancy tokenization).
  * `latency_ms` is always 0 — no sleep, no real I/O.

Custom canned responses:

  * Pass `canned_responses` (a dict from a hash of the request to a
    pre-baked response string) to override the deterministic default.
    Useful for testing prompt-enhancer output post-conditions.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterator

from sange.adapters.ai._protocol import (
    CompletionChunk,
    CompletionRequest,
    CompletionResponse,
    FinishReason,
    ProviderCapabilities,
    Usage,
)


_DEFAULT_CHUNK_COUNT = 4


def _hash_request(request: CompletionRequest) -> str:
    """Stable hash of a request — covers model + messages + format."""

    h = hashlib.sha256()
    h.update(request.model.encode("utf-8"))
    h.update(request.response_format.value.encode("utf-8"))
    for msg in request.messages:
        h.update(msg.role.value.encode("utf-8"))
        h.update(msg.content.encode("utf-8"))
    return h.hexdigest()


def _canned_response(request: CompletionRequest) -> str:
    """Deterministic stand-in for a real model's response.

    The text echoes the last user message's first line + a fixed suffix
    so prompt-enhancer tests can assert the output references the input.
    """

    last_user = ""
    for msg in reversed(request.messages):
        if msg.role.value == "user":
            last_user = msg.content
            break
    first_line = last_user.split("\n", 1)[0].strip() or "(no input)"
    return f"[mock-completion] echo: {first_line}"


def _estimate_tokens(text: str) -> int:
    """Rough char-to-token estimate (4 chars ≈ 1 token)."""

    return max(1, len(text) // 4)


class MockProvider:
    """Deterministic, no-I/O AI provider for testing."""

    capabilities: ProviderCapabilities = ProviderCapabilities(
        name="mock",
        supports_streaming=True,
        supports_json_mode=True,
        supports_structured_output=True,
        supports_tool_use=False,
        supports_vision=False,
        supports_audio=False,
        sdk_installed=True,
        default_model="mock-1",
        notes=(
            "Deterministic test provider; never calls a real API.",
            "Use canned_responses kwarg to inject specific outputs.",
        ),
    )

    def __init__(
        self,
        *,
        canned_responses: dict[str, str] | None = None,
        chunk_count: int = _DEFAULT_CHUNK_COUNT,
    ) -> None:
        self._canned: dict[str, str] = dict(canned_responses or {})
        self._chunk_count = max(1, int(chunk_count))

    # ----- complete --------------------------------------------------- #

    def complete(self, request: CompletionRequest) -> CompletionResponse:
        text = self._resolve_text(request)
        tokens_in = sum(_estimate_tokens(m.content) for m in request.messages)
        tokens_out = _estimate_tokens(text)
        return CompletionResponse(
            text=text,
            finish_reason=FinishReason.STOP,
            usage=Usage(
                tokens_in=tokens_in,
                tokens_out=tokens_out,
                cost_estimate_usd=0.0,  # Mock is free.
                model=request.model,
            ),
            latency_ms=0,
            model=request.model,
            provider="mock",
        )

    # ----- stream ----------------------------------------------------- #

    def stream(self, request: CompletionRequest) -> Iterator[CompletionChunk]:
        text = self._resolve_text(request)
        # Split into `chunk_count` roughly-equal pieces.
        if not text:
            # Emit only a final marker.
            yield CompletionChunk(
                text="",
                is_final=True,
                finish_reason=FinishReason.STOP,
                usage=Usage(model=request.model),
                model=request.model,
            )
            return

        n = self._chunk_count
        size = max(1, len(text) // n)
        pieces = [text[i : i + size] for i in range(0, len(text), size)]
        # If the simple chunking produced more than n pieces (text not
        # divisible by n), merge the tail into the last piece.
        if len(pieces) > n:
            pieces[n - 1] = "".join(pieces[n - 1 :])
            pieces = pieces[:n]

        for piece in pieces:
            yield CompletionChunk(text=piece, is_final=False)

        # Final marker.
        tokens_in = sum(_estimate_tokens(m.content) for m in request.messages)
        tokens_out = _estimate_tokens(text)
        yield CompletionChunk(
            text="",
            is_final=True,
            finish_reason=FinishReason.STOP,
            usage=Usage(
                tokens_in=tokens_in,
                tokens_out=tokens_out,
                cost_estimate_usd=0.0,
                model=request.model,
            ),
            model=request.model,
        )

    # ----- internals -------------------------------------------------- #

    def _resolve_text(self, request: CompletionRequest) -> str:
        """Look up canned response if registered; otherwise compute one."""

        key = _hash_request(request)
        if key in self._canned:
            return self._canned[key]
        return _canned_response(request)

    # ----- convenience for tests ------------------------------------- #

    def register_canned(self, request: CompletionRequest, text: str) -> None:
        """Pre-bake a response for a specific request shape."""

        self._canned[_hash_request(request)] = text


__all__ = ["MockProvider"]
