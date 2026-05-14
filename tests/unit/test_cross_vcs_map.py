"""Tests for T-G-003 — `tools/generators/cross_vcs_map.py`."""

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

import cross_vcs_map  # noqa: E402

from _lib.output import WriteMode  # noqa: E402


FIXED_CLOCK = _dt.datetime(2026, 5, 15, 2, 0, 0, tzinfo=_dt.timezone.utc)


# --------------------------------------------------------------------------- #
# Concept inventory invariants
# --------------------------------------------------------------------------- #


class TestConceptInventory:
    def test_concept_ids_unique(self) -> None:
        ids = [c.id for c in cross_vcs_map.CONCEPTS]
        assert len(ids) == len(set(ids))

    def test_concept_ids_are_c_nnn(self) -> None:
        pattern = re.compile(r"^C-\d{3}$")
        offenders = [c.id for c in cross_vcs_map.CONCEPTS if not pattern.match(c.id)]
        assert not offenders, f"non-C-NNN ids: {offenders}"

    def test_v1_columns_always_populated(self) -> None:
        """Git + SVN + Hg are mandatory per §9.3."""

        offenders: list[str] = []
        for c in cross_vcs_map.CONCEPTS:
            for col_name, value in (("git", c.git), ("svn", c.svn), ("hg", c.hg)):
                if not value.strip():
                    offenders.append(f"{c.id}.{col_name} is empty")
        assert not offenders, ", ".join(offenders)

    def test_at_least_25_concepts(self) -> None:
        # §9.3 doesn't pin a minimum, but the §6.2 Domain layer + §6.11 purge
        # subsystem both rely on ≥25 concepts being mapped.
        assert len(cross_vcs_map.CONCEPTS) >= 25

    def test_purge_concept_present(self) -> None:
        """§6.11 cross-VCS purge requires C-090 (history rewrite) to be mapped."""

        purge = next(
            (c for c in cross_vcs_map.CONCEPTS if c.id == "C-090"), None
        )
        assert purge is not None, "C-090 (history rewrite) missing from concept catalog"
        assert "PurgePlan" in purge.sange_domain

    def test_sange_native_concepts_marked(self) -> None:
        """Concepts like 'Variant' that have no direct VCS equivalent should
        be marked as Sange-native."""

        natives = [
            c for c in cross_vcs_map.CONCEPTS
            if "Sange-native" in c.notes
        ]
        assert natives, "no Sange-native concepts marked"


# --------------------------------------------------------------------------- #
# Generator end-to-end
# --------------------------------------------------------------------------- #


class TestGeneratorEndToEnd:
    def test_produces_file_with_frontmatter(self, tmp_path: Path) -> None:
        target = tmp_path / "appendix-f.md"
        cross_vcs_map.run(mode=WriteMode.WRITE, clock=FIXED_CLOCK, output_path=target)
        body = target.read_text(encoding="utf-8")
        assert body.startswith("---\n")
        assert "generated_by: tools/generators/cross_vcs_map.py" in body

    def test_body_contains_every_concept(self, tmp_path: Path) -> None:
        target = tmp_path / "appendix-f.md"
        cross_vcs_map.run(mode=WriteMode.WRITE, clock=FIXED_CLOCK, output_path=target)
        body = target.read_text(encoding="utf-8")
        for c in cross_vcs_map.CONCEPTS:
            assert c.id in body, f"missing {c.id} in output"
            assert c.concept in body, f"missing concept {c.concept!r}"

    def test_byte_identical_rerun(self, tmp_path: Path) -> None:
        target = tmp_path / "appendix-f.md"
        cross_vcs_map.run(mode=WriteMode.WRITE, clock=FIXED_CLOCK, output_path=target)
        first = target.read_bytes()
        cross_vcs_map.run(mode=WriteMode.WRITE, clock=FIXED_CLOCK, output_path=target)
        assert target.read_bytes() == first

    def test_check_mode_match(self, tmp_path: Path) -> None:
        target = tmp_path / "appendix-f.md"
        cross_vcs_map.run(mode=WriteMode.WRITE, clock=FIXED_CLOCK, output_path=target)
        outcomes = cross_vcs_map.run(
            mode=WriteMode.CHECK, clock=FIXED_CLOCK, output_path=target
        )
        assert outcomes[0].result is not None
        assert outcomes[0].result.value == "match"
