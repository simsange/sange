"""`CommitRef` + `DiffSummary` — VCS-agnostic commit and diff models."""

from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass, field


@dataclass(frozen=True)
class CommitRef:
    """A single commit reference, abstracted across VCS kinds.

    The Adapter populates `sha` with whatever the underlying VCS uses as a
    stable identifier (Git's sha1/sha256, SVN's revision number rendered as
    a string, Hg's changeset hash, etc.). Code that consumes `CommitRef`
    treats the `sha` as opaque.

    Fields:
      * `sha`         — opaque VCS-specific commit identifier.
      * `subject`     — first line of the commit message (≤72 chars by
                        convention; Sange CLI enforces this for new commits).
      * `body`        — rest of the commit message (may be empty).
      * `author_name`/`author_email` — committer identity.
      * `committed_at` — when the commit landed (UTC).
      * `parents`     — list of parent SHAs (0 for the root commit, 2+ for
                        merge commits).
    """

    sha: str
    subject: str
    body: str = ""
    author_name: str = ""
    author_email: str = ""
    committed_at: _dt.datetime | None = None
    parents: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not self.sha:
            raise ValueError("CommitRef.sha must be non-empty")
        if not self.subject:
            raise ValueError("CommitRef.subject must be non-empty")
        # CR or CRLF in subjects breaks Markdown table rendering + the §6.8
        # commit-lifecycle JSON file naming. Reject early.
        if "\r" in self.subject or "\n" in self.subject:
            raise ValueError(
                f"CommitRef.subject must be a single line; got {self.subject!r}"
            )

    @property
    def short_sha(self) -> str:
        """First 12 characters of the SHA — useful for log display."""

        return self.sha[:12]

    @property
    def is_merge(self) -> bool:
        return len(self.parents) >= 2


@dataclass(frozen=True)
class DiffSummary:
    """Aggregate change statistics for a commit or pending working-copy change.

    Adapters compute this from `git diff --shortstat`, `svn diff --summarize`,
    `hg diff --stat`, etc. The `content_hash` is the Adapter's sha256 of the
    diff payload — used by the §6.8 commit lifecycle to detect when the
    staged set changed between draft and approval.

    Fields:
      * `files_changed` — count of files touched.
      * `insertions`    — total lines added.
      * `deletions`     — total lines removed.
      * `content_hash`  — sha256 hex of the diff content.
    """

    files_changed: int
    insertions: int
    deletions: int
    content_hash: str

    def __post_init__(self) -> None:
        if self.files_changed < 0 or self.insertions < 0 or self.deletions < 0:
            raise ValueError(
                f"DiffSummary counts must be non-negative; "
                f"got files={self.files_changed} +{self.insertions} -{self.deletions}"
            )
        if self.content_hash and len(self.content_hash) != 64:
            raise ValueError(
                f"DiffSummary.content_hash must be a 64-char sha256 or empty; "
                f"got {len(self.content_hash)} chars"
            )

    @property
    def net_lines(self) -> int:
        return self.insertions - self.deletions

    @property
    def is_empty(self) -> bool:
        return self.files_changed == 0


__all__ = ["CommitRef", "DiffSummary"]
