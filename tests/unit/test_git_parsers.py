"""Tests for src/sange/adapters/vcs/git/parsers.py — pure parsers.

No subprocess. Pure-function tests against fixture text drawn from real
git outputs. Fixture text is the same shape any installed git produces
(en_US C locale, LC_ALL=C).
"""

from __future__ import annotations

from pathlib import Path

from sange.adapters.vcs.git import parsers as P
from sange.core.models import FileState


# --------------------------------------------------------------------------- #
# parse_status_porcelain_v2
# --------------------------------------------------------------------------- #


class TestStatusParser:
    def test_clean_pristine_repo(self) -> None:
        text = (
            "# branch.oid abc123\n"
            "# branch.head main\n"
        )
        ws = P.parse_status_porcelain_v2(text)
        assert ws.branch == "main"
        assert ws.is_pristine

    def test_modified_file(self) -> None:
        text = (
            "# branch.head feature\n"
            "1 .M N... 100644 100644 100644 abc abc src/foo.py\n"
        )
        ws = P.parse_status_porcelain_v2(text)
        assert ws.branch == "feature"
        assert ws.total() == 1
        e = ws.entries[0]
        assert e.path == Path("src/foo.py")
        assert e.state is FileState.MODIFIED

    def test_added_staged_file(self) -> None:
        text = (
            "# branch.head main\n"
            "1 A. N... 000000 100644 100644 0 abc new.py\n"
        )
        ws = P.parse_status_porcelain_v2(text)
        assert ws.entries[0].state is FileState.ADDED

    def test_deleted_file(self) -> None:
        text = (
            "# branch.head main\n"
            "1 D. N... 100644 000000 100644 abc 000 deleted.py\n"
        )
        ws = P.parse_status_porcelain_v2(text)
        assert ws.entries[0].state is FileState.DELETED

    def test_untracked_file(self) -> None:
        text = (
            "# branch.head main\n"
            "? new-script.sh\n"
            "? nested/dir/new.py\n"
        )
        ws = P.parse_status_porcelain_v2(text)
        states = {e.state for e in ws.entries}
        assert states == {FileState.UNTRACKED}
        assert ws.total() == 2

    def test_renamed_file_with_previous(self) -> None:
        # Format-2 rename with TAB separator: new_path<TAB>old_path
        text = (
            "# branch.head main\n"
            "2 R. N... 100644 100644 100644 abc abc R100 new.py\told.py\n"
        )
        ws = P.parse_status_porcelain_v2(text)
        assert ws.total() == 1
        e = ws.entries[0]
        assert e.state is FileState.RENAMED
        assert e.path == Path("new.py")
        assert e.previous_path == Path("old.py")

    def test_ignored_file(self) -> None:
        text = (
            "# branch.head main\n"
            "! .DS_Store\n"
        )
        ws = P.parse_status_porcelain_v2(text)
        assert ws.entries[0].state is FileState.IGNORED

    def test_conflicted_file(self) -> None:
        text = (
            "# branch.head main\n"
            "u UU N... 100644 100644 100644 100644 abc abc abc conflicted.py\n"
        )
        ws = P.parse_status_porcelain_v2(text)
        assert ws.entries[0].state is FileState.CONFLICTED

    def test_mixed_states_entries_sorted_by_path(self) -> None:
        text = (
            "# branch.head main\n"
            "? z-new.py\n"
            "1 .M N... 100644 100644 100644 abc abc a-modified.py\n"
            "? m-untracked.py\n"
        )
        ws = P.parse_status_porcelain_v2(text)
        paths = [str(e.path) for e in ws.entries]
        assert paths == ["a-modified.py", "m-untracked.py", "z-new.py"]


# --------------------------------------------------------------------------- #
# parse_log_records
# --------------------------------------------------------------------------- #


