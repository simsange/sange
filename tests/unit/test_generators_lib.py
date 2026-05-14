"""Smoke tests for the tools/generators/_lib/ shared helpers.

These guard the determinism contract every catalog appendix depends on:

  * `fingerprint` round-trips bytes ↔ sha256 ↔ extract_body cleanly.
  * `output.assemble` produces stable output_sha256 for stable inputs.
  * `output.write_generated_file` writes atomically and check-mode catches drift.
  * `markdown.table` escapes pipes + newlines; renders deterministic rows.
  * `manpage.parse_git_help_all` recovers commands + sections from fixtures.

The tests intentionally do NOT depend on `git` / `svn` / `hg` being installed —
the parsers consume text, and the text is fed from inline fixtures here.

`tests/unit/` lives outside `src/sange/` so the tests can exercise the
`tools/generators/_lib/` package without bundling it into the wheel.
"""

from __future__ import annotations

import datetime as _dt
import sys
from pathlib import Path

import pytest

# Make `tools/generators/_lib` importable when tests are run from the repo root.
REPO_ROOT = Path(__file__).resolve().parents[2]
GENERATORS_DIR = REPO_ROOT / "tools" / "generators"
if str(GENERATORS_DIR) not in sys.path:
    sys.path.insert(0, str(GENERATORS_DIR))

from _lib import fingerprint, manpage, markdown  # noqa: E402
from _lib.output import (  # noqa: E402
    GeneratorMetadata,
    VerificationResult,
    WriteMode,
    assemble,
    render_frontmatter,
    write_generated_file,
)


# --------------------------------------------------------------------------- #
# fingerprint
# --------------------------------------------------------------------------- #


class TestFingerprint:
    def test_canonical_bytes_strips_crlf(self) -> None:
        assert fingerprint.canonical_bytes("a\r\nb\r\nc") == b"a\nb\nc"

    def test_canonical_bytes_strips_bare_cr(self) -> None:
        assert fingerprint.canonical_bytes("a\rb\rc") == b"a\nb\nc"

    def test_sha256_text_is_lower_hex(self) -> None:
        digest = fingerprint.sha256_text("hello world\n")
        assert len(digest) == 64
        assert digest == digest.lower()
        assert all(c in "0123456789abcdef" for c in digest)

    def test_sha256_text_is_normalized(self) -> None:
        # Same content, different line endings → same hash.
        a = fingerprint.sha256_text("line1\nline2\n")
        b = fingerprint.sha256_text("line1\r\nline2\r\n")
        c = fingerprint.sha256_text("line1\rline2\r")
        assert a == b == c

    def test_extract_body_no_frontmatter(self) -> None:
        front, body = fingerprint.extract_body("# title\n\ncontent")
        assert front == ""
        assert body == "# title\n\ncontent"

    def test_extract_body_with_frontmatter(self) -> None:
        text = "---\nfoo: bar\nbaz: 1\n---\n\nbody line\n"
        front, body = fingerprint.extract_body(text)
        assert front.startswith("---\n")
        assert front.rstrip().endswith("---")
        assert "foo: bar" in front
        assert body == "body line\n"

    def test_extract_body_no_closing_delimiter(self) -> None:
        text = "---\nfoo: bar\nno closing fence ever\n"
        front, body = fingerprint.extract_body(text)
        # Defensive — without a closing fence we treat the whole content as body.
        assert front == ""

    def test_body_sha256_matches_manual_hash(self) -> None:
        text = "---\nfoo: 1\n---\n\nhello\n"
        _, body = fingerprint.extract_body(text)
        assert fingerprint.body_sha256(text) == fingerprint.sha256_text(body)


# --------------------------------------------------------------------------- #
# output.assemble + write_generated_file
# --------------------------------------------------------------------------- #


def _meta(input_sha: str = "deadbeef") -> GeneratorMetadata:
    return GeneratorMetadata(
        generated_by="tools/generators/example.py",
        generator_version="1.2.3",
        input_sha256=input_sha,
        manual_edits_allowed=False,
        generated_at=_dt.datetime(2026, 1, 2, 3, 4, 5, tzinfo=_dt.timezone.utc),
    )


class TestRenderFrontmatter:
    def test_keys_in_canonical_order(self) -> None:
        text = render_frontmatter(_meta(), output_sha256="cafe")
        # Keys appear in the exact order documented in §16.4.1.
        order = [
            "generated_by",
            "generator_version",
            "generated_at",
            "input_sha256",
            "output_sha256",
            "manual_edits_allowed",
        ]
        idx = 0
        for line in text.splitlines():
            if idx < len(order) and line.startswith(order[idx] + ":"):
                idx += 1
        assert idx == len(order), text

    def test_timestamp_is_iso8601_z(self) -> None:
        text = render_frontmatter(_meta(), "cafe")
        assert "generated_at: 2026-01-02T03:04:05Z" in text


