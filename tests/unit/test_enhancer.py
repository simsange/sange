"""Tests for src/sange/core/enhancer/enhancer.py — the §6.7.1 orchestrator."""

from __future__ import annotations

import json

import pytest

from sange.adapters.ai import (
    CompletionRequest,
    Message,
    MessageRole,
    MockProvider,
    ResponseFormat,
)
from sange.core.enhancer import (
    EnhancedResult,
    EnhancerValidationError,
    PromptEnhancer,
    PromptTemplate,
    RedactionPolicy,
    Redactor,
    TemplateRegistry,
)

# --------------------------------------------------------------------------- #
# Test fixtures
# --------------------------------------------------------------------------- #


def _commit_msg_template() -> PromptTemplate:
    return PromptTemplate(
        id="commit-msg",
        version="1.0.0",
        task="commit-msg",
        system_template="You are a Conventional Commits expert.",
        user_template="Generate a commit message for: {diff}",
        required_vars=("diff",),
        output_schema={
            "type": "object",
            "required": ["type", "subject"],
            "properties": {
                "type": {"type": "string"},
                "subject": {"type": "string"},
            },
        },
    )


def _free_form_template() -> PromptTemplate:
    return PromptTemplate(
        id="free-form",
        version="1.0.0",
        task="free-form",
        user_template="Summarize: {text}",
        required_vars=("text",),
    )


def _registry() -> TemplateRegistry:
    return TemplateRegistry([_commit_msg_template(), _free_form_template()])


def _enhancer(**kwargs) -> PromptEnhancer:
    defaults: dict = {"templates": _registry()}
    defaults.update(kwargs)
    return PromptEnhancer(**defaults)


# --------------------------------------------------------------------------- #
# Construction
# --------------------------------------------------------------------------- #


class TestConstruction:
    def test_basic(self) -> None:
        e = _enhancer()
        assert isinstance(e, PromptEnhancer)

    def test_templates_required(self) -> None:
        with pytest.raises(TypeError):
            PromptEnhancer(templates="not-a-registry")  # type: ignore[arg-type]

    def test_negative_retries_rejected(self) -> None:
        with pytest.raises(ValueError, match="max_retries"):
            PromptEnhancer(templates=_registry(), max_retries=-1)


# --------------------------------------------------------------------------- #
# preview() — no provider call
# --------------------------------------------------------------------------- #


class TestPreview:
    def test_preview_returns_formatted_request(self) -> None:
        e = _enhancer()
        preview = e.preview("free-form", {"text": "hello"})
        assert len(preview.messages) >= 1
        joined = "\n".join(m.content for m in preview.messages)
        assert "hello" in joined

    def test_preview_redacts_secrets(self) -> None:
        e = _enhancer()
        preview = e.preview("free-form", {"text": "key=AKIAIOSFODNN7EXAMPLE"})
        joined = "\n".join(m.content for m in preview.messages)
        assert "AKIA" not in joined
        assert "<redacted:" in joined

    def test_preview_doesnt_call_provider(self) -> None:
        # Build a MockProvider that would fail loudly if called.
        class _ExplodingProvider(MockProvider):
            def complete(self, request):  # type: ignore[override]
                raise AssertionError("preview must not call provider")

            def stream(self, request):  # type: ignore[override]
                raise AssertionError("preview must not call provider")

        e = PromptEnhancer(
            templates=_registry(),
            providers={"mock": _ExplodingProvider()},
        )
        # Should not raise.
        e.preview("free-form", {"text": "hi"})

    def test_preview_provider_specific_formatting(self) -> None:
        e = _enhancer()
        anthropic_preview = e.preview("free-form", {"text": "hi"}, provider="anthropic")
        openai_preview = e.preview("free-form", {"text": "hi"}, provider="openai")
        # Anthropic gets <task>; OpenAI doesn't.
        anth_user = next(
            m.content for m in anthropic_preview.messages if m.role is MessageRole.USER
        )
        oai_user = next(
            m.content for m in openai_preview.messages if m.role is MessageRole.USER
        )
        assert "<task>" in anth_user
        assert "<task>" not in oai_user


# --------------------------------------------------------------------------- #
# enhance() — happy paths
# --------------------------------------------------------------------------- #


