"""`VCSDriver` Protocol — the contract every VCS adapter implements.

Per §6.2 of the architecture prompt. Defines the minimum surface Sange's
Application + Domain layers depend on; concrete adapters (`GitDriver`,
`SvnDriver`, `HgDriver`, `P4Driver`) implement this Protocol.

Design rules:

  * **Structural subtyping via `typing.Protocol`**. Adapters don't need to
    inherit — they just need matching method signatures. Mypy / Pyright
    enforce the contract statically; runtime introspection via
    `isinstance(driver, VCSDriver)` is intentionally NOT supported
    (Protocols are static-typing constructs unless decorated with
    `@runtime_checkable`).
  * **Domain-typed returns**. Methods return `CommitRef` / `BranchInfo` /
    `WorkingCopyStatus` / `DiffSummary` — never VCS-specific shapes.
  * **Side effects are explicit**. Read-only methods (`status`, `log`,
    `diff`) are pure; mutating methods (`add`, `commit`, `push`, `tag_create`)
    document their effect + may raise `DriverError` on failure.
  * **Capability sub-Protocols**. Operations that don't apply to every
    VCS (stash, bisect, rebase, LFS) live in optional sub-Protocols. An
    adapter that doesn't support stash simply doesn't satisfy `SupportsStash`.
  * **Fluent / chainable wrappers** (ADR-025) are NOT on the Protocol —
    they live in the concrete adapter modules. The Protocol is the
    minimum imperative surface; chainable façades are sugar on top.
  * **No subprocess details**. The Protocol doesn't expose subprocess
    handles, stdout pipes, or exit codes. Adapters translate those into
    `DriverError` exceptions with structured details.
"""

from __future__ import annotations

import datetime as _dt
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol, runtime_checkable

from sange.core.models import (
    BranchInfo,
    CommitRef,
    DiffSummary,
    RemoteInfo,
    Repo,
    VCSKind,
    WorkingCopyStatus,
)


# --------------------------------------------------------------------------- #
# Exceptions
# --------------------------------------------------------------------------- #


class DriverError(Exception):
    """Base exception for VCS adapter failures.

    Concrete adapters subclass for VCS-specific situations
    (`GitNotInstalled`, `SvnAuthenticationRequired`, etc.) but never raise
    raw `subprocess.CalledProcessError` or `OSError` into the Application
    layer.
    """


# --------------------------------------------------------------------------- #
# Auxiliary result shapes
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class PushResult:
    """The outcome of a `VCSDriver.push()` call.

    Fields:
      * `remote`      — the remote name pushed to.
      * `refs_updated` — list of `(local_ref, remote_ref)` tuples that the
                          push moved forward.
      * `was_no_op`   — True when there was nothing new to push.
      * `forced`      — True when the operator passed force flags (Git's
                          `--force` / `--force-with-lease`, SVN N/A,
                          Hg's `--force`). Audit-logged separately.
    """

    remote: str
    refs_updated: tuple[tuple[str, str], ...] = field(default_factory=tuple)
    was_no_op: bool = False
    forced: bool = False


@dataclass(frozen=True)
class TagInfo:
    """A tag reference — VCS-agnostic.

    Fields:
      * `name`         — tag name (Git/Hg) or branch-tag URL leaf (SVN).
      * `target_sha`   — SHA the tag points to.
      * `is_annotated` — True for `git tag -a` / signed Hg tags.
      * `is_signed`    — True for `git tag -s` / GPG-signed tags.
      * `message`      — annotation message (empty for lightweight tags).
      * `created_at`   — when the tag was created (UTC), or None when the
                          adapter can't determine it cheaply.
    """

    name: str
    target_sha: str
    is_annotated: bool = False
    is_signed: bool = False
    message: str = ""
    created_at: _dt.datetime | None = None


@dataclass(frozen=True)
class DriverCapabilities:
    """Declarative descriptor an adapter exposes for introspection.

    `sange doctor` reads each registered adapter's `.capabilities` to surface
    "your Git version supports X but not Y" warnings.

    Fields:
      * `vcs`               — which `VCSKind` this adapter implements.
      * `vcs_version`       — the installed binary version (`"git 2.51.0"`).
      * `supports_stash`    — does this adapter satisfy `SupportsStash`?
      * `supports_bisect`   — does this adapter satisfy `SupportsBisect`?
      * `supports_rebase`   — does this adapter satisfy `SupportsRebase`?
      * `supports_lfs`      — does this adapter satisfy `SupportsLFS`?
      * `supports_signed_tags` — does this adapter ship signed-tag support?
      * `supports_history_rewrite` — does the §6.11 purge subsystem have an
                                       executor for this VCS?
      * `notes`             — free-form caveats surfaced in `sange doctor`.
    """

    vcs: VCSKind
    vcs_version: str
    supports_stash: bool = False
    supports_bisect: bool = False
    supports_rebase: bool = False
    supports_lfs: bool = False
    supports_signed_tags: bool = True
    supports_history_rewrite: bool = False
    notes: tuple[str, ...] = field(default_factory=tuple)


