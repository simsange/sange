"""Tests for T-G-015 — `tools/generators/profile_registry.py`.

Asserts:
  * Every §6.5.1 row has a registered Profile.
  * Profiles have all required fields populated.
  * `_core/secrets` and `_core/license` are always-on safety profiles.
  * `_core/license` declares only re-include patterns (the never-exclude set).
  * Auto-detect signals don't accidentally collide within a category.
  * Every emitted TOML parses cleanly.
  * Byte-identical re-run.
  * Reference doc contains every profile name.
  * Profile-name slugs match the §10.4 Category convention.
"""

from __future__ import annotations

import datetime as _dt
import sys
from pathlib import Path

import pytest

# Python 3.11+ has tomllib; on 3.10 we fall back to tomli.
try:
    import tomllib  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover
    import tomli as tomllib  # type: ignore[import-not-found]

REPO_ROOT = Path(__file__).resolve().parents[2]
GENERATORS_DIR = REPO_ROOT / "tools" / "generators"
if str(GENERATORS_DIR) not in sys.path:
    sys.path.insert(0, str(GENERATORS_DIR))

import profile_registry  # noqa: E402

from _lib.output import WriteMode  # noqa: E402


FIXED_CLOCK = _dt.datetime(2026, 5, 14, 14, 0, 0, tzinfo=_dt.timezone.utc)

# The §6.5.1 v1.0 canonical row list (35 patterns-owning + 1 _core/license safety = 36 total).
# Kotlin (`lang/kotlin`) is intentionally NOT in v1.0 — it's documented in the reference
# doc as covered by `lang/java` + `editor/jetbrains`, which avoids the
# `build.gradle.kts` auto-detect collision with java.
EXPECTED_PROFILE_NAMES = {
    # _core
    "_core/secrets",
    "_core/editor-noise",
    "_core/license",
    # lang (11 — kotlin documented-not-shipped per ADR-026)
    "lang/python", "lang/node", "lang/php", "lang/go", "lang/rust", "lang/ruby",
    "lang/java", "lang/dotnet", "lang/elixir", "lang/swift", "lang/dart",
    # framework
    "framework/laravel", "framework/django", "framework/rails", "framework/nextjs",
    "framework/nuxt", "framework/symfony", "framework/astro", "framework/sveltekit",
    "framework/flutter",
    # infra
    "infra/docker", "infra/kubernetes", "infra/terraform", "infra/ansible",
    "infra/pulumi",
    # editor
    "editor/jetbrains", "editor/vscode", "editor/vim", "editor/emacs", "editor/claude",
    # os
    "os/macos", "os/windows", "os/linux",
}


# --------------------------------------------------------------------------- #
# Registry inventory
# --------------------------------------------------------------------------- #


class TestRegistryInventory:
    def test_all_canonical_profiles_present(self) -> None:
        emitted_names = {p.name for p in profile_registry._all_profiles()}
        missing = EXPECTED_PROFILE_NAMES - emitted_names
        extra = emitted_names - EXPECTED_PROFILE_NAMES
        assert not missing, f"missing profiles: {sorted(missing)}"
        assert not extra, f"unexpected extra profiles: {sorted(extra)}"

    def test_profile_count_is_36(self) -> None:
        # 35 patterns-owning profiles + 1 _core/license safety = 36 total.
        assert len(profile_registry._all_profiles()) == 36

    def test_every_profile_slug_matches_category_convention(self) -> None:
        """§10.4: every fragment slug is `<category>/<name>`; category from
        the canonical list."""

        valid_categories = {"_core", "lang", "framework", "infra", "editor", "os"}
        for p in profile_registry._all_profiles():
            cat, _, name = p.name.partition("/")
            assert "/" in p.name, f"{p.name!r} missing category prefix"
            assert cat == p.category, f"{p.name!r} slug category {cat!r} != p.category {p.category!r}"
            assert cat in valid_categories, f"{p.name!r} has unknown category {cat!r}"
            assert name, f"{p.name!r} missing name after category"

    def test_required_fields_populated(self) -> None:
        for p in profile_registry._all_profiles():
            assert p.display_name, f"{p.name}: display_name empty"
            assert p.version, f"{p.name}: version empty"
            assert p.maintainer, f"{p.name}: maintainer empty"


# --------------------------------------------------------------------------- #
# Safety profiles
# --------------------------------------------------------------------------- #


