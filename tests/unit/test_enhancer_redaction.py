"""Tests for src/sange/core/enhancer/redaction.py — T-030 mitigation."""

from __future__ import annotations

import pytest

from sange.core.enhancer.redaction import (
    RedactionPolicy,
    RedactionResult,
    Redactor,
    shannon_entropy,
)

# --------------------------------------------------------------------------- #
# RedactionPolicy validators
# --------------------------------------------------------------------------- #


class TestRedactionPolicy:
    def test_defaults(self) -> None:
        p = RedactionPolicy()
        assert p.enabled is True
        assert p.entropy_min_length == 32
        assert "{label}" in p.redaction_token

    def test_min_length_too_low(self) -> None:
        with pytest.raises(ValueError, match="entropy_min_length"):
            RedactionPolicy(entropy_min_length=4)

    @pytest.mark.parametrize("t", [-1.0, 9.0, 100.0])
    def test_threshold_out_of_bounds(self, t: float) -> None:
        with pytest.raises(ValueError, match="entropy_threshold"):
            RedactionPolicy(entropy_threshold=t)

    def test_redaction_token_must_have_label(self) -> None:
        with pytest.raises(ValueError, match="label"):
            RedactionPolicy(redaction_token="<redacted>")

    def test_custom_pattern_label_required(self) -> None:
        with pytest.raises(ValueError, match="label"):
            RedactionPolicy(custom_patterns=(("", r"\d+"),))

    def test_custom_pattern_invalid_regex_caught(self) -> None:
        # Bad regex must surface at policy construction, not first use.
        import re

        with pytest.raises(re.error):
            RedactionPolicy(custom_patterns=(("bad", "[unclosed"),))


# --------------------------------------------------------------------------- #
# shannon_entropy
# --------------------------------------------------------------------------- #


class TestShannonEntropy:
    def test_empty(self) -> None:
        assert shannon_entropy("") == 0.0

    def test_single_char(self) -> None:
        # Only one distinct symbol → entropy 0.
        assert shannon_entropy("aaaaaaa") == 0.0

    def test_random_high(self) -> None:
        # 64-char hex is ~3.9 bits/char, base64-random ~5+ bits/char.
        random_b64 = "aBcDeFgHiJkLmNoPqRsTuVwXyZ0123456789+/aBcDeFgHiJkLmNoPqRs"
        assert shannon_entropy(random_b64) > 4.0

    def test_english_prose_low(self) -> None:
        # English prose is ~3.5-4.0 bits/char.
        # A very repetitive structure should be well below 4.
        text = "this is some normal english sentence text. " * 3
        assert shannon_entropy(text) < 4.5


# --------------------------------------------------------------------------- #
# Redactor — known patterns
# --------------------------------------------------------------------------- #


class TestRedactorKnownPatterns:
    def test_aws_access_key(self) -> None:
        r = Redactor()
        out = r.scrub("AWS=AKIAIOSFODNN7EXAMPLE rest of line")
        assert "AKIA" not in out.text
        assert "aws-access-key" in out.labels_applied
        assert out.redactions >= 1

    def test_github_pat(self) -> None:
        r = Redactor()
        tok = "ghp_" + "a" * 40
        out = r.scrub(f"token={tok}")
        assert "ghp_" not in out.text
        assert "github-pat" in out.labels_applied

    def test_openai_key(self) -> None:
        r = Redactor()
        out = r.scrub("sk-abcdefghij1234567890ABCDEF")
        assert "sk-abc" not in out.text
        assert "openai-key" in out.labels_applied

    def test_anthropic_key(self) -> None:
        r = Redactor()
        out = r.scrub("sk-ant-abcdef1234567890abcdef1234567890XYZ")
        assert "sk-ant-" not in out.text
        assert "anthropic-key" in out.labels_applied

    def test_slack_token(self) -> None:
        r = Redactor()
        out = r.scrub("xoxb-abc-1234567890-abcdef")
        assert "xoxb-" not in out.text
        assert "slack-token" in out.labels_applied

    def test_jwt(self) -> None:
        r = Redactor()
        jwt = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjMifQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
        out = r.scrub(f"Bearer {jwt}")
        assert "eyJ" not in out.text
        assert "jwt" in out.labels_applied

    def test_pem_private_key(self) -> None:
        r = Redactor()
        pem = (
            "-----BEGIN PRIVATE KEY-----\n"
            "MIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQDk\n"
            "-----END PRIVATE KEY-----"
        )
        out = r.scrub(pem)
        assert "BEGIN PRIVATE KEY" not in out.text
        assert "private-key-pem" in out.labels_applied

    def test_google_api_key(self) -> None:
        r = Redactor()
        key = "AIza" + "x" * 35
        out = r.scrub(key)
        assert "AIza" not in out.text
        assert "google-api-key" in out.labels_applied

    def test_clean_text_passes_through(self) -> None:
        r = Redactor()
        text = "this is a normal sentence without any secrets."
        out = r.scrub(text)
        assert out.text == text
        assert out.redactions == 0
        assert out.labels_applied == frozenset()


