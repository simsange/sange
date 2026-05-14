"""Tests for T-G-012 — `tools/generators/threat_model_table.py`.

Asserts:
  * Every STRIDE category has ≥1 threat.
  * Threat IDs are unique + T-NNN-shaped.
  * Every threat has ≥1 mitigation; Critical-blast threats have ≥3.
  * `blast_radius` is one of the documented values.
  * `affected` references look like §-anchors or known subsystem labels.
  * Markdown output carries §16.4.1 frontmatter.
  * Byte-identical re-run; drift detection.
"""

from __future__ import annotations

import datetime as _dt
import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
GENERATORS_DIR = REPO_ROOT / "tools" / "generators"
if str(GENERATORS_DIR) not in sys.path:
    sys.path.insert(0, str(GENERATORS_DIR))

import threat_model_table  # noqa: E402

from _lib.output import WriteMode  # noqa: E402


FIXED_CLOCK = _dt.datetime(2026, 5, 14, 18, 0, 0, tzinfo=_dt.timezone.utc)


# --------------------------------------------------------------------------- #
# Catalog invariants
# --------------------------------------------------------------------------- #


class TestCatalogInvariants:
    def test_every_stride_category_has_at_least_one_threat(self) -> None:
        seen = {t.category for t in threat_model_table.THREATS}
        missing = set(threat_model_table.STRIDE_ORDER) - seen
        assert not missing, f"STRIDE categories with no threat: {sorted(s.value for s in missing)}"

    def test_threat_ids_are_unique(self) -> None:
        ids = [t.id for t in threat_model_table.THREATS]
        assert len(ids) == len(set(ids)), (
            "duplicate threat IDs: " + str([i for i in ids if ids.count(i) > 1])
        )

    def test_threat_ids_are_t_nnn(self) -> None:
        pattern = re.compile(r"^T-\d{3}$")
        offenders = [t.id for t in threat_model_table.THREATS if not pattern.match(t.id)]
        assert not offenders, f"non-T-NNN ids: {offenders}"

    def test_id_block_matches_category(self) -> None:
        """Convention from the generator's docstring + the §-anchored table:
        T-001..T-009 → Spoofing
        T-010..T-019 → Tampering
        T-020..T-029 → Repudiation
        T-030..T-039 → Information Disclosure
        T-040..T-049 → Denial of Service
        T-050..T-059 → Elevation of Privilege
        """

        category_to_range = {
            threat_model_table.Stride.SPOOFING: range(1, 10),
            threat_model_table.Stride.TAMPERING: range(10, 20),
            threat_model_table.Stride.REPUDIATION: range(20, 30),
            threat_model_table.Stride.INFORMATION_DISCLOSURE: range(30, 40),
            threat_model_table.Stride.DENIAL_OF_SERVICE: range(40, 50),
            threat_model_table.Stride.ELEVATION_OF_PRIVILEGE: range(50, 60),
        }
        offenders: list[str] = []
        for t in threat_model_table.THREATS:
            number = int(t.id.split("-")[1])
            expected_range = category_to_range[t.category]
            if number not in expected_range:
                offenders.append(
                    f"{t.id} ({t.category.value}) outside range "
                    f"{expected_range.start}..{expected_range.stop - 1}"
                )
        assert not offenders, "id-range/category mismatches: " + "; ".join(offenders)

    def test_every_threat_has_at_least_one_mitigation(self) -> None:
        offenders = [t.id for t in threat_model_table.THREATS if not t.mitigations]
        assert not offenders, f"threats with no mitigation: {offenders}"

    def test_critical_threats_have_at_least_three_mitigations(self) -> None:
        """Defense-in-depth invariant: Critical-blast threats must layer."""

        offenders = [
            f"{t.id} ({len(t.mitigations)} mitigation(s))"
            for t in threat_model_table.THREATS
            if t.blast_radius == threat_model_table.Blast.CRITICAL
            and len(t.mitigations) < 3
        ]
        assert not offenders, (
            "Critical-blast threats must have ≥3 mitigations: " + ", ".join(offenders)
        )

    def test_blast_radius_is_documented_value(self) -> None:
        for t in threat_model_table.THREATS:
            assert isinstance(t.blast_radius, threat_model_table.Blast)

    def test_affected_subsystems_look_like_anchors(self) -> None:
        """Every `affected` entry should look like a §-anchor, an ADR ref, or a
        recognizable subsystem name. This catches typos like "§ 6.11 Pure"."""

        pattern = re.compile(r"^(§|ADR-|\.design/|tests/|tools/|src/|docs/)\S")
        for t in threat_model_table.THREATS:
            for affected in t.affected:
                assert pattern.match(affected), (
                    f"{t.id}: affected entry {affected!r} doesn't start with a §, ADR-, "
                    "or known path prefix"
                )

    def test_at_least_25_threats(self) -> None:
        # The prompt §11 has ~25 rows; the catalog should not regress below that.
        assert len(threat_model_table.THREATS) >= 25


