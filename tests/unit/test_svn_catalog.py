"""Tests for T-G-002 — `tools/generators/svn_catalog.py`."""

from __future__ import annotations

import datetime as _dt
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
GENERATORS_DIR = REPO_ROOT / "tools" / "generators"
if str(GENERATORS_DIR) not in sys.path:
    sys.path.insert(0, str(GENERATORS_DIR))

import svn_catalog  # noqa: E402

from _lib.fingerprint import body_sha256  # noqa: E402
from _lib.output import WriteMode  # noqa: E402


FIXED_CLOCK = _dt.datetime(2026, 5, 15, 0, 0, 0, tzinfo=_dt.timezone.utc)
SVN_VERSION_FIXTURE = "svn, version 1.14.3"

SVN_HELP_FIXTURE = """\
usage: svn <subcommand> [options] [args]

Available subcommands:
   add
   blame (praise, annotate, ann)  Output the content with revision info.
   cat                            Output the content of specified files.
   checkout (co)                  Check out a working copy.
   commit (ci)                    Send changes from your working copy.
   diff (di)                      Display differences between two paths.
   log                            Show log messages for revisions.
   merge                          Apply differences between two sources.
   status (stat, st)              Print status of working copy files.
   update (up)                    Bring changes from repo into working copy.
"""

SVNADMIN_HELP_FIXTURE = """\
General usage: svnadmin SUBCOMMAND REPOS_PATH

Available subcommands:
   create        Create a new empty repository.
   dump          Dump the contents of filesystem.
   load          Read a dumpfile stream.
   verify        Verify the data stored in the repository.
"""


# --------------------------------------------------------------------------- #
# Enrichment inventory
# --------------------------------------------------------------------------- #


REQUIRED_SVN_COMMANDS = {
    # §9.0.3 floor (svn binary)
    "checkout", "update", "commit", "add", "delete", "copy", "move", "revert",
    "diff", "status", "log", "info", "blame", "cat", "list", "merge",
    "mergeinfo", "switch", "relocate", "resolve", "resolved", "cleanup",
    "lock", "unlock", "propset", "propget", "proplist", "propedit", "propdel",
    "import", "export", "mkdir", "changelist", "upgrade", "patch",
}

REQUIRED_SVNADMIN_COMMANDS = {"dump", "load", "create", "hotcopy", "verify"}
REQUIRED_SVNDUMPFILTER_COMMANDS = {"exclude", "include"}
REQUIRED_SVNSYNC_COMMANDS = {"init", "sync"}
REQUIRED_SVNLOOK_COMMANDS = {"tree", "log"}


class TestEnrichmentInventory:
    def test_every_required_svn_command_enriched(self) -> None:
        enriched = {r.name for r in svn_catalog.ENRICHMENT if r.binary == "svn"}
        missing = REQUIRED_SVN_COMMANDS - enriched
        assert not missing, f"svn missing: {sorted(missing)}"

    def test_every_required_svnadmin_command_enriched(self) -> None:
        enriched = {r.name for r in svn_catalog.ENRICHMENT if r.binary == "svnadmin"}
        missing = REQUIRED_SVNADMIN_COMMANDS - enriched
        assert not missing, f"svnadmin missing: {sorted(missing)}"

    def test_every_required_svndumpfilter_command_enriched(self) -> None:
        enriched = {r.name for r in svn_catalog.ENRICHMENT if r.binary == "svndumpfilter"}
        missing = REQUIRED_SVNDUMPFILTER_COMMANDS - enriched
        assert not missing, f"svndumpfilter missing: {sorted(missing)}"

    def test_every_required_svnsync_command_enriched(self) -> None:
        enriched = {r.name for r in svn_catalog.ENRICHMENT if r.binary == "svnsync"}
        missing = REQUIRED_SVNSYNC_COMMANDS - enriched
        assert not missing, f"svnsync missing: {sorted(missing)}"

    def test_every_required_svnlook_command_enriched(self) -> None:
        enriched = {r.name for r in svn_catalog.ENRICHMENT if r.binary == "svnlook"}
        missing = REQUIRED_SVNLOOK_COMMANDS - enriched
        assert not missing, f"svnlook missing: {sorted(missing)}"


# --------------------------------------------------------------------------- #
# Safety / confirmation invariant
# --------------------------------------------------------------------------- #


