"""Tests for src/sange/core/enhancer/tasks/commit_message.py — T-011."""

from __future__ import annotations

import json

import pytest

from sange.adapters.ai import (
    CompletionRequest,
    CompletionResponse,
    FinishReason,
    MockProvider,
    ResponseFormat,
    Usage,
)
from sange.core.enhancer import (
    CONVENTIONAL_COMMIT_TYPES,
    CommitMessageRequest,
    CommitMessageResult,
    EnhancerValidationError,
    PromptEnhancer,
    TemplateRegistry,
    build_commit_message_template,
    generate_commit_message,
)
from sange.core.enhancer.tasks.commit_message import (
    TEMPLATE_ID,
    TEMPLATE_VERSION,
)
from sange.core.lifecycle.schema import CommitMessage as LifecycleCommitMessage

# --------------------------------------------------------------------------- #
# Conventional Commits types invariants
# --------------------------------------------------------------------------- #


class TestConventionalCommitTypes:
    def test_count(self) -> None:
        assert len(CONVENTIONAL_COMMIT_TYPES) == 11

    def test_canonical_set(self) -> None:
        assert set(CONVENTIONAL_COMMIT_TYPES) == {
            "feat", "fix", "docs", "style", "refactor", "perf",
            "test", "build", "ci", "chore", "revert",
        }

    def test_matches_generator_source_of_truth(self) -> None:
        """The template's type set must exactly equal the generator's
        `CC_TYPES`. If a future contributor changes one, the other
        must move with it — this regression test enforces that."""

        # Pure-Python parse of the generator file to avoid running it.
        import re
        from pathlib import Path

        gen = Path(__file__).resolve().parents[2] / "tools" / "generators" / "commit_templates.py"
        text = gen.read_text()
        match = re.search(
            r"CC_TYPES:\s*tuple\[str,\s*\.\.\.\]\s*=\s*\((.*?)\)",
            text,
            re.DOTALL,
        )
        assert match is not None, "CC_TYPES not found in generator"
        gen_types = tuple(
            sorted(re.findall(r'"([a-z]+)"', match.group(1)))
        )
        assert gen_types == tuple(sorted(CONVENTIONAL_COMMIT_TYPES))


# --------------------------------------------------------------------------- #
# build_commit_message_template
# --------------------------------------------------------------------------- #


class TestBuildTemplate:
    def test_id_and_version(self) -> None:
        t = build_commit_message_template()
        assert t.id == "commit-message"
        assert t.version == "1.0.0"
        assert t.task == "commit-msg"

    def test_required_vars(self) -> None:
        t = build_commit_message_template()
        assert set(t.required_vars) == {
            "diff", "branch", "recent_commits",
            "files_changed_count", "files_changed_summary",
        }

    def test_output_schema_required_keys(self) -> None:
        t = build_commit_message_template()
        schema = t.output_schema
        assert schema is not None
        assert set(schema["required"]) == {
            "type", "scope", "subject", "body", "breaking_change"
        }

    def test_constants_exported(self) -> None:
        assert TEMPLATE_ID == "commit-message"
        assert TEMPLATE_VERSION == "1.0.0"


# --------------------------------------------------------------------------- #
# CommitMessageRequest
# --------------------------------------------------------------------------- #


class TestCommitMessageRequest:
    def test_minimal(self) -> None:
        req = CommitMessageRequest(diff="+ a\n- b\n")
        assert req.diff == "+ a\n- b\n"
        assert req.branch == ""
        assert req.files_changed == ()

    def test_empty_diff_rejected(self) -> None:
        with pytest.raises(ValueError, match="diff must be non-empty"):
            CommitMessageRequest(diff="")

    def test_files_changed_is_immutable(self) -> None:
        req = CommitMessageRequest(diff="d", files_changed=("a.py",))
        # frozen dataclass — assignment must fail.
        with pytest.raises(Exception):
            req.diff = "modified"  # type: ignore[misc]


# --------------------------------------------------------------------------- #
# CommitMessageResult
# --------------------------------------------------------------------------- #


