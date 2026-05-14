"""Tests for T-G-004 — `tools/generators/commit_templates.py`.

Asserts:
  * ≥50 presets shipped (per §6.8.5).
  * Every Conventional Commits type has at least one preset.
  * Every v1 legacy message resolves to exactly ONE preset alias OR to FILTERED
    (no orphans, no double-coverage).
  * Preset IDs are unique + kebab-case.
  * v1 legacy tuple exactly matches the actual file on disk
    (`sange-v1/configs/config.sh`) — anti-hallucination guard.
  * TOML output parses cleanly.
  * Byte-identical re-run with the same clock.
  * Drift detection via CHECK mode.
"""

from __future__ import annotations

import datetime as _dt
import re
import sys
from pathlib import Path

import pytest

try:
    import tomllib  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover — Python 3.10 fallback
    import tomli as tomllib  # type: ignore[import-not-found]

REPO_ROOT = Path(__file__).resolve().parents[2]
GENERATORS_DIR = REPO_ROOT / "tools" / "generators"
if str(GENERATORS_DIR) not in sys.path:
    sys.path.insert(0, str(GENERATORS_DIR))

import commit_templates  # noqa: E402

from _lib.output import WriteMode  # noqa: E402


FIXED_CLOCK = _dt.datetime(2026, 5, 14, 16, 0, 0, tzinfo=_dt.timezone.utc)


# --------------------------------------------------------------------------- #
# Inventory invariants
# --------------------------------------------------------------------------- #


class TestPresetInventory:
    def test_at_least_50_presets(self) -> None:
        # §6.8.5 floor.
        assert len(commit_templates.PRESETS) >= 50

    def test_every_cc_type_has_at_least_one_preset(self) -> None:
        types_covered = {p.type for p in commit_templates.PRESETS}
        missing = set(commit_templates.CC_TYPES) - types_covered
        assert not missing, f"CC types with no preset: {sorted(missing)}"

    def test_preset_ids_unique(self) -> None:
        ids = [p.id for p in commit_templates.PRESETS]
        assert len(ids) == len(set(ids)), "duplicate preset ids: " + str(
            [i for i in ids if ids.count(i) > 1]
        )

    def test_preset_ids_are_kebab_case(self) -> None:
        pattern = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
        offenders = [p.id for p in commit_templates.PRESETS if not pattern.match(p.id)]
        assert not offenders, f"non-kebab-case ids: {offenders}"

    def test_preset_types_are_valid_cc_types(self) -> None:
        valid = set(commit_templates.CC_TYPES)
        offenders = [p for p in commit_templates.PRESETS if p.type not in valid]
        assert not offenders, (
            "presets with non-CC types: "
            + ", ".join(f"{p.id}({p.type})" for p in offenders)
        )

    def test_templates_use_valid_placeholders(self) -> None:
        """Placeholders are limited to a known set so the §6.8 renderer doesn't
        choke on a typo'd `${ssubject}`."""

        allowed = {"scope", "subject", "body", "refs", "breaking", "type"}
        bad: list[str] = []
        for p in commit_templates.PRESETS:
            for m in re.finditer(r"\$\{(\w+)\}", p.template + p.body_template):
                if m.group(1) not in allowed:
                    bad.append(f"{p.id}: ${{{m.group(1)}}}")
        assert not bad, "unknown placeholders: " + ", ".join(bad)


# --------------------------------------------------------------------------- #
# v1 legacy fidelity (anti-hallucination)
# --------------------------------------------------------------------------- #


class TestLegacyTupleMatchesActualFile:
    def test_v1_tuple_byte_exact_match(self) -> None:
        """The V1_LEGACY_MESSAGES tuple must match the actual file on disk.

        Per ADR-030: this generator's correctness depends on a verbatim
        capture of `sange-v1/configs/config.sh:25-128`. A drift here would
        mean we're transforming a fabricated input.
        """

        path = REPO_ROOT / "sange-v1" / "configs" / "config.sh"
        if not path.exists():
            pytest.skip(f"v1 source not on disk at {path}; R-017 may have closed early")
        text = path.read_text(encoding="utf-8")
        # Parse the bash array literal: lines between DEFAULT_GIT_COMMIT_MESSAGES=( and )
        m = re.search(
            r"DEFAULT_GIT_COMMIT_MESSAGES=\((.*?)\n\)",
            text,
            re.DOTALL,
        )
        assert m, "could not locate DEFAULT_GIT_COMMIT_MESSAGES=( ... ) in v1 file"
        raw_block = m.group(1)
        entries = re.findall(r'^\s*"(.+?)"\s*$', raw_block, re.MULTILINE)
        # Bash arrays don't quote-escape backslashes; the strings are literal.
        assert tuple(entries) == commit_templates.V1_LEGACY_MESSAGES, (
            f"v1 tuple drift detected. file={len(entries)} entries, "
            f"tuple={len(commit_templates.V1_LEGACY_MESSAGES)} entries"
        )


# --------------------------------------------------------------------------- #
# Coverage: every v1 string is either aliased or filtered
# --------------------------------------------------------------------------- #


