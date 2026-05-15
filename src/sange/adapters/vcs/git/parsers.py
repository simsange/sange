"""Pure parsers for `git` machine-readable outputs.

Separated from `driver.py` so the parsers are fuzz-able + unit-testable
without subprocess. Each function takes text and returns a Domain object.

Parser inventory:
  * `parse_status_porcelain_v2(text)` → `WorkingCopyStatus`
  * `parse_log_records(text)` → tuple[CommitRef, ...]
  * `parse_branch_list(text)` → tuple[BranchInfo, ...]
  * `parse_remotes(text)` → tuple[RemoteInfo, ...]
  * `parse_tag_list(text)` → tuple[TagInfo, ...]
  * `parse_shortstat(text)` → (files_changed, insertions, deletions)
  * `parse_version(text)` → str

The format strings the driver uses live next to each parser as constants
so the round-trip is self-documenting.

Format choices:
  * `git status --porcelain=v2 --branch` — stable across versions,
    machine-friendly, branch + state in one call.
  * `git log --format=...` with NUL-delimited fields — robust against
    commit messages containing newlines, tabs, etc.
  * `git for-each-ref refs/heads/ --format=...` — branches with tracking,
    ahead/behind counts.
  * `git remote -v` — old but ubiquitous; parsing is straightforward.
  * `git tag --format=...` — lightweight + annotated tags in one call.
"""

from __future__ import annotations

import datetime as _dt
import re
from pathlib import Path

from sange.adapters.vcs._protocol import TagInfo
from sange.core.models import (
    BranchInfo,
    CommitRef,
    FileEntry,
    FileState,
    RemoteInfo,
    WorkingCopyStatus,
)

# --------------------------------------------------------------------------- #
# git status --porcelain=v2 --branch
# --------------------------------------------------------------------------- #


# Format spec excerpts (from `man git-status`):
#
#   # branch.head <head>
#   # branch.oid  <commit_or_initial>
#   # branch.upstream <upstream>
#   # branch.ab +<ahead> -<behind>
#
#   1 XY sub <mH> <mI> <mW> <hH> <hI> <path>          # ordinary
#   2 XY sub <mH> <mI> <mW> <hH> <hI> <X><score> <path><sep><origPath>  # renamed/copied
#   u XY ...                                          # unmerged
#   ? <path>                                          # untracked
#   ! <path>                                          # ignored
#
# Where XY is two characters: the staged + worktree statuses.


STATUS_PORCELAIN_V2_ARGS = ("status", "--porcelain=v2", "--branch")


_XY_TO_STATE = {
    # Staged states
    "A": FileState.ADDED,
    "M": FileState.MODIFIED,
    "D": FileState.DELETED,
    "R": FileState.RENAMED,
    "C": FileState.COPIED,
    "U": FileState.CONFLICTED,
}


def _classify_xy(xy: str) -> FileState:
    """Map a porcelain-v2 XY code to a `FileState`.

    Priority: staged code wins over worktree code; treat the file as the
    most-significant status. The exception: untracked + ignored already
    use the `?` / `!` line prefix and don't reach this function.
    """

    if len(xy) != 2:
        raise ValueError(f"XY must be 2 chars, got {xy!r}")
    staged, worktree = xy[0], xy[1]
    # Conflicted (any U in either position) → CONFLICTED first.
    if "U" in (staged, worktree):
        return FileState.CONFLICTED
    # Staged is the primary state; falls back to worktree for unmodified-staged.
    if staged != "." and staged in _XY_TO_STATE:
        return _XY_TO_STATE[staged]
    if worktree != "." and worktree in _XY_TO_STATE:
        return _XY_TO_STATE[worktree]
    return FileState.UNCHANGED


