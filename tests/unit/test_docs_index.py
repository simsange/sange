"""Tests for T-G-006 — `tools/generators/docs_index.py`.

Asserts:
  * Walk extracts H1 headings (skipping §16.4.1 frontmatter).
  * Files are grouped by top-level subdirectory.
  * Section ordering follows SECTION_ORDER then alphabetical fallback.
  * Hidden + skip-named files excluded.
  * Both indexes (main + tools) emit with §16.4.1 frontmatter.
  * Byte-identical re-run.
  * Empty docs/tools/ produces a graceful placeholder.
"""

from __future__ import annotations

import datetime as _dt
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
GENERATORS_DIR = REPO_ROOT / "tools" / "generators"
if str(GENERATORS_DIR) not in sys.path:
    sys.path.insert(0, str(GENERATORS_DIR))

import docs_index  # noqa: E402

from _lib.output import WriteMode  # noqa: E402


FIXED_CLOCK = _dt.datetime(2026, 5, 14, 22, 0, 0, tzinfo=_dt.timezone.utc)


@pytest.fixture
def staged_docs(tmp_path: Path) -> tuple[Path, Path, Path]:
    docs = tmp_path / "docs"
    (docs / "reference").mkdir(parents=True)
    (docs / "security").mkdir()
    (docs / "adr").mkdir()
    (docs / "tools" / "vcs").mkdir(parents=True)

    # Frontmatter'd file (heading is AFTER the frontmatter block)
    (docs / "reference" / "exit-codes.md").write_text(
        "---\n"
        "generated_by: tools/generators/exit_codes.py\n"
        "generator_version: 1.0.0\n"
        "generated_at: 2026-05-14T06:30:00Z\n"
        "input_sha256: abc\n"
        "output_sha256: def\n"
        "manual_edits_allowed: false\n"
        "---\n"
        "# Sange exit codes\n\n"
        "Body content here.\n",
        encoding="utf-8",
    )
    # Plain markdown — heading is at the top
    (docs / "security" / "threat-model.md").write_text(
        "# STRIDE threat model\n\nMore content.\n",
        encoding="utf-8",
    )
    # File with no heading — should fall back to title-cased filename
    (docs / "adr" / "0032-variant-matrix.md").write_text(
        "Just body, no heading.\n", encoding="utf-8",
    )
    # tools/vcs/git.md
    (docs / "tools" / "vcs" / "git.md").write_text(
        "# Git tool walkthrough\n", encoding="utf-8",
    )
    # Hidden + skip-named files (must NOT be indexed)
    (docs / ".DS_Store").write_bytes(b"\x00")
    (docs / "README.md").write_text("# old index\n", encoding="utf-8")

    return docs, tmp_path / "main-README.md", tmp_path / "tools-README.md"


# --------------------------------------------------------------------------- #
# Walk / heading extraction
# --------------------------------------------------------------------------- #


class TestWalkAndExtract:
    def test_skip_named_readme_excluded(self, staged_docs: tuple[Path, Path, Path]) -> None:
        docs, _, _ = staged_docs
        files = docs_index.walk_docs(docs)
        names = {f.relative_path for f in files}
        assert "README.md" not in names

    def test_hidden_files_excluded(self, staged_docs: tuple[Path, Path, Path]) -> None:
        docs, _, _ = staged_docs
        files = docs_index.walk_docs(docs)
        names = {f.relative_path for f in files}
        assert ".DS_Store" not in names

    def test_heading_extracted_skipping_frontmatter(self, staged_docs: tuple[Path, Path, Path]) -> None:
        docs, _, _ = staged_docs
        files = docs_index.walk_docs(docs)
        by_path = {f.relative_path: f for f in files}
        assert by_path["reference/exit-codes.md"].heading == "Sange exit codes"

    def test_heading_extracted_plain_markdown(self, staged_docs: tuple[Path, Path, Path]) -> None:
        docs, _, _ = staged_docs
        files = docs_index.walk_docs(docs)
        by_path = {f.relative_path: f for f in files}
        assert by_path["security/threat-model.md"].heading == "STRIDE threat model"

    def test_heading_fallback_when_missing(self, staged_docs: tuple[Path, Path, Path]) -> None:
        docs, _, _ = staged_docs
        files = docs_index.walk_docs(docs)
        by_path = {f.relative_path: f for f in files}
        # Filename "0032-variant-matrix.md" → "0032 Variant Matrix" (title-case).
        assert "Variant Matrix" in by_path["adr/0032-variant-matrix.md"].heading

    def test_section_classification(self, staged_docs: tuple[Path, Path, Path]) -> None:
        docs, _, _ = staged_docs
        files = docs_index.walk_docs(docs)
        by_path = {f.relative_path: f for f in files}
        assert by_path["reference/exit-codes.md"].section == "reference"
        assert by_path["security/threat-model.md"].section == "security"
        assert by_path["adr/0032-variant-matrix.md"].section == "adr"
        assert by_path["tools/vcs/git.md"].section == "tools"


# --------------------------------------------------------------------------- #
# Index rendering
# --------------------------------------------------------------------------- #


