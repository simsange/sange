"""`SvnDriver` — `VCSDriver` implementation for Subversion (T-100).

v0.5 first slice ships **detect + capabilities + status**. The
remaining read methods (log, diff, branches, current_branch,
remotes, tags, show_commit) and every write method raise
`NotImplementedError("T-100b")` until the follow-up commits land.

The class structure mirrors `sange.adapters.vcs.git.GitDriver`:
parser layer is pure (no subprocess); the driver orchestrates
subprocess + parser + Domain-model construction.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from sange.adapters.vcs._protocol import DriverCapabilities, DriverError
from sange.adapters.vcs.svn._subprocess import (
    SvnCommandFailed,
    run_svn,
)
from sange.adapters.vcs.svn.parsers import (
    SvnInfo,
    SvnVersion,
    parse_info_xml,
    parse_status_xml,
    parse_version,
)
from sange.core.models.repo import Repo
from sange.core.models.working_copy import WorkingCopyStatus

# --------------------------------------------------------------------------- #
# Errors
# --------------------------------------------------------------------------- #


class SvnRepoNotFound(DriverError):
    """Raised by `SvnDriver.detect` when the path isn't an SVN working copy."""


# --------------------------------------------------------------------------- #
# Capabilities
# --------------------------------------------------------------------------- #


def _build_capabilities() -> DriverCapabilities:
    """Build the SVN capability descriptor.

    Read once at import time via `svn --version --quiet`; tolerant of
    `svn` not being installed (returns a "version unknown" capability
    rather than raising — `SvnDriver.detect` is the right place to
    surface that failure).
    """

    try:
        text = run_svn(("--version", "--quiet"))
        version = parse_version(text)
        version_str = str(version)
    except DriverError:
        version_str = "unknown"

    # SVN does not support local branches in the git sense (a branch
    # is a directory copy + svn switch). No stash, no bisect, no rebase,
    # no LFS analog. Signed tags + history rewrite handled via svnadmin.
    return DriverCapabilities(
        vcs="svn",
        vcs_version=version_str,
        supports_stash=False,
        supports_bisect=False,
        supports_rebase=False,
        supports_lfs=False,
        supports_signed_tags=False,
        supports_history_rewrite=False,  # svnadmin dump+filter (not user-facing yet)
    )


# --------------------------------------------------------------------------- #
# SvnDriver
# --------------------------------------------------------------------------- #


