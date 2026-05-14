"""Tests for src/sange/adapters/ai/mock.py — deterministic test provider."""

from __future__ import annotations

import pytest

from sange.adapters.ai import (
    CompletionChunk,
    CompletionRequest,
    FinishReason,
    Message,
    MessageRole,
    MockProvider,
    ResponseFormat,
)


def _req(user_content: str = "summarize this", model: str = "mock-1") -> CompletionRequest:
    return CompletionRequest(
        model=model,
        messages=[
            Message(role=MessageRole.SYSTEM, content="You are helpful."),
            Message(role=MessageRole.USER, content=user_content),
        ],
    )


# --------------------------------------------------------------------------- #
# capabilities descriptor
# --------------------------------------------------------------------------- #


class TestMockCapabilities:
    def test_name(self) -> None:
        assert MockProvider.capabilities.name == "mock"

    def test_streaming(self) -> None:
        assert MockProvider.capabilities.supports_streaming is True

    def test_sdk_installed(self) -> None:
        # Mock has no SDK so it always reports installed.
        assert MockProvider.capabilities.sdk_installed is True

    def test_no_tool_use(self) -> None:
        assert MockProvider.capabilities.supports_tool_use is False


# --------------------------------------------------------------------------- #
# complete()
# --------------------------------------------------------------------------- #


class TestComplete:
    def test_returns_completion_response(self) -> None:
        p = MockProvider()
        resp = p.complete(_req())
        assert resp.finish_reason is FinishReason.STOP
        assert resp.provider == "mock"
        assert resp.model == "mock-1"

    def test_response_echoes_user_input(self) -> None:
        p = MockProvider()
        resp = p.complete(_req("the quick brown fox"))
        assert "the quick brown fox" in resp.text

    def test_uses_last_user_message_not_first(self) -> None:
        p = MockProvider()
        req = CompletionRequest(
            model="m",
            messages=[
                Message(role=MessageRole.USER, content="first"),
                Message(role=MessageRole.ASSISTANT, content="reply"),
                Message(role=MessageRole.USER, content="LAST"),
            ],
        )
        resp = p.complete(req)
        assert "LAST" in resp.text
        assert "first" not in resp.text

    def test_first_line_only(self) -> None:
        # _canned_response takes the first line of the last user message.
        p = MockProvider()
        resp = p.complete(_req("line one\nline two\nline three"))
        assert "line one" in resp.text
        assert "line two" not in resp.text

    def test_deterministic(self) -> None:
        p = MockProvider()
        r1 = p.complete(_req("abc"))
        r2 = p.complete(_req("abc"))
        assert r1.text == r2.text
        assert r1.usage.tokens_in == r2.usage.tokens_in
        assert r1.usage.tokens_out == r2.usage.tokens_out

    def test_usage_populated(self) -> None:
        p = MockProvider()
        resp = p.complete(_req("hello world"))
        assert resp.usage.tokens_in > 0
        assert resp.usage.tokens_out > 0
        # Mock is free.
        assert resp.usage.cost_estimate_usd == 0.0

    def test_zero_latency(self) -> None:
        # No real I/O → latency is 0.
        p = MockProvider()
        resp = p.complete(_req())
        assert resp.latency_ms == 0

    def test_model_echoed(self) -> None:
        p = MockProvider()
        resp = p.complete(_req(model="claude-opus-4-7"))
        assert resp.model == "claude-opus-4-7"
        assert resp.usage.model == "claude-opus-4-7"


# --------------------------------------------------------------------------- #
# stream()
# --------------------------------------------------------------------------- #


