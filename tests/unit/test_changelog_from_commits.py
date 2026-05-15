"""Tests for tools/generators/changelog_from_commits.py — T-G-013."""

from __future__ import annotations

import datetime as _dt
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
GENERATORS_DIR = REPO_ROOT / "tools" / "generators"
SRC_DIR = REPO_ROOT / "src"
for p in (str(SRC_DIR), str(GENERATORS_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)

from _lib.output import VerificationResult, WriteMode  # noqa: E402
from changelog_from_commits import (  # noqa: E402
    _TYPE_TO_SECTION,
    _bucket,
    _build_body,
    _Entry,
    _input_fingerprint,
    _pushed_commits,
    run,
)

from sange.core.lifecycle import (  # noqa: E402
    CommitJSON,
    CommitMessage,
    CommitsDirectory,
    CommitStatus,
)

_NOW = _dt.datetime(2026, 1, 1, 12, 0, 0, tzinfo=_dt.UTC)
_LATER = _dt.datetime(2026, 5, 1, 12, 0, 0, tzinfo=_dt.UTC)
_FIXED_CLOCK = _NOW


def _pushed(
    counter: int,
    type_: str = "feat",
    scope: str = "auth",
    subject: str = "add login",
    breaking: bool = False,
    sha: str = "a" * 40,
) -> CommitJSON:
    return CommitJSON(
        counter=counter,
        created_at=_NOW,
        updated_at=_LATER,
        status=CommitStatus.PUSHED,
        message=CommitMessage(
            type=type_,  # type: ignore[arg-type]
            scope=scope,
            subject=subject,
            breaking_change=breaking,
        ),
        committed_sha=sha,
        pushed_remote="origin",
    )


def _seed(tmp_path: Path, commits: list[CommitJSON]) -> Path:
    """Plant `commits` under `<tmp_path>/.sange/commits/`. Returns tmp_path."""

    cd = CommitsDirectory(tmp_path)
    for c in commits:
        cd.save(c)
    return tmp_path


# --------------------------------------------------------------------------- #
# Type-to-section mapping
# --------------------------------------------------------------------------- #


class TestTypeMapping:
    def test_feat_to_added(self) -> None:
        assert _TYPE_TO_SECTION["feat"] == "Added"

    def test_fix_to_fixed(self) -> None:
        assert _TYPE_TO_SECTION["fix"] == "Fixed"

    def test_docs_to_documentation(self) -> None:
        assert _TYPE_TO_SECTION["docs"] == "Documentation"

    def test_chore_to_maintenance(self) -> None:
        assert _TYPE_TO_SECTION["chore"] == "Maintenance"

    def test_all_11_types_mapped(self) -> None:
        # Every Conventional Commits 1.0.0 type maps to a section.
        for type_ in (
            "feat", "fix", "docs", "style", "refactor", "perf",
            "test", "build", "ci", "chore", "revert",
        ):
            assert type_ in _TYPE_TO_SECTION


# --------------------------------------------------------------------------- #
# _pushed_commits — input collection
# --------------------------------------------------------------------------- #


class TestPushedCommits:
    def test_empty_when_no_commits_dir(self, tmp_path: Path) -> None:
        # No .sange/commits/ at all.
        assert _pushed_commits(tmp_path) == []

    def test_collects_pushed_only(self, tmp_path: Path) -> None:
        cd = CommitsDirectory(tmp_path)
        # One DRAFT, one APPROVED, one PUSHED.
        cd.save(CommitJSON(
            counter=1, created_at=_NOW, updated_at=_NOW,
            message=CommitMessage(type="feat", scope="", subject="draft"),
        ))
        cd.save(CommitJSON(
            counter=2, created_at=_NOW, updated_at=_NOW,
            status=CommitStatus.APPROVED,
            message=CommitMessage(type="fix", scope="", subject="approved"),
        ))
        cd.save(_pushed(3, "feat", "auth", "pushed thing"))
        out = _pushed_commits(tmp_path)
        assert len(out) == 1
        assert out[0].counter == 3

    def test_pushed_returned_in_counter_order(self, tmp_path: Path) -> None:
        _seed(tmp_path, [
            _pushed(3, "feat", "c", "third"),
            _pushed(1, "feat", "a", "first"),
            _pushed(2, "fix", "b", "second"),
        ])
        out = _pushed_commits(tmp_path)
        assert [c.counter for c in out] == [1, 2, 3]


# --------------------------------------------------------------------------- #
# _bucket — section grouping
# --------------------------------------------------------------------------- #


class TestBucket:
    def test_feat_bucketed_under_added(self) -> None:
        commits = [_pushed(1, "feat", "auth", "new flow")]
        b = _bucket(commits)
        assert len(b["Added"]) == 1
        assert b["Fixed"] == []

    def test_multiple_types(self) -> None:
        commits = [
            _pushed(1, "feat", "auth", "add login"),
            _pushed(2, "fix", "core", "tighten loop"),
            _pushed(3, "docs", "", "update readme"),
            _pushed(4, "chore", "", "tidy"),
        ]
        b = _bucket(commits)
        assert len(b["Added"]) == 1
        assert len(b["Fixed"]) == 1
        assert len(b["Documentation"]) == 1
        assert len(b["Maintenance"]) == 1


# --------------------------------------------------------------------------- #
# _build_body — markdown rendering
# --------------------------------------------------------------------------- #


class TestBuildBody:
    def test_empty_body_shows_placeholder(self) -> None:
        body = _build_body([])
        assert "Unreleased" in body
        assert "No PUSHED commits yet" in body

    def test_body_lists_feat(self) -> None:
        body = _build_body([_pushed(1, "feat", "auth", "add login")])
        assert "## Unreleased" in body
        assert "### Added" in body
        assert "add login" in body
        assert "**auth:**" in body

    def test_body_lists_fix_under_fixed(self) -> None:
        body = _build_body([_pushed(1, "fix", "core", "tighten loop")])
        assert "### Fixed" in body
        assert "tighten loop" in body

    def test_breaking_marker_inline(self) -> None:
        body = _build_body([
            _pushed(1, "feat", "api", "remove v1", breaking=True)
        ])
        assert "**BREAKING:**" in body

    def test_short_sha_appears(self) -> None:
        commit = _pushed(1, "feat", "x", "y", sha="abcdef1234567890" + "0" * 24)
        body = _build_body([commit])
        assert "`abcdef1`" in body

    def test_sections_in_keep_a_changelog_order(self) -> None:
        # Both Added + Fixed present; Added must appear before Fixed.
        body = _build_body([
            _pushed(1, "fix", "x", "fix A"),
            _pushed(2, "feat", "y", "feature B"),
        ])
        added_idx = body.find("### Added")
        fixed_idx = body.find("### Fixed")
        assert added_idx >= 0 and fixed_idx >= 0
        assert added_idx < fixed_idx

    def test_empty_sections_omitted(self) -> None:
        # Only `feat` PUSHED → only "Added" section should appear.
        body = _build_body([_pushed(1, "feat", "x", "y")])
        assert "### Added" in body
        assert "### Fixed" not in body
        assert "### Documentation" not in body
        assert "### Maintenance" not in body

    def test_within_section_chronological(self) -> None:
        body = _build_body([
            _pushed(2, "feat", "b", "second"),
            _pushed(1, "feat", "a", "first"),
        ])
        # Within "Added", counter 1 ("first") must appear before counter 2 ("second").
        idx1 = body.find("first")
        idx2 = body.find("second")
        assert idx1 < idx2


# --------------------------------------------------------------------------- #
# Fingerprint stability
# --------------------------------------------------------------------------- #


class TestFingerprint:
    def test_empty_fingerprint_stable(self) -> None:
        assert _input_fingerprint([]) == _input_fingerprint([])

    def test_same_commits_same_fingerprint(self) -> None:
        # Realistic flow: serialize a commit, parse it back, and confirm
        # the fingerprint matches. (Two fresh constructions get different
        # uuid4 ids by design — that's content, so fingerprints differ.)
        c1 = _pushed(1, "feat", "x", "y")
        c1_replayed = CommitJSON.model_validate_json(c1.model_dump_json())
        assert _input_fingerprint([c1]) == _input_fingerprint([c1_replayed])

    def test_different_subject_different_fingerprint(self) -> None:
        c1 = _pushed(1, "feat", "x", "subject A")
        c2 = _pushed(1, "feat", "x", "subject B")
        assert _input_fingerprint([c1]) != _input_fingerprint([c2])


# --------------------------------------------------------------------------- #
# Generator entry-point — write/check round-trip
# --------------------------------------------------------------------------- #


class TestRun:
    def test_write_then_check_matches(self, tmp_path: Path) -> None:
        # Use the real repo's commits dir (currently empty).
        from changelog_from_commits import OUTPUT_PATH

        original = OUTPUT_PATH.read_text(encoding="utf-8") if OUTPUT_PATH.exists() else None
        try:
            w = run(mode=WriteMode.WRITE, clock=_FIXED_CLOCK)
            assert len(w) == 1
            c = run(mode=WriteMode.CHECK, clock=_FIXED_CLOCK)
            assert c[0].result is VerificationResult.MATCH
        finally:
            if original is not None:
                OUTPUT_PATH.write_text(original, encoding="utf-8")

    def test_run_with_seeded_commits_dir(self, tmp_path: Path) -> None:
        # Seed a tmp commits dir + point the generator at it.
        _seed(tmp_path, [
            _pushed(1, "feat", "auth", "passkey support"),
            _pushed(2, "fix", "core", "race condition"),
        ])
        # Re-write to a temp output path so we don't touch docs/CHANGELOG.md.
        # We capture content via a manual round-trip.
        from changelog_from_commits import _build_body, _pushed_commits
        commits = _pushed_commits(tmp_path)
        body = _build_body(commits)
        assert "passkey support" in body
        assert "race condition" in body
        assert "### Added" in body
        assert "### Fixed" in body


# --------------------------------------------------------------------------- #
# _Entry dataclass
# --------------------------------------------------------------------------- #


class TestEntry:
    def test_basic_bullet(self) -> None:
        e = _Entry(
            type_="feat", scope="auth", subject="x", breaking=False,
            sha="abcdef1234567890" + "0" * 24, counter=1,
        )
        assert "**auth:**" in e.bullet
        assert "x" in e.bullet
        assert "`abcdef1`" in e.bullet
        assert "BREAKING" not in e.bullet

    def test_breaking_bullet(self) -> None:
        e = _Entry(
            type_="feat", scope="api", subject="remove v1", breaking=True,
            sha="0" * 40, counter=1,
        )
        assert "**BREAKING:**" in e.bullet

    def test_no_scope_no_prefix(self) -> None:
        e = _Entry(
            type_="chore", scope="", subject="tidy", breaking=False,
            sha="0" * 40, counter=1,
        )
        assert "**:**" not in e.bullet
        assert e.bullet.startswith("tidy") or "tidy" in e.bullet