class SvnDriver:
    """VCSDriver implementation for Subversion — read-only first slice.

    Implemented in this commit (T-100a):
      * `detect(path)`            → `Repo`
      * `capabilities`            → class attribute
      * `status(repo)`            → `WorkingCopyStatus`
      * `_info(repo)`             → `SvnInfo` (driver-internal helper)
      * `version()`               → `SvnVersion`

    Raise NotImplementedError("T-100b") in this commit:
      * `log`, `diff`, `branches`, `current_branch`, `remotes`, `tags`,
        `show_commit` — read ops, follow-up.
      * `add`, `remove`, `revert_working_copy`, `commit`, `branch_create`,
        `branch_delete`, `switch`, `fetch`, `pull`, `push`, `tag_create`,
        `tag_delete` — write ops, T-100c.

    The same `VCSDriver` Protocol surface means callers don't change
    based on VCS — `sange commits push` on an SVN working copy in v0.5
    will route through `SvnDriver.push()` once that lands.
    """

    capabilities: DriverCapabilities = _build_capabilities()

    # ----- factory / detection ---------------------------------------- #

    @classmethod
    def detect(cls, path: Path) -> Repo:
        """Return a `Repo` if `path` is inside an SVN working copy.

        Unlike git's `rev-parse --show-toplevel`, SVN's `info` doesn't
        walk up looking for the WC root — it fails on unversioned
        paths. So we walk up looking for `.svn/` first (SVN 1.7+ stores
        all working-copy metadata at the root only) and run `info`
        from there.

        Raises `SvnRepoNotFound` if no `.svn/` is found in any
        parent, or if `info` fails when called from the discovered root.
        """

        wc_root = cls._find_wc_root(path)
        if wc_root is None:
            raise SvnRepoNotFound(
                f"{path} is not inside an SVN working copy "
                f"(no .svn/ in any parent)"
            )

        try:
            xml = run_svn(("info", "--xml", "--non-interactive"), cwd=wc_root)
        except SvnCommandFailed as exc:
            raise SvnRepoNotFound(
                f"{wc_root}: svn info failed: {exc}"
            ) from exc

        try:
            info = parse_info_xml(xml)
        except ValueError as exc:
            raise SvnRepoNotFound(
                f"{wc_root}: svn info returned unexpected XML: {exc}"
            ) from exc

        if not info.wc_root_abs:
            raise SvnRepoNotFound(
                f"{wc_root}: svn info returned no <wcroot-abspath>; "
                "is this a pre-1.7 working copy?"
            )

        wc_root = Path(info.wc_root_abs).resolve()

        # SVN's "default branch" analog is `trunk`. We store it for
        # cross-VCS parity even though SVN itself doesn't enforce the
        # `trunk/branches/tags` convention.
        # The repository_root URL is the closest thing SVN has to a
        # "remote" — every operation against a working copy ultimately
        # talks to it.
        metadata: dict[str, str] = {
            "url": info.url,
            "relative_url": info.relative_url,
            "repository_uuid": info.repository_uuid,
            "revision": str(info.revision),
        }

        return Repo(
            path=wc_root,
            vcs="svn",
            remote=info.repository_root or None,
            default_branch="trunk",
            metadata=metadata,
        )

    @staticmethod
    def _find_wc_root(start: Path) -> Path | None:
        """Walk up from `start` looking for a `.svn/` directory.

        SVN 1.7+ stores all working-copy metadata at the WC root only,
        so the first ancestor (or `start` itself) containing `.svn/`
        is the root. Returns None if no `.svn/` is found before
        reaching the filesystem root.
        """

        try:
            current = start.resolve()
        except OSError:
            return None

        # If `start` is a regular file, begin from its parent.
        if current.is_file():
            current = current.parent

        while True:
            if (current / ".svn").is_dir():
                return current
            parent = current.parent
            if parent == current:
                # Hit the filesystem root.
                return None
            current = parent

    # ----- introspection ---------------------------------------------- #

    @classmethod
    def version(cls) -> SvnVersion:
        """Return the installed `svn` version."""

        text = run_svn(("--version", "--quiet"))
        return parse_version(text)

    def _info(self, repo: Repo) -> SvnInfo:
        """Return `svn info --xml` for the working-copy root."""

        xml = run_svn(("info", "--xml", "--non-interactive"), cwd=repo.path)
        return parse_info_xml(xml)

    # ----- read methods ----------------------------------------------- #

    def status(self, repo: Repo) -> WorkingCopyStatus:
        """Return the current working-copy status.

        Runs `svn status --xml` against the working-copy root and
        parses into the VCS-agnostic `WorkingCopyStatus`. Untracked
        files (`?` lines in human-readable output) are included as
        `FileState.UNTRACKED`.
        """

        xml = run_svn(("status", "--xml", "--non-interactive"), cwd=repo.path)
        entries = parse_status_xml(xml)
        return WorkingCopyStatus(
            entries=entries,
            branch=repo.default_branch,
        )

    # ----- not-yet-implemented surfaces ------------------------------- #

    def log(self, *_: Any, **__: Any) -> Any:
        raise NotImplementedError("T-100b: SvnDriver.log lands with the read-ops follow-up")

    def diff(self, *_: Any, **__: Any) -> Any:
        raise NotImplementedError("T-100b: SvnDriver.diff lands with the read-ops follow-up")

    def branches(self, *_: Any, **__: Any) -> Any:
        raise NotImplementedError("T-100b: SvnDriver.branches lands with the read-ops follow-up")

    def current_branch(self, *_: Any, **__: Any) -> Any:
        raise NotImplementedError("T-100b: SvnDriver.current_branch lands with the read-ops follow-up")

    def remotes(self, *_: Any, **__: Any) -> Any:
        raise NotImplementedError("T-100b: SvnDriver.remotes lands with the read-ops follow-up")

    def tags(self, *_: Any, **__: Any) -> Any:
        raise NotImplementedError("T-100b: SvnDriver.tags lands with the read-ops follow-up")

    def show_commit(self, *_: Any, **__: Any) -> Any:
        raise NotImplementedError("T-100b: SvnDriver.show_commit lands with the read-ops follow-up")

    # Write methods — T-100c.
    def add(self, *_: Any, **__: Any) -> Any:
        raise NotImplementedError("T-100c: SvnDriver write ops")

    def remove(self, *_: Any, **__: Any) -> Any:
        raise NotImplementedError("T-100c: SvnDriver write ops")

    def revert_working_copy(self, *_: Any, **__: Any) -> Any:
        raise NotImplementedError("T-100c: SvnDriver write ops")

    def commit(self, *_: Any, **__: Any) -> Any:
        raise NotImplementedError("T-100c: SvnDriver write ops")

    def branch_create(self, *_: Any, **__: Any) -> Any:
        raise NotImplementedError("T-100c: SvnDriver write ops")

    def branch_delete(self, *_: Any, **__: Any) -> Any:
        raise NotImplementedError("T-100c: SvnDriver write ops")

    def switch(self, *_: Any, **__: Any) -> Any:
        raise NotImplementedError("T-100c: SvnDriver write ops")

    def fetch(self, *_: Any, **__: Any) -> Any:
        raise NotImplementedError("T-100c: SvnDriver write ops (svn equivalent: update)")

    def pull(self, *_: Any, **__: Any) -> Any:
        raise NotImplementedError("T-100c: SvnDriver write ops (svn equivalent: update)")

    def push(self, *_: Any, **__: Any) -> Any:
        # In SVN, commit IS push — there's no local-then-push split.
        # The write-ops commit will route push to commit semantically.
        raise NotImplementedError("T-100c: SvnDriver write ops (svn semantics: push == commit)")

    def tag_create(self, *_: Any, **__: Any) -> Any:
        raise NotImplementedError("T-100c: SvnDriver write ops (svn equivalent: svn copy)")

    def tag_delete(self, *_: Any, **__: Any) -> Any:
        raise NotImplementedError("T-100c: SvnDriver write ops")


__all__ = ["SvnDriver", "SvnRepoNotFound"]
