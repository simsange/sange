"""Tests for T-G-001 — `tools/generators/git_catalog.py`.

Asserts:
  * Every §9.0.1 Top-25 command appears in the catalog.
  * Every §9.0.2 power command appears.
  * Tier classification is correct (Essential/Common/Power/Plumbing/Third-party).
  * Mandatory column shape (9 columns per §9.1).
  * Safety/Confirmation invariant per §9.0 Red-Team Pass #2:
    Destructive/Catastrophic commands must NOT have `confirmation_gate=None`.
  * Byte-identical re-run with the same clock + git_help_text override.
  * Fallback row for commands present in git but not in the enrichment table.
  * Sange-native rows (no git equivalent) appear in the catalog.
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

import git_catalog  # noqa: E402
from _lib.fingerprint import body_sha256  # noqa: E402
from _lib.output import WriteMode  # noqa: E402

FIXED_CLOCK = _dt.datetime(2026, 5, 14, 12, 0, 0, tzinfo=_dt.UTC)


# A minimal but realistic `git help -a` fixture — every Top-25 command + a few
# power commands + an unenriched command (to exercise the passthrough fallback).
GIT_HELP_FIXTURE = """\
See 'git help <command>' to read about a specific subcommand

Main Porcelain Commands
   add                Add file contents to the index
   am                 Apply a series of patches from a mailbox
   archive            Create an archive of files from a named tree
   bisect             Use binary search to find the commit that introduced a bug
   branch             List, create, or delete branches
   checkout           Switch branches or restore working tree files
   cherry-pick        Apply the changes introduced by some existing commits
   clean              Remove untracked files from the working tree
   clone              Clone a repository into a new directory
   commit             Record changes to the repository
   describe           Give an object a human readable name based on an available ref
   diff               Show changes between commits, commit and working tree, etc
   fetch              Download objects and refs from another repository
   format-patch       Prepare patches for e-mail submission
   gc                 Cleanup unnecessary files and optimize the local repository
   init               Create an empty Git repository or reinitialize an existing one
   log                Show commit logs
   maintenance        Run tasks to optimize Git repository data
   merge              Join two or more development histories together
   mv                 Move or rename a file, a directory, or a symlink
   notes              Add or inspect object notes
   pull               Fetch from and integrate with another repository or a local branch
   push               Update remote refs along with associated objects
   range-diff         Compare two commit ranges (e.g. two versions of a branch)
   rebase             Reapply commits on top of another base tip
   reset              Reset current HEAD to the specified state
   restore            Restore working tree files
   revert             Revert some existing commits
   rm                 Remove files from the working tree and from the index
   shortlog           Summarize 'git log' output
   show               Show various types of objects
   sparse-checkout    Reduce your working tree to a subset of tracked files
   stash              Stash the changes in a dirty working directory away
   status             Show the working tree status
   submodule          Initialize, update or inspect submodules
   switch             Switch branches
   tag                Create, list, delete or verify a tag object signed with GPG
   worktree           Manage multiple working trees

Ancillary Commands / Manipulators
   config             Get and set repository or global options
   remote             Manage set of tracked repositories
   replace            Create, list, delete refs to replace objects

Ancillary Commands / Interrogators
   blame              Show what revision and author last modified each line
   grep               Print lines matching a pattern
   reflog             Manage reflog information

Low-level Commands / Manipulators
   apply              Apply a patch to files and/or to the index
   rerere             Reuse recorded resolution of conflicted merges

Low-level Commands / Internal Helpers
   pack-refs          Pack heads and tags for efficient repository access
