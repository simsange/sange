"""Tests for src/sange/adapters/ai/_protocol.py — Protocol + dataclasses + factory."""

from __future__ import annotations

import pytest

from sange.adapters.ai import (
    AIError,
    AIProvider,
    AIProviderNotInstalled,
    CompletionChunk,
    CompletionRequest,
    CompletionResponse,
    FinishReason,
    Message,
    MessageRole,
    MockProvider,
    ProviderCapabilities,
    ResponseFormat,
    Usage,
    get_provider,
)


# --------------------------------------------------------------------------- #
# Message
# --------------------------------------------------------------------------- #


class TestMessage:
    def test_basic(self) -> None:
        m = Message(role=MessageRole.USER, content="hello")
        assert m.role is MessageRole.USER
        assert m.content == "hello"
        assert m.name == ""

    def test_empty_user_content_rejected(self) -> None:
        with pytest.raises(ValueError, match="non-empty"):
            Message(role=MessageRole.USER, content="")

    def test_empty_system_content_rejected(self) -> None:
        with pytest.raises(ValueError, match="non-empty"):
            Message(role=MessageRole.SYSTEM, content="")

    def test_empty_assistant_content_allowed(self) -> None:
        # Assistant messages may be empty during streaming setup.
        m = Message(role=MessageRole.ASSISTANT, content="")
        assert m.content == ""

    def test_non_enum_role_rejected(self) -> None:
        with pytest.raises(ValueError, match="MessageRole"):
            Message(role="user", content="hi")  # type: ignore[arg-type]

    def test_frozen(self) -> None:
        m = Message(role=MessageRole.USER, content="hi")
        with pytest.raises(Exception):  # FrozenInstanceError
            m.content = "bye"  # type: ignore[misc]


# --------------------------------------------------------------------------- #
# CompletionRequest
# --------------------------------------------------------------------------- #


class TestCompletionRequest:
    def _msgs(self) -> list[Message]:
        return [Message(role=MessageRole.USER, content="hi")]

    def test_basic(self) -> None:
        req = CompletionRequest(model="m", messages=self._msgs())
        assert req.model == "m"
        assert req.temperature == 0.0
        assert req.response_format is ResponseFormat.TEXT
        assert req.max_tokens is None

    def test_empty_model_rejected(self) -> None:
        with pytest.raises(ValueError, match="model"):
            CompletionRequest(model="", messages=self._msgs())

    def test_empty_messages_rejected(self) -> None:
        with pytest.raises(ValueError, match="messages"):
            CompletionRequest(model="m", messages=[])

    @pytest.mark.parametrize("temp", [-0.1, 2.1, 100.0])
    def test_temperature_out_of_bounds(self, temp: float) -> None:
        with pytest.raises(ValueError, match="temperature"):
            CompletionRequest(model="m", messages=self._msgs(), temperature=temp)

    @pytest.mark.parametrize("temp", [0.0, 1.0, 2.0])
    def test_temperature_in_bounds(self, temp: float) -> None:
        # Should not raise.
        CompletionRequest(model="m", messages=self._msgs(), temperature=temp)

    def test_max_tokens_zero_rejected(self) -> None:
        with pytest.raises(ValueError, match="max_tokens"):
            CompletionRequest(model="m", messages=self._msgs(), max_tokens=0)

    def test_max_tokens_negative_rejected(self) -> None:
        with pytest.raises(ValueError, match="max_tokens"):
            CompletionRequest(model="m", messages=self._msgs(), max_tokens=-5)

    def test_max_tokens_none_allowed(self) -> None:
        req = CompletionRequest(model="m", messages=self._msgs(), max_tokens=None)
        assert req.max_tokens is None

    def test_structured_without_schema_rejected(self) -> None:
        with pytest.raises(ValueError, match="schema"):
            CompletionRequest(
                model="m",
                messages=self._msgs(),
                response_format=ResponseFormat.STRUCTURED,
            )

    def test_structured_with_schema_accepted(self) -> None:
        req = CompletionRequest(
            model="m",
            messages=self._msgs(),
            response_format=ResponseFormat.STRUCTURED,
            schema={"type": "object"},
        )
        assert req.schema == {"type": "object"}


# --------------------------------------------------------------------------- #
# Usage
# --------------------------------------------------------------------------- #


class TestUsage:
    def test_total_tokens(self) -> None:
        u = Usage(tokens_in=10, tokens_out=20)
        assert u.total_tokens == 30

    @pytest.mark.parametrize("ti,to", [(-1, 0), (0, -1), (-5, -5)])
    def test_negative_tokens_rejected(self, ti: int, to: int) -> None:
        with pytest.raises(ValueError, match="tokens"):
            Usage(tokens_in=ti, tokens_out=to)

    def test_negative_cost_rejected(self) -> None:
        with pytest.raises(ValueError, match="cost"):
            Usage(cost_estimate_usd=-0.01)

    def test_zero_defaults(self) -> None:
        u = Usage()
        assert u.tokens_in == 0
        assert u.tokens_out == 0
        assert u.cost_estimate_usd == 0.0


# --------------------------------------------------------------------------- #
# CompletionResponse
# --------------------------------------------------------------------------- #