def parse_status_porcelain_v2(text: str) -> WorkingCopyStatus:
    """Parse `git status --porcelain=v2 --branch` output into WorkingCopyStatus.

    The format is line-oriented; each line starts with a code (`#`, `1`,
    `2`, `u`, `?`, `!`) that determines parsing. Renamed/copied lines (`2`)
    encode the source path after a separator we have to detect manually
    because `-z` would replace newlines with NULs and complicate every
    other parser. Here we use the non-`-z` form and split rename paths on
    tab — that's the documented separator without `-z`.
    """

    branch = ""
    entries: list[FileEntry] = []

    for line in text.splitlines():
        if not line:
            continue

        # ---- header lines (`# branch.head <name>` etc.) ------------- #
        if line.startswith("# branch.head "):
            branch = line[len("# branch.head "):].strip()
            continue
        if line.startswith("# "):
            # other header fields ignored for now (oid / upstream / ab)
            continue

        # ---- ordinary tracked file ---------------------------------- #
        if line.startswith("1 "):
            parts = line.split(" ", 8)
            if len(parts) < 9:
                continue
            xy = parts[1]
            path = parts[8]
            entries.append(
                FileEntry(path=Path(path), state=_classify_xy(xy))
            )
            continue

        # ---- renamed or copied file --------------------------------- #
        if line.startswith("2 "):
            # `2 XY sub <mH> <mI> <mW> <hH> <hI> <X><score> <path>\t<origPath>`
            parts = line.split(" ", 9)
            if len(parts) < 10:
                continue
            xy = parts[1]
            path_with_orig = parts[9]
            # Without -z, the path<TAB>origPath separator is a literal tab.
            if "\t" in path_with_orig:
                new_path, old_path = path_with_orig.split("\t", 1)
            else:
                new_path, old_path = path_with_orig, path_with_orig
            state = _classify_xy(xy)
            if state not in (FileState.RENAMED, FileState.COPIED):
                # Fall back — XY didn't have R/C even though we saw a `2` line.
                state = FileState.RENAMED
            entries.append(
                FileEntry(
                    path=Path(new_path),
                    state=state,
                    previous_path=Path(old_path),
                )
            )
            continue

        # ---- unmerged (conflict) ----------------------------------- #
        if line.startswith("u "):
            parts = line.split(" ", 10)
            if len(parts) < 11:
                continue
            path = parts[10]
            entries.append(
                FileEntry(path=Path(path), state=FileState.CONFLICTED)
            )
            continue

        # ---- untracked --------------------------------------------- #
        if line.startswith("? "):
            entries.append(
                FileEntry(path=Path(line[2:]), state=FileState.UNTRACKED)
            )
            continue

        # ---- ignored ----------------------------------------------- #
        if line.startswith("! "):
            entries.append(
                FileEntry(path=Path(line[2:]), state=FileState.IGNORED)
            )
            continue

    return WorkingCopyStatus(entries=tuple(entries), branch=branch)


# --------------------------------------------------------------------------- #
# git log --format=...
# --------------------------------------------------------------------------- #


# Use NUL between fields and a sentinel between records so commit messages
# containing tabs/newlines don't break the parser. The body is the last
# field so any newlines stay self-contained.
#
# Field order:
#   %H        — full hash
#   %an       — author name
#   %ae       — author email
#   %aI       — author timestamp ISO-8601-strict
#   %P        — parent hashes (space-separated)
#   %s        — subject (first commit-msg line)
#   %B        — full body (subject + body)
#
# Format: <fields>\x1f...\x1e (record separator)
_FIELD_SEP = "\x1f"
_RECORD_SEP = "\x1e"
LOG_PRETTY_FORMAT = (
    f"%H{_FIELD_SEP}%an{_FIELD_SEP}%ae{_FIELD_SEP}%aI"
    f"{_FIELD_SEP}%P{_FIELD_SEP}%s{_FIELD_SEP}%B{_RECORD_SEP}"
)