class TestSafetyProfiles:
    def test_core_secrets_present(self) -> None:
        names = {p.name for p in profile_registry._all_profiles()}
        assert "_core/secrets" in names

    def test_core_license_is_only_re_include_patterns(self) -> None:
        """The never-exclude safety profile must declare only `!path` lines."""

        license_profile = next(
            p for p in profile_registry._all_profiles() if p.name == "_core/license"
        )
        for pattern in license_profile.patterns_always:
            assert pattern.startswith("!"), (
                f"_core/license declared non-negation pattern {pattern!r}; the safety "
                "profile must only re-include — it cannot exclude paths."
            )
        for pattern in license_profile.patterns_dev_only:
            assert pattern.startswith("!"), f"_core/license dev_only: {pattern!r}"
        for pattern in license_profile.patterns_prod_only:
            assert pattern.startswith("!"), f"_core/license prod_only: {pattern!r}"

    def test_core_secrets_includes_env_files(self) -> None:
        secrets = next(
            p for p in profile_registry._all_profiles() if p.name == "_core/secrets"
        )
        patterns = list(secrets.patterns_always)
        for required in (".env", ".env.*", "*.pem", "*.key"):
            assert required in patterns, f"_core/secrets missing {required!r}"


# --------------------------------------------------------------------------- #
# Auto-detection consistency
# --------------------------------------------------------------------------- #


class TestAutoDetectConsistency:
    def test_no_two_profiles_share_required_any_within_a_category(self) -> None:
        """If `lang/python` and `lang/node` both claimed `package.json`, the
        suggestion engine would propose both for every Node repo. Catch
        accidental duplicates at the category level."""

        by_category: dict[str, dict[str, list[str]]] = {}
        for p in profile_registry._all_profiles():
            if p.category == "_core":
                continue  # _core profiles are always-on; no detection signal
            cat_map = by_category.setdefault(p.category, {})
            for signal in p.detect_required_any:
                cat_map.setdefault(signal, []).append(p.name)

        offenders: list[str] = []
        for category, signals in by_category.items():
            for signal, owners in signals.items():
                if len(owners) > 1:
                    offenders.append(f"{category}: {signal!r} claimed by {owners}")
        # Allow lang/node + framework/* to share package.json (it's a
        # legitimate signal for Next/Nuxt/Astro/SvelteKit all extending node);
        # detection picks the most-specific via extends.
        # So we only flag duplicates WITHIN the same category.
        assert not offenders, "auto-detect signal collisions: " + "; ".join(offenders)

    def test_framework_profiles_extend_their_language(self) -> None:
        """Sanity check that framework profiles declare their language as a parent."""

        framework_to_lang = {
            "framework/laravel": "lang/php",
            "framework/symfony": "lang/php",
            "framework/django": "lang/python",
            "framework/rails": "lang/ruby",
            "framework/nextjs": "lang/node",
            "framework/nuxt": "lang/node",
            "framework/astro": "lang/node",
            "framework/sveltekit": "lang/node",
            "framework/flutter": "lang/dart",
        }
        by_name = {p.name: p for p in profile_registry._all_profiles()}
        for framework, language in framework_to_lang.items():
            extends = by_name[framework].extends
            assert language in extends, (
                f"{framework} should extend {language}; got extends={extends}"
            )


# --------------------------------------------------------------------------- #
# TOML emission
# --------------------------------------------------------------------------- #


