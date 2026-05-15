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

import hashlib
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from sange.adapters.vcs._protocol import (
    DriverCapabilities,
    DriverError,
    TagInfo,
)
from sange.adapters.vcs.svn._subprocess import (
    SvnCommandFailed,
    run_svn,
)
from sange.adapters.vcs.svn.parsers import (
    SvnInfo,
    SvnVersion,
    extract_branch_from_url,
    parse_diff_stat,
    parse_info_xml,
    parse_log_xml,
    parse_ls_xml,
    parse_status_xml,
    parse_version,
)
from sange.core.models.branch import BranchInfo, RemoteInfo
from sange.core.models.commit import CommitRef, DiffSummary
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

    # ----- log -------------------------------------------------------- #

    def log(
        self,
        repo: Repo,
        *,
        revision_range: str = "",
        max_count: int | None = None,
    ) -> tuple[CommitRef, ...]:
        """Return revision history (newest first).

        `revision_range` follows SVN's `-r` syntax: `BASE:HEAD`,
        `42:50`, `HEAD:1`, etc. `max_count` maps to `--limit`.
        """

        # SVN rejects `--limit 0` ("Argument to --limit must be positive"),
        # so short-circuit that case before invoking the subprocess. None
        # or negative means "no limit"; 0 means "no results"; positive
        # is `--limit N`.
        if max_count == 0:
            return ()

        args: list[str] = ["log", "--xml", "--non-interactive"]
        if revision_range:
            args.extend(("-r", revision_range))
        if max_count is not None and max_count > 0:
            args.extend(("--limit", str(max_count)))
        out = run_svn(args, cwd=repo.path)
        return parse_log_xml(out)

    # ----- diff ------------------------------------------------------- #

    def diff(
        self,
        repo: Repo,
        *,
        paths: Sequence[Path] = (),
        revision_range: str = "",
    ) -> DiffSummary:
        """Aggregate diff statistics + content hash.

        SVN doesn't have a clean `--shortstat` equivalent — we compute
        (files, insertions, deletions) by parsing the unified diff
        directly via `parse_diff_stat`. The content_hash is sha256 of
        the diff payload, matching Git adapter semantics.
        """

        args: list[str] = ["diff", "--non-interactive"]
        if revision_range:
            args.extend(("-r", revision_range))
        for p in paths:
            args.append(str(p))
        diff_out = run_svn(args, cwd=repo.path)

        files, ins, dels = parse_diff_stat(diff_out)
        if files == 0 and ins == 0 and dels == 0:
            return DiffSummary(
                files_changed=0, insertions=0, deletions=0, content_hash=""
            )
        content_hash = hashlib.sha256(diff_out.encode("utf-8")).hexdigest()
        return DiffSummary(
            files_changed=files,
            insertions=ins,
            deletions=dels,
            content_hash=content_hash,
        )

    # ----- branches --------------------------------------------------- #

    def branches(self, repo: Repo) -> tuple[BranchInfo, ...]:
        """List branches under the conventional `^/branches/` URL plus trunk.

        SVN doesn't enforce the `trunk/branches/tags` layout. If
        `^/branches` doesn't exist, we still return `trunk` (when
        `^/trunk` exists). If neither exists, we return `()` rather
        than raising — the caller can detect "no convention" and act
        accordingly.
        """

        current = self.current_branch(repo)
        result: list[BranchInfo] = []

        trunk_exists = self._ls_exists(repo, "^/trunk")
        if trunk_exists:
            tip = self._ls_tip_revision(repo, "^/trunk")
            result.append(
                BranchInfo(
                    name="trunk",
                    tip_sha=str(tip) if tip >= 0 else "",
                    tracking=None,
                    is_current=(current is not None and current.name == "trunk"),
                )
            )

        branches_xml = run_svn(
            ("ls", "--xml", "--non-interactive", "^/branches"),
            cwd=repo.path,
            allow_failure=True,
        )
        if branches_xml:
            for entry in parse_ls_xml(branches_xml):
                if entry.kind != "dir":
                    continue
                result.append(
                    BranchInfo(
                        name=entry.name,
                        tip_sha=str(entry.revision) if entry.revision >= 0 else "",
                        tracking=None,
                        is_current=(
                            current is not None and current.name == entry.name
                        ),
                    )
                )

        # Sort: current first, then alphabetical.
        return tuple(sorted(result, key=lambda b: (not b.is_current, b.name)))

    def current_branch(self, repo: Repo) -> BranchInfo | None:
        """Derive the current branch from `repo.metadata['relative_url']`.

        Returns None if the WC's URL doesn't follow the
        trunk/branches/tags convention, or points at a tag (tags
        aren't branches).
        """

        rel = repo.metadata.get("relative_url", "")
        if not rel:
            # Fresh detect — query svn info now.
            info = self._info(repo)
            rel = info.relative_url

        extracted = extract_branch_from_url(rel)
        if extracted is None:
            return None
        kind, name = extracted
        if kind == "tag":
            return None  # Tags aren't branches.

        # Last-commit revision from info is the closest analog to "tip".
        info = self._info(repo)
        tip = str(info.revision) if info.revision >= 0 else ""

        return BranchInfo(
            name=name,
            tip_sha=tip,
            tracking=None,
            is_current=True,
        )

    # ----- remotes ---------------------------------------------------- #

    def remotes(self, repo: Repo) -> tuple[RemoteInfo, ...]:
        """SVN has a single canonical remote — the repository root URL.

        We return it under the conventional name `origin` so cross-VCS
        tooling can treat SVN + Git uniformly.
        """

        url = repo.remote
        if not url:
            return ()
        return (RemoteInfo(name="origin", url=url),)

    # ----- tags ------------------------------------------------------- #

    def tags(self, repo: Repo) -> tuple[TagInfo, ...]:
        """List tags under the conventional `^/tags/` URL.

        Returns `()` if `^/tags` doesn't exist.
        """

        out = run_svn(
            ("ls", "--xml", "--non-interactive", "^/tags"),
            cwd=repo.path,
            allow_failure=True,
        )
        if not out:
            return ()

        result: list[TagInfo] = []
        for entry in parse_ls_xml(out):
            if entry.kind != "dir":
                continue
            result.append(
                TagInfo(
                    name=entry.name,
                    target_sha=str(entry.revision) if entry.revision >= 0 else "",
                    is_annotated=False,  # SVN tags are dir-copies.
                    is_signed=False,
                    message="",
                    created_at=entry.date,
                )
            )
        return tuple(result)

    # ----- show commit ------------------------------------------------ #

    def show_commit(self, repo: Repo, sha: str) -> CommitRef:
        """Return a single CommitRef for the given revision.

        SVN uses revision numbers (or `HEAD` / `BASE` / `PREV` /
        `COMMITTED`) as the opaque `sha` field. Accepts any value
        SVN's `-r` understands.
        """

        if not sha:
            raise DriverError("show_commit requires a non-empty revision")
        out = run_svn(
            ("log", "--xml", "--non-interactive", "-r", sha, "-l", "1"),
            cwd=repo.path,
        )
        refs = parse_log_xml(out)
        if not refs:
            raise DriverError(f"revision {sha} not found in {repo.path}")
        return refs[0]

    # ----- internal helpers ------------------------------------------- #

    def _ls_exists(self, repo: Repo, url: str) -> bool:
        """True if `svn ls <url>` succeeds (path is present in the repo)."""

        out = run_svn(
            ("ls", "--non-interactive", url),
            cwd=repo.path,
            allow_failure=True,
        )
        return bool(out.strip()) or self._ls_path_known(repo, url)

    def _ls_path_known(self, repo: Repo, url: str) -> bool:
        """Disambiguate empty-but-existing from missing.

        `svn ls` on an existing-but-empty directory returns empty
        stdout AND exit 0; on a missing path it returns empty AND
        exit non-zero. We re-run with `--depth empty` which gives
        a non-empty response on existing paths.
        """

        out = run_svn(
            ("info", "--non-interactive", "--depth", "empty", url),
            cwd=repo.path,
            allow_failure=True,
        )
        return bool(out.strip())

    def _ls_tip_revision(self, repo: Repo, url: str) -> int:
        """Last-changed revision of `url` (or -1 on failure)."""

        out = run_svn(
            ("info", "--xml", "--non-interactive", "--depth", "empty", url),
            cwd=repo.path,
            allow_failure=True,
        )
        if not out:
            return -1
        try:
            info = parse_info_xml(out)
        except ValueError:
            return -1
        return info.revision if info.revision >= 0 else -1

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