class TestAssemble:
    def test_deterministic_output_sha(self) -> None:
        a_text, a_sha = assemble(_meta(), "hello\n")
        b_text, b_sha = assemble(_meta(), "hello\n")
        assert a_text == b_text
        assert a_sha == b_sha

    def test_output_sha_changes_when_body_changes(self) -> None:
        _, a_sha = assemble(_meta(), "hello\n")
        _, b_sha = assemble(_meta(), "hello!\n")
        assert a_sha != b_sha

    def test_body_normalized_to_lf(self) -> None:
        a, _ = assemble(_meta(), "hello\r\nworld\r\n")
        b, _ = assemble(_meta(), "hello\nworld\n")
        assert a == b


class TestWriteGeneratedFile:
    def test_writes_then_checks_match(self, tmp_path: Path) -> None:
        path = tmp_path / "out.md"
        outcome = write_generated_file(path, "body!\n", _meta(), mode=WriteMode.WRITE)
        assert path.exists()
        check = write_generated_file(path, "body!\n", _meta(), mode=WriteMode.CHECK)
        assert check.result is VerificationResult.MATCH
        assert outcome.output_sha256 == check.output_sha256

    def test_check_detects_body_drift(self, tmp_path: Path) -> None:
        path = tmp_path / "out.md"
        write_generated_file(path, "body!\n", _meta(), mode=WriteMode.WRITE)
        # Manually tamper with the body.
        text = path.read_text(encoding="utf-8")
        path.write_text(text.replace("body!", "TAMPERED"), encoding="utf-8")
        check = write_generated_file(path, "body!\n", _meta(), mode=WriteMode.CHECK)
        assert check.result is VerificationResult.MISMATCH

    def test_check_detects_missing(self, tmp_path: Path) -> None:
        path = tmp_path / "nope.md"
        check = write_generated_file(path, "body\n", _meta(), mode=WriteMode.CHECK)
        assert check.result is VerificationResult.MISSING

    def test_check_matches_across_different_clocks(self, tmp_path: Path) -> None:
        """The clock only affects the frontmatter's `generated_at` field.

        Two runs with different clocks but the same body should still match
        in CHECK mode — otherwise every re-run would be flagged stale and the
        verifier would be useless. Regression test for S-002-T-24.
        """
        import datetime as _dt

        path = tmp_path / "out.md"
        meta_a = GeneratorMetadata(
            generated_by="x",
            generator_version="1",
            input_sha256="abc",
            manual_edits_allowed=False,
            generated_at=_dt.datetime(2026, 1, 1, tzinfo=_dt.timezone.utc),
        )
        meta_b = GeneratorMetadata(
            generated_by="x",
            generator_version="1",
            input_sha256="abc",
            manual_edits_allowed=False,
            generated_at=_dt.datetime(2026, 6, 30, tzinfo=_dt.timezone.utc),
        )
        write_generated_file(path, "Stable body!\n", meta_a, mode=WriteMode.WRITE)
        check = write_generated_file(path, "Stable body!\n", meta_b, mode=WriteMode.CHECK)
        assert check.result is VerificationResult.MATCH


# --------------------------------------------------------------------------- #
# markdown
# --------------------------------------------------------------------------- #


class TestMarkdown:
    def test_slugify(self) -> None:
        assert markdown.slugify("Hello, World!") == "hello-world"
        assert markdown.slugify("§6.5 The Profile Registry") == "65-the-profile-registry"
        assert markdown.slugify("   leading-and-trailing   ") == "leading-and-trailing"

    def test_escape_cell_pipe(self) -> None:
        assert markdown.escape_cell("a|b") == "a\\|b"

    def test_escape_cell_newline(self) -> None:
        assert markdown.escape_cell("a\nb") == "a<br>b"

    def test_escape_cell_none(self) -> None:
        assert markdown.escape_cell(None) == ""

    def test_table_rejects_row_length_mismatch(self) -> None:
        with pytest.raises(ValueError):
            markdown.table(["a", "b"], [["only one"]])

    def test_table_renders_alignment_markers(self) -> None:
        out = markdown.table(
            ["a", "b"],
            [["1", "2"]],
            alignments=["left", "right"],
        )
        assert "| :--- | ---: |" in out

    def test_table_basic_round_trip(self) -> None:
        out = markdown.table(
            ["Name", "Note"],
            [["foo", "bar"], ["baz|x", "y\nz"]],
        )
        # Header + separator + 2 rows + trailing newline = 4 + trailing \n.
        lines = out.rstrip("\n").splitlines()
        assert len(lines) == 4
        assert "baz\\|x" in lines[3]
        assert "y<br>z" in lines[3]

    def test_code_block_escapes_internal_fence(self) -> None:
        content = "outer\n```\ninner triple backticks\n```\nouter"
        block = markdown.code_block(content, lang="text")
        assert block.startswith("````text\n")
        assert block.endswith("````\n")

    def test_heading_with_anchor(self) -> None:
        out = markdown.heading(2, "Hello", anchor="hello-anchor")
        assert 'id="hello-anchor"' in out
        assert "## Hello" in out

    def test_heading_rejects_invalid_level(self) -> None:
        with pytest.raises(ValueError):
            markdown.heading(0, "x")
        with pytest.raises(ValueError):
            markdown.heading(7, "x")