# --------------------------------------------------------------------------- #
# Generator end-to-end
# --------------------------------------------------------------------------- #


class TestGeneratorEndToEnd:
    def test_produces_file_with_frontmatter(self, tmp_path: Path) -> None:
        target = tmp_path / "stride.md"
        threat_model_table.run(mode=WriteMode.WRITE, clock=FIXED_CLOCK, output_path=target)
        body = target.read_text(encoding="utf-8")
        assert body.startswith("---\n")
        assert "generated_by: tools/generators/threat_model_table.py" in body

    def test_body_contains_every_threat(self, tmp_path: Path) -> None:
        target = tmp_path / "stride.md"
        threat_model_table.run(mode=WriteMode.WRITE, clock=FIXED_CLOCK, output_path=target)
        body = target.read_text(encoding="utf-8")
        for t in threat_model_table.THREATS:
            assert t.id in body, f"missing {t.id} in output"
            assert t.title in body, f"missing title for {t.id}: {t.title!r}"

    def test_body_contains_every_category(self, tmp_path: Path) -> None:
        target = tmp_path / "stride.md"
        threat_model_table.run(mode=WriteMode.WRITE, clock=FIXED_CLOCK, output_path=target)
        body = target.read_text(encoding="utf-8")
        for category in threat_model_table.STRIDE_ORDER:
            assert category.value in body, f"missing STRIDE category {category.value}"

    def test_byte_identical_rerun(self, tmp_path: Path) -> None:
        target = tmp_path / "stride.md"
        threat_model_table.run(mode=WriteMode.WRITE, clock=FIXED_CLOCK, output_path=target)
        first = target.read_bytes()
        threat_model_table.run(mode=WriteMode.WRITE, clock=FIXED_CLOCK, output_path=target)
        assert target.read_bytes() == first

    def test_check_mode_match(self, tmp_path: Path) -> None:
        target = tmp_path / "stride.md"
        threat_model_table.run(mode=WriteMode.WRITE, clock=FIXED_CLOCK, output_path=target)
        outcomes = threat_model_table.run(
            mode=WriteMode.CHECK, clock=FIXED_CLOCK, output_path=target
        )
        assert outcomes[0].result is not None
        assert outcomes[0].result.value == "match"

    def test_check_mode_detects_drift(self, tmp_path: Path) -> None:
        target = tmp_path / "stride.md"
        threat_model_table.run(mode=WriteMode.WRITE, clock=FIXED_CLOCK, output_path=target)
        text = target.read_text(encoding="utf-8")
        target.write_text(text.replace("STRIDE", "MUTATED"), encoding="utf-8")
        outcomes = threat_model_table.run(
            mode=WriteMode.CHECK, clock=FIXED_CLOCK, output_path=target
        )
        assert outcomes[0].result is not None
        assert outcomes[0].result.value == "mismatch"

    def test_input_sha_is_stable(self) -> None:
        a = threat_model_table._input_sha256()
        b = threat_model_table._input_sha256()
        assert a == b