class TestCommitMessageResult:
    def test_basic(self) -> None:
        r = CommitMessageResult(type="feat", subject="add auth")
        assert r.type == "feat"
        assert r.subject == "add auth"
        assert r.body == ""
        assert r.breaking_change is False

    def test_invalid_type_rejected(self) -> None:
        with pytest.raises(ValueError, match="must be one of"):
            CommitMessageResult(type="frobnicate", subject="x")

    def test_empty_subject_rejected(self) -> None:
        with pytest.raises(ValueError, match="subject must be non-empty"):
            CommitMessageResult(type="feat", subject="")

    def test_subject_too_long_rejected(self) -> None:
        with pytest.raises(ValueError, match="must be ≤ 72 chars"):
            CommitMessageResult(type="feat", subject="x" * 73)

    def test_subject_exactly_72_accepted(self) -> None:
        r = CommitMessageResult(type="feat", subject="x" * 72)
        assert len(r.subject) == 72

    def test_multiline_subject_rejected(self) -> None:
        with pytest.raises(ValueError, match="single-line"):
            CommitMessageResult(type="feat", subject="line one\nline two")


# --------------------------------------------------------------------------- #
# generate_commit_message — end-to-end with a canned MockProvider
# --------------------------------------------------------------------------- #


def _build_enhancer_with_canned_response(
    response_payload: dict,
    request: CommitMessageRequest,
) -> tuple[PromptEnhancer, MockProvider]:
    """Helper: build an enhancer where the mock will return
    `response_payload` (as JSON) for the request that `request` will
    produce."""

    registry = TemplateRegistry([build_commit_message_template()])
    mock = MockProvider()
    e = PromptEnhancer(templates=registry, providers={"mock": mock})

    # Compute the exact CompletionRequest the enhancer will send.
    files_summary = (
        "\n".join(f"- {p}" for p in request.files_changed)
        if request.files_changed
        else "(no files listed)"
    )
    diff_for_prompt = request.diff
    if request.scope_override:
        diff_for_prompt = (
            f"Suggested scope: {request.scope_override}\n\n{request.diff}"
        )
    preview = e.preview(
        TEMPLATE_ID,
        {
            "diff": diff_for_prompt,
            "branch": request.branch or "(unknown)",
            "recent_commits": request.recent_commits or "(none)",
            "files_changed_count": str(len(request.files_changed)),
            "files_changed_summary": files_summary,
        },
        trusted_vars={
            "branch", "recent_commits",
            "files_changed_count", "files_changed_summary",
        },
    )
    canned_req = CompletionRequest(
        model="mock-1",
        messages=preview.messages,
        temperature=0.0,
        response_format=ResponseFormat.JSON_OBJECT,
    )
    mock.register_canned(canned_req, json.dumps(response_payload))
    return e, mock