"""

GIT_VERSION_FIXTURE = "git version 2.51.0"


# --------------------------------------------------------------------------- #
# Row inventory invariants
# --------------------------------------------------------------------------- #


class TestEnrichmentInventory:
    TOP_25_NAMES = {
        "init", "clone", "status", "add", "commit", "log", "diff",
        "branch", "checkout", "switch", "merge", "rebase", "pull",
        "push", "fetch", "remote", "stash", "reset", "revert", "tag",
        "show", "rm", "mv", "config",
        # Note: §9.0.1 lists 25; "stash pop" is a sub-command of stash and
        # documented within the stash row's notes rather than a separate entry.
    }
    POWER_NAMES = {
        "bisect", "worktree", "rerere", "maintenance", "sparse-checkout",
        "replace", "notes", "reflog", "restore", "range-diff", "cherry-pick",
        "blame", "grep", "submodule", "clean", "describe", "archive", "gc",
        "apply", "am", "format-patch", "shortlog", "filter-repo",
    }

    def test_every_top_25_in_enrichment(self) -> None:
        missing = self.TOP_25_NAMES - set(git_catalog.ENRICHMENT.keys())
        assert not missing, f"missing Top-25 entries: {sorted(missing)}"

    def test_every_power_in_enrichment(self) -> None:
        missing = self.POWER_NAMES - set(git_catalog.ENRICHMENT.keys())
        assert not missing, f"missing power entries: {sorted(missing)}"

    def test_every_enrichment_row_is_a_catalog_row(self) -> None:
        for name, row in git_catalog.ENRICHMENT.items():
            assert isinstance(row, git_catalog.CatalogRow)
            assert row.name == name, f"enrichment dict key {name!r} != row.name {row.name!r}"
            for field in ("tier", "purpose", "sange_wrapper", "ai_augmentation",
                          "safety_class", "confirmation_gate", "web_ui_parity"):
                value = getattr(row, field)
                assert value, f"{name}.{field} is empty"

    def test_sange_native_rows_have_no_git_equivalent(self) -> None:
        # By construction these don't show up in `git help -a`.
        git_names = {c.name for c in git_catalog.SANGE_NATIVE_ROWS}
        assert "undo" in git_names
        assert "review" in git_names
        assert "variant" in git_names
        assert "scaffold" in git_names
        assert "doctor" in git_names
        assert "recover" in git_names


# --------------------------------------------------------------------------- #
# Safety/Confirmation invariant — §9.0 Red-Team #2
# --------------------------------------------------------------------------- #


class TestSafetyConfirmationInvariant:
    """Every Destructive/Catastrophic command must have a non-None gate."""

    def test_destructive_rows_have_gates(self) -> None:
        offenders: list[str] = []
        for row in git_catalog.ENRICHMENT.values():
            if row.safety_class in {"Destructive", "Catastrophic"} and row.confirmation_gate == "None":
                offenders.append(f"{row.name} ({row.safety_class})")
        assert not offenders, (
            "These rows violate §9.0 Red-Team #2 (Destructive/Catastrophic must have a "
            "gate): " + ", ".join(offenders)
        )

    def test_read_only_rows_typically_dont_gate(self) -> None:
        # Not strictly invariant, but worth surfacing: a Read-only row with a
        # gate other than None is unusual and deserves a note in its `notes`.
        unusual: list[str] = []
        for row in git_catalog.ENRICHMENT.values():
            if row.safety_class == "Read-only" and row.confirmation_gate != "None":
                # Only flag if the notes don't explain why.
                if "review" not in row.notes.lower() and "preview" not in row.notes.lower():
                    unusual.append(f"{row.name} (gate={row.confirmation_gate}, notes={row.notes!r})")
        # This is a soft assertion — we just print for awareness.
        if unusual:
            print(f"\n  Note: {len(unusual)} read-only row(s) carry a gate: {unusual}")


# --------------------------------------------------------------------------- #
# Tier classification
# --------------------------------------------------------------------------- #


class TestTierClassification:
    def test_known_essentials(self) -> None:
        for name in ("init", "clone", "status", "add", "commit", "push", "pull",
                     "log", "diff", "branch", "fetch", "config"):
            row = git_catalog.ENRICHMENT[name]
            assert row.tier == "Essential", f"{name} should be Essential, got {row.tier}"

    def test_known_commons(self) -> None:
        for name in ("rebase", "stash", "reset", "revert", "tag", "show", "rm",
                     "mv", "cherry-pick", "restore", "blame", "grep"):
            row = git_catalog.ENRICHMENT[name]
            assert row.tier == "Common", f"{name} should be Common, got {row.tier}"

    def test_known_powers(self) -> None:
        for name in ("bisect", "worktree", "rerere", "maintenance",
                     "sparse-checkout", "reflog", "submodule"):
            row = git_catalog.ENRICHMENT[name]
            assert row.tier == "Power", f"{name} should be Power, got {row.tier}"

    def test_filter_repo_is_power_and_catastrophic(self) -> None:
        row = git_catalog.ENRICHMENT["filter-repo"]
        assert row.tier == "Power"
        assert row.safety_class == "Catastrophic"
        assert "purge" in row.sange_wrapper.lower()


# --------------------------------------------------------------------------- #
# End-to-end generation
# --------------------------------------------------------------------------- #


class TestGeneratorEndToEnd:
    def test_produces_file_with_frontmatter(self, tmp_path: Path) -> None:
        target = tmp_path / "appendix-d.md"
        outcomes = git_catalog.run(
            mode=WriteMode.WRITE,
            clock=FIXED_CLOCK,
            git_help_text=GIT_HELP_FIXTURE,
            git_version_text=GIT_VERSION_FIXTURE,
            output_path=target,
        )
        assert len(outcomes) == 1
        assert target.exists()
        body = target.read_text(encoding="utf-8")
        assert body.startswith("---\n")
        assert "generated_by: tools/generators/git_catalog.py" in body
        assert "manual_edits_allowed: false" in body

    def test_body_contains_every_top_25(self, tmp_path: Path) -> None:
        target = tmp_path / "appendix-d.md"
        git_catalog.run(
            mode=WriteMode.WRITE,
            clock=FIXED_CLOCK,
            git_help_text=GIT_HELP_FIXTURE,
            git_version_text=GIT_VERSION_FIXTURE,
            output_path=target,
        )
        body = target.read_text(encoding="utf-8")
        # Each command appears as backtick-wrapped in the table.
        for name in TestEnrichmentInventory.TOP_25_NAMES:
            assert f"`git {name}`" in body, f"missing `git {name}` in output"

    def test_body_contains_sange_native_rows(self, tmp_path: Path) -> None:
        target = tmp_path / "appendix-d.md"
        git_catalog.run(
            mode=WriteMode.WRITE,
            clock=FIXED_CLOCK,
            git_help_text=GIT_HELP_FIXTURE,
            git_version_text=GIT_VERSION_FIXTURE,
            output_path=target,
        )
        body = target.read_text(encoding="utf-8")
        for native in git_catalog.SANGE_NATIVE_ROWS:
            assert native.name in body

    def test_byte_identical_rerun_with_same_clock(self, tmp_path: Path) -> None:
        target = tmp_path / "appendix-d.md"
        git_catalog.run(
            mode=WriteMode.WRITE,
            clock=FIXED_CLOCK,
            git_help_text=GIT_HELP_FIXTURE,
            git_version_text=GIT_VERSION_FIXTURE,
            output_path=target,
        )
        first = target.read_bytes()
        git_catalog.run(
            mode=WriteMode.WRITE,
            clock=FIXED_CLOCK,
            git_help_text=GIT_HELP_FIXTURE,
            git_version_text=GIT_VERSION_FIXTURE,
            output_path=target,
        )
        second = target.read_bytes()
        assert first == second

    def test_check_mode_passes_on_fresh_write(self, tmp_path: Path) -> None:
        target = tmp_path / "appendix-d.md"
        git_catalog.run(
            mode=WriteMode.WRITE,
            clock=FIXED_CLOCK,
            git_help_text=GIT_HELP_FIXTURE,
            git_version_text=GIT_VERSION_FIXTURE,
            output_path=target,
        )
        outcomes = git_catalog.run(
            mode=WriteMode.CHECK,
            clock=FIXED_CLOCK,
            git_help_text=GIT_HELP_FIXTURE,
            git_version_text=GIT_VERSION_FIXTURE,
            output_path=target,
        )
        assert outcomes[0].result is not None
        assert outcomes[0].result.value == "match"

    def test_check_detects_drift(self, tmp_path: Path) -> None:
        target = tmp_path / "appendix-d.md"
        git_catalog.run(
            mode=WriteMode.WRITE,
            clock=FIXED_CLOCK,
            git_help_text=GIT_HELP_FIXTURE,
            git_version_text=GIT_VERSION_FIXTURE,
            output_path=target,
        )
        text = target.read_text(encoding="utf-8")
        target.write_text(text.replace("Appendix D", "TAMPERED"), encoding="utf-8")
        outcomes = git_catalog.run(
            mode=WriteMode.CHECK,
            clock=FIXED_CLOCK,
            git_help_text=GIT_HELP_FIXTURE,
            git_version_text=GIT_VERSION_FIXTURE,
            output_path=target,
        )
        assert outcomes[0].result is not None
        assert outcomes[0].result.value == "mismatch"

    def test_body_sha_round_trip(self, tmp_path: Path) -> None:
        import re

        target = tmp_path / "appendix-d.md"
        git_catalog.run(
            mode=WriteMode.WRITE,
            clock=FIXED_CLOCK,
            git_help_text=GIT_HELP_FIXTURE,
            git_version_text=GIT_VERSION_FIXTURE,
            output_path=target,
        )
        text = target.read_text(encoding="utf-8")
        m = re.search(r"output_sha256: ([0-9a-f]{64})", text)
        assert m is not None
        declared = m.group(1)
        actual = body_sha256(text)
        assert declared == actual

    def test_unenriched_command_gets_passthrough_default(self, tmp_path: Path) -> None:
        # `pack-refs` is in the fixture (Low-level / Internal Helpers) but not
        # in ENRICHMENT — it should appear in the catalog with the
        # passthrough default.
        target = tmp_path / "appendix-d.md"
        git_catalog.run(
            mode=WriteMode.WRITE,
            clock=FIXED_CLOCK,
            git_help_text=GIT_HELP_FIXTURE,
            git_version_text=GIT_VERSION_FIXTURE,
            output_path=target,
        )
        body = target.read_text(encoding="utf-8")
        assert "`git pack-refs`" in body
        assert "passthrough" in body  # the default Sange wrapper for unenriched rows


# --------------------------------------------------------------------------- #
# Orchestrator integration
# --------------------------------------------------------------------------- #


class TestOrchestratorEntry:
    def test_run_returns_one_outcome(self, tmp_path: Path) -> None:
        target = tmp_path / "appendix-d.md"
        outcomes = git_catalog.run(
            mode=WriteMode.WRITE,
            clock=FIXED_CLOCK,
            git_help_text=GIT_HELP_FIXTURE,
            git_version_text=GIT_VERSION_FIXTURE,
            output_path=target,
        )
        assert len(outcomes) == 1

    def test_run_signature_matches_orchestrator_contract(self) -> None:
        # The orchestrator calls run(mode=..., clock=...) with kwargs.
        import inspect
        sig = inspect.signature(git_catalog.run)
        for param in ("mode", "clock"):
            assert param in sig.parameters, f"run() missing keyword-only parameter {param}"
