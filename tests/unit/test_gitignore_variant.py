"""Tests for src/sange/core/gitignore/variant.py + compose_variant()."""

from __future__ import annotations

import datetime as _dt
from pathlib import Path

import pytest

from sange.core.gitignore.compose import compose_variant
from sange.core.gitignore.registry import ProfileRegistry
from sange.core.gitignore.variant import (
    Variant,
    VariantConfig,
    VariantDimension,
    VariantError,
    VariantStageAxis,
)

_FIXED_CLOCK = _dt.datetime(2026, 5, 16, 12, 0, tzinfo=_dt.UTC)


def _write(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


class TestVariantStageAxis:
    def test_default(self) -> None:
        axis = VariantStageAxis()
        assert axis.name == "stage"
        assert axis.values == ("dev", "prod")

    def test_three_stage(self) -> None:
        axis = VariantStageAxis(values=("dev", "staging", "production"))
        assert axis.index_of("production") == 2

    def test_empty_values_rejected(self) -> None:
        with pytest.raises(VariantError, match="non-empty"):
            VariantStageAxis(values=())

    def test_duplicate_values_rejected(self) -> None:
        with pytest.raises(VariantError, match="duplicate"):
            VariantStageAxis(values=("dev", "dev"))

    def test_unknown_stage_lookup(self) -> None:
        axis = VariantStageAxis()
        with pytest.raises(VariantError, match="not in axis"):
            axis.index_of("nope")


class TestVariantDimension:
    def test_basic(self) -> None:
        d = VariantDimension(name="audience", values=("internal", "external"))
        assert d.is_valid("internal")
        assert not d.is_valid("partner")

    def test_empty_name_rejected(self) -> None:
        with pytest.raises(VariantError, match="name"):
            VariantDimension(name="", values=("x",))

    def test_empty_values_rejected(self) -> None:
        with pytest.raises(VariantError, match="non-empty"):
            VariantDimension(name="audience", values=())

    def test_duplicate_values_rejected(self) -> None:
        with pytest.raises(VariantError, match="duplicate"):
            VariantDimension(name="audience", values=("a", "a"))


class TestVariantConfig:
    def test_default_minimal(self) -> None:
        cfg = VariantConfig()
        variants = cfg.all_variants()
        assert len(variants) == 2  # dev + prod, no flavors

    def test_cartesian_size(self) -> None:
        cfg = VariantConfig(
            stage_axis=VariantStageAxis(values=("dev", "staging", "production")),
            dimensions=(
                VariantDimension(name="audience", values=("int", "ext")),
                VariantDimension(name="surface", values=("web", "api")),
            ),
        )
        assert len(cfg.all_variants()) == 3 * 2 * 2

    def test_dimension_collision_with_stage_axis(self) -> None:
        with pytest.raises(VariantError, match="collision"):
            VariantConfig(
                stage_axis=VariantStageAxis(name="surface", values=("a",)),
                dimensions=(VariantDimension(name="surface", values=("x",)),),
            )

    def test_make_variant_full_validation(self) -> None:
        cfg = VariantConfig(
            stage_axis=VariantStageAxis(values=("dev", "prod")),
            dimensions=(
                VariantDimension(name="audience", values=("int", "ext")),
            ),
        )
        v = cfg.make_variant("prod", audience="ext")
        assert v.stage == "prod"
        assert dict(v.flavors) == {"audience": "ext"}

    def test_make_variant_missing_dimension_value(self) -> None:
        cfg = VariantConfig(
            dimensions=(VariantDimension(name="audience", values=("int",)),),
        )
        with pytest.raises(VariantError, match=r"audience.*requires"):
            cfg.make_variant("dev")

    def test_make_variant_unknown_stage(self) -> None:
        cfg = VariantConfig()
        with pytest.raises(VariantError, match="staging"):
            cfg.make_variant("staging")

    def test_make_variant_unknown_value(self) -> None:
        cfg = VariantConfig(
            dimensions=(VariantDimension(name="audience", values=("int",)),),
        )
        with pytest.raises(VariantError, match="not valid"):
            cfg.make_variant("dev", audience="partner")

    def test_make_variant_extra_dimension_rejected(self) -> None:
        cfg = VariantConfig()
        with pytest.raises(VariantError, match="unknown flavor"):
            cfg.make_variant("dev", surface="web")

    def test_dimension_by_name(self) -> None:
        d = VariantDimension(name="audience", values=("int",))
        cfg = VariantConfig(dimensions=(d,))
        assert cfg.dimension_by_name("audience") is d
        with pytest.raises(VariantError, match="unknown dimension"):
            cfg.dimension_by_name("ghost")


class TestVariant:
    def test_equality_is_canonical(self) -> None:
        # Flavor order at construction time should not affect equality.
        # (make_variant always sorts, so we have to fabricate by hand
        # — even then, Variant stores the sorted form passed in.)
        a = Variant(stage="dev", flavors=(("a", "1"), ("b", "2")))
        b = Variant(stage="dev", flavors=(("a", "1"), ("b", "2")))
        assert a == b

    def test_slug(self) -> None:
        v = Variant(stage="production",
                    flavors=(("audience", "external"), ("surface", "web")))
        assert v.slug() == "production-external-web"

    def test_has_flavor(self) -> None:
        v = Variant(stage="dev", flavors=(("audience", "int"),))
        assert v.has_flavor("audience", "int")
        assert not v.has_flavor("audience", "ext")
        assert not v.has_flavor("surface", "web")

    def test_duplicate_dimension_rejected(self) -> None:
        with pytest.raises(VariantError, match="duplicate"):
            Variant(stage="dev", flavors=(("a", "1"), ("a", "2")))


class TestComposeVariant:
    """End-to-end variant composition against a tiny in-memory registry."""

    @pytest.fixture
    def registry(self, tmp_path: Path) -> ProfileRegistry:
        # A profile that uses both legacy + variant-aware patterns.
        # Schema: [patterns.stages] maps stage_name → list[str].
        #         [patterns.flavors.<dim>] maps value_name → list[str].
        _write(tmp_path / "p.toml", '''
[profile]
name = "lang/python"
category = "lang"

[patterns]
always = ["__pycache__/", "*.pyc"]
dev_only = [".venv/"]
prod_only = ["/dist/"]

[patterns.stages]
staging = ["staging.log"]
production = ["production.log"]

[patterns.flavors.audience]
internal = ["internal-debug.log"]
external = ["external-redirect.cfg"]

[patterns.flavors.surface]
web = ["webpack.cache/"]
''')
        return ProfileRegistry([tmp_path])

    def test_dev_stage_no_flavors(self, registry: ProfileRegistry) -> None:
        # Note: TOML reads `[patterns.stages.<stage>]` as a dict of
        # "subkey -> list". The profile loader treats the *value* of
        # each subkey as the patterns list. The test fixture uses an
        # `all` subkey, but the loader iterates over the dict to find
        # ANY list-of-strings — so an extra layer is fine but uniform.
        # In real use, the convention is one flat list per stage.
        # For this test, just verify the legacy + always lines emit.
        v = Variant(stage="dev", flavors=())
        text = compose_variant(
            ["lang/python"], variant=v, registry=registry,
            clock=_FIXED_CLOCK,
        )
        assert "__pycache__/" in text
        assert ".venv/" in text   # legacy dev_only emits for stage=dev
        assert "/dist/" not in text

    def test_production_stage_uses_prod_only_legacy(
        self, registry: ProfileRegistry,
    ) -> None:
        v = Variant(stage="prod", flavors=())
        text = compose_variant(
            ["lang/python"], variant=v, registry=registry,
            clock=_FIXED_CLOCK,
        )
        assert "/dist/" in text
        assert ".venv/" not in text

    def test_header_records_variant_info(self, registry: ProfileRegistry) -> None:
        v = Variant(stage="prod", flavors=(("audience", "external"),))
        text = compose_variant(
            ["lang/python"], variant=v, registry=registry,
            clock=_FIXED_CLOCK,
        )
        assert "variant:       prod-external" in text
        assert "audience=external" in text


# --- Variant pattern selection (focused on Profile.patterns_for_variant) --- #


def _make_loaded(tmp_path: Path) -> ProfileRegistry:
    _write(tmp_path / "p.toml", '''
[profile]
name = "lang/x"
category = "lang"

[patterns]
always = ["always-line"]
dev_only = ["legacy-dev"]

[patterns.stages]
staging = ["staging-only-line"]

[patterns.flavors.audience]
internal = ["audience-internal-line"]

[patterns.flavors.surface]
web = ["surface-web-line"]
''')
    return ProfileRegistry([tmp_path])


class TestPatternsForVariant:
    def test_always_only_for_unknown_stage(self, tmp_path: Path) -> None:
        reg = _make_loaded(tmp_path)
        prof = reg.get("lang/x")
        out = prof.patterns_for_variant(stage="production", flavors=())
        # always-line is in; legacy dev/prod doesn't fire for "production".
        assert "always-line" in out
        assert "legacy-dev" not in out

    def test_legacy_dev_fires_for_dev_stage(self, tmp_path: Path) -> None:
        reg = _make_loaded(tmp_path)
        prof = reg.get("lang/x")
        out = prof.patterns_for_variant(stage="dev", flavors=())
        assert "always-line" in out
        assert "legacy-dev" in out

    def test_variant_stage_block_fires(self, tmp_path: Path) -> None:
        reg = _make_loaded(tmp_path)
        prof = reg.get("lang/x")
        out = prof.patterns_for_variant(stage="staging", flavors=())
        assert "staging-only-line" in out
        assert "legacy-dev" not in out

    def test_flavor_block_fires(self, tmp_path: Path) -> None:
        reg = _make_loaded(tmp_path)
        prof = reg.get("lang/x")
        out = prof.patterns_for_variant(
            stage="dev", flavors=(("audience", "internal"),),
        )
        assert "audience-internal-line" in out

    def test_unmatched_flavor_does_not_fire(self, tmp_path: Path) -> None:
        reg = _make_loaded(tmp_path)
        prof = reg.get("lang/x")
        out = prof.patterns_for_variant(
            stage="dev", flavors=(("audience", "external"),),
        )
        assert "audience-internal-line" not in out

    def test_multiple_flavors_combine(self, tmp_path: Path) -> None:
        reg = _make_loaded(tmp_path)
        prof = reg.get("lang/x")
        out = prof.patterns_for_variant(
            stage="dev",
            flavors=(("audience", "internal"), ("surface", "web")),
        )
        assert "audience-internal-line" in out
        assert "surface-web-line" in out