# --------------------------------------------------------------------------- #
# Redactor — high-entropy heuristic
# --------------------------------------------------------------------------- #


class TestRedactorHighEntropy:
    def test_random_long_string_redacted(self) -> None:
        r = Redactor()
        # 32+ chars of random-looking base64
        token = "aB3cD4eF5gH6iJ7kL8mN9oP0qR1sT2uV3wX4"
        out = r.scrub(f"value={token}")
        assert token not in out.text
        assert "high-entropy" in out.labels_applied

    def test_short_string_not_redacted(self) -> None:
        r = Redactor()
        out = r.scrub("short=abc123")  # < 32 chars
        assert "abc123" in out.text
        assert "high-entropy" not in out.labels_applied

    def test_low_entropy_long_string_kept(self) -> None:
        r = Redactor()
        # 50 chars, all identical → entropy = 0, not redacted.
        text = "a" * 50
        out = r.scrub(text)
        assert text in out.text
        assert "high-entropy" not in out.labels_applied


# --------------------------------------------------------------------------- #
# Redactor — custom patterns
# --------------------------------------------------------------------------- #


class TestRedactorCustomPatterns:
    def test_custom_pattern_fires(self) -> None:
        policy = RedactionPolicy(
            custom_patterns=(("vault-ref", r"vault://[a-z0-9-]+"),),
        )
        r = Redactor(policy)
        out = r.scrub("password = vault://prod-creds-2024")
        assert "vault://" not in out.text
        assert "vault-ref" in out.labels_applied


# --------------------------------------------------------------------------- #
# Redactor — disabled mode
# --------------------------------------------------------------------------- #


class TestRedactorDisabled:
    def test_disabled_passes_through(self) -> None:
        r = Redactor(RedactionPolicy(enabled=False))
        text = "AKIAIOSFODNN7EXAMPLE is an AWS key"
        out = r.scrub(text)
        assert out.text == text
        assert out.redactions == 0


# --------------------------------------------------------------------------- #
# Redactor — multi-pattern + result shape
# --------------------------------------------------------------------------- #


class TestRedactorMultiPattern:
    def test_two_distinct_secrets_both_redacted(self) -> None:
        r = Redactor()
        text = "aws=AKIAIOSFODNN7EXAMPLE\ngithub=ghp_" + "x" * 40
        out = r.scrub(text)
        assert "aws-access-key" in out.labels_applied
        assert "github-pat" in out.labels_applied
        assert out.redactions >= 2

    def test_scrub_many(self) -> None:
        r = Redactor()
        results = r.scrub_many(["AKIAIOSFODNN7EXAMPLE", "no secret here"])
        assert isinstance(results[0], RedactionResult)
        assert results[0].redactions == 1
        assert results[1].redactions == 0

    def test_empty_text(self) -> None:
        r = Redactor()
        out = r.scrub("")
        assert out.text == ""
        assert out.redactions == 0

    def test_policy_accessor(self) -> None:
        policy = RedactionPolicy(entropy_min_length=64)
        r = Redactor(policy)
        assert r.policy is policy
        assert r.policy.entropy_min_length == 64
