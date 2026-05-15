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
    SvnVersion,
    parse_info_xml,
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