def parse_log_records(text: str) -> tuple[CommitRef, ...]:
    """Parse `git log --format=<LOG_PRETTY_FORMAT>` output → tuple[CommitRef]."""

    out: list[CommitRef] = []
    for raw_record in text.split(_RECORD_SEP):
        record = raw_record.strip("\n")
        if not record:
            continue
        fields = record.split(_FIELD_SEP)
        if len(fields) < 7:
            continue
        sha, author_name, author_email, ts_iso, parents, subject, body = fields[:7]
        if not sha:
            continue
        committed_at: _dt.datetime | None = None
        if ts_iso:
            try:
                committed_at = _dt.datetime.fromisoformat(ts_iso)
            except ValueError:
                committed_at = None
        parent_tuple = tuple(p for p in parents.split() if p)
        # `%B` includes the subject as its first line — strip if present.
        stripped_body = body.lstrip()
        if stripped_body.startswith(subject):
            stripped_body = stripped_body[len(subject):].lstrip("\n")
        out.append(
            CommitRef(
                sha=sha,
                subject=subject,
                body=stripped_body,
                author_name=author_name,
                author_email=author_email,
                committed_at=committed_at,
                parents=parent_tuple,
            )
        )
    return tuple(out)


# --------------------------------------------------------------------------- #
# git for-each-ref refs/heads/ --format=...
# --------------------------------------------------------------------------- #


# Field order: short-name | tip-hash | upstream-short | ahead | behind | HEAD-flag
#   %(refname:short)
#   %(objectname)
#   %(upstream:short)
#   %(upstream:track,nobracket)     → "ahead 3, behind 2" or "" or "[gone]"
#   %(HEAD)                         → "*" or " "
_BR_SEP = "\x1f"
BRANCH_FORMAT = (
    f"%(refname:short){_BR_SEP}%(objectname){_BR_SEP}"
    f"%(upstream:short){_BR_SEP}%(upstream:track,nobracket){_BR_SEP}%(HEAD)"
)
BRANCH_LIST_ARGS = (
    "for-each-ref", "refs/heads/", f"--format={BRANCH_FORMAT}",
)


_TRACK_RE = re.compile(r"(?:ahead\s+(\d+))?(?:,\s*)?(?:behind\s+(\d+))?")


def _parse_track_field(track: str) -> tuple[int | None, int | None]:
    """Parse the `%(upstream:track,nobracket)` field.

    Examples it produces:
      ""                  — no upstream OR perfectly in-sync
      "ahead 3"           — 3 ahead, 0 behind
      "behind 2"          — 0 ahead, 2 behind
      "ahead 3, behind 2" — both
      "gone"              — upstream is gone (return None, None)
    """

    track = track.strip()
    if not track:
        return None, None
    if track == "gone":
        return None, None
    ahead = 0
    behind = 0
    found_anything = False
    m = re.search(r"ahead\s+(\d+)", track)
    if m:
        ahead = int(m.group(1))
        found_anything = True
    m = re.search(r"behind\s+(\d+)", track)
    if m:
        behind = int(m.group(1))
        found_anything = True
    if not found_anything:
        return None, None
    return ahead, behind


def parse_branch_list(text: str) -> tuple[BranchInfo, ...]:
    """Parse `for-each-ref refs/heads/` output → tuple[BranchInfo]."""

    out: list[BranchInfo] = []
    for line in text.splitlines():
        if not line:
            continue
        parts = line.split(_BR_SEP)
        if len(parts) < 5:
            continue
        name, tip_sha, upstream_short, track, head_flag = parts[:5]
        if not name or not tip_sha:
            continue
        tracking = upstream_short if upstream_short else None
        ahead, behind = _parse_track_field(track) if tracking else (None, None)
        is_current = head_flag.strip() == "*"
        out.append(
            BranchInfo(
                name=name,
                tip_sha=tip_sha,
                tracking=tracking,
                ahead=ahead,
                behind=behind,
                is_current=is_current,
            )
        )
    return tuple(out)


# --------------------------------------------------------------------------- #
# git remote -v
# --------------------------------------------------------------------------- #


REMOTE_LIST_ARGS = ("remote", "-v")


