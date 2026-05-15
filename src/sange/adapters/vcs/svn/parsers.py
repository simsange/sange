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

import datetime as _dt
import re
from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree as ET

from sange.core.models.commit import CommitRef
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


# --------------------------------------------------------------------------- #
# log --xml
# --------------------------------------------------------------------------- #

# `svn log --xml --limit N` produces:
#
#   <log>
#     <logentry revision="N">
#       <author>alice</author>
#       <date>2026-05-15T21:16:49.101972Z</date>
#       <msg>multi-line message
#       continued</msg>
#     </logentry>
#     ...
#   </log>
#
# Some logentries may be missing <author> (anonymous commits in
# pre-authz repos) or <date> (rare; treated as epoch). <msg> may
# be empty.


def _parse_svn_date(text: str) -> _dt.datetime:
    """Parse an SVN ISO 8601 timestamp.

    SVN writes dates as `YYYY-MM-DDTHH:MM:SS.fZ` (microseconds + 'Z').
    Python's `_dt.datetime.fromisoformat` accepts that since 3.11.
    """

    if not text:
        return _dt.datetime(1970, 1, 1, tzinfo=_dt.UTC)
    # Replace trailing Z with +00:00 — fromisoformat in 3.11+ also
    # accepts the bare Z, but the explicit form is portable.
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = _dt.datetime.fromisoformat(text)
    except ValueError:
        return _dt.datetime(1970, 1, 1, tzinfo=_dt.UTC)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=_dt.UTC)
    return dt


def parse_log_xml(text: str) -> tuple[CommitRef, ...]:
    """Parse `svn log --xml` into a tuple of `CommitRef`.

    The CommitRef contract uses `sha` as opaque — we put the
    revision number (as a string) there. SVN's commit history is
    effectively linear from any working-copy's perspective, so
    `parents` is `()` for v0.5 (a future enhancement could pass
    `--use-merge-history` and reconstruct branched-from parents).

    Subject = first line of `<msg>`; body = remainder. Empty
    messages produce empty subject + empty body.

    Author email is left empty — `<author>` in SVN is a username,
    not an email address.
    """

    if not text.strip():
        return ()

    root = ET.fromstring(text)
    refs: list[CommitRef] = []
    for entry in root.iter("logentry"):
        rev = entry.get("revision", "")
        if not rev:
            continue
        author = _text_of(entry, "author")
        date_text = _text_of(entry, "date")
        msg = _text_of(entry, "msg") or ""
        # Split subject / body on first newline. CommitRef requires
        # a non-empty subject (per its __post_init__); SVN commits
        # with empty messages get a placeholder so the lifecycle
        # surface stays clean.
        if "\n" in msg:
            subject, body = msg.split("\n", 1)
            body = body.rstrip()
        else:
            subject, body = msg, ""
        if not subject:
            subject = "(no commit message)"
        refs.append(
            CommitRef(
                sha=rev,
                subject=subject,
                body=body,
                author_name=author,
                author_email="",
                committed_at=_parse_svn_date(date_text),
                parents=(),
            )
        )
    return tuple(refs)


# --------------------------------------------------------------------------- #
# ls --xml
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class SvnLsEntry:
    """One entry in `svn ls --xml <url>` output.

    Used by `branches()` + `tags()` to list directory children
    under `^/branches/` and `^/tags/`. The `revision` is the
    last-changed revision of the entry (which is what SVN
    treats as the "tip" of a branch).
    """

    name: str
    kind: str  # 'file' | 'dir'
    revision: int
    author: str
    date: _dt.datetime


def parse_ls_xml(text: str) -> tuple[SvnLsEntry, ...]:
    """Parse `svn ls --xml <url>` into a tuple of `SvnLsEntry`.

    Returns `()` for an empty listing (e.g. when `^/branches`
    exists but has no children).
    """

    if not text.strip():
        return ()

    root = ET.fromstring(text)
    entries: list[SvnLsEntry] = []
    for entry in root.iter("entry"):
        name = _text_of(entry, "name")
        if not name:
            continue
        kind = entry.get("kind", "")
        commit_el = entry.find("commit")
        rev = -1
        author = ""
        date_text = ""
        if commit_el is not None:
            try:
                rev = int(commit_el.get("revision", "-1"))
            except ValueError:
                rev = -1
            author = _text_of(commit_el, "author")
            date_text = _text_of(commit_el, "date")
        entries.append(
            SvnLsEntry(
                name=name,
                kind=kind,
                revision=rev,
                author=author,
                date=_parse_svn_date(date_text),
            )
        )
    return tuple(entries)


