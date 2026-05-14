"""Tests for tools/generators/cli_reference.py — T-G-009."""

from __future__ import annotations

import datetime as _dt
import sys
from pathlib import Path

import click
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
GENERATORS_DIR = REPO_ROOT / "tools" / "generators"
SRC_DIR = REPO_ROOT / "src"
for p in (str(SRC_DIR), str(GENERATORS_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)

# Imports happen after the path bootstrap.
from _lib.output import WriteMode  # noqa: E402
from cli_reference import (  # noqa: E402
    _Argument,
    _CommandNode,
    _Option,
    _build_body,
    _build_tree,
    _fingerprint,
    _walk,
    run,
)


_FIXED_CLOCK = _dt.datetime(2026, 5, 14, 12, 0, 0, tzinfo=_dt.timezone.utc)


# --------------------------------------------------------------------------- #
# _walk — live-tree introspection
# --------------------------------------------------------------------------- #


class TestWalkLiveTree:
    def test_root_is_a_group(self) -> None:
        tree = _build_tree()
        assert tree.invocation == "sange"
        assert tree.is_group is True
        assert tree.help

    def test_has_known_subcommands(self) -> None:
        tree = _build_tree()
        names = {c.invocation for c in tree.children}
        assert "sange ai" in names
        assert "sange doctor" in names
        assert "sange commit" in names

    def test_ai_subcommands(self) -> None:
        tree = _build_tree()
        ai = next(c for c in tree.children if c.invocation == "sange ai")
        assert ai.is_group is True
        sub_names = {s.invocation for s in ai.children}
        assert "sange ai preview" in sub_names
        assert "sange ai providers" in sub_names

    def test_ai_preview_has_task_option(self) -> None:
        tree = _build_tree()
        ai = next(c for c in tree.children if c.invocation == "sange ai")
        preview = next(s for s in ai.children if s.invocation == "sange ai preview")
        flags = [
            f
            for o in preview.options
            for f in o.flags
        ]
        assert "--task" in flags
        assert "--diff" in flags
        assert "--provider" in flags

    def test_commit_has_repo_option(self) -> None:
        tree = _build_tree()
        commit = next(c for c in tree.children if c.invocation == "sange commit")
        flags = [f for o in commit.options for f in o.flags]
        assert "--diff" in flags
        assert "--repo" in flags
        assert "--scope" in flags

    def test_doctor_is_leaf(self) -> None:
        tree = _build_tree()
        doctor = next(c for c in tree.children if c.invocation == "sange doctor")
        assert doctor.is_group is False
        assert doctor.children == ()


# --------------------------------------------------------------------------- #
# Determinism — fingerprint stability + body hash round-trip
# --------------------------------------------------------------------------- #


class TestDeterminism:
    def test_fingerprint_stable_across_calls(self) -> None:
        tree = _build_tree()
        assert _fingerprint(tree) == _fingerprint(tree)

    def test_fingerprint_changes_when_help_changes(self) -> None:
        tree = _build_tree()
        # Synthesize a sibling with a different help text and verify
        # the hash changes.
        mutated = _CommandNode(
            invocation=tree.invocation,
            help=tree.help + " (modified)",
            is_group=tree.is_group,
            options=tree.options,
            arguments=tree.arguments,
            children=tree.children,
        )
        assert _fingerprint(tree) != _fingerprint(mutated)

    def test_run_write_then_check_matches(self, tmp_path: Path) -> None:
        # Run WRITE then CHECK; check must report "match".
        from cli_reference import OUTPUT_PATH

        # Snapshot the current file so we restore it after the test.
        original = OUTPUT_PATH.read_text(encoding="utf-8")
        try:
            write_result = run(mode=WriteMode.WRITE, clock=_FIXED_CLOCK)
            assert len(write_result) == 1
            check_result = run(mode=WriteMode.CHECK, clock=_FIXED_CLOCK)
            assert check_result[0].result is not None
            assert check_result[0].result.value == "match"
        finally:
            OUTPUT_PATH.write_text(original, encoding="utf-8")

    def test_alphabetical_ordering_of_subcommands(self) -> None:
        tree = _build_tree()
        names = [c.invocation for c in tree.children]
        assert names == sorted(names)


# --------------------------------------------------------------------------- #
# _build_body — rendering shape
# --------------------------------------------------------------------------- #


class TestBuildBody:
    def test_body_has_required_sections(self) -> None:
        tree = _build_tree()
        body = _build_body(tree)
        assert "# Sange CLI reference" in body
        assert "## Command index" in body
        assert "## Commands" in body
        assert "## Exit codes" in body

    def test_body_lists_every_command(self) -> None:
        tree = _build_tree()
        body = _build_body(tree)
        for expected in ("sange ai", "sange ai preview", "sange ai providers",
                         "sange commit", "sange doctor"):
            assert f"`{expected}`" in body

    def test_body_shows_options_for_commit(self) -> None:
        tree = _build_tree()
        body = _build_body(tree)
        # The commit command's --diff option must appear in the body.
        assert "--diff" in body
        assert "--scope" in body


# --------------------------------------------------------------------------- #
# _walk with synthesized click commands (no live app)
# --------------------------------------------------------------------------- #


class TestWalkSynthesized:
    def test_simple_command(self) -> None:
        @click.command()
        @click.option("--flag", is_flag=True, help="A flag.")
        @click.option("--name", default="world", help="A name.")
        def cmd() -> None:
            """A test command."""

        node = _walk(cmd, "test")
        assert node.invocation == "test"
        assert "test command" in node.help.lower()
        assert node.is_group is False
        # Options sorted by their first flag.
        first_flags = [o.flags[0] for o in node.options]
        assert first_flags == sorted(first_flags)

    def test_group_with_children(self) -> None:
        @click.group()
        def grp() -> None:
            """A group."""

        @grp.command("alpha")
        def _alpha() -> None:
            """Alpha sub-command."""

        @grp.command("zulu")
        def _zulu() -> None:
            """Zulu sub-command."""

        node = _walk(grp, "test")
        assert node.is_group is True
        assert [c.invocation for c in node.children] == [
            "test alpha", "test zulu"
        ]


# --------------------------------------------------------------------------- #
# _Option + _Argument shape
# --------------------------------------------------------------------------- #


class TestDataclasses:
    def test_option_is_frozen(self) -> None:
        o = _Option(flags=("--x",), help="h", is_flag=False, default=None, required=False)
        with pytest.raises(Exception):
            o.help = "y"  # type: ignore[misc]

    def test_argument_is_frozen(self) -> None:
        a = _Argument(name="x", required=True)
        with pytest.raises(Exception):
            a.required = False  # type: ignore[misc]

    def test_command_node_is_frozen(self) -> None:
        n = _CommandNode(
            invocation="x",
            help="h",
            is_group=False,
            options=(),
            arguments=(),
            children=(),
        )
        with pytest.raises(Exception):
            n.help = "y"  # type: ignore[misc]
