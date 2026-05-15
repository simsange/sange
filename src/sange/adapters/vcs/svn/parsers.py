"""Pure parsers for `svn` output.

No subprocess invocation; no I/O. Every function takes a text blob
(as `svn` writes it) and returns a typed value. This keeps the
parsers unit-testable from fixture strings — no SVN binary
required at test time.

The XML shapes are documented inline by `svn help status --xml` /
`svn help info --xml` / `svn help log --xml`. We parse with
`xml.etree.ElementTree` (stdlib, no external dep).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree as ET

from sange.core.models.working_copy import FileEntry, FileState

# --------------------------------------------------------------------------- #
# Version
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class SvnVersion:
    """The version of the installed `svn` binary.

    Parsed from `svn --version --quiet` (one line, e.g. `1.14.3`).
    The trio `(major, minor, patch)` is the same as Python's
    `sys.version_info[:3]`.
    """

    major: int
    minor: int
    patch: int
    raw: str

    @property
    def tuple3(self) -> tuple[int, int, int]:
        return (self.major, self.minor, self.patch)

    def __str__(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}"


_VERSION_RE = re.compile(r"(\d+)\.(\d+)\.(\d+)")


def parse_version(text: str) -> SvnVersion:
    """Parse the output of `svn --version --quiet`.

    The quiet form prints exactly one line like `1.14.3`. We accept
    the verbose form too — the regex picks up the first
    `M.N.P` triple on the first non-blank line.
    """

    first_line = ""
    for line in text.splitlines():
        if line.strip():
            first_line = line.strip()
            break
    m = _VERSION_RE.search(first_line)
    if not m:
        raise ValueError(
            f"parse_version: no M.N.P triple in {first_line!r}"
        )
    return SvnVersion(
        major=int(m.group(1)),
        minor=int(m.group(2)),
        patch=int(m.group(3)),
        raw=first_line,
    )


# --------------------------------------------------------------------------- #
# status --xml
# --------------------------------------------------------------------------- #

# `svn status --xml` produces:
#
#   <status>
#     <target path=".">
#       <entry path="a.txt">
#         <wc-status item="modified" revision="1" props="none">
#           <commit revision="1">...</commit>
#         </wc-status>
#       </entry>
#       ...
#     </target>
#   </status>
#
# The `item` attribute is the working-copy status code. SVN's full set
# (per `svn help status`) includes: added, conflicted, deleted, external,
# ignored, incomplete, merged, missing, modified, none, normal,
# obstructed, replaced, unversioned. We map to FileState.

_SVN_STATUS_MAP = {
    "added": FileState.ADDED,
    "conflicted": FileState.CONFLICTED,
    "deleted": FileState.DELETED,
    "ignored": FileState.IGNORED,
    "modified": FileState.MODIFIED,
    "normal": FileState.UNCHANGED,
    "unversioned": FileState.UNTRACKED,
    "replaced": FileState.MODIFIED,   # treat replace as modify
    "missing": FileState.DELETED,     # file missing from disk
    "incomplete": FileState.MODIFIED, # interrupted update
    # "external", "obstructed", "merged", "none" deliberately not mapped;
    # they're edge cases handled by skipping the entry (see below).
}


def parse_status_xml(text: str) -> tuple[FileEntry, ...]:
    """Parse `svn status --xml` into a tuple of `FileEntry`.

    Empty/unmapped status items (e.g. `external`, `obstructed`,
    `none`) are skipped — they don't map to a meaningful working-copy
    state for Sange's purposes. Their presence in the raw XML is
    valid but not actionable through the unified `FileState`.

    Per the `FileEntry` invariant, `path` must be relative — we
    coerce any leading `./` and reject absolute paths.
    """

    if not text.strip():
        return ()

    root = ET.fromstring(text)
    entries: list[FileEntry] = []
    for entry_el in root.iter("entry"):
        path_raw = entry_el.get("path", "")
        wc = entry_el.find("wc-status")
        if wc is None:
            continue
        item = wc.get("item", "")
        state = _SVN_STATUS_MAP.get(item)
        if state is None:
            continue

        # Normalize the path. SVN reports `./relative` for the working-copy
        # root; trim that. Reject absolute paths to satisfy the FileEntry
        # invariant.
        path_str = path_raw
        if path_str.startswith("./"):
            path_str = path_str[2:]
        path = Path(path_str)
        if path.is_absolute():
            # An absolute path in `svn status` means the caller ran the
            # command from outside the working copy. The semantics aren't
            # right for FileEntry; skip with no error.
            continue
        if str(path) in ("", "."):
            # The target itself (the working-copy root); not a file entry.
            continue

        entries.append(FileEntry(path=path, state=state))

    return tuple(entries)


# --------------------------------------------------------------------------- #
# info --xml
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class SvnInfo:
    """Selected fields from `svn info --xml`.

    Fields:
      * `path`               — the path the info was queried about (often `.`).
      * `revision`           — the working-copy's current revision.
      * `kind`               — `dir` | `file` (the target's kind).
      * `url`                — the working-copy's URL in the repo.
      * `relative_url`       — relative-to-repo-root URL (`^/...`).
      * `repository_root`    — the repository's root URL.
      * `repository_uuid`    — the repository's UUID.
      * `wc_root_abs`        — absolute path to the working-copy root.
      * `schedule`           — `normal` | `add` | `delete` | `replace`.
      * `depth`              — `infinity` | `immediates` | `files` | `empty` | `exclude`.
      * `commit_revision`    — last-changed revision.
      * `commit_author`      — last-changed author (empty if no commits yet).
    """

    path: str
    revision: int
    kind: str
    url: str
    relative_url: str
    repository_root: str
    repository_uuid: str
    wc_root_abs: str
    schedule: str
    depth: str
    commit_revision: int
    commit_author: str


def _text_of(parent: ET.Element, tag: str) -> str:
    """Return the text of the first child named `tag`, or '' if missing."""

    child = parent.find(tag)
    if child is None or child.text is None:
        return ""
    return child.text


def parse_info_xml(text: str) -> SvnInfo:
    """Parse `svn info --xml` into an `SvnInfo` dataclass.

    Raises `ValueError` if the XML doesn't contain a single `<entry>`
    (the multi-entry case — querying info on multiple paths — is not
    supported by this parser; the driver always queries one path).
    """

    if not text.strip():
        raise ValueError("parse_info_xml: empty input")

    root = ET.fromstring(text)
    entries = list(root.iter("entry"))
    if len(entries) != 1:
        raise ValueError(
            f"parse_info_xml: expected exactly one <entry>, got {len(entries)}"
        )
    e = entries[0]

    rev_attr = e.get("revision", "")
    try:
        revision = int(rev_attr)
    except ValueError:
        revision = -1

    repo_el = e.find("repository")
    wc_el = e.find("wc-info")
    commit_el = e.find("commit")

    commit_rev = -1
    commit_author = ""
    if commit_el is not None:
        commit_rev_attr = commit_el.get("revision", "")
        try:
            commit_rev = int(commit_rev_attr)
        except ValueError:
            commit_rev = -1
        commit_author = _text_of(commit_el, "author")

    return SvnInfo(
        path=e.get("path", ""),
        revision=revision,
        kind=e.get("kind", ""),
        url=_text_of(e, "url"),
        relative_url=_text_of(e, "relative-url"),
        repository_root=_text_of(repo_el, "root") if repo_el is not None else "",
        repository_uuid=_text_of(repo_el, "uuid") if repo_el is not None else "",
        wc_root_abs=_text_of(wc_el, "wcroot-abspath") if wc_el is not None else "",
        schedule=_text_of(wc_el, "schedule") if wc_el is not None else "",
        depth=_text_of(wc_el, "depth") if wc_el is not None else "",
        commit_revision=commit_rev,
        commit_author=commit_author,
    )


__all__ = [
    "SvnInfo",
    "SvnVersion",
    "parse_info_xml",
    "parse_status_xml",
    "parse_version",
]