# --------------------------------------------------------------------------- #
# Branch / tag URL extraction
# --------------------------------------------------------------------------- #

# SVN doesn't enforce the `trunk / branches / tags` layout, but
# the convention is so universal that Sange treats it as the
# default. The relative-url from `svn info` looks like:
#
#   ^/trunk                  → branch "trunk"
#   ^/trunk/sub              → branch "trunk" (sub-path)
#   ^/branches/feature-x     → branch "feature-x"
#   ^/branches/feature-x/sub → branch "feature-x"
#   ^/tags/v1                → tag "v1" (NOT a branch)
#   ^/tags/v1/sub            → tag "v1"
#   ^/                       → no branch (working copy is at repo root)
#   ^/something-else         → no branch convention; return None
#
# `extract_branch_from_url` returns `(kind, name)` where kind is
# one of `'trunk' | 'branch' | 'tag'`. Tags are intentionally
# distinguished from branches; the SvnDriver translates tag URLs
# differently in `tags()` vs `branches()`.

_BRANCH_URL_RE = re.compile(r"^\^/(trunk|branches|tags)(?:/([^/]+))?(?:/.*)?$")


def extract_branch_from_url(relative_url: str) -> tuple[str, str] | None:
    """Map an SVN relative-url to ('trunk'|'branch'|'tag', name) or None.

    Returns None when the URL doesn't follow the trunk/branches/tags
    convention. The repo root (`^/`) returns None.
    """

    if not relative_url:
        return None
    m = _BRANCH_URL_RE.match(relative_url)
    if m is None:
        return None
    top = m.group(1)
    sub = m.group(2) or ""
    if top == "trunk":
        return ("trunk", "trunk")
    if top == "branches":
        if not sub:
            return None
        return ("branch", sub)
    if top == "tags":
        if not sub:
            return None
        return ("tag", sub)
    return None


# --------------------------------------------------------------------------- #
# diff stat (from unified-diff text)
# --------------------------------------------------------------------------- #

# SVN's `svn diff --summarize --xml` doesn't give insertion / deletion
# counts — only modified file paths. To compute the (files,
# insertions, deletions) triple that DiffSummary expects, we parse
# the unified-diff text directly: count `+` / `-` lines at the
# start of each line, EXCEPT the `+++ ` / `--- ` file headers.

_DIFF_FILE_HEADER_RE = re.compile(r"^(?:---|\+\+\+) ")


def parse_diff_stat(text: str) -> tuple[int, int, int]:
    """Count (files, insertions, deletions) from a unified-diff blob.

    Files: counted from `Index: <path>` lines (SVN's per-file
    marker; falls back to counting `+++ ` headers if absent).
    Insertions: `+` lines that aren't `+++ ` headers.
    Deletions: `-` lines that aren't `--- ` headers.
    """

    if not text:
        return (0, 0, 0)

    files = 0
    insertions = 0
    deletions = 0
    plus_headers = 0
    for line in text.splitlines():
        if line.startswith("Index: "):
            files += 1
            continue
        if _DIFF_FILE_HEADER_RE.match(line):
            if line.startswith("+++ "):
                plus_headers += 1
            continue
        if line.startswith("+"):
            insertions += 1
        elif line.startswith("-"):
            deletions += 1

    # If the diff was produced without `Index:` (rare; some
    # `svn diff` invocations elide it), use the `+++ ` count
    # as the file tally.
    if files == 0:
        files = plus_headers

    return (files, insertions, deletions)


__all__ = [
    "SvnInfo",
    "SvnLsEntry",
    "SvnVersion",
    "extract_branch_from_url",
    "parse_diff_stat",
    "parse_info_xml",
    "parse_log_xml",
    "parse_ls_xml",
    "parse_status_xml",
    "parse_version",
]