class TestCompletionResponse:
    def test_basic(self) -> None:
        r = CompletionResponse(
            text="hi", finish_reason=FinishReason.STOP, usage=Usage()
        )
        assert r.text == "hi"
        assert r.finish_reason is FinishReason.STOP

    def test_negative_latency_rejected(self) -> None:
        with pytest.raises(ValueError, match="latency"):
            CompletionResponse(
                text="x", finish_reason=FinishReason.STOP, usage=Usage(), latency_ms=-1
            )


# --------------------------------------------------------------------------- #
# CompletionChunk
# --------------------------------------------------------------------------- #


class TestCompletionChunk:
    def test_non_final(self) -> None:
        c = CompletionChunk(text="hello")
        assert c.text == "hello"
        assert c.is_final is False
        assert c.finish_reason is None
        assert c.usage is None

    def test_final_requires_finish_reason(self) -> None:
        with pytest.raises(ValueError, match="finish_reason"):
            CompletionChunk(is_final=True, usage=Usage())

    def test_final_requires_usage(self) -> None:
        with pytest.raises(ValueError, match="usage"):
            CompletionChunk(is_final=True, finish_reason=FinishReason.STOP)

    def test_non_final_must_not_have_finish_reason(self) -> None:
        with pytest.raises(ValueError, match="non-final"):
            CompletionChunk(
                text="hi", is_final=False, finish_reason=FinishReason.STOP
            )

    def test_final_complete(self) -> None:
        c = CompletionChunk(
            is_final=True,
            finish_reason=FinishReason.STOP,
            usage=Usage(tokens_in=1, tokens_out=2),
        )
        assert c.is_final
        assert c.usage is not None
        assert c.usage.total_tokens == 3


# --------------------------------------------------------------------------- #
# ProviderCapabilities
# --------------------------------------------------------------------------- #


class TestProviderCapabilities:
    def test_defaults(self) -> None:
        c = ProviderCapabilities(name="foo")
        assert c.name == "foo"
        assert c.supports_streaming is True
        assert c.supports_json_mode is False
        assert c.sdk_installed is True
        assert c.notes == ()


# --------------------------------------------------------------------------- #
# Protocol shape — MockProvider satisfies AIProvider structurally
# --------------------------------------------------------------------------- #


class TestAIProviderProtocol:
    def test_mock_provider_satisfies_protocol(self) -> None:
        # Structural typing: MockProvider doesn't inherit from AIProvider
        # but must satisfy isinstance() at runtime when @runtime_checkable
        # is set. Even without that decorator, the duck-typing contract is
        # that all of these attributes exist.
        p = MockProvider()
        assert hasattr(p, "capabilities")
        assert hasattr(p, "complete")
        assert hasattr(p, "stream")
        assert callable(p.complete)
        assert callable(p.stream)
        assert isinstance(p.capabilities, ProviderCapabilities)

    def test_assignment_to_aiprovider_typevar(self) -> None:
        # Structural-typing smoke test: a MockProvider should be assignable
        # to an `AIProvider`-typed variable (this is mostly a mypy check,
        # but the assignment itself must not blow up at runtime).
        provider: AIProvider = MockProvider()
        assert provider.capabilities.name == "mock"


# --------------------------------------------------------------------------- #
# get_provider() factory
# --------------------------------------------------------------------------- #


class TestGetProvider:
    def test_mock(self) -> None:
        p = get_provider("mock")
        assert isinstance(p, MockProvider)

    def test_unknown_raises_aierror(self) -> None:
        with pytest.raises(AIError, match="unknown AI provider"):
            get_provider("not-a-real-provider")

    def test_anthropic_missing_sdk(self) -> None:
        # The anthropic SDK isn't installed in the test environment, so
        # the factory must raise AIProviderNotInstalled with a helpful
        # extras hint.
        with pytest.raises(AIProviderNotInstalled, match="ai-anthropic"):
            get_provider("anthropic", api_key="ignored")

    def test_openai_missing_sdk(self) -> None:
        with pytest.raises(AIProviderNotInstalled, match="ai-openai"):
            get_provider("openai", api_key="ignored")

    def test_ollama_missing_sdk(self) -> None:
        with pytest.raises(AIProviderNotInstalled, match="ai-ollama"):
            get_provider("ollama")


# --------------------------------------------------------------------------- #
# Enums — sanity
# --------------------------------------------------------------------------- #


class TestEnums:
    def test_message_role_values(self) -> None:
        assert MessageRole.SYSTEM.value == "system"
        assert MessageRole.USER.value == "user"
        assert MessageRole.ASSISTANT.value == "assistant"
        assert MessageRole.TOOL.value == "tool"

    def test_response_format_values(self) -> None:
        assert ResponseFormat.TEXT.value == "text"
        assert ResponseFormat.JSON_OBJECT.value == "json_object"
        assert ResponseFormat.STRUCTURED.value == "structured"

    def test_finish_reason_values(self) -> None:
        assert FinishReason.STOP.value == "stop"
        assert FinishReason.MAX_TOKENS.value == "max_tokens"
        assert FinishReason.TOOL_CALL.value == "tool_call"
        assert FinishReason.CONTENT_FILTER.value == "content_filter"
        assert FinishReason.ERROR.value == "error"