class TestGenerateCommitMessage:
    def test_happy_path(self) -> None:
        req = CommitMessageRequest(
            diff="+ added auth flow\n",
            branch="feat/auth",
            recent_commits="chore: bump deps",
            files_changed=("src/auth/login.py",),
        )
        e, _ = _build_enhancer_with_canned_response(
            {
                "type": "feat",
                "scope": "auth",
                "subject": "add login flow",
                "body": "Wires up the new auth handler.",
                "breaking_change": False,
            },
            req,
        )
        result = generate_commit_message(req, enhancer=e)
        assert result.type == "feat"
        assert result.scope == "auth"
        assert result.subject == "add login flow"
        assert "auth handler" in result.body
        assert result.breaking_change is False
        assert result.audit_id == f"{TEMPLATE_ID}@{TEMPLATE_VERSION}"

    def test_breaking_change_propagates(self) -> None:
        req = CommitMessageRequest(diff="+ breaking change\n")
        e, _ = _build_enhancer_with_canned_response(
            {
                "type": "feat",
                "scope": "api",
                "subject": "remove deprecated v1 endpoints",
                "body": "v1 endpoints retired. Migrate callers to v2.",
                "breaking_change": True,
            },
            req,
        )
        result = generate_commit_message(req, enhancer=e)
        assert result.breaking_change is True

    def test_empty_optional_fields_handled(self) -> None:
        req = CommitMessageRequest(diff="+ minor change\n")
        e, _ = _build_enhancer_with_canned_response(
            {
                "type": "chore",
                "scope": "",
                "subject": "tidy imports",
                "body": "",
                "breaking_change": False,
            },
            req,
        )
        result = generate_commit_message(req, enhancer=e)
        assert result.scope == ""
        assert result.body == ""

    def test_invalid_response_type_raises(self) -> None:
        """Provider returns valid JSON, but type isn't in the CC set.
        Schema validation passes (type is a string); the result-level
        validator catches the unknown type."""

        req = CommitMessageRequest(diff="+ change\n")
        e, _ = _build_enhancer_with_canned_response(
            {
                "type": "invalid-type",
                "scope": "",
                "subject": "do something",
                "body": "",
                "breaking_change": False,
            },
            req,
        )
        with pytest.raises(ValueError, match="must be one of"):
            generate_commit_message(req, enhancer=e)

    def test_invalid_json_raises_validation_error(self) -> None:
        """If the model returns non-JSON, the enhancer's schema layer
        catches it (after one retry) and raises EnhancerValidationError."""

        req = CommitMessageRequest(diff="+ change\n")
        # Use a vanilla enhancer with no canned responses → MockProvider
        # echoes the input as text (not JSON).
        registry = TemplateRegistry([build_commit_message_template()])
        e = PromptEnhancer(templates=registry, max_retries=1)
        with pytest.raises(EnhancerValidationError):
            generate_commit_message(req, enhancer=e)

    def test_default_enhancer_auto_built(self) -> None:
        """When no enhancer is passed, generate_commit_message builds
        one. Default mock will fail validation (echo response), so
        we expect EnhancerValidationError — but the path exercises
        the auto-built enhancer."""

        req = CommitMessageRequest(diff="+ change\n")
        with pytest.raises(EnhancerValidationError):
            generate_commit_message(req)

    def test_scope_override_injected_into_prompt(self) -> None:
        """Verify the scope_override changes the diff variable seen by
        the redactor (the canned-response key depends on it)."""

        req = CommitMessageRequest(
            diff="+ change\n",
            scope_override="payments",
        )
        e, _ = _build_enhancer_with_canned_response(
            {
                "type": "fix",
                "scope": "payments",
                "subject": "correct rounding error",
                "body": "",
                "breaking_change": False,
            },
            req,
        )
        result = generate_commit_message(req, enhancer=e)
        # The injected scope wins because the model honored it.
        assert result.scope == "payments"

    def test_uses_existing_enhancer_without_double_register(self) -> None:
        """An enhancer that already has the template registered is
        used as-is (no TemplateConflictError on register)."""

        registry = TemplateRegistry([build_commit_message_template()])
        e = PromptEnhancer(templates=registry)
        req = CommitMessageRequest(diff="+ change\n")
        # We expect EnhancerValidationError (mock echoes invalid JSON),
        # not TemplateConflictError.
        with pytest.raises(EnhancerValidationError):
            generate_commit_message(req, enhancer=e)


# --------------------------------------------------------------------------- #
# Schema compatibility with lifecycle CommitMessage
# --------------------------------------------------------------------------- #


class TestLifecycleSchemaCompatibility:
    def test_result_promotes_to_lifecycle_commit_message(self) -> None:
        """A CommitMessageResult's fields must drop cleanly into the
        lifecycle `CommitMessage` Pydantic model. This is the §6.8
        promotion path: enhance() → CommitMessageResult → CommitMessage
        → CommitJSON.DRAFT."""

        result = CommitMessageResult(
            type="feat",
            scope="auth",
            subject="add passkey",
            body="Implements WebAuthn.",
            breaking_change=False,
        )
        lifecycle_msg = LifecycleCommitMessage(
            type=result.type,
            scope=result.scope,
            subject=result.subject,
            body=result.body,
            breaking_change=result.breaking_change,
        )
        assert lifecycle_msg.type == "feat"
        assert lifecycle_msg.subject == "add passkey"