def parse_remotes(text: str) -> tuple[RemoteInfo, ...]:
    """Parse `git remote -v` output → tuple[RemoteInfo].

    The output looks like:
      origin    git@github.com:foo/bar.git (fetch)
      origin    git@github.com:foo/bar.git (push)

    We dedupe by (name, url) since fetch/push URLs are usually identical.
    """

    seen: dict[tuple[str, str], None] = {}
    for line in text.splitlines():
        parts = line.split()
        if len(parts) < 2:
            continue
        name, url = parts[0], parts[1]
        seen.setdefault((name, url), None)
    return tuple(RemoteInfo(name=n, url=u) for (n, u) in seen)


# --------------------------------------------------------------------------- #
# git tag --format=...
# --------------------------------------------------------------------------- #


# Field order: name | target-hash | objecttype | subject | gpgsign-status
#   %(refname:short)
#   %(*objectname) || %(objectname)  — target sha for annotated/lightweight
#   %(objecttype)                    — "tag" for annotated, "commit" for lightweight
#   %(contents:subject)              — annotation message
_TAG_SEP = "\x1f"
TAG_FORMAT = (
    f"%(refname:short){_TAG_SEP}"
    f"%(if)%(*objectname)%(then)%(*objectname)%(else)%(objectname)%(end)"
    f"{_TAG_SEP}%(objecttype){_TAG_SEP}%(contents:subject)"
)
TAG_LIST_ARGS = ("tag", f"--format={TAG_FORMAT}")


def parse_tag_list(text: str) -> tuple[TagInfo, ...]:
    """Parse `git tag --format=<TAG_FORMAT>` output → tuple[TagInfo]."""

    out: list[TagInfo] = []
    for line in text.splitlines():
        if not line:
            continue
        parts = line.split(_TAG_SEP)
        if len(parts) < 4:
            # Lightweight tags missing the message field — pad.
            parts += [""] * (4 - len(parts))
        name, target_sha, object_type, message = parts[:4]
        if not name:
            continue
        is_annotated = object_type == "tag"
        out.append(
            TagInfo(
                name=name,
                target_sha=target_sha,
                is_annotated=is_annotated,
                # Signature detection happens via a separate
                # `git verify-tag` probe; the format string can't tell
                # us cheaply. T-005 (write side) will set is_signed
                # when it creates signed tags.
                is_signed=False,
                message=message,
            )
        )
    return tuple(out)


# --------------------------------------------------------------------------- #
# git diff --shortstat
# --------------------------------------------------------------------------- #


_SHORTSTAT_RE = re.compile(
    r"(?P<files>\d+)\s+files?\s+changed"
    r"(?:,\s+(?P<ins>\d+)\s+insertion[s]?\(\+\))?"
    r"(?:,\s+(?P<dels>\d+)\s+deletion[s]?\(\-\))?"
)


def parse_shortstat(text: str) -> tuple[int, int, int]:
    """Parse `git diff --shortstat` output → (files_changed, insertions, deletions).

    Empty input → (0, 0, 0).
    """

    text = text.strip()
    if not text:
        return (0, 0, 0)
    m = _SHORTSTAT_RE.search(text)
    if not m:
        return (0, 0, 0)
    files = int(m.group("files") or 0)
    ins = int(m.group("ins") or 0)
    dels = int(m.group("dels") or 0)
    return (files, ins, dels)


# --------------------------------------------------------------------------- #
# git --version
# --------------------------------------------------------------------------- #


def parse_version(text: str) -> str:
    """Strip `git --version` output to a clean version string.

    Example input:  "git version 2.51.0\\n"
    Example output: "git 2.51.0"
    """

    stripped = text.strip()
    if stripped.startswith("git version "):
        return "git " + stripped.removeprefix("git version ")
    return stripped or "git ?"


__all__ = [
    "BRANCH_FORMAT",
    "BRANCH_LIST_ARGS",
    "LOG_PRETTY_FORMAT",
    "REMOTE_LIST_ARGS",
    "STATUS_PORCELAIN_V2_ARGS",
    "TAG_FORMAT",
    "TAG_LIST_ARGS",
    "parse_branch_list",
    "parse_log_records",
    "parse_remotes",
    "parse_shortstat",
    "parse_status_porcelain_v2",
    "parse_tag_list",
    "parse_version",
]