class TestEnhanceFreeForm:
    def test_free_form_succeeds(self) -> None:
        e = _enhancer()
        result = e.enhance("free-form", {"text": "the quick brown fox"})
        assert isinstance(result, EnhancedResult)
        assert result.text  # populated
        assert result.data is None  # no schema declared
        assert result.audit.template_id == "free-form"
        assert result.audit.template_version == "1.0.0"
        assert result.audit.provider == "mock"
        assert result.audit.retries == 0

    def test_audit_carries_usage(self) -> None:
        e = _enhancer()
        result = e.enhance("free-form", {"text": "hi"})
        assert result.audit.usage.tokens_in > 0
        assert result.audit.usage.tokens_out > 0


class TestEnhanceWithSchema:
    def test_schema_validated_success(self) -> None:
        # Pre-register a canned valid response that matches the schema.
        mock = MockProvider()
        e = PromptEnhancer(
            templates=_registry(), providers={"mock": mock}
        )
        # Compute the exact request the enhancer will send, then register
        # a JSON response matching the schema.
        preview = e.preview("commit-msg", {"diff": "fix bug"})
        canned_req = CompletionRequest(
            model="mock-1",
            messages=preview.messages,
            temperature=0.0,
            response_format=ResponseFormat.JSON_OBJECT,
        )
        mock.register_canned(
            canned_req, json.dumps({"type": "fix", "subject": "fix bug"})
        )

        result = e.enhance("commit-msg", {"diff": "fix bug"})
        assert result.data == {"type": "fix", "subject": "fix bug"}
        assert result.audit.retries == 0


# --------------------------------------------------------------------------- #
# enhance() — validation failure + retry
# --------------------------------------------------------------------------- #


class TestEnhanceValidation:
    def test_invalid_json_raises_after_retry(self) -> None:
        # MockProvider's default response is echo text — not JSON.
        # Schema validation fails; we retry once; same response → raise.
        e = _enhancer(max_retries=1)
        with pytest.raises(EnhancerValidationError, match="schema"):
            e.enhance("commit-msg", {"diff": "fix bug"})

    def test_no_retries_raises_immediately(self) -> None:
        e = _enhancer(max_retries=0)
        with pytest.raises(EnhancerValidationError):
            e.enhance("commit-msg", {"diff": "fix bug"})

    def test_retry_succeeds_on_second_try(self) -> None:
        """First call returns invalid; second returns valid JSON."""

        class _RetryAwareMock(MockProvider):
            def __init__(self) -> None:
                super().__init__()
                self._call_count = 0

            def complete(self, request):  # type: ignore[override]
                self._call_count += 1
                if self._call_count == 1:
                    # First response: invalid JSON.
                    return super().complete(request)
                # Second response: valid JSON matching schema.
                from sange.adapters.ai import (
                    CompletionResponse,
                    FinishReason,
                    Usage,
                )

                return CompletionResponse(
                    text=json.dumps({"type": "fix", "subject": "fix bug"}),
                    finish_reason=FinishReason.STOP,
                    usage=Usage(tokens_in=5, tokens_out=5, model=request.model),
                    provider="mock",
                    model=request.model,
                )

        e = PromptEnhancer(
            templates=_registry(),
            providers={"mock": _RetryAwareMock()},
            max_retries=1,
        )
        result = e.enhance("commit-msg", {"diff": "fix bug"})
        assert result.audit.retries == 1
        assert result.data == {"type": "fix", "subject": "fix bug"}

    def test_schema_property_type_mismatch_fails(self) -> None:
        """If response is JSON but a property has the wrong type, validation fails."""

        class _WrongTypeMock(MockProvider):
            def complete(self, request):  # type: ignore[override]
                from sange.adapters.ai import (
                    CompletionResponse,
                    FinishReason,
                    Usage,
                )

                return CompletionResponse(
                    text=json.dumps({"type": 123, "subject": "fix bug"}),  # type is int
                    finish_reason=FinishReason.STOP,
                    usage=Usage(model=request.model),
                    provider="mock",
                    model=request.model,
                )

        e = PromptEnhancer(
            templates=_registry(),
            providers={"mock": _WrongTypeMock()},
            max_retries=0,
        )
        with pytest.raises(EnhancerValidationError):
            e.enhance("commit-msg", {"diff": "fix bug"})

    def test_schema_missing_required_key_fails(self) -> None:
        class _MissingKeyMock(MockProvider):
            def complete(self, request):  # type: ignore[override]
                from sange.adapters.ai import (
                    CompletionResponse,
                    FinishReason,
                    Usage,
                )

                return CompletionResponse(
                    text=json.dumps({"type": "fix"}),  # missing 'subject'
                    finish_reason=FinishReason.STOP,
                    usage=Usage(model=request.model),
                    provider="mock",
                    model=request.model,
                )

        e = PromptEnhancer(
            templates=_registry(),
            providers={"mock": _MissingKeyMock()},
            max_retries=0,
        )
        with pytest.raises(EnhancerValidationError, match="missing"):
            e.enhance("commit-msg", {"diff": "fix bug"})


