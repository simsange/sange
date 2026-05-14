"""Tests for src/sange/core/lifecycle/schema.py — CommitJSON Pydantic model."""

from __future__ import annotations

import datetime as _dt

import pytest
from pydantic import ValidationError

from sange.core.lifecycle.schema import (
    AIProvenance,
    Approval,
    Author,
    CommitDiff,
    CommitJSON,
    CommitMessage,
    CommitStatus,
    Rejection,
    SCHEMA_VERSION,
)


_NOW = _dt.datetime(2026, 5, 15, 12, 0, 0, tzinfo=_dt.timezone.utc)


def _minimal_message() -> CommitMessage:
    return CommitMessage(type="feat", subject="add passkey")


def _minimal_commit(**overrides) -> CommitJSON:
    kw = {
        "counter": 1,
        "created_at": _NOW,
        "updated_at": _NOW,
        "message": _minimal_message(),
    }
    kw.update(overrides)
    return CommitJSON(**kw)


# --------------------------------------------------------------------------- #
# CommitMessage
# --------------------------------------------------------------------------- #


class TestCommitMessage:
    def test_minimal(self) -> None:
        m = CommitMessage(type="feat", subject="add login")
        assert m.type == "feat"
        assert m.scope == ""
        assert not m.breaking_change

    def test_scope_slug_validated(self) -> None:
        m = CommitMessage(type="fix", scope="security", subject="x")
        assert m.scope == "security"
        with pytest.raises(ValidationError, match="lowercase"):
            CommitMessage(type="fix", scope="Security", subject="x")
        with pytest.raises(ValidationError, match="lowercase"):
            CommitMessage(type="fix", scope="my_scope_with_underscore", subject="x")

    def test_subject_single_line(self) -> None:
        with pytest.raises(ValidationError, match="single-line"):
            CommitMessage(type="feat", subject="a\nb")
        with pytest.raises(ValidationError, match="single-line"):
            CommitMessage(type="feat", subject="a\rb")

    def test_subject_length(self) -> None:
        with pytest.raises(ValidationError):
            CommitMessage(type="feat", subject="x" * 121)

    def test_unknown_type_rejected(self) -> None:
        with pytest.raises(ValidationError):
            CommitMessage(type="not-a-cc-type", subject="x")  # type: ignore[arg-type]


# --------------------------------------------------------------------------- #
# CommitDiff
# --------------------------------------------------------------------------- #


class TestCommitDiff:
    def test_defaults(self) -> None:
        d = CommitDiff()
        assert d.files_changed == 0
        assert d.content_hash == ""

    def test_negative_count_rejected(self) -> None:
        with pytest.raises(ValidationError):
            CommitDiff(files_changed=-1)

    def test_content_hash_length(self) -> None:
        with pytest.raises(ValidationError, match="64-char"):
            CommitDiff(content_hash="abc")
        # Empty is ok.
        assert CommitDiff(content_hash="").content_hash == ""
        # 64-char is ok.
        h = "a" * 64
        assert CommitDiff(content_hash=h).content_hash == h


# --------------------------------------------------------------------------- #
# AIProvenance
# --------------------------------------------------------------------------- #


class TestAIProvenance:
    def test_default_is_not_generated(self) -> None:
        p = AIProvenance()
        assert not p.generated

    def test_generated_requires_provider_and_model(self) -> None:
        with pytest.raises(ValidationError, match="provider \\+ model"):
            AIProvenance(generated=True, provider="anthropic", model="")
        with pytest.raises(ValidationError, match="provider \\+ model"):
            AIProvenance(generated=True, provider="", model="claude")

    def test_populated_without_generated_rejected(self) -> None:
        with pytest.raises(ValidationError, match="generated=False"):
            AIProvenance(generated=False, provider="anthropic", model="claude")

    def test_generated_with_full_provenance(self) -> None:
        p = AIProvenance(
            generated=True,
            provider="anthropic",
            model="claude-opus-4-7",
            prompt_version="commit-msg-v3",
            template_id="conventional",
            cost_estimate_usd=0.012,
            tokens_in=1500,
            tokens_out=120,
            enhancer_version="1.0",
        )
        assert p.cost_estimate_usd == 0.012


