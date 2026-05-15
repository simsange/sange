"""Tests for src/sange/adapters/vcs/svn/parsers.py — pure XML / text parsers.

No subprocess; every test feeds a fixture string and asserts on the
parsed value. Captures the SVN-1.14 XML shapes verbatim so the
parser is locked against drift.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from sange.adapters.vcs.svn.parsers import (
    SvnInfo,
    SvnLsEntry,
    SvnVersion,
    extract_branch_from_url,
    parse_diff_stat,
    parse_info_xml,
    parse_log_xml,
    parse_ls_xml,
    parse_status_xml,
    parse_version,
)
from sange.core.models.working_copy import FileState

# --------------------------------------------------------------------------- #
# parse_version
# --------------------------------------------------------------------------- #


class TestParseVersion:
    def test_quiet_form(self) -> None:
        v = parse_version("1.14.3\n")
        assert v.major == 1
        assert v.minor == 14
        assert v.patch == 3
        assert v.raw == "1.14.3"
        assert v.tuple3 == (1, 14, 3)
        assert str(v) == "1.14.3"

    def test_verbose_form(self) -> None:
        text = (
            "svn, version 1.14.3 (r1907316)\n"
            "   compiled May 14 2026, 11:23:51 on x86_64-apple-darwin23.4.0\n"
        )
        v = parse_version(text)
        assert v.major == 1
        assert v.minor == 14
        assert v.patch == 3

    def test_no_triple_raises(self) -> None:
        with pytest.raises(ValueError, match=r"no M\.N\.P"):
            parse_version("garbage\n")

    def test_empty_raises(self) -> None:
        with pytest.raises(ValueError):
            parse_version("\n\n")


# --------------------------------------------------------------------------- #
# parse_status_xml
# --------------------------------------------------------------------------- #


_STATUS_FIXTURE = '''<?xml version="1.0" encoding="UTF-8"?>
<status>
<target path=".">
<entry path="a.txt">
<wc-status item="modified" revision="1" props="none">
<commit revision="1">
<author>alice</author>
<date>2026-05-15T19:56:57.118248Z</date>
</commit>
</wc-status>
</entry>
<entry path="b.txt">
<wc-status item="added" revision="-1" props="none">
</wc-status>
</entry>
<entry path="c.txt">
<wc-status item="unversioned" revision="-1" props="none">
</wc-status>
</entry>
<entry path="d.txt">
<wc-status item="deleted" revision="1" props="none">
</wc-status>
</entry>
<entry path="e.txt">
<wc-status item="conflicted" revision="1" props="none">
</wc-status>
</entry>
<entry path="ignored-file.log">
<wc-status item="ignored" revision="-1" props="none">
</wc-status>
</entry>
</target>
</status>
'''


class TestParseStatusXml:
    def test_modified_added_unversioned_etc(self) -> None:
        entries = parse_status_xml(_STATUS_FIXTURE)
        by_path = {str(e.path): e.state for e in entries}
        assert by_path["a.txt"] is FileState.MODIFIED
        assert by_path["b.txt"] is FileState.ADDED
        assert by_path["c.txt"] is FileState.UNTRACKED
        assert by_path["d.txt"] is FileState.DELETED
        assert by_path["e.txt"] is FileState.CONFLICTED
        assert by_path["ignored-file.log"] is FileState.IGNORED

    def test_relative_paths(self) -> None:
        entries = parse_status_xml(_STATUS_FIXTURE)
        for e in entries:
            assert not e.path.is_absolute()

    def test_empty_status(self) -> None:
        # A clean working copy returns just `<status><target path="."/></status>`.
        empty = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<status><target path="."></target></status>'
        )
        assert parse_status_xml(empty) == ()

    def test_empty_input(self) -> None:
        assert parse_status_xml("") == ()
        assert parse_status_xml("\n\n   ") == ()

    def test_skips_unmapped_items(self) -> None:
        # `external` / `obstructed` / `none` aren't mapped to FileState
        # and should be silently skipped (legal but not actionable).
        fixture = '''<?xml version="1.0"?>
<status>
<target path=".">
<entry path="ext-dir"><wc-status item="external"/></entry>
<entry path="weird"><wc-status item="obstructed"/></entry>
<entry path="nothing"><wc-status item="none"/></entry>
<entry path="real.txt"><wc-status item="modified"/></entry>
</target>
</status>
'''
        entries = parse_status_xml(fixture)
        paths = {str(e.path) for e in entries}
        assert paths == {"real.txt"}

    def test_dot_root_entry_skipped(self) -> None:
        # `path="."` is the working-copy root itself, not a file entry.
        fixture = '''<?xml version="1.0"?>
<status>
<target path=".">
<entry path="."><wc-status item="normal"/></entry>
<entry path="x.txt"><wc-status item="modified"/></entry>
</target>
</status>
'''
        entries = parse_status_xml(fixture)
        assert [str(e.path) for e in entries] == ["x.txt"]

    def test_dot_slash_prefix_stripped(self) -> None:
        fixture = '''<?xml version="1.0"?>
<status>
<target path=".">
<entry path="./sub/file.txt"><wc-status item="modified"/></entry>
</target>
</status>
'''
        entries = parse_status_xml(fixture)
        assert [str(e.path) for e in entries] == [str(Path("sub/file.txt"))]


# --------------------------------------------------------------------------- #
# parse_info_xml
# --------------------------------------------------------------------------- #


_INFO_FIXTURE = '''<?xml version="1.0" encoding="UTF-8"?>
<info>
<entry revision="42" kind="dir" path=".">
<url>file:///srv/svn/myrepo/trunk</url>
<relative-url>^/trunk</relative-url>
<repository>
<root>file:///srv/svn/myrepo</root>
<uuid>abc-123-def-456</uuid>
</repository>
<wc-info>
<wcroot-abspath>/home/alice/myproject</wcroot-abspath>
<schedule>normal</schedule>
<depth>infinity</depth>
</wc-info>
<commit revision="42">
<author>alice</author>
<date>2026-05-15T19:56:55.973701Z</date>
</commit>
</entry>
</info>
'''


class TestParseInfoXml:
    def test_full_fixture(self) -> None:
        info = parse_info_xml(_INFO_FIXTURE)
        assert isinstance(info, SvnInfo)
        assert info.path == "."
        assert info.revision == 42
        assert info.kind == "dir"
        assert info.url == "file:///srv/svn/myrepo/trunk"
        assert info.relative_url == "^/trunk"
        assert info.repository_root == "file:///srv/svn/myrepo"
        assert info.repository_uuid == "abc-123-def-456"
        assert info.wc_root_abs == "/home/alice/myproject"
        assert info.schedule == "normal"
        assert info.depth == "infinity"
        assert info.commit_revision == 42
        assert info.commit_author == "alice"

    def test_empty_raises(self) -> None:
        with pytest.raises(ValueError, match="empty input"):
            parse_info_xml("")

    def test_multi_entry_raises(self) -> None:
        fixture = '''<?xml version="1.0"?>
<info>
<entry path="a"/>
<entry path="b"/>
</info>
'''
        with pytest.raises(ValueError, match="exactly one"):
            parse_info_xml(fixture)

    def test_pre_commit_repo(self) -> None:
        # A working copy on a fresh repo (no commits yet) has no <commit>
        # element under <entry>. Author should be empty.
        fixture = '''<?xml version="1.0"?>
<info>
<entry revision="0" kind="dir" path=".">
<url>file:///tmp/r</url>
<relative-url>^/</relative-url>
<repository><root>file:///tmp/r</root><uuid>x</uuid></repository>
<wc-info><wcroot-abspath>/tmp/wc</wcroot-abspath><schedule>normal</schedule><depth>infinity</depth></wc-info>
</entry>
</info>
'''
        info = parse_info_xml(fixture)
        assert info.revision == 0
        assert info.commit_revision == -1
        assert info.commit_author == ""


# --------------------------------------------------------------------------- #
# parse_log_xml
# --------------------------------------------------------------------------- #


_LOG_FIXTURE = '''<?xml version="1.0" encoding="UTF-8"?>
<log>
<logentry revision="3">
<author>alice</author>
<date>2026-05-15T21:16:49.101972Z</date>
<msg>commit 3 subject

extra body line
second body line</msg>
</logentry>
<logentry revision="2">
<author>bob</author>
<date>2026-05-15T21:16:48.103957Z</date>
<msg>commit 2</msg>
</logentry>
<logentry revision="1">
<date>2026-05-15T21:16:47.095798Z</date>
<msg></msg>
</logentry>
</log>
'''


class TestParseLogXml:
    def test_basic_parsing(self) -> None:
        refs = parse_log_xml(_LOG_FIXTURE)
        assert len(refs) == 3
        assert [r.sha for r in refs] == ["3", "2", "1"]

    def test_subject_and_body_split(self) -> None:
        refs = parse_log_xml(_LOG_FIXTURE)
        r3 = refs[0]
        assert r3.subject == "commit 3 subject"
        assert "extra body line" in r3.body
        assert "second body line" in r3.body

    def test_single_line_message_has_empty_body(self) -> None:
        refs = parse_log_xml(_LOG_FIXTURE)
        r2 = refs[1]
        assert r2.subject == "commit 2"
        assert r2.body == ""

    def test_empty_author(self) -> None:
        refs = parse_log_xml(_LOG_FIXTURE)
        r1 = refs[2]
        assert r1.author_name == ""
        assert r1.author_email == ""   # SVN never populates email

    def test_empty_message_gets_placeholder(self) -> None:
        # CommitRef requires a non-empty subject (per its __post_init__);
        # SVN's empty messages get the documented placeholder.
        refs = parse_log_xml(_LOG_FIXTURE)
        r1 = refs[2]
        assert r1.subject == "(no commit message)"
        assert r1.body == ""

    def test_date_parsed_as_utc(self) -> None:
        refs = parse_log_xml(_LOG_FIXTURE)
        r3 = refs[0]
        assert r3.committed_at.tzinfo is not None
        assert r3.committed_at.year == 2026
        assert r3.committed_at.month == 5

    def test_parents_always_empty(self) -> None:
        # v0.5 does not reconstruct merge parents.
        for ref in parse_log_xml(_LOG_FIXTURE):
            assert ref.parents == ()

    def test_empty_input(self) -> None:
        assert parse_log_xml("") == ()
        assert parse_log_xml("\n\n   ") == ()


# --------------------------------------------------------------------------- #
# parse_ls_xml
# --------------------------------------------------------------------------- #


_LS_FIXTURE = '''<?xml version="1.0" encoding="UTF-8"?>
<lists>
<list path="file:///srv/r/branches">
<entry kind="dir">
<name>feature-x</name>
<commit revision="2">
<author>alice</author>
<date>2026-05-15T21:17:07.073668Z</date>
</commit>
</entry>
<entry kind="dir">
<name>feature-y</name>
<commit revision="5">
<author>bob</author>
<date>2026-05-15T22:00:00.000000Z</date>
</commit>
</entry>
<entry kind="file">
<name>readme.txt</name>
<commit revision="3">
<author>alice</author>
<date>2026-05-15T22:00:00.000000Z</date>
</commit>
</entry>
</list>
</lists>
'''


class TestParseLsXml:
    def test_dirs_and_files(self) -> None:
        entries = parse_ls_xml(_LS_FIXTURE)
        assert len(entries) == 3
        kinds = {e.name: e.kind for e in entries}
        assert kinds["feature-x"] == "dir"
        assert kinds["feature-y"] == "dir"
        assert kinds["readme.txt"] == "file"

    def test_revision_parsed(self) -> None:
        entries = {e.name: e for e in parse_ls_xml(_LS_FIXTURE)}
        assert entries["feature-x"].revision == 2
        assert entries["feature-y"].revision == 5

    def test_author_and_date(self) -> None:
        entries = {e.name: e for e in parse_ls_xml(_LS_FIXTURE)}
        assert entries["feature-x"].author == "alice"
        assert entries["feature-x"].date.year == 2026
        assert entries["feature-x"].date.tzinfo is not None

    def test_empty(self) -> None:
        assert parse_ls_xml("") == ()
        assert parse_ls_xml(
            '<?xml version="1.0"?>\n<lists><list path="x"></list></lists>'
        ) == ()


# --------------------------------------------------------------------------- #
# extract_branch_from_url
# --------------------------------------------------------------------------- #


class TestExtractBranchFromUrl:
    def test_trunk(self) -> None:
        assert extract_branch_from_url("^/trunk") == ("trunk", "trunk")
        assert extract_branch_from_url("^/trunk/sub/dir") == ("trunk", "trunk")

    def test_branch(self) -> None:
        assert extract_branch_from_url("^/branches/feature-x") == ("branch", "feature-x")
        assert extract_branch_from_url("^/branches/feature-x/sub") == (
            "branch", "feature-x"
        )

    def test_tag(self) -> None:
        assert extract_branch_from_url("^/tags/v1") == ("tag", "v1")
        assert extract_branch_from_url("^/tags/v1/path") == ("tag", "v1")

    def test_repo_root_returns_none(self) -> None:
        assert extract_branch_from_url("^/") is None
        assert extract_branch_from_url("") is None

    def test_unknown_convention_returns_none(self) -> None:
        assert extract_branch_from_url("^/something-else") is None
        assert extract_branch_from_url("^/lib/utils") is None

    def test_branches_root_without_name_returns_none(self) -> None:
        # `^/branches` itself (no sub) is not a specific branch.
        assert extract_branch_from_url("^/branches") is None
        assert extract_branch_from_url("^/tags") is None


# --------------------------------------------------------------------------- #
# parse_diff_stat
# --------------------------------------------------------------------------- #


_DIFF_FIXTURE = """Index: a.txt
===================================================================
--- a.txt	(revision 1)
+++ a.txt	(working copy)
@@ -1 +1,2 @@
 unchanged line