# --------------------------------------------------------------------------- #
# Core VCSDriver Protocol
# --------------------------------------------------------------------------- #


class VCSDriver(Protocol):
    """The minimum surface every VCS adapter implements.

    Adapters live in `sange/adapters/vcs/<vcs>.py`. Each adapter exposes a
    `Driver` class that satisfies this Protocol (and optionally one or
    more capability sub-Protocols below).

    All path arguments are repo-relative `Path` objects unless documented
    otherwise. Absolute paths are explicitly rejected with `DriverError`.
    """

    # ----- capability descriptor + factory ----------------------------- #

    capabilities: DriverCapabilities

    @classmethod
    def detect(cls, path: Path) -> Repo:
        """Inspect `path` and return a `Repo` if this driver recognizes it.

        Raises `DriverError` if `path` is not a repository this driver can
        handle. Stateless — multiple `detect()` calls on the same path
        return equal `Repo` objects.
        """
        ...

    # ----- read-only -------------------------------------------------- #

    def status(self, repo: Repo) -> WorkingCopyStatus:
        """Return the current working-copy status."""
        ...

    def log(
        self,
        repo: Repo,
        *,
        revision_range: str = "",
        max_count: int | None = None,
    ) -> tuple[CommitRef, ...]:
        """Return commits in `revision_range` (newest first).

        `revision_range`: VCS-specific (`HEAD~10..HEAD`, `r100:HEAD`, etc.).
        Empty string defaults to "all reachable from HEAD" subject to
        `max_count`.
        """
        ...

    def diff(
        self,
        repo: Repo,
        *,
        paths: Sequence[Path] = (),
        revision_range: str = "",
    ) -> DiffSummary:
        """Aggregate diff statistics for the given paths / revision range."""
        ...

    def branches(self, repo: Repo) -> tuple[BranchInfo, ...]:
        """List all local branches (current branch first)."""
        ...

    def current_branch(self, repo: Repo) -> BranchInfo | None:
        """Return the active branch, or None for detached-HEAD states."""
        ...

    def remotes(self, repo: Repo) -> tuple[RemoteInfo, ...]:
        """Return configured remotes (Git/Hg) or the canonical repo URL (SVN)."""
        ...

    def tags(self, repo: Repo) -> tuple[TagInfo, ...]:
        """List all tags."""
        ...

    def show_commit(self, repo: Repo, sha: str) -> CommitRef:
        """Resolve a single commit by SHA. Raises `DriverError` if not found."""
        ...

    # ----- mutating: staging ------------------------------------------ #

    def add(self, repo: Repo, paths: Sequence[Path]) -> None:
        """Stage `paths` (Git index / SVN scheduled-for-add / Hg add)."""
        ...

    def remove(self, repo: Repo, paths: Sequence[Path], *, force: bool = False) -> None:
        """Remove `paths` from the working copy and stage the deletion.

        `force=True` allows removing files with uncommitted changes (Git's
        `--force`, SVN equivalent). The §6.8 commit lifecycle's
        approve-on-destructive gate intercepts this before it lands.
        """
        ...

    def revert_working_copy(self, repo: Repo, paths: Sequence[Path]) -> None:
        """Discard uncommitted changes to `paths` (Git's `git restore`,
        SVN's `svn revert`, Hg's `hg revert`).

        DESTRUCTIVE — paired with a type-to-confirm gate at the CLI layer.
        """
        ...

    # ----- mutating: commit ------------------------------------------- #

    def commit(
        self,
        repo: Repo,
        *,
        message: str,
        author_name: str = "",
        author_email: str = "",
        allow_empty: bool = False,
        sign: bool = False,
    ) -> CommitRef:
        """Create a new commit from the staged content."""
        ...

    # ----- mutating: branch ------------------------------------------- #

    def branch_create(self, repo: Repo, name: str, *, base: str = "") -> BranchInfo:
        """Create a new branch off `base` (default: current branch / HEAD)."""
        ...

    def branch_delete(self, repo: Repo, name: str, *, force: bool = False) -> None:
        """Delete branch `name`. `force=True` deletes unmerged branches."""
        ...

    def switch(self, repo: Repo, branch: str) -> BranchInfo:
        """Switch the working copy to `branch` (Git's `switch`, SVN's
        `svn switch <branch-url>`, Hg's `hg update <branch>`)."""
        ...

    # ----- mutating: remote ------------------------------------------- #

    def fetch(self, repo: Repo, remote: str = "") -> None:
        """Fetch updates from `remote` (or all remotes if empty)."""
        ...

    def pull(self, repo: Repo, remote: str = "") -> None:
        """Fetch + integrate (merge or rebase per config).

        For SVN: equivalent to `svn update`.
        """
        ...

    def push(
        self,
        repo: Repo,
        *,
        remote: str = "",
        branch: str = "",
        force: bool = False,
        force_with_lease: bool = False,
    ) -> PushResult:
        """Push local commits to `remote/branch`.

        `force_with_lease` is preferred over `force` when supported (Git);
        adapters that don't distinguish raise `DriverError` if both are set.
        """
        ...

    # ----- mutating: tag ----------------------------------------------- #

    def tag_create(
        self,
        repo: Repo,
        name: str,
        *,
        target_sha: str = "",
        message: str = "",
        sign: bool = False,
    ) -> TagInfo:
        """Create a tag.

        * `target_sha` empty → tag HEAD.
        * `message` empty → lightweight tag (Git); annotated otherwise.
        * `sign=True` → GPG/sigstore signature (depends on adapter +
          configuration).
        """
        ...

    def tag_delete(self, repo: Repo, name: str) -> None:
        """Delete tag `name` from the local repository.

        Deleting from the remote is a separate operation handled at the
        Application layer (§6.9 release-engineering pipeline).
        """
        ...


