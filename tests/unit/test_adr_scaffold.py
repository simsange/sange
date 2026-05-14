"""Tests for `tools/generators/adr_scaffold.py` (T-G-007).

Covers: next-number detection, slug generation, template field presence,
collision refusal, dry-run mode, orchestrator no-op.
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

import adr_scaffold  # noqa: E402

from _lib.output import WriteMode  # noqa: E402


FIXED_CLOCK = _dt.datetime(2026, 5, 14, 8, 0, 0, tzinfo=_dt.timezone.utc)


# --------------------------------------------------------------------------- #
# next_adr_number
# --------------------------------------------------------------------------- #


class TestNextAdrNumber:
    def test_one_when_both_sources_empty(self, tmp_path: Path) -> None:
        empty_log = tmp_path / "decisions-log.md"
        empty_log.write_text("# log\n\nno ADRs yet\n", encoding="utf-8")
        empty_adr = tmp_path / "adr"
        empty_adr.mkdir()
        assert (
            adr_scaffold.next_adr_number(decisions_log=empty_log, adr_dir=empty_adr)
            == 1
        )

    def test_picks_max_plus_one_from_log(self, tmp_path: Path) -> None:
        log = tmp_path / "decisions-log.md"
        log.write_text("| ADR-001 | foo |\n| ADR-007 | bar |\n", encoding="utf-8")
        adr_dir = tmp_path / "adr"
        adr_dir.mkdir()
        assert (
            adr_scaffold.next_adr_number(decisions_log=log, adr_dir=adr_dir) == 8
        )

    def test_picks_max_plus_one_from_files(self, tmp_path: Path) -> None:
        log = tmp_path / "decisions-log.md"
        log.write_text("(empty)\n", encoding="utf-8")
        adr_dir = tmp_path / "adr"
        adr_dir.mkdir()
        (adr_dir / "0003-foo.md").write_text("dummy", encoding="utf-8")
        (adr_dir / "0012-bar.md").write_text("dummy", encoding="utf-8")
        assert (
            adr_scaffold.next_adr_number(decisions_log=log, adr_dir=adr_dir) == 13
        )

    def test_max_across_both_sources(self, tmp_path: Path) -> None:
        log = tmp_path / "decisions-log.md"
        log.write_text("| ADR-005 | x |\n| ADR-010 | y |\n", encoding="utf-8")
        adr_dir = tmp_path / "adr"
        adr_dir.mkdir()
        (adr_dir / "0009-foo.md").write_text("dummy", encoding="utf-8")
        # Log winner is 10, file winner is 9 → 11 is correct.
        assert (
            adr_scaffold.next_adr_number(decisions_log=log, adr_dir=adr_dir) == 11
        )

    def test_ignores_prose_mentions_outside_table_rows(self, tmp_path: Path) -> None:
        """A "next slot" callout or any prose reference must NOT bump the count.

        Regression test for the bug where the loose `\\bADR-NNN\\b` regex picked
        up the meta-callout `**ADR-032** is the next available number...` in
        the canonical decisions-log, yielding next=33 instead of next=32.
        """

        log = tmp_path / "decisions-log.md"
        log.write_text(
            "| ADR | Title |\n| --- | --- |\n"
            "| ADR-001 | First |\n"
            "| ADR-031 | Latest accepted |\n"
            "\n## Next ADR slot\n\n"
            "**ADR-032** is the next available number. Supersedes ADR-027? No.\n",
            encoding="utf-8",
        )
        adr_dir = tmp_path / "adr"
        adr_dir.mkdir()
        # Canonical table rows: 001, 031. Prose mentions 032 and 027 — ignored.
        assert (
            adr_scaffold.next_adr_number(decisions_log=log, adr_dir=adr_dir) == 32
        )

    def test_real_decisions_log_next_slot_advances_with_each_acceptance(self) -> None:
        """Sanity check the real decisions-log against itself.

        Asserts: the next-free number returned by the parser equals the
        explicit "Next ADR slot: **ADR-NNN**" callout at the bottom of
        `.design/plans/decisions-log.md`. The parser and the human-edited
        callout must agree, or the canonical doc is in conflict with itself.

        (S-002-T-19 + S-002-T-23 are the load-bearing entries: when ADR-032
        was added the callout bumped from 0032 → 0033 in lockstep. This test
        catches drift between the row count and the callout.)
        """

        from pathlib import Path

        REPO_ROOT = Path(__file__).resolve().parents[2]
        log_text = (REPO_ROOT / ".design" / "plans" / "decisions-log.md").read_text(encoding="utf-8")

        # Extract the canonical "Next ADR slot" callout's number.
        callout_match = re.search(
            r"## Next ADR slot\s*\n\s*\n\s*\*\*ADR-(\d{3,4})\*\* is the next available number",
            log_text,
        )
        assert callout_match, "could not locate '## Next ADR slot ... **ADR-NNN**' callout"
        callout_number = int(callout_match.group(1))

        parser_result = adr_scaffold.next_adr_number()
        assert parser_result == callout_number, (
            f"parser returned {parser_result} but the decisions-log's "
            f"\"Next ADR slot\" callout claims {callout_number}. One of them "
            f"is wrong; investigate before scaffolding the next ADR."
        )


# --------------------------------------------------------------------------- #
# scaffold()
# --------------------------------------------------------------------------- #


class TestScaffold:
    def _setup(self, tmp_path: Path, *, log_text: str = "(empty)\n") -> tuple[Path, Path]:
        log = tmp_path / "decisions-log.md"
        log.write_text(log_text, encoding="utf-8")
        adr_dir = tmp_path / "adr"
        adr_dir.mkdir()
        return log, adr_dir

    def test_writes_expected_filename(self, tmp_path: Path) -> None:
        log, adr_dir = self._setup(tmp_path)
        outcome = adr_scaffold.scaffold(
            "Switch to Pydantic v3",
            clock=FIXED_CLOCK,
            decisions_log=log,
            adr_dir=adr_dir,
        )
        assert outcome.path == adr_dir / "0001-switch-to-pydantic-v3.md"
        assert outcome.path.exists()

    def test_filename_is_zero_padded_four_digits(self, tmp_path: Path) -> None:
        log, adr_dir = self._setup(tmp_path)
        outcome = adr_scaffold.scaffold(
            "Tiny",
            number=42,
            clock=FIXED_CLOCK,
            decisions_log=log,
            adr_dir=adr_dir,
        )
        assert outcome.path.name == "0042-tiny.md"

    def test_explicit_slug(self, tmp_path: Path) -> None:
        log, adr_dir = self._setup(tmp_path)
        outcome = adr_scaffold.scaffold(
            "Something very long",
            slug="short-name",
            clock=FIXED_CLOCK,
            decisions_log=log,
            adr_dir=adr_dir,
        )
        assert outcome.path.name == "0001-short-name.md"

    def test_refuses_overwrite_by_default(self, tmp_path: Path) -> None:
        log, adr_dir = self._setup(tmp_path)
        adr_scaffold.scaffold(
            "First",
            number=5,
            clock=FIXED_CLOCK,
            decisions_log=log,
            adr_dir=adr_dir,
        )
        with pytest.raises(FileExistsError):
            adr_scaffold.scaffold(
                "Second",
                number=5,
                slug="first",
                clock=FIXED_CLOCK,
                decisions_log=log,
                adr_dir=adr_dir,
            )

    def test_overwrite_flag_allows_replacement(self, tmp_path: Path) -> None:
        log, adr_dir = self._setup(tmp_path)
        adr_scaffold.scaffold(
            "First", number=5, slug="x", clock=FIXED_CLOCK,
            decisions_log=log, adr_dir=adr_dir,
        )
        outcome = adr_scaffold.scaffold(
            "Replaced",
            number=5,
            slug="x",
            clock=FIXED_CLOCK,
            decisions_log=log,
            adr_dir=adr_dir,
            overwrite=True,
        )
        body = outcome.path.read_text(encoding="utf-8")
        assert "ADR-0005: Replaced" in body

    def test_template_contains_required_fields(self, tmp_path: Path) -> None:
        log, adr_dir = self._setup(tmp_path)
        outcome = adr_scaffold.scaffold(
            "Some Decision",
            clock=FIXED_CLOCK,
            decisions_log=log,
            adr_dir=adr_dir,
        )
        body = outcome.path.read_text(encoding="utf-8")
        for field in (
            "**Status:**",
            "**Date:**",
            "**Context:**",
            "**Decision:**",
            "**Alternatives Rejected:**",
            "**Consequences:**",
            "**Lens Notes:**",
            "ADR-0001: Some Decision",
        ):
            assert field in body, f"missing {field!r}"

    def test_frontmatter_marks_manual_edits_allowed(self, tmp_path: Path) -> None:
        log, adr_dir = self._setup(tmp_path)
        outcome = adr_scaffold.scaffold(
            "x", clock=FIXED_CLOCK, decisions_log=log, adr_dir=adr_dir,
        )
        text = outcome.path.read_text(encoding="utf-8")
        assert "manual_edits_allowed: true" in text

    def test_check_mode_does_not_write(self, tmp_path: Path) -> None:
        log, adr_dir = self._setup(tmp_path)
        outcome = adr_scaffold.scaffold(
            "Check Me",
            clock=FIXED_CLOCK,
            decisions_log=log,
            adr_dir=adr_dir,
            mode=WriteMode.CHECK,
        )
        assert outcome.result is not None
        assert outcome.result.value == "missing"
        assert not outcome.path.exists()

    def test_blank_title_rejected(self, tmp_path: Path) -> None:
        log, adr_dir = self._setup(tmp_path)
        with pytest.raises(ValueError):
            adr_scaffold.scaffold(
                "    ",
                clock=FIXED_CLOCK,
                decisions_log=log,
                adr_dir=adr_dir,
            )


# --------------------------------------------------------------------------- #
# Orchestrator integration
# --------------------------------------------------------------------------- #


class TestOrchestratorIntegration:
    def test_run_is_a_noop(self) -> None:
        # T-G-007 is on-demand; the orchestrator entry-point returns no work.
        result = adr_scaffold.run(mode=WriteMode.WRITE, clock=FIXED_CLOCK)
        assert result == []