# --------------------------------------------------------------------------- #
# manpage
# --------------------------------------------------------------------------- #


GIT_HELP_FIXTURE = """\
See 'git help <command>' to read about a specific subcommand

Main Porcelain Commands
   add                Add file contents to the index
   am                 Apply a series of patches from a mailbox
   commit             Record changes to the repository

Ancillary Commands / Manipulators
   config             Get and set repository or global options
   fsck               Verifies the connectivity and validity of objects
"""

SVN_HELP_FIXTURE = """\
usage: svn <subcommand> [options] [args]

Most subcommands take file and/or directory arguments, recursing
on the directories.

Available subcommands:
   add
   blame (praise, annotate, ann)  Output the content of specified files or
                                  URLs with revision and author info.
   cat                            Output the content of specified files or URLs.
   commit (ci)                    Send changes from your working copy to the repository.
"""

HG_HELP_FIXTURE = """\
Mercurial Distributed SCM

list of commands:

 Repository creation:

 init           create a new repository in the given directory
 clone          make a copy of an existing repository

 Working directory management:

 add            add the specified files on the next commit
 commit         commit the specified files or all outstanding changes
"""


class TestParseGitHelpAll:
    def test_extracts_commands(self) -> None:
        result = manpage.parse_git_help_all(GIT_HELP_FIXTURE)
        names = {c.name for c in result.commands}
        assert {"add", "am", "commit", "config", "fsck"}.issubset(names)

    def test_tracks_section(self) -> None:
        result = manpage.parse_git_help_all(GIT_HELP_FIXTURE)
        sections = {c.section for c in result.commands}
        assert "Main Porcelain Commands" in sections
        assert "Ancillary Commands / Manipulators" in sections

    def test_descriptions_captured(self) -> None:
        result = manpage.parse_git_help_all(GIT_HELP_FIXTURE)
        by_name = {c.name: c.short_description for c in result.commands}
        assert by_name["commit"] == "Record changes to the repository"

    def test_unclassified_empty_on_clean_fixture(self) -> None:
        result = manpage.parse_git_help_all(GIT_HELP_FIXTURE)
        assert result.unclassified == ()


class TestParseSvnHelp:
    def test_extracts_subcommands(self) -> None:
        result = manpage.parse_svn_help(SVN_HELP_FIXTURE)
        # "add" lives on its own line (no description in this fixture), so the
        # parser drops it — that's fine; the catalog can add a description from
        # `svn help add` later.
        names = {c.name for c in result.commands}
        assert {"blame", "cat", "commit"}.issubset(names)

    def test_aliases_become_extra_entries(self) -> None:
        result = manpage.parse_svn_help(SVN_HELP_FIXTURE)
        names = {c.name for c in result.commands}
        # blame's aliases: praise, annotate, ann
        assert {"praise", "annotate", "ann", "ci"}.issubset(names)


class TestParseHgHelp:
    def test_extracts_commands(self) -> None:
        result = manpage.parse_hg_help(HG_HELP_FIXTURE)
        names = {c.name for c in result.commands}
        assert {"init", "clone", "add", "commit"}.issubset(names)


class TestExtractSynopsis:
    def test_returns_block_until_next_section(self) -> None:
        man = (
            "NAME\n   git-foo - do a thing\n\n"
            "SYNOPSIS\n   git foo [--bar]\n   git foo --baz <arg>\n\n"
            "DESCRIPTION\n   The foo command does ...\n"
        )
        synopsis = manpage.extract_synopsis(man)
        assert "git foo [--bar]" in synopsis
        assert "DESCRIPTION" not in synopsis

    def test_empty_when_no_synopsis(self) -> None:
        man = "NAME\n   git-foo - do a thing\n"
        assert manpage.extract_synopsis(man) == ""