# --------------------------------------------------------------------------- #
# Redaction in variables
# --------------------------------------------------------------------------- #


class TestRedactionInVariables:
    def test_secret_in_variable_redacted(self) -> None:
        e = _enhancer()
        secret = "AKIAIOSFODNN7EXAMPLE"
        result = e.enhance("free-form", {"text": f"key={secret}"})
        # The audit record proves redaction fired.
        assert result.audit.redaction_count >= 1
        assert "aws-access-key" in result.audit.redaction_labels

    def test_trusted_var_bypasses_redaction(self) -> None:
        e = _enhancer()
        secret = "AKIAIOSFODNN7EXAMPLE"
        result = e.enhance(
            "free-form",
            {"text": f"key={secret}"},
            trusted_vars={"text"},
        )
        # No redaction because the variable was marked trusted.
        assert result.audit.redaction_count == 0

    def test_non_string_variables_skip_redaction(self) -> None:
        # A non-string variable shouldn't crash the scrubber pipeline.
        e = _enhancer()
        t = PromptTemplate(
            id="int-vars",
            version="1.0",
            task="t",
            user_template="Count: {n}",
            required_vars=("n",),
        )
        e._templates.register(t)
        # The mock provider echoes the formatted user message ("## Task")
        # which is fine — the contract being tested is "doesn't crash".
        result = e.enhance("int-vars", {"n": 42})
        assert result.audit.redaction_count == 0
        assert result.text  # populated


# --------------------------------------------------------------------------- #
# Default provider behavior
# --------------------------------------------------------------------------- #


class TestProviderResolution:
    def test_default_provider_is_mock(self) -> None:
        e = _enhancer()
        result = e.enhance("free-form", {"text": "hi"})
        assert result.audit.provider == "mock"

    def test_explicit_provider_overrides(self) -> None:
        e = _enhancer()
        result = e.enhance("free-form", {"text": "hi"}, provider="mock")
        assert result.audit.provider == "mock"

    def test_provider_instance_reused(self) -> None:
        mock = MockProvider()
        e = PromptEnhancer(templates=_registry(), providers={"mock": mock})
        e.enhance("free-form", {"text": "first"})
        e.enhance("free-form", {"text": "second"})
        # We can't directly assert "same instance used"; but
        # registering canned responses lets us prove it by side effect.
        preview = e.preview("free-form", {"text": "third"})
        canned_req = CompletionRequest(
            model="mock-1",
            messages=preview.messages,
            temperature=0.0,
        )
        mock.register_canned(canned_req, "REUSED-PROVIDER")
        out = e.enhance("free-form", {"text": "third"})
        assert "REUSED-PROVIDER" in out.text


# --------------------------------------------------------------------------- #
# Custom redactor
# --------------------------------------------------------------------------- #


class TestCustomRedactor:
    def test_disabled_redactor(self) -> None:
        # When redaction is disabled, secrets pass through.
        r = Redactor(RedactionPolicy(enabled=False))
        e = PromptEnhancer(templates=_registry(), redactor=r)
        preview = e.preview("free-form", {"text": "AKIAIOSFODNN7EXAMPLE"})
        joined = "\n".join(m.content for m in preview.messages)
        assert "AKIAIOSFODNN7EXAMPLE" in joined