# --------------------------------------------------------------------------- #
# Approval / Rejection
# --------------------------------------------------------------------------- #


class TestApprovalRejection:
    def test_approval_basic(self) -> None:
        a = Approval(actor="user@host", at=_NOW)
        assert a.via == "cli"

    def test_approval_via_validated(self) -> None:
        with pytest.raises(ValidationError):
            Approval(actor="x", at=_NOW, via="invented-surface")  # type: ignore[arg-type]

    def test_rejection_requires_reason(self) -> None:
        with pytest.raises(ValidationError):
            Rejection(actor="x", at=_NOW, reason="")


# --------------------------------------------------------------------------- #
# CommitJSON — top-level model
# --------------------------------------------------------------------------- #


class TestCommitJSONInvariants:
    def test_minimal_construction(self) -> None:
        c = _minimal_commit()
        assert c.schema_version == SCHEMA_VERSION
        assert c.status is CommitStatus.DRAFT
        assert c.counter == 1
        # id auto-populates
        assert len(c.id) >= 16

    def test_updated_before_created_rejected(self) -> None:
        with pytest.raises(ValidationError, match="updated_at"):
            _minimal_commit(
                updated_at=_NOW - _dt.timedelta(seconds=1),
            )

    def test_extra_fields_rejected(self) -> None:
        with pytest.raises(ValidationError, match="Extra inputs"):
            CommitJSON.model_validate({
                "counter": 1,
                "created_at": _NOW.isoformat(),
                "updated_at": _NOW.isoformat(),
                "message": {"type": "feat", "subject": "x"},
                "invented_field": "x",
            })

    def test_counter_must_be_positive(self) -> None:
        with pytest.raises(ValidationError):
            _minimal_commit(counter=0)


class TestCommittedShaInvariants:
    def test_draft_with_committed_sha_rejected(self) -> None:
        with pytest.raises(ValidationError, match="committed_sha is set"):
            _minimal_commit(committed_sha="a" * 40)

    def test_committed_without_sha_rejected(self) -> None:
        with pytest.raises(ValidationError, match="committed_sha is empty"):
            _minimal_commit(
                status=CommitStatus.COMMITTED,
                committed_sha="",
            )

    def test_committed_with_sha_ok(self) -> None:
        c = _minimal_commit(
            status=CommitStatus.COMMITTED,
            committed_sha="a" * 40,
        )
        assert c.status is CommitStatus.COMMITTED


class TestPushedRemoteInvariants:
    def test_pushed_without_remote_rejected(self) -> None:
        with pytest.raises(ValidationError, match="pushed_remote is empty"):
            _minimal_commit(
                status=CommitStatus.PUSHED,
                committed_sha="a" * 40,
                pushed_remote="",
            )

    def test_pushed_with_remote_and_sha_ok(self) -> None:
        c = _minimal_commit(
            status=CommitStatus.PUSHED,
            committed_sha="a" * 40,
            pushed_remote="origin",
        )
        assert c.pushed_remote == "origin"

    def test_draft_with_pushed_remote_rejected(self) -> None:
        with pytest.raises(ValidationError, match="pushed_remote is set"):
            _minimal_commit(pushed_remote="origin")


class TestRoundTrip:
    def test_model_dump_roundtrip(self) -> None:
        c = _minimal_commit()
        replayed = CommitJSON.model_validate(c.model_dump(mode="json"))
        assert c == replayed

    def test_model_dump_json_roundtrip(self) -> None:
        c = _minimal_commit()
        import json
        replayed = CommitJSON.model_validate(json.loads(c.model_dump_json()))
        assert c == replayed