class TestLogParser:
    def _make_record(
        self,
        sha: str = "a" * 40,
        author_name: str = "Imani",
        author_email: str = "imani@simtabi.com",
        ts: str = "2026-05-15T00:00:00+00:00",
        parents: str = "",
        subject: str = "test commit",
        body: str = "",
    ) -> str:
        full_body = body if body else subject
        from sange.adapters.vcs.git.parsers import _FIELD_SEP, _RECORD_SEP
        return (
            f"{sha}{_FIELD_SEP}{author_name}{_FIELD_SEP}{author_email}{_FIELD_SEP}{ts}"
            f"{_FIELD_SEP}{parents}{_FIELD_SEP}{subject}{_FIELD_SEP}{full_body}{_RECORD_SEP}"
        )

    def test_single_record(self) -> None:
        text = self._make_record()
        records = P.parse_log_records(text)
        assert len(records) == 1
        c = records[0]
        assert c.sha == "a" * 40
        assert c.subject == "test commit"
        assert c.author_email == "imani@simtabi.com"

    def test_merge_commit_parents(self) -> None:
        text = self._make_record(parents="b" * 40 + " " + "c" * 40)
        c = P.parse_log_records(text)[0]
        assert len(c.parents) == 2
        assert c.is_merge

    def test_body_stripped_of_subject(self) -> None:
        text = self._make_record(
            subject="feat: add login",
            body="feat: add login\n\nLong description here.",
        )
        c = P.parse_log_records(text)[0]
        assert c.subject == "feat: add login"
        assert c.body == "Long description here."

    def test_multiple_records(self) -> None:
        text = (
            self._make_record(sha="a" * 40, subject="first")
            + self._make_record(sha="b" * 40, subject="second")
        )
        records = P.parse_log_records(text)
        assert len(records) == 2
        assert records[0].subject == "first"
        assert records[1].subject == "second"

    def test_empty_input(self) -> None:
        assert P.parse_log_records("") == ()

    def test_malformed_record_skipped(self) -> None:
        # Too few fields → record dropped.
        text = "just-a-sha\x1eanother-bad\x1e"
        assert P.parse_log_records(text) == ()


# --------------------------------------------------------------------------- #
# parse_branch_list
# --------------------------------------------------------------------------- #


class TestBranchParser:
    def test_single_local_branch_no_upstream(self) -> None:
        from sange.adapters.vcs.git.parsers import _BR_SEP
        line = f"main{_BR_SEP}abc123{_BR_SEP}{_BR_SEP}{_BR_SEP}*"
        out = P.parse_branch_list(line)
        assert len(out) == 1
        b = out[0]
        assert b.name == "main"
        assert b.tip_sha == "abc123"
        assert b.tracking is None
        assert b.is_current

    def test_branch_with_tracking_in_sync(self) -> None:
        from sange.adapters.vcs.git.parsers import _BR_SEP
        line = f"main{_BR_SEP}abc{_BR_SEP}origin/main{_BR_SEP}{_BR_SEP} "
        out = P.parse_branch_list(line)
        b = out[0]
        assert b.tracking == "origin/main"
        # No track field → ahead/behind are None (per `_parse_track_field("")`).
        assert b.ahead is None
        assert b.behind is None

    def test_branch_ahead_only(self) -> None:
        from sange.adapters.vcs.git.parsers import _BR_SEP
        line = f"feature{_BR_SEP}xyz{_BR_SEP}origin/feature{_BR_SEP}ahead 3{_BR_SEP} "
        out = P.parse_branch_list(line)
        b = out[0]
        assert b.ahead == 3
        assert b.behind == 0

    def test_branch_both_ahead_and_behind(self) -> None:
        from sange.adapters.vcs.git.parsers import _BR_SEP
        line = f"feature{_BR_SEP}xyz{_BR_SEP}origin/feature{_BR_SEP}ahead 3, behind 2{_BR_SEP} "
        out = P.parse_branch_list(line)
        b = out[0]
        assert b.ahead == 3
        assert b.behind == 2

    def test_branch_with_gone_upstream(self) -> None:
        from sange.adapters.vcs.git.parsers import _BR_SEP
        line = f"old{_BR_SEP}xyz{_BR_SEP}origin/old{_BR_SEP}gone{_BR_SEP} "
        out = P.parse_branch_list(line)
        b = out[0]
        # Upstream is gone → tracking populated but ahead/behind None.
        assert b.tracking == "origin/old"
        assert b.ahead is None
        assert b.behind is None