class TestStream:
    def test_yields_chunks(self) -> None:
        p = MockProvider()
        chunks = list(p.stream(_req()))
        assert len(chunks) >= 2  # At least one text chunk + a final marker.

    def test_last_chunk_is_final(self) -> None:
        p = MockProvider()
        chunks = list(p.stream(_req()))
        assert chunks[-1].is_final is True
        assert chunks[-1].finish_reason is FinishReason.STOP
        assert chunks[-1].usage is not None

    def test_non_final_chunks_have_no_finish_reason(self) -> None:
        p = MockProvider()
        chunks = list(p.stream(_req()))
        for c in chunks[:-1]:
            assert c.is_final is False
            assert c.finish_reason is None
            assert c.usage is None

    def test_concat_equals_complete(self) -> None:
        """The streamed text concatenated must equal complete() output."""

        p = MockProvider()
        req = _req("equivalence test")
        full = p.complete(req).text
        joined = "".join(c.text for c in p.stream(req) if not c.is_final)
        assert joined == full

    def test_chunk_count_respected(self) -> None:
        p = MockProvider(chunk_count=3)
        chunks = list(p.stream(_req("a much longer message that splits into several pieces")))
        non_final = [c for c in chunks if not c.is_final]
        assert len(non_final) <= 3

    def test_chunk_count_clamped_to_min_one(self) -> None:
        p = MockProvider(chunk_count=0)
        chunks = list(p.stream(_req("hello")))
        # Must still produce at least one piece + final.
        assert any(c.text for c in chunks)
        assert chunks[-1].is_final

    def test_final_usage_matches_complete(self) -> None:
        p = MockProvider()
        req = _req("usage parity")
        complete_usage = p.complete(req).usage
        stream_final = list(p.stream(req))[-1]
        assert stream_final.usage is not None
        assert stream_final.usage.tokens_in == complete_usage.tokens_in
        assert stream_final.usage.tokens_out == complete_usage.tokens_out


# --------------------------------------------------------------------------- #
# canned_responses + register_canned
# --------------------------------------------------------------------------- #


class TestCannedResponses:
    def test_register_overrides_default(self) -> None:
        p = MockProvider()
        req = _req("trigger phrase")
        p.register_canned(req, "CANNED OUTPUT")
        assert p.complete(req).text == "CANNED OUTPUT"

    def test_register_only_matches_exact_request(self) -> None:
        p = MockProvider()
        req1 = _req("phrase one")
        req2 = _req("phrase two")
        p.register_canned(req1, "ONE")
        # req2 must fall back to the deterministic default, not return "ONE".
        assert "ONE" not in p.complete(req2).text

    def test_canned_propagates_to_stream(self) -> None:
        p = MockProvider()
        req = _req("trigger")
        p.register_canned(req, "STREAMED CANNED")
        joined = "".join(c.text for c in p.stream(req) if not c.is_final)
        assert joined == "STREAMED CANNED"

    def test_canned_responses_kwarg_ignored_if_keys_dont_match(self) -> None:
        # The kwarg accepts a pre-built dict but caller must use the same
        # hash function — easier path is register_canned(). The kwarg dict
        # exists for symmetry but if the key isn't a real request hash it
        # never matches.
        p = MockProvider(canned_responses={"arbitrary-key": "never-used"})
        resp = p.complete(_req("normal request"))
        assert "never-used" not in resp.text


# --------------------------------------------------------------------------- #
# Edge cases
# --------------------------------------------------------------------------- #


class TestEdgeCases:
    def test_no_user_message_falls_back(self) -> None:
        # Request with only a system message → no user content; the canned
        # default uses "(no input)".
        p = MockProvider()
        req = CompletionRequest(
            model="m",
            messages=[Message(role=MessageRole.SYSTEM, content="System only.")],
        )
        resp = p.complete(req)
        assert "(no input)" in resp.text

    def test_json_object_format_still_returns_text(self) -> None:
        # The mock doesn't actually emit JSON; it just exercises the
        # ResponseFormat.JSON_OBJECT codepath without crashing.
        p = MockProvider()
        req = CompletionRequest(
            model="m",
            messages=[Message(role=MessageRole.USER, content="give json")],
            response_format=ResponseFormat.JSON_OBJECT,
        )
        resp = p.complete(req)
        assert resp.text  # Non-empty.

    def test_structured_with_schema_works(self) -> None:
        p = MockProvider()
        req = CompletionRequest(
            model="m",
            messages=[Message(role=MessageRole.USER, content="structured request")],
            response_format=ResponseFormat.STRUCTURED,
            schema={"type": "object", "properties": {"x": {"type": "string"}}},
        )
        resp = p.complete(req)
        assert resp.text
