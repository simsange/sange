"""Tests for src/sange/core/config/models.py — SangeConfig Pydantic v2 model.

Asserts:
  * Default-minimal `SangeConfig()` validates.
  * Sub-model defaults are sensible (binary stages, _core safety profiles, etc.).
  * Cross-field validators fire (publish_stage ∈ stages, etc.).
  * `extra="forbid"` rejects typos.
  * Schema versioning round-trips.
  * Convenience accessors return correct data.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

import sange
from sange.core.config import (
    AIConfig,
    AIProviderConfig,
    AuditConfig,
    DimensionConfig,
    GitignoreConfig,
    GitignorePolicy,
    ProjectMeta,
    SangeConfig,
    SchemaVersion,
    SecretsConfig,
    StageConfig,
    TelemetryConfig,
    VariantConfig,
    VariantFilter,
)
from sange.core.config.models import SCHEMA_CURRENT


# --------------------------------------------------------------------------- #
# Default-minimal
# --------------------------------------------------------------------------- #


class TestDefaultMinimal:
    def test_construct_with_no_args(self) -> None:
        c = SangeConfig()
        assert c.schema_version.as_tuple() == SCHEMA_CURRENT.as_tuple()

    def test_default_stages_are_dev_and_production(self) -> None:
        c = SangeConfig()
        assert c.variants.stages == ["dev", "production"]
        assert c.variants.default_stage == "dev"
        assert c.variants.publish_stage == "production"

    def test_default_gitignore_includes_core_safety(self) -> None:
        c = SangeConfig()
        for profile in ("_core/secrets", "_core/license"):
            assert profile in c.gitignore.dev or profile in c.gitignore.prod

    def test_default_ai_has_no_providers(self) -> None:
        c = SangeConfig()
        assert c.ai.providers == []
        assert c.ai.default_provider == ""

    def test_default_redaction_patterns_present(self) -> None:
        c = SangeConfig()
        # Sanity check a few well-known regexes are seeded.
        assert any("AKIA" in p for p in c.ai.redaction_patterns)
        assert any("PRIVATE KEY" in p for p in c.ai.redaction_patterns)

    def test_default_telemetry_external_send_off(self) -> None:
        """Per ADR-008 — external send is OFF by default."""

        c = SangeConfig()
        assert c.telemetry.enabled is True
        assert c.telemetry.external_send_enabled is False

    def test_default_audit_enabled(self) -> None:
        c = SangeConfig()
        assert c.audit.enabled is True
        assert c.audit.verbosity == "normal"


# --------------------------------------------------------------------------- #
# Round-trip
# --------------------------------------------------------------------------- #


class TestRoundTrip:
    def test_model_dump_roundtrip(self) -> None:
        original = SangeConfig()
        replayed = SangeConfig.model_validate(original.model_dump())
        assert original == replayed

    def test_model_dump_json_roundtrip(self) -> None:
        import json
        original = SangeConfig()
        replayed = SangeConfig.model_validate(json.loads(original.model_dump_json()))
        assert original == replayed


# --------------------------------------------------------------------------- #
# Schema versioning
# --------------------------------------------------------------------------- #


class TestSchemaVersion:
    def test_current_is_1_0(self) -> None:
        assert SCHEMA_CURRENT.as_tuple() == (1, 0)

    def test_compatibility_same_major(self) -> None:
        v = SchemaVersion(major=1, minor=0)
        assert v.is_compatible_with(SchemaVersion(major=1, minor=0))
        assert SchemaVersion(major=1, minor=0).is_compatible_with(
            SchemaVersion(major=1, minor=2)
        )

    def test_incompatibility_different_major(self) -> None:
        old = SchemaVersion(major=1, minor=0)
        new = SchemaVersion(major=2, minor=0)
        assert not old.is_compatible_with(new) or not new.is_compatible_with(old)

    def test_is_newer_than(self) -> None:
        assert SchemaVersion(major=2, minor=0).is_newer_than(
            SchemaVersion(major=1, minor=0)
        )
        assert not SchemaVersion(major=1, minor=0).is_newer_than(
            SchemaVersion(major=1, minor=0)
        )


# --------------------------------------------------------------------------- #
# VariantConfig validators
# --------------------------------------------------------------------------- #


class TestVariantConfigValidators:
    def test_publish_stage_must_be_in_stages(self) -> None:
        with pytest.raises(ValidationError, match="publish_stage"):
            VariantConfig(
                stages=["dev", "production"],
                default_stage="dev",
                publish_stage="not-a-stage",
            )

    def test_default_stage_must_be_in_stages(self) -> None:
        with pytest.raises(ValidationError, match="default_stage"):
            VariantConfig(
                stages=["dev", "production"],
                default_stage="not-a-stage",
                publish_stage="production",
            )

    def test_branch_map_target_must_be_a_stage(self) -> None:
        with pytest.raises(ValidationError, match="branch_map"):
            VariantConfig(
                stages=["dev", "production"],
                branch_map={"feature/*": "not-a-stage"},
            )

    def test_per_stage_override_must_reference_real_stage(self) -> None:
        with pytest.raises(ValidationError, match="not a declared stage"):
            VariantConfig(
                stages=["dev", "production"],
                stage={"not-a-stage": StageConfig(ai_provider="anthropic")},
            )

    def test_three_stage_config_valid(self) -> None:
        v = VariantConfig(
            stages=["dev", "staging", "production"],
            default_stage="dev",
            publish_stage="production",
            branch_map={"staging/*": "staging", "main": "production"},
            stage={"staging": StageConfig(ai_provider="ollama")},
        )
        assert "staging" in v.stages
        assert v.stage["staging"].ai_provider == "ollama"


# --------------------------------------------------------------------------- #
# DimensionConfig
# --------------------------------------------------------------------------- #


class TestDimensionConfig:
    def test_default_picks_first_flavor(self) -> None:
        d = DimensionConfig(flavors=["public", "internal"])
        assert d.default == "public"

    def test_explicit_default_must_be_in_flavors(self) -> None:
        with pytest.raises(ValidationError, match="default"):
            DimensionConfig(flavors=["public", "internal"], default="other")

    def test_empty_flavors_rejected(self) -> None:
        # min_length=1 on the field
        with pytest.raises(ValidationError):
            DimensionConfig(flavors=[])


# --------------------------------------------------------------------------- #
# VariantFilter
# --------------------------------------------------------------------------- #


class TestVariantFilter:
    def test_match_required(self) -> None:
        with pytest.raises(ValidationError, match="match"):
            VariantFilter(match={})

    def test_filter_axis_must_be_known(self) -> None:
        with pytest.raises(ValidationError, match="axis"):
            VariantConfig(
                stages=["dev", "production"],
                filter=[VariantFilter(match={"unknown_axis": "x"})],
            )

    def test_filter_stage_must_be_declared(self) -> None:
        with pytest.raises(ValidationError, match="match.stage"):
            VariantConfig(
                stages=["dev", "production"],
                filter=[VariantFilter(match={"stage": "missing"})],
            )

    def test_filter_with_real_axis_passes(self) -> None:
        v = VariantConfig(
            stages=["dev", "production"],
            dimensions={"audience": DimensionConfig(flavors=["public", "internal"])},
            filter=[
                VariantFilter(
                    match={"audience": "internal", "stage": "production"},
                    reason="internal builds never ship to production",
                )
            ],
        )
        assert v.filter[0].match["stage"] == "production"


# --------------------------------------------------------------------------- #
# GitignoreConfig
# --------------------------------------------------------------------------- #


class TestGitignoreConfig:
    def test_profile_slugs_validate(self) -> None:
        gi = GitignoreConfig(dev=["_core/secrets", "lang/python", "framework/django"])
        assert "lang/python" in gi.dev

    def test_malformed_slug_rejected(self) -> None:
        with pytest.raises(ValidationError, match="<category>/<name>"):
            GitignoreConfig(dev=["bare-name-no-category"])

    def test_unknown_category_rejected(self) -> None:
        with pytest.raises(ValidationError, match="<category>/<name>"):
            GitignoreConfig(dev=["unknowncategory/something"])


# --------------------------------------------------------------------------- #
# AIConfig
# --------------------------------------------------------------------------- #


class TestAIConfig:
    def test_default_provider_picks_first_when_empty(self) -> None:
        ai = AIConfig(providers=[AIProviderConfig(name="anthropic")])
        assert ai.default_provider == "anthropic"

    def test_default_provider_must_be_configured(self) -> None:
        with pytest.raises(ValidationError, match="default_provider"):
            AIConfig(
                providers=[AIProviderConfig(name="anthropic")],
                default_provider="openai",
            )

    def test_unknown_provider_name_rejected(self) -> None:
        with pytest.raises(ValidationError):
            AIProviderConfig(name="not-a-real-provider")  # type: ignore[arg-type]

    def test_cost_limit_non_negative(self) -> None:
        with pytest.raises(ValidationError):
            AIProviderConfig(name="anthropic", cost_limit_usd_per_day=-1.0)


# --------------------------------------------------------------------------- #
# Extra-fields strictness
# --------------------------------------------------------------------------- #


class TestExtraForbid:
    def test_typo_at_top_level_rejected(self) -> None:
        with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
            SangeConfig.model_validate({"variants_typo": {}})

    def test_typo_in_variants_rejected(self) -> None:
        with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
            SangeConfig.model_validate({"variants": {"default_stagee": "dev"}})


# --------------------------------------------------------------------------- #
# Convenience accessors
# --------------------------------------------------------------------------- #


class TestConvenienceAccessors:
    def test_active_stage_config_returns_empty_default_for_unknown(self) -> None:
        c = SangeConfig()
        sc = c.active_stage_config("not-declared")
        assert sc.ai_provider == ""
        assert sc.secrets_resolver == ""

    def test_active_stage_config_returns_real_overrides(self) -> None:
        c = SangeConfig.model_validate({
            "variants": {
                "stages": ["dev", "production"],
                "stage": {
                    "production": {
                        "ai_provider": "anthropic",
                        "audit_verbosity": "elevated",
                        "signing_required": True,
                    },
                },
            },
        })
        sc = c.active_stage_config("production")
        assert sc.ai_provider == "anthropic"
        assert sc.audit_verbosity == "elevated"
        assert sc.signing_required is True

    def test_is_publish_stage(self) -> None:
        c = SangeConfig()
        assert c.is_publish_stage("production")
        assert not c.is_publish_stage("dev")

    def test_all_declared_stages(self) -> None:
        c = SangeConfig()
        assert c.all_declared_stages() == ["dev", "production"]

    def test_all_declared_dimensions_alphabetical(self) -> None:
        c = SangeConfig.model_validate({
            "variants": {
                "stages": ["dev", "production"],
                "dimensions": {
                    "surface": {"flavors": ["cli", "web"]},
                    "audience": {"flavors": ["public", "internal"]},
                },
            },
        })
        assert c.all_declared_dimensions() == ["audience", "surface"]