class TestIndexRendering:
    def test_main_index_has_frontmatter(self, staged_docs: tuple[Path, Path, Path]) -> None:
        docs, main, tools = staged_docs
        docs_index.run(
            mode=WriteMode.WRITE, clock=FIXED_CLOCK,
            docs_dir=docs, main_index_path=main, tools_index_path=tools,
        )
        body = main.read_text(encoding="utf-8")
        assert body.startswith("---\n")
        assert "generated_by: tools/generators/docs_index.py" in body

    def test_tools_index_has_frontmatter(self, staged_docs: tuple[Path, Path, Path]) -> None:
        docs, main, tools = staged_docs
        docs_index.run(
            mode=WriteMode.WRITE, clock=FIXED_CLOCK,
            docs_dir=docs, main_index_path=main, tools_index_path=tools,
        )
        body = tools.read_text(encoding="utf-8")
        assert body.startswith("---\n")

    def test_main_index_links_to_every_doc(self, staged_docs: tuple[Path, Path, Path]) -> None:
        docs, main, tools = staged_docs
        docs_index.run(
            mode=WriteMode.WRITE, clock=FIXED_CLOCK,
            docs_dir=docs, main_index_path=main, tools_index_path=tools,
        )
        body = main.read_text(encoding="utf-8")
        for path in (
            "reference/exit-codes.md",
            "security/threat-model.md",
            "adr/0032-variant-matrix.md",
            "tools/vcs/git.md",
        ):
            assert path in body, f"main index missing link to {path}"

    def test_main_index_omits_skip_files(self, staged_docs: tuple[Path, Path, Path]) -> None:
        docs, main, tools = staged_docs
        docs_index.run(
            mode=WriteMode.WRITE, clock=FIXED_CLOCK,
            docs_dir=docs, main_index_path=main, tools_index_path=tools,
        )
        body = main.read_text(encoding="utf-8")
        assert ".DS_Store" not in body

    def test_section_ordering_canonical_first(self, staged_docs: tuple[Path, Path, Path]) -> None:
        docs, main, tools = staged_docs
        docs_index.run(
            mode=WriteMode.WRITE, clock=FIXED_CLOCK,
            docs_dir=docs, main_index_path=main, tools_index_path=tools,
        )
        body = main.read_text(encoding="utf-8")
        # tools appears before reference; reference before security; security
        # before adr (per SECTION_ORDER).
        tools_idx = body.index("`tools/` ")
        ref_idx = body.index("`reference/` ")
        sec_idx = body.index("`security/` ")
        adr_idx = body.index("`adr/` ")
        assert tools_idx < ref_idx < sec_idx < adr_idx

    def test_tools_index_lists_subcategory_files(self, staged_docs: tuple[Path, Path, Path]) -> None:
        docs, main, tools = staged_docs
        docs_index.run(
            mode=WriteMode.WRITE, clock=FIXED_CLOCK,
            docs_dir=docs, main_index_path=main, tools_index_path=tools,
        )
        body = tools.read_text(encoding="utf-8")
        assert "Git tool walkthrough" in body
        assert "tools/vcs/git.md" in body or "../tools/vcs/git.md" in body

    def test_empty_tools_section_emits_placeholder(self, tmp_path: Path) -> None:
        docs = tmp_path / "docs"
        docs.mkdir()
        (docs / "reference").mkdir()
        (docs / "reference" / "foo.md").write_text("# Foo\n", encoding="utf-8")
        main = tmp_path / "main.md"
        tools = tmp_path / "tools.md"
        docs_index.run(
            mode=WriteMode.WRITE, clock=FIXED_CLOCK,
            docs_dir=docs, main_index_path=main, tools_index_path=tools,
        )
        body = tools.read_text(encoding="utf-8")
        assert "No per-tool walkthroughs" in body

    def test_byte_identical_rerun(self, staged_docs: tuple[Path, Path, Path]) -> None:
        docs, main, tools = staged_docs
        docs_index.run(
            mode=WriteMode.WRITE, clock=FIXED_CLOCK,
            docs_dir=docs, main_index_path=main, tools_index_path=tools,
        )
        first_main = main.read_bytes()
        first_tools = tools.read_bytes()
        docs_index.run(
            mode=WriteMode.WRITE, clock=FIXED_CLOCK,
            docs_dir=docs, main_index_path=main, tools_index_path=tools,
        )
        assert main.read_bytes() == first_main
        assert tools.read_bytes() == first_tools

    def test_check_mode_match(self, staged_docs: tuple[Path, Path, Path]) -> None:
        docs, main, tools = staged_docs
        docs_index.run(
            mode=WriteMode.WRITE, clock=FIXED_CLOCK,
            docs_dir=docs, main_index_path=main, tools_index_path=tools,
        )
        outcomes = docs_index.run(
            mode=WriteMode.CHECK, clock=FIXED_CLOCK,
            docs_dir=docs, main_index_path=main, tools_index_path=tools,
        )
        for outcome in outcomes:
            assert outcome.result is not None
            assert outcome.result.value == "match"