class TestTomlEmission:
    @pytest.fixture
    def staging_dir(self, tmp_path: Path) -> tuple[Path, Path]:
        out_dir = tmp_path / "templates" / "gitignore-profiles"
        out_doc = tmp_path / "docs" / "reference" / "profile-registry.md"
        profile_registry.run(
            mode=WriteMode.WRITE,
            clock=FIXED_CLOCK,
            profiles_output_dir=out_dir,
            reference_doc_path=out_doc,
        )
        return out_dir, out_doc

    def test_one_toml_per_profile_emitted(self, staging_dir: tuple[Path, Path]) -> None:
        out_dir, _ = staging_dir
        emitted = list(out_dir.rglob("*.toml"))
        assert len(emitted) == 36, f"expected 36 TOMLs, found {len(emitted)}"

    def test_every_toml_parses(self, staging_dir: tuple[Path, Path]) -> None:
        out_dir, _ = staging_dir
        for path in out_dir.rglob("*.toml"):
            with path.open("rb") as fh:
                try:
                    data = tomllib.load(fh)
                except Exception as exc:  # noqa: BLE001
                    pytest.fail(f"failed to parse {path}: {exc}")
            assert "profile" in data, f"{path}: missing [profile] table"
            assert "patterns" in data, f"{path}: missing [patterns] table"

    def test_toml_shape_matches_spec(self, staging_dir: tuple[Path, Path]) -> None:
        out_dir, _ = staging_dir
        python_path = out_dir / "lang" / "python.toml"
        with python_path.open("rb") as fh:
            data = tomllib.load(fh)
        assert data["profile"]["name"] == "lang/python"
        assert data["profile"]["category"] == "lang"
        assert "patterns" in data
        assert "always" in data["patterns"]
        assert "__pycache__/" in data["patterns"]["always"]
        assert ".ruff_cache/" in data["patterns"]["dev_only"]

    def test_kotlin_is_documented_not_shipped(self, staging_dir: tuple[Path, Path]) -> None:
        """Kotlin doesn't ship a TOML — it would collide with Java on
        build.gradle.kts. The reference doc must mention this."""

        out_dir, out_doc = staging_dir
        kotlin_path = out_dir / "lang" / "kotlin.toml"
        assert not kotlin_path.exists(), (
            "lang/kotlin should NOT ship a TOML per ADR-026 — Java + JetBrains cover it"
        )
        body = out_doc.read_text(encoding="utf-8")
        assert "Kotlin" in body, "reference doc should mention Kotlin coverage"


# --------------------------------------------------------------------------- #
# Reference doc end-to-end
# --------------------------------------------------------------------------- #


class TestReferenceDoc:
    def test_reference_doc_has_frontmatter(self, tmp_path: Path) -> None:
        out_dir = tmp_path / "templates" / "gitignore-profiles"
        out_doc = tmp_path / "doc.md"
        profile_registry.run(
            mode=WriteMode.WRITE,
            clock=FIXED_CLOCK,
            profiles_output_dir=out_dir,
            reference_doc_path=out_doc,
        )
        body = out_doc.read_text(encoding="utf-8")
        assert body.startswith("---\n")
        assert "generated_by: tools/generators/profile_registry.py" in body

    def test_reference_doc_lists_every_profile(self, tmp_path: Path) -> None:
        out_dir = tmp_path / "templates" / "gitignore-profiles"
        out_doc = tmp_path / "doc.md"
        profile_registry.run(
            mode=WriteMode.WRITE,
            clock=FIXED_CLOCK,
            profiles_output_dir=out_dir,
            reference_doc_path=out_doc,
        )
        body = out_doc.read_text(encoding="utf-8")
        for name in EXPECTED_PROFILE_NAMES:
            assert f"`{name}`" in body, f"reference doc missing `{name}`"

    def test_byte_identical_rerun(self, tmp_path: Path) -> None:
        out_dir = tmp_path / "templates" / "gitignore-profiles"
        out_doc = tmp_path / "doc.md"
        profile_registry.run(
            mode=WriteMode.WRITE, clock=FIXED_CLOCK,
            profiles_output_dir=out_dir, reference_doc_path=out_doc,
        )
        first = out_doc.read_bytes()
        first_tomls = {p.relative_to(out_dir): p.read_bytes() for p in out_dir.rglob("*.toml")}
        profile_registry.run(
            mode=WriteMode.WRITE, clock=FIXED_CLOCK,
            profiles_output_dir=out_dir, reference_doc_path=out_doc,
        )
        assert out_doc.read_bytes() == first
        for rel, bytes_first in first_tomls.items():
            assert (out_dir / rel).read_bytes() == bytes_first

    def test_check_mode_match(self, tmp_path: Path) -> None:
        out_dir = tmp_path / "templates" / "gitignore-profiles"
        out_doc = tmp_path / "doc.md"
        profile_registry.run(
            mode=WriteMode.WRITE, clock=FIXED_CLOCK,
            profiles_output_dir=out_dir, reference_doc_path=out_doc,
        )
        outcomes = profile_registry.run(
            mode=WriteMode.CHECK, clock=FIXED_CLOCK,
            profiles_output_dir=out_dir, reference_doc_path=out_doc,
        )
        assert outcomes[0].result is not None
        assert outcomes[0].result.value == "match"
