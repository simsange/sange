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
import re
from collections.abc import Sequence
from pathlib import Path

from sange.adapters.vcs._protocol import (
    DriverCapabilities,
    DriverError,
    PushResult,
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
    """VCSDriver implementation for Subversion (T-100 complete).

    Three SVN-specific behaviors worth flagging:

      * **`commit` is immediately remote.** Unlike Git, `svn commit`
        publishes to the central repo in one step. `push()` is a no-op
        for SVN — it returns `PushResult(was_no_op=True)`.
      * **Branches and tags are server-side directory copies.**
        `branch_create()` runs `svn copy ^/<base> ^/branches/<name>`;
        `tag_create()` runs `svn copy ^/trunk ^/tags/<name>`. Both
        commit immediately. There's no local-only branch concept.
      * **No commit signing, no allow-empty.** SVN's commit primitive
        rejects empty commits server-side and has no GPG-signing
        equivalent to `git commit -S`. The adapter raises
        `DriverError` rather than silently dropping these flags.

    The same `VCSDriver` Protocol surface means callers don't branch
    on VCS — `sange commits push` against an SVN working copy routes
    through `SvnDriver.commit()` (which publishes) + `SvnDriver.push()`
    (which is the documented no-op).
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
        """Derive the current branch from a fresh `svn info` query.

        Earlier versions of this method read `repo.metadata['relative_url']`
        which was captured at `detect()` time — but `switch()` shifts the
        WC's URL without updating the (frozen) `Repo` instance, so the
        cache went stale. The fresh-query cost is one `svn info` call
        per invocation; acceptable.

        Returns None if the WC's URL doesn't follow the
        trunk/branches/tags convention, or points at a tag (tags
        aren't branches).
        """

        info = self._info(repo)
        extracted = extract_branch_from_url(info.relative_url)
        if extracted is None:
            return None
        kind, name = extracted
        if kind == "tag":
            return None  # Tags aren't branches.

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

    # ----- write methods (T-100c) ------------------------------------- #

    def add(self, repo: Repo, paths: Sequence[Path]) -> None:
        """Schedule `paths` for addition (`svn add`).

        Per-path absolute-path rejection — the Protocol declares paths
        repo-relative. SVN auto-recurses into directories by default
        which matches Git's stage-everything-under-a-dir behavior.
        """

        if not paths:
            return
        for p in paths:
            if p.is_absolute():
                raise DriverError(
                    f"add: path {p!r} must be relative to repo root"
                )
        # `--parents` schedules missing parent dirs too (mirrors `git add`'s
        # tree-aware behavior); harmless when parents are already versioned.
        run_svn(
            ("add", "--parents", "--non-interactive", "--",
             *(str(p) for p in paths)),
            cwd=repo.path,
        )

    def remove(self, repo: Repo, paths: Sequence[Path], *, force: bool = False) -> None:
        """Schedule `paths` for removal (`svn rm`).

        `force=True` passes `--force`, which lets SVN remove files with
        local modifications. Without it, SVN refuses on dirty paths.
        """

        if not paths:
            return
        for p in paths:
            if p.is_absolute():
                raise DriverError(f"remove: path {p!r} must be relative")
        args: list[str] = ["rm", "--non-interactive"]
        if force:
            args.append("--force")
        args.append("--")
        args.extend(str(p) for p in paths)
        run_svn(args, cwd=repo.path)

    def revert_working_copy(self, repo: Repo, paths: Sequence[Path]) -> None:
        """Discard local changes to `paths` (`svn revert -R`).

        DESTRUCTIVE — the CLI/TUI layer wraps with the §7.0.5
        type-to-confirm gate; the adapter is the imperative contract.
        Recursive by default so reverting a directory clears the whole
        subtree.
        """

        if not paths:
            return
        for p in paths:
            if p.is_absolute():
                raise DriverError(
                    f"revert_working_copy: path {p!r} must be relative"
                )
        run_svn(
            ("revert", "-R", "--non-interactive", "--",
             *(str(p) for p in paths)),
            cwd=repo.path,
        )

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
        """Create a revision (`svn commit`).

        **SVN commits are immediately remote** — there's no local-then-push
        split. `SvnDriver.push()` is a no-op for SVN.

        Behavioral divergences from Git's commit:
          * `author_email` is not separable in SVN's auth model — only the
            username (which `--username` overrides) is tracked. We accept
            the parameter for Protocol parity but only use `author_name`
            (as `--username`) and reject the partial-set case for symmetry
            with the Git adapter.
          * `allow_empty=True` is rejected — SVN exits non-zero with no
            way to override "nothing to commit".
          * `sign=True` is rejected — SVN has no per-commit GPG signing
            (the v1.0 release-engineering signing path covers tag-level
            sigstore + cosign instead).
        """

        if not message:
            raise DriverError("commit: message must be non-empty")
        first_line = message.split("\n", 1)[0]
        if "\r" in first_line:
            raise DriverError("commit: subject must be single-line")
        if bool(author_name) != bool(author_email):
            raise DriverError(
                "commit: author_name and author_email must both be set or both omitted"
            )
        if allow_empty:
            raise DriverError(
                "commit: SVN has no --allow-empty equivalent (server rejects "
                "no-op commits); call with at least one staged change"
            )
        if sign:
            raise DriverError(
                "commit: SVN does not support per-commit GPG signing; "
                "sign tags via tag_create() in v1.0+ release engineering"
            )

        args: list[str] = ["commit", "--non-interactive", "-m", message]
        if author_name:
            args.extend(("--username", author_name))

        out = run_svn(args, cwd=repo.path)
        # `svn commit` prints "Committed revision N." as its last
        # informational line. Parse that — `svn info` on the WC root
        # only reports the *directory's* last-changed revision, which
        # doesn't bump when only child files were modified.
        new_rev = _extract_committed_revision(out)
        if new_rev is None:
            raise DriverError(
                "commit: could not parse 'Committed revision N.' from svn output"
            )
        return self.show_commit(repo, str(new_rev))

    def branch_create(self, repo: Repo, name: str, *, base: str = "") -> BranchInfo:
        """Create a branch via `svn copy ^/<base> ^/branches/<name>`.

        SVN branches are server-side directory copies. `base` defaults to
        `trunk` (the conventional source). The copy commits immediately —
        SVN doesn't have a local-only branch concept.
        """

        if not name:
            raise DriverError("branch_create: name must be non-empty")
        if "/" in name:
            raise DriverError(
                f"branch_create: branch name {name!r} cannot contain '/'"
            )

        base_url = self._branch_url(base or "trunk")
        target_url = f"^/branches/{name}"

        run_svn(
            ("copy", "--non-interactive",
             "-m", f"Create branch {name} from {base or 'trunk'}",
             base_url, target_url),
            cwd=repo.path,
        )

        for b in self.branches(repo):
            if b.name == name:
                return b
        raise DriverError(f"branch_create: created {name!r} but couldn't find it")

    def branch_delete(self, repo: Repo, name: str, *, force: bool = False) -> None:
        """Delete `^/branches/<name>` server-side.

        SVN doesn't have a "merged vs unmerged" concept — `force` is
        accepted for Protocol parity but has no effect on the SVN
        invocation. Reviewers wrap branch_delete with the §6.11 purge
        gates at the Application layer.
        """

        _ = force  # accepted for parity; SVN has no merged/unmerged check
        if not name:
            raise DriverError("branch_delete: name must be non-empty")
        if "/" in name:
            raise DriverError(
                f"branch_delete: branch name {name!r} cannot contain '/'"
            )
        if name == "trunk":
            raise DriverError("branch_delete: refusing to delete trunk")

        target_url = f"^/branches/{name}"
        run_svn(
            ("rm", "--non-interactive",
             "-m", f"Delete branch {name}",
             target_url),
            cwd=repo.path,
        )

    def switch(self, repo: Repo, branch: str) -> BranchInfo:
        """Switch the working copy to a different branch URL (`svn switch`).

        `branch` is one of:
          * `"trunk"`              → `^/trunk`
          * `"<branch-name>"`      → `^/branches/<branch-name>`

        Switching to a tag URL is technically possible in SVN but
        Sange treats tags as immutable references — pass `^/tags/<name>`
        explicitly if you really mean it (no string-conventional alias).
        """

        if not branch:
            raise DriverError("switch: branch must be non-empty")
        url = self._branch_url(branch)
        run_svn(("switch", "--non-interactive", url), cwd=repo.path)
        cb = self.current_branch(repo)
        if cb is None:
            # WC may now point at a non-convention URL; surface as error
            # rather than return a synthetic BranchInfo.
            raise DriverError(
                f"switch: after switching to {branch!r}, the URL is "
                "not under trunk/branches/"
            )
        return cb

    def fetch(self, repo: Repo, remote: str = "") -> None:
        """SVN doesn't have a fetch-without-apply primitive.

        For Protocol parity, `fetch` is a no-op on SVN. The closest
        equivalent is `svn status --show-updates` (which queries the
        repo without modifying the WC), but it doesn't materialize a
        local refs database the way `git fetch` does. The caller wants
        `pull()` (`svn update`) for "bring my WC up to date".
        """

        _ = remote  # accepted for parity; SVN's single remote is implicit
        # Intentionally a no-op. See docstring for rationale.

    def pull(self, repo: Repo, remote: str = "") -> None:
        """Update the working copy to the latest revision (`svn update`).

        SVN's analog to `git pull`: fetches + applies in one step.
        `remote` is accepted for parity (SVN's single remote is implicit).
        """

        _ = remote
        run_svn(("update", "--non-interactive"), cwd=repo.path)

    def push(
        self,
        repo: Repo,
        *,
        remote: str = "",
        branch: str = "",
        force: bool = False,
        force_with_lease: bool = False,
    ) -> PushResult:
        """SVN commits are immediately remote — push is a no-op.

        The `force` / `force_with_lease` flags are rejected when set,
        not silently ignored: their semantics (rewriting remote history)
        do not exist in SVN's commit model. The driver returns
        `PushResult(was_no_op=True)` so the lifecycle layer can detect
        "nothing more to do" without a special-case branch per VCS.
        """

        if force or force_with_lease:
            raise DriverError(
                "push: SVN has no history-rewrite primitive equivalent to "
                "git push --force / --force-with-lease; use the v0.5 purge "
                "subsystem for history rewriting"
            )
        target_remote = remote or "origin"
        # The data is already on the server (svn commit landed it).
        return PushResult(
            remote=target_remote,
            was_no_op=True,
            forced=False,
        )

    def tag_create(
        self,
        repo: Repo,
        name: str,
        *,
        target_sha: str = "",
        message: str = "",
        sign: bool = False,
    ) -> TagInfo:
        """Create a tag via `svn copy ^/trunk ^/tags/<name>`.

        SVN tags are dir-copies — never annotated, never signed. The
        `message` parameter is recorded as the copy's commit message
        (visible in `svn log ^/tags/<name>`). `target_sha`, when set,
        copies from `-r <sha> ^/trunk` so the tag points at a specific
        revision rather than HEAD.

        `sign=True` is rejected — there's no SVN-level signing primitive
        (the v1.0 release engineering supplies cosign for tag signing).
        """

        if not name:
            raise DriverError("tag_create: name must be non-empty")
        if "/" in name:
            raise DriverError(
                f"tag_create: tag name {name!r} cannot contain '/'"
            )
        if sign:
            raise DriverError(
                "tag_create: SVN does not support per-tag GPG signing; "
                "the v1.0 release engineering supplies cosign instead"
            )

        source_url = "^/trunk"
        target_url = f"^/tags/{name}"
        commit_msg = message or f"Create tag {name}"
        args: list[str] = ["copy", "--non-interactive", "-m", commit_msg]
        if target_sha:
            args.extend(("-r", target_sha))
        args.extend((source_url, target_url))

        run_svn(args, cwd=repo.path)

        for t in self.tags(repo):
            if t.name == name:
                # Patch the message field — `parse_ls_xml` doesn't capture
                # the per-entry log message, but we know what we wrote.
                if message and not t.message:
                    t = TagInfo(
                        name=t.name,
                        target_sha=t.target_sha,
                        is_annotated=t.is_annotated,
                        is_signed=t.is_signed,
                        message=message,
                        created_at=t.created_at,
                    )
                return t
        raise DriverError(f"tag_create: created {name!r} but couldn't find it")

    def tag_delete(self, repo: Repo, name: str) -> None:
        """Delete `^/tags/<name>` server-side."""

        if not name:
            raise DriverError("tag_delete: name must be non-empty")
        if "/" in name:
            raise DriverError(
                f"tag_delete: tag name {name!r} cannot contain '/'"
            )
        target_url = f"^/tags/{name}"
        run_svn(
            ("rm", "--non-interactive",
             "-m", f"Delete tag {name}",
             target_url),
            cwd=repo.path,
        )

    # ----- branch-url helper ------------------------------------------ #

    @staticmethod
    def _branch_url(branch: str) -> str:
        """Resolve a `branch` argument to a relative `^/...` URL.

        Accepts:
          * `"trunk"`                  → `^/trunk`
          * `"<name>"`                 → `^/branches/<name>`
          * `"^/..."` (any caret URL)  → passes through verbatim

        The caret-URL passthrough lets callers target `^/tags/<name>`
        or other unconventional layouts when they explicitly need to.
        """

        if branch.startswith("^/"):
            return branch
        if branch == "trunk":
            return "^/trunk"
        return f"^/branches/{branch}"


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


_COMMITTED_RE = re.compile(r"^Committed revision (\d+)\.\s*$", re.MULTILINE)


def _extract_committed_revision(svn_commit_output: str) -> int | None:
    """Parse `svn commit`'s 'Committed revision N.' line into an int.

    `svn commit` writes informational lines like:

        Adding         b.txt
        Transmitting file data .done
        Committing transaction...
        Committed revision 3.

    The final line carries the assigned revision number. Returns None
    when the marker is absent (e.g. a dry-run, a no-op commit, or a
    future SVN version with different output formatting).
    """

    m = _COMMITTED_RE.search(svn_commit_output)
    if m is None:
        return None
    try:
        return int(m.group(1))
    except ValueError:
        return None


__all__ = ["SvnDriver", "SvnRepoNotFound"]