class TestCoverage:
    def test_no_orphan_legacy_messages(self) -> None:
        """Every v1 string must be either:
          (a) in some preset's `aliases` tuple, OR
          (b) in `FILTERED` with an explanation.
        No v1 string is allowed to be silently dropped.
        """

        report = commit_templates.coverage_report()
        assert report["orphans"] == [], f"orphans: {report['orphans']}"

    def test_no_double_coverage(self) -> None:
        report = commit_templates.coverage_report()
        assert report["overlap"] == [], (
            f"v1 strings both aliased AND filtered: {report['overlap']}"
        )

    def test_no_extra_aliases(self) -> None:
        report = commit_templates.coverage_report()
        assert report["extra_aliases"] == [], (
            "preset aliases reference strings not in the v1 array (typo?): "
            + str(report["extra_aliases"])
        )

    def test_no_extra_filtered(self) -> None:
        report = commit_templates.coverage_report()
        assert report["extra_filtered"] == [], (
            f"FILTERED contains strings not in the v1 array: {report['extra_filtered']}"
        )

    def test_coverage_total_matches_legacy_count(self) -> None:
        report = commit_templates.coverage_report()
        assert report["aliased"] + report["filtered"] == report["legacy_total"]

    def test_alias_uniqueness(self) -> None:
        """No v1 alias may map to two presets — caught by the helper."""

        # Building the map raises ValueError on duplicates; just call it.
        commit_templates._alias_to_preset_map()


# --------------------------------------------------------------------------- #
# Generator end-to-end
# --------------------------------------------------------------------------- #


class TestGeneratorEndToEnd:
    def test_emits_library_and_appendix(self, tmp_path: Path) -> None:
        library = tmp_path / "default.toml"
        appendix = tmp_path / "appendix-g.md"
        commit_templates.run(
            mode=WriteMode.WRITE,
            clock=FIXED_CLOCK,
            library_path=library,
            appendix_path=appendix,
        )
        assert library.exists()
        assert appendix.exists()

    def test_library_parses_as_toml(self, tmp_path: Path) -> None:
        library = tmp_path / "default.toml"
        appendix = tmp_path / "appendix-g.md"
        commit_templates.run(
            mode=WriteMode.WRITE,
            clock=FIXED_CLOCK,
            library_path=library,
            appendix_path=appendix,
        )
        with library.open("rb") as fh:
            data = tomllib.load(fh)
        assert "meta" in data
        assert "preset" in data
        assert len(data["preset"]) == len(commit_templates.PRESETS)
        for entry in data["preset"]:
            for required in ("id", "type", "template", "description"):
                assert required in entry, f"preset missing {required}: {entry}"

    def test_appendix_has_frontmatter(self, tmp_path: Path) -> None:
        library = tmp_path / "default.toml"
        appendix = tmp_path / "appendix-g.md"
        commit_templates.run(
            mode=WriteMode.WRITE,
            clock=FIXED_CLOCK,
            library_path=library,
            appendix_path=appendix,
        )
        body = appendix.read_text(encoding="utf-8")
        assert body.startswith("---\n")
        assert "generated_by: tools/generators/commit_templates.py" in body

    def test_appendix_lists_every_preset(self, tmp_path: Path) -> None:
        library = tmp_path / "default.toml"
        appendix = tmp_path / "appendix-g.md"
        commit_templates.run(
            mode=WriteMode.WRITE,
            clock=FIXED_CLOCK,
            library_path=library,
            appendix_path=appendix,
        )
        body = appendix.read_text(encoding="utf-8")
        for preset in commit_templates.PRESETS:
            assert f"`{preset.id}`" in body, f"appendix missing preset {preset.id!r}"

    def test_appendix_lists_filtered_v1_strings(self, tmp_path: Path) -> None:
        library = tmp_path / "default.toml"
        appendix = tmp_path / "appendix-g.md"
        commit_templates.run(
            mode=WriteMode.WRITE,
            clock=FIXED_CLOCK,
            library_path=library,
            appendix_path=appendix,
        )
        body = appendix.read_text(encoding="utf-8")
        for legacy_string in commit_templates.FILTERED:
            assert legacy_string in body

    def test_byte_identical_rerun(self, tmp_path: Path) -> None:
        library = tmp_path / "default.toml"
        appendix = tmp_path / "appendix-g.md"
        commit_templates.run(
            mode=WriteMode.WRITE, clock=FIXED_CLOCK,
            library_path=library, appendix_path=appendix,
        )
        first_lib = library.read_bytes()
        first_apx = appendix.read_bytes()
        commit_templates.run(
            mode=WriteMode.WRITE, clock=FIXED_CLOCK,
            library_path=library, appendix_path=appendix,
        )
        assert library.read_bytes() == first_lib
        assert appendix.read_bytes() == first_apx

    def test_check_mode_match(self, tmp_path: Path) -> None:
        library = tmp_path / "default.toml"
        appendix = tmp_path / "appendix-g.md"
        commit_templates.run(
            mode=WriteMode.WRITE, clock=FIXED_CLOCK,
            library_path=library, appendix_path=appendix,
        )
        outcomes = commit_templates.run(
            mode=WriteMode.CHECK, clock=FIXED_CLOCK,
            library_path=library, appendix_path=appendix,
        )
        assert outcomes[0].result is not None
        assert outcomes[0].result.value == "match"

    def test_check_mode_detects_drift(self, tmp_path: Path) -> None:
        library = tmp_path / "default.toml"
        appendix = tmp_path / "appendix-g.md"
        commit_templates.run(
            mode=WriteMode.WRITE, clock=FIXED_CLOCK,
            library_path=library, appendix_path=appendix,
        )
        text = appendix.read_text(encoding="utf-8")
        appendix.write_text(text.replace("Appendix G", "MUTATED"), encoding="utf-8")
        outcomes = commit_templates.run(
            mode=WriteMode.CHECK, clock=FIXED_CLOCK,
            library_path=library, appendix_path=appendix,
        )
        assert outcomes[0].result is not None
        assert outcomes[0].result.value == "mismatch"