class TestSafetyConfirmationInvariant:
    def test_destructive_rows_have_gates(self) -> None:
        offenders: list[str] = []
        for row in svn_catalog.ENRICHMENT:
            if row.safety_class in {"Destructive", "Catastrophic"} and row.confirmation_gate == "None":
                offenders.append(f"{row.binary} {row.name} ({row.safety_class})")
        assert not offenders, (
            "These rows violate §9.0 Red-Team #2 (Destructive/Catastrophic must gate): "
            + ", ".join(offenders)
        )

    def test_load_and_filter_exclude_are_catastrophic(self) -> None:
        load = next(
            r for r in svn_catalog.ENRICHMENT
            if r.binary == "svnadmin" and r.name == "load"
        )
        filter_exclude = next(
            r for r in svn_catalog.ENRICHMENT
            if r.binary == "svndumpfilter" and r.name == "exclude"
        )
        assert load.safety_class == "Catastrophic"
        assert filter_exclude.safety_class == "Catastrophic"
        assert "purge" in load.sange_wrapper.lower()
        assert "purge" in filter_exclude.sange_wrapper.lower()


# --------------------------------------------------------------------------- #
# Live-help parsers
# --------------------------------------------------------------------------- #


class TestParseSvnadminHelp:
    def test_extracts_commands(self) -> None:
        out = svn_catalog.parse_svnadmin_help(SVNADMIN_HELP_FIXTURE)
        names = {c.name for c in out}
        assert {"create", "dump", "load", "verify"}.issubset(names)


# --------------------------------------------------------------------------- #
# Generator end-to-end
# --------------------------------------------------------------------------- #


class TestGeneratorEndToEnd:
    def test_produces_file_with_frontmatter(self, tmp_path: Path) -> None:
        target = tmp_path / "appendix-e.md"
        svn_catalog.run(
            mode=WriteMode.WRITE, clock=FIXED_CLOCK,
            svn_help_text=SVN_HELP_FIXTURE,
            svnadmin_help_text=SVNADMIN_HELP_FIXTURE,
            svn_version_text=SVN_VERSION_FIXTURE,
            output_path=target,
        )
        body = target.read_text(encoding="utf-8")
        assert body.startswith("---\n")
        assert "generated_by: tools/generators/svn_catalog.py" in body

    def test_body_contains_every_required_command(self, tmp_path: Path) -> None:
        target = tmp_path / "appendix-e.md"
        svn_catalog.run(
            mode=WriteMode.WRITE, clock=FIXED_CLOCK,
            svn_help_text=SVN_HELP_FIXTURE,
            svnadmin_help_text=SVNADMIN_HELP_FIXTURE,
            svn_version_text=SVN_VERSION_FIXTURE,
            output_path=target,
        )
        body = target.read_text(encoding="utf-8")
        for command in REQUIRED_SVN_COMMANDS:
            assert f"`svn {command}`" in body, f"missing svn {command}"
        for command in REQUIRED_SVNADMIN_COMMANDS:
            assert f"`svnadmin {command}`" in body, f"missing svnadmin {command}"

    def test_byte_identical_rerun(self, tmp_path: Path) -> None:
        target = tmp_path / "appendix-e.md"
        kw = dict(
            mode=WriteMode.WRITE, clock=FIXED_CLOCK,
            svn_help_text=SVN_HELP_FIXTURE,
            svnadmin_help_text=SVNADMIN_HELP_FIXTURE,
            svn_version_text=SVN_VERSION_FIXTURE,
            output_path=target,
        )
        svn_catalog.run(**kw)
        first = target.read_bytes()
        svn_catalog.run(**kw)
        assert target.read_bytes() == first

    def test_check_mode_match(self, tmp_path: Path) -> None:
        target = tmp_path / "appendix-e.md"
        kw_write = dict(
            mode=WriteMode.WRITE, clock=FIXED_CLOCK,
            svn_help_text=SVN_HELP_FIXTURE,
            svnadmin_help_text=SVNADMIN_HELP_FIXTURE,
            svn_version_text=SVN_VERSION_FIXTURE,
            output_path=target,
        )
        kw_check = {**kw_write, "mode": WriteMode.CHECK}
        svn_catalog.run(**kw_write)
        outcomes = svn_catalog.run(**kw_check)
        assert outcomes[0].result is not None
        assert outcomes[0].result.value == "match"

    def test_body_sha_round_trip(self, tmp_path: Path) -> None:
        import re
        target = tmp_path / "appendix-e.md"
        svn_catalog.run(
            mode=WriteMode.WRITE, clock=FIXED_CLOCK,
            svn_help_text=SVN_HELP_FIXTURE,
            svnadmin_help_text=SVNADMIN_HELP_FIXTURE,
            svn_version_text=SVN_VERSION_FIXTURE,
            output_path=target,
        )
        text = target.read_text(encoding="utf-8")
        m = re.search(r"output_sha256: ([0-9a-f]{64})", text)
        assert m is not None
        assert m.group(1) == body_sha256(text)