# --------------------------------------------------------------------------- #
# Optional capability sub-Protocols
# --------------------------------------------------------------------------- #


class SupportsStash(Protocol):
    """For Git stash + Hg shelve."""

    def stash_push(self, repo: Repo, *, message: str = "") -> str:
        """Set aside uncommitted changes. Returns the stash ref/id."""
        ...

    def stash_pop(self, repo: Repo, *, stash_id: str = "") -> None:
        """Restore the most-recent stash (or `stash_id`)."""
        ...

    def stash_list(self, repo: Repo) -> tuple[str, ...]:
        """Return stash refs/ids, newest first."""
        ...


class SupportsBisect(Protocol):
    """For Git / Hg / Fossil bisect — binary-search regression hunt."""

    def bisect_start(self, repo: Repo, *, bad_sha: str, good_sha: str) -> None: ...
    def bisect_good(self, repo: Repo) -> CommitRef | None: ...
    def bisect_bad(self, repo: Repo) -> CommitRef | None: ...
    def bisect_reset(self, repo: Repo) -> None: ...


class SupportsRebase(Protocol):
    """For Git + Hg — local history rewrite.

    SVN + Fossil are intentionally rebase-free; the §6.11 purge subsystem
    is the only way to rewrite their history.
    """

    def rebase(
        self,
        repo: Repo,
        *,
        onto: str,
        interactive: bool = False,
    ) -> None: ...

    def rebase_abort(self, repo: Repo) -> None: ...


class SupportsLFS(Protocol):
    """For Git LFS + Hg largefiles."""

    def lfs_track(self, repo: Repo, pattern: str) -> None: ...
    def lfs_untrack(self, repo: Repo, pattern: str) -> None: ...
    def lfs_status(self, repo: Repo) -> tuple[Path, ...]:
        """Return paths currently tracked under LFS."""
        ...


# --------------------------------------------------------------------------- #
# Runtime introspection helper
# --------------------------------------------------------------------------- #


@runtime_checkable
class _IntrospectibleVCSDriver(Protocol):
    """Internal helper for `isinstance()` checks at the Application boundary.

    Mirrors `VCSDriver` but is `@runtime_checkable`. Tests + the doctor
    code use this for "does this object look like a driver?" probes.
    `VCSDriver` itself is NOT runtime-checkable because Protocols with
    many methods are slow to runtime-check.
    """

    capabilities: DriverCapabilities

    def status(self, repo: Repo) -> WorkingCopyStatus: ...
    def commit(self, repo: Repo, *, message: str, **kwargs: object) -> CommitRef: ...


__all__ = [
    "DriverCapabilities",
    "DriverError",
    "PushResult",
    "SupportsBisect",
    "SupportsLFS",
    "SupportsRebase",
    "SupportsStash",
    "TagInfo",
    "VCSDriver",
]
