"""Tests for T-G-016 — `tools/generators/verify_session_log.py`.

Asserts:
  * Parser recognises both 8-column (legacy) and 10-column (grounding-aware) rows.
  * Cross-reference resolver catches unresolved ADR-NNN, T-NNN, R-NNN, S-NNN refs.
  * Cross-reference resolver tolerates T-NNN refs that resolve via STRIDE.
  * Grounding-column check fires for S-001-T-20+ + every S-002+ row that's empty.
  * Files-touched check ignores sha256 hashes, identifiers, range placeholders.
  * Real session log passes (integration check against the actual canonical file).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
GENERATORS_DIR = REPO_ROOT / "tools" / "generators"
if str(GENERATORS_DIR) not in sys.path:
    sys.path.insert(0, str(GENERATORS_DIR))

import verify_session_log as vsl  # noqa: E402

# --------------------------------------------------------------------------- #
# Parsing
# --------------------------------------------------------------------------- #


SAMPLE_8COL = (
    "| S-001-T-05 | 2026-05-13T10:00Z | model | prompt | Did something | "
    "`a.md` | T-001 / ADR-007 | Some notes |\n"
)
SAMPLE_10COL = (
    "| S-002-T-01 | 2026-05-14T05:25Z | user | code | Did something else | "
    "`b.md` | `.design/plans/checklist.md` | T-001 / ADR-027 | — | More notes |\n"
)


class TestParsing:
    def test_parses_8col_row(self) -> None:
        rows = vsl.parse_session_log(SAMPLE_8COL)
        assert len(rows) == 1
        assert rows[0].id == "S-001-T-05"
        assert rows[0].grounding_raw == ""

    def test_parses_10col_row(self) -> None:
        rows = vsl.parse_session_log(SAMPLE_10COL)
        assert len(rows) == 1
        assert rows[0].id == "S-002-T-01"
        assert rows[0].grounding_raw == "`.design/plans/checklist.md`"

    def test_skips_non_row_lines(self) -> None:
        text = "Some intro paragraph.\n" + SAMPLE_8COL + "Another paragraph.\n"
        rows = vsl.parse_session_log(text)
        assert len(rows) == 1


# --------------------------------------------------------------------------- #
# Cross-references
# --------------------------------------------------------------------------- #


class TestCrossReferences:
    def test_unknown_adr_flagged(self) -> None:
        rows = [
            vsl.SessionLogRow(
                id="S-001-T-99", timestamp="", actor="", surface="", action="",
                files_touched_raw="", grounding_raw="", linked_raw="ADR-999",
                notes_raw="",
            )
        ]
        failures = vsl.check_cross_references(
            rows, known_adrs=set(), known_risks=set(), known_tasks=set(),
            known_sessions=set(),
        )
        assert any("ADR-999" in f for f in failures)

    def test_known_adr_passes(self) -> None:
        rows = [
            vsl.SessionLogRow(
                id="S-001-T-99", timestamp="", actor="", surface="", action="",
                files_touched_raw="", grounding_raw="", linked_raw="ADR-001",
                notes_raw="",
            )
        ]
        failures = vsl.check_cross_references(
            rows, known_adrs={"ADR-001"}, known_risks=set(), known_tasks=set(),
            known_sessions=set(),
        )
        assert not failures

    def test_t_nnn_falls_back_to_stride(self) -> None:
        """T-001 should resolve via STRIDE when not in checklist."""

        rows = [
            vsl.SessionLogRow(
                id="S-001-T-99", timestamp="", actor="", surface="", action="",
                files_touched_raw="", grounding_raw="", linked_raw="T-001",
                notes_raw="",
            )
        ]
        failures = vsl.check_cross_references(
            rows,
            known_adrs=set(),
            known_risks=set(),
            known_tasks=set(),
            known_sessions=set(),
            known_stride_threats={"T-001"},
        )
        assert not failures

    def test_unknown_risk_flagged(self) -> None:
        rows = [
            vsl.SessionLogRow(
                id="S-001-T-99", timestamp="", actor="", surface="", action="",
                files_touched_raw="", grounding_raw="", linked_raw="",
                notes_raw="see R-999",
            )
        ]
        failures = vsl.check_cross_references(
            rows, known_adrs=set(), known_risks={"R-001"},
            known_tasks=set(), known_sessions=set(),
        )
        assert any("R-999" in f for f in failures)

    def test_session_self_ref_ok(self) -> None:
        rows = [
            vsl.SessionLogRow(
                id="S-002-T-08", timestamp="", actor="", surface="", action="",
                files_touched_raw="", grounding_raw="", linked_raw="S-002-T-08",
                notes_raw="",
            )
        ]
        # Self-ref doesn't need to be in known_sessions.
        failures = vsl.check_cross_references(
            rows, known_adrs=set(), known_risks=set(),
            known_tasks=set(), known_sessions=set(),
        )
        assert not failures


# --------------------------------------------------------------------------- #
# Grounding column
# --------------------------------------------------------------------------- #


class TestGrounding:
    def test_required_from_s001_t20(self) -> None:
        assert vsl._is_grounding_required("S-001-T-20")
        assert vsl._is_grounding_required("S-001-T-21")
        assert not vsl._is_grounding_required("S-001-T-19")

    def test_all_s002_required(self) -> None:
        assert vsl._is_grounding_required("S-002-T-01")
        assert vsl._is_grounding_required("S-002-T-99")

    def test_empty_grounding_flagged(self) -> None:
        rows = [
            vsl.SessionLogRow(
                id="S-002-T-05", timestamp="", actor="", surface="", action="",
                files_touched_raw="`x.md`", grounding_raw="", linked_raw="",
                notes_raw="",
            )
        ]
        failures = vsl.check_grounding(rows)
        assert any("S-002-T-05" in f for f in failures)

    def test_dash_grounding_flagged(self) -> None:
        rows = [
            vsl.SessionLogRow(
                id="S-002-T-05", timestamp="", actor="", surface="", action="",
                files_touched_raw="", grounding_raw="—", linked_raw="",
                notes_raw="",
            )
        ]
        failures = vsl.check_grounding(rows)
        assert any("S-002-T-05" in f for f in failures)

    def test_populated_grounding_passes(self) -> None:
        rows = [
            vsl.SessionLogRow(
                id="S-002-T-05", timestamp="", actor="", surface="", action="",
                files_touched_raw="", grounding_raw="`some/file.py`",
                linked_raw="", notes_raw="",
            )
        ]
        assert not vsl.check_grounding(rows)

    def test_pre_s001_t20_exempt(self) -> None:
        rows = [
            vsl.SessionLogRow(
                id="S-001-T-05", timestamp="", actor="", surface="", action="",
                files_touched_raw="", grounding_raw="", linked_raw="",
                notes_raw="",
            )
        ]
        assert not vsl.check_grounding(rows)


# --------------------------------------------------------------------------- #
# Files-touched heuristic
# --------------------------------------------------------------------------- #


class TestFilesTouchedHeuristic:
    def test_sha256_is_not_a_path(self) -> None:
        assert not vsl._looks_like_a_path("a" * 64)
        assert not vsl._looks_like_a_path(
            "1eb540553029da512da2d995a9a0cc6479885fdb9a8c6b84126f79b135915db6"
        )

    def test_identifier_is_not_a_path(self) -> None:
        assert not vsl._looks_like_a_path("output_sha256")
        assert not vsl._looks_like_a_path("test_check_matches_across_different_clocks")

    def test_template_placeholder_is_not_a_path(self) -> None:
        assert not vsl._looks_like_a_path("templates/gitignore-profiles/<category>/<name>.toml")

    def test_real_paths_pass(self) -> None:
        assert vsl._looks_like_a_path("tools/generators/exit_codes.py")
        assert vsl._looks_like_a_path("docs/reference/exit-codes.md")
        assert vsl._looks_like_a_path("pyproject.toml")  # known extension
        assert vsl._looks_like_a_path("README.md")

    def test_anchor_is_not_a_path(self) -> None:
        assert not vsl._looks_like_a_path("§6.5.1")
        assert not vsl._looks_like_a_path("§11 (the table)")


# --------------------------------------------------------------------------- #
# Integration — real session-log must pass
# --------------------------------------------------------------------------- #


class TestRealSessionLog:
    def test_canonical_session_log_passes_all_checks(self) -> None:
        """The actual `.design/plans/session-log.md` must verify cleanly.

        Per ADR-030 + ADR-031: this is the discipline gate. If the canonical
        log has unresolved cross-refs or missing grounding, the project's
        own continuity rules are violated.
        """

        report = vsl.verify()
        assert report.passed, (
            f"verify_session_log failed against the canonical .design/plans/session-log.md:\n"
            f"  cross-ref failures ({len(report.cross_ref_failures)}): "
            f"{report.cross_ref_failures[:5]}\n"
            f"  grounding failures ({len(report.grounding_failures)}): "
            f"{report.grounding_failures[:5]}\n"
            f"  files_touched failures ({len(report.files_touched_failures)}): "
            f"{report.files_touched_failures[:5]}"
        )

    def test_rows_parsed_count_sanity(self) -> None:
        report = vsl.verify()
        # Should have parsed at least 30 rows by S-002-T-30.
        assert report.rows_parsed >= 30
