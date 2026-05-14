"""`WorkingCopyStatus` + `FileEntry` — VCS-agnostic working-copy state."""

from __future__ import annotations

import enum
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path


class FileState(str, enum.Enum):
    """The state of a single file in the working copy.

    Adapters translate VCS-specific status codes (`git status -s` flags,
    `svn status` letters, `hg status` flags) into this enum. The mapping
    is documented per-adapter; the rest of Sange consumes the enum.
    """

    UNTRACKED = "untracked"   # Not under version control
    ADDED = "added"           # Staged for add / scheduled for add
    MODIFIED = "modified"     # Tracked + edited
    DELETED = "deleted"       # Tracked + removed
    RENAMED = "renamed"       # Tracked + renamed (Git, SVN copy)
    COPIED = "copied"         # Tracked + copied (Git -M / SVN copy)
    CONFLICTED = "conflicted" # Merge/update conflict
    IGNORED = "ignored"       # Matched .gitignore / svn:ignore / .hgignore
    UNCHANGED = "unchanged"   # Tracked + clean

    @classmethod
    def all_dirty(cls) -> tuple["FileState", ...]:
        """States that represent uncommitted changes (excludes IGNORED + UNCHANGED)."""

        return (
            cls.UNTRACKED, cls.ADDED, cls.MODIFIED,
            cls.DELETED, cls.RENAMED, cls.COPIED, cls.CONFLICTED,
        )


@dataclass(frozen=True)
class FileEntry:
    """One entry in a `WorkingCopyStatus`.

    Fields:
      * `path`           — file path relative to the repo root.
      * `state`          — `FileState` describing the file's status.
      * `previous_path`  — for RENAMED/COPIED entries, the source path
                            (None otherwise).
    """

    path: Path
    state: FileState
    previous_path: Path | None = None

    def __post_init__(self) -> None:
        if self.path.is_absolute():
            raise ValueError(
                f"FileEntry.path must be relative to the repo root; "
                f"got absolute {self.path!r}"
            )
        if self.state in (FileState.RENAMED, FileState.COPIED):
            if self.previous_path is None:
                raise ValueError(
                    f"FileEntry({self.path!r}, state={self.state.value}): "
                    "previous_path required for RENAMED/COPIED"
                )
        else:
            if self.previous_path is not None:
                raise ValueError(
                    f"FileEntry({self.path!r}, state={self.state.value}): "
                    "previous_path only valid for RENAMED/COPIED"
                )


@dataclass(frozen=True)
class WorkingCopyStatus:
    """Aggregate working-copy state — every file the adapter knows about.

    Constructed by an Adapter (e.g. `GitDriver.status(repo)`); the rest of
    Sange operates on the entries + counts.

    Fields:
      * `entries`     — sorted by path; one `FileEntry` per file.
      * `branch`      — current branch name (or detached-HEAD synthetic name).
    """

    entries: tuple[FileEntry, ...]
    branch: str = ""

    def __post_init__(self) -> None:
        # Force tuple (callers may pass list).
        object.__setattr__(self, "entries", tuple(self.entries))
        # Deterministic sort by path so adapters don't have to.
        sorted_entries = tuple(
            sorted(self.entries, key=lambda e: str(e.path))
        )
        object.__setattr__(self, "entries", sorted_entries)

    # ----- convenience accessors -------------------------------------- #

    def by_state(self, state: FileState) -> tuple[FileEntry, ...]:
        return tuple(e for e in self.entries if e.state is state)

    def dirty_entries(self) -> tuple[FileEntry, ...]:
        """All entries with uncommitted changes."""

        dirty = set(FileState.all_dirty())
        return tuple(e for e in self.entries if e.state in dirty)

    @property
    def is_clean(self) -> bool:
        """True iff no uncommitted changes (ignoring untracked-files-only — see is_pristine)."""

        return not self.dirty_entries()

    @property
    def is_pristine(self) -> bool:
        """True iff no entries at all (truly clean — no untracked files either)."""

        return not self.entries

    def count(self, state: FileState) -> int:
        return sum(1 for e in self.entries if e.state is state)

    def total(self) -> int:
        return len(self.entries)


__all__ = ["FileEntry", "FileState", "WorkingCopyStatus"]