+added line 1
+added line 2
Index: b.txt
===================================================================
--- b.txt	(revision 1)
+++ b.txt	(working copy)
@@ -1,2 +1 @@
-removed line 1
-removed line 2
+just one new
"""


class TestParseDiffStat:
    def test_basic_counts(self) -> None:
        files, ins, dels = parse_diff_stat(_DIFF_FIXTURE)
        assert files == 2          # two `Index:` lines
        assert ins == 3            # +added line 1, +added line 2, +just one new
        assert dels == 2           # -removed line 1, -removed line 2

    def test_empty_diff(self) -> None:
        assert parse_diff_stat("") == (0, 0, 0)
        assert parse_diff_stat("\n\n") == (0, 0, 0)

    def test_no_index_lines_falls_back_to_plus_headers(self) -> None:
        # Some `svn diff` invocations elide the `Index:` marker;
        # files should still be counted from `+++ ` headers.
        fixture = """--- a.txt	(rev 1)
+++ a.txt	(rev 2)
@@ -1 +1 @@
-old
+new
"""
        files, ins, dels = parse_diff_stat(fixture)
        assert files == 1
        assert ins == 1
        assert dels == 1

    def test_header_lines_not_counted_as_changes(self) -> None:
        # The +++ and --- lines start with + and - but must NOT
        # be counted toward insertions/deletions.
        _, ins, dels = parse_diff_stat(_DIFF_FIXTURE)
        # If header counting were wrong, ins would be 5 (3 real + 2 +++).
        assert ins == 3
        # And dels would be 4 (2 real + 2 ---).
        assert dels == 2