# --------------------------------------------------------------------------- #
# parse_remotes
# --------------------------------------------------------------------------- #


class TestRemoteParser:
    def test_single_remote(self) -> None:
        text = (
            "origin\tgit@github.com:foo/bar.git (fetch)\n"
            "origin\tgit@github.com:foo/bar.git (push)\n"
        )
        out = P.parse_remotes(text)
        assert len(out) == 1
        assert out[0].name == "origin"
        assert out[0].url == "git@github.com:foo/bar.git"

    def test_multiple_remotes(self) -> None:
        text = (
            "origin\tgit@github.com:foo/bar.git (fetch)\n"
            "origin\tgit@github.com:foo/bar.git (push)\n"
            "upstream\thttps://gitlab.com/foo/bar.git (fetch)\n"
            "upstream\thttps://gitlab.com/foo/bar.git (push)\n"
        )
        out = P.parse_remotes(text)
        names = {r.name for r in out}
        assert names == {"origin", "upstream"}

    def test_empty_input(self) -> None:
        assert P.parse_remotes("") == ()


# --------------------------------------------------------------------------- #
# parse_tag_list
# --------------------------------------------------------------------------- #


class TestTagParser:
    def test_lightweight_tag(self) -> None:
        from sange.adapters.vcs.git.parsers import _TAG_SEP
        line = f"v0.1.0{_TAG_SEP}abc123{_TAG_SEP}commit{_TAG_SEP}"
        out = P.parse_tag_list(line)
        assert out[0].name == "v0.1.0"
        assert out[0].target_sha == "abc123"
        assert not out[0].is_annotated

    def test_annotated_tag_with_message(self) -> None:
        from sange.adapters.vcs.git.parsers import _TAG_SEP
        line = f"v1.0.0{_TAG_SEP}xyz{_TAG_SEP}tag{_TAG_SEP}First public release"
        out = P.parse_tag_list(line)
        assert out[0].is_annotated
        assert out[0].message == "First public release"


# --------------------------------------------------------------------------- #
# parse_shortstat
# --------------------------------------------------------------------------- #


class TestShortstatParser:
    def test_full_line(self) -> None:
        text = " 3 files changed, 42 insertions(+), 5 deletions(-)"
        files, ins, dels = P.parse_shortstat(text)
        assert (files, ins, dels) == (3, 42, 5)

    def test_inserts_only(self) -> None:
        text = " 1 file changed, 12 insertions(+)"
        assert P.parse_shortstat(text) == (1, 12, 0)

    def test_deletions_only(self) -> None:
        text = " 1 file changed, 3 deletions(-)"
        assert P.parse_shortstat(text) == (1, 0, 3)

    def test_empty(self) -> None:
        assert P.parse_shortstat("") == (0, 0, 0)


# --------------------------------------------------------------------------- #
# parse_version
# --------------------------------------------------------------------------- #


class TestVersionParser:
    def test_typical_output(self) -> None:
        assert P.parse_version("git version 2.51.0\n") == "git 2.51.0"

    def test_with_extra_text(self) -> None:
        # Some packages append "(Apple Git-NN)" — we keep the rest.
        assert P.parse_version("git version 2.51.0 (Apple Git-1234)\n") == \
            "git 2.51.0 (Apple Git-1234)"

    def test_empty(self) -> None:
        assert P.parse_version("") == "git ?"
