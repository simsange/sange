"""`GitDriver` — `VCSDriver` Protocol implementation for Git (read-only, T-004).

Write operations (add, commit, push, tag_create, etc.) land in T-005.
This module covers detect + every read-only method on the Protocol.

Design:

  * The driver class is **stateless** — all state lives on the `Repo`
    object the caller passes. Multiple driver instances are
    interchangeable.
  * Subprocess invocations go through `_subprocess.run_git` so the env
    + error-mapping discipline is uniform.
  * Parsers (in `parsers.py`) are pure; the driver orchestrates
    subprocess + parser.
  * `capabilities` is a class attribute computed once at module load —
    it reflects the installed `git` version. Tests can construct a
    driver against a fake env via direct instantiation.

Test surface:
  * `tests/unit/test_git_parsers.py` — pure-parser fuzz against fixture
    text (no git installed required).
  * `tests/unit/test_git_driver.py` — driver methods against ephemeral
    real-git repos (skipped when `git` not on PATH).
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from sange.adapters.vcs._protocol import (
    DriverCapabilities,
    DriverError,
    TagInfo,
)
from sange.adapters.vcs.git import parsers as P
from sange.adapters.vcs.git._subprocess import (
    GitCommandFailed,
    GitNotInstalled,
    run_git,
    run_git_lines,
)
from sange.core.models import (
    BranchInfo,
    CommitRef,
    DiffSummary,
    RemoteInfo,
    Repo,
    VCSKind,
    WorkingCopyStatus,
)


class GitRepoNotFound(DriverError):
    """`GitDriver.detect()` was called on a path that's not in a git repo."""


def _git_version() -> str:
    """Probe the installed git version. Returns `'git not installed'` if absent."""

    try:
        out = run_git(("--version",))
    except (GitNotInstalled, GitCommandFailed):
        return "git not installed"
    return P.parse_version(out)


def _build_capabilities() -> DriverCapabilities:
    """Compute the `capabilities` descriptor reflecting the installed git.

    All modern git (≥ 2.20) supports every capability we care about:
      * `git stash` — yes since forever.
      * `git bisect` — yes.
      * `git rebase` — yes (the interactive form too).
      * Git LFS — separate binary; capability is True when git is present
        even if `git-lfs` isn't (the §6.10 LFS subsystem checks at use-time).
      * History rewrite — via `git filter-repo` (third-party); we declare
        True at the driver level and let `sange purge` check the binary
        at execute time.
    """

    return DriverCapabilities(
        vcs="git",
        vcs_version=_git_version(),
        supports_stash=True,
        supports_bisect=True,
        supports_rebase=True,
        supports_lfs=True,
        supports_signed_tags=True,
        supports_history_rewrite=True,
        notes=(
            "git rebase --interactive supported",
            "git filter-repo (third-party) wraps the §6.11 purge executor",
        ),
    )


class GitDriver:
    """VCSDriver implementation for Git — read-only operations (T-004).

    Write operations land in T-005 as a follow-up commit; the class
    structure is set up so adding them is purely additive.
    """

    # Module-level capability descriptor — computed once at import time so
    # `sange doctor` can introspect without invoking the driver.
    capabilities: DriverCapabilities = _build_capabilities()

    # ----- factory / detection ---------------------------------------- #

    @classmethod
    def detect(cls, path: Path) -> Repo:
        """Return a `Repo` if `path` is inside a git working tree.

        Resolves to the repo's top-level via `git rev-parse --show-toplevel`.
        Raises `GitRepoNotFound` when `path` is not inside a git repo.
        """

        # Use the supplied path as cwd; `--show-toplevel` returns the
        # repository root regardless of where we invoke it inside the
        # working tree.
        try:
            toplevel = run_git(
                ("rev-parse", "--show-toplevel"),
                cwd=path,
            ).strip()
        except GitCommandFailed as exc:
            raise GitRepoNotFound(
                f"{path} is not inside a git repository: {exc}"
            ) from exc

        if not toplevel:
            raise GitRepoNotFound(f"{path} is not inside a git repository")

        repo_path = Path(toplevel).resolve()

        # Look up the default branch heuristic: prefer the remote HEAD's
        # symbolic-ref; fall back to the configured init.defaultBranch;
        # fall back to "main".
        default_branch = cls._discover_default_branch(repo_path)

        # Primary remote URL (origin, if it exists).
        remote = cls._discover_origin_url(repo_path)

        return Repo(
            path=repo_path,
            vcs="git",
            remote=remote,
            default_branch=default_branch,
        )

    @staticmethod
    def _discover_default_branch(repo_path: Path) -> str:
        """Best-effort default-branch discovery."""

        # 1. The remote's HEAD pointer (set by `git clone`).
        try:
            head = run_git(
                ("symbolic-ref", "--short", "refs/remotes/origin/HEAD"),
                cwd=repo_path,
                allow_failure=True,
            ).strip()
        except (GitCommandFailed, GitNotInstalled):
            head = ""
        if head:
            # Strip leading "origin/" if present.
            return head.removeprefix("origin/")

        # 2. The local `init.defaultBranch` config.
        try:
            configured = run_git(
                ("config", "--get", "init.defaultBranch"),
                cwd=repo_path,
                allow_failure=True,
            ).strip()
        except (GitCommandFailed, GitNotInstalled):
            configured = ""
        if configured:
            return configured

        # 3. Common defaults — main wins.
        for candidate in ("main", "master"):
            exists = run_git(
                ("show-ref", "--verify", "--quiet", f"refs/heads/{candidate}"),
                cwd=repo_path,
                allow_failure=True,
            )
            if exists is not None and exists != "":
                return candidate
            # show-ref --quiet returns "" on success; we can't tell success
            # from failure here. Use exit-code probe via `branch --list`.
            br = run_git(
                ("branch", "--list", candidate),
                cwd=repo_path,
                allow_failure=True,
            ).strip()
            if br:
                return candidate

        return "main"

    @staticmethod
    def _discover_origin_url(repo_path: Path) -> str | None:
        try:
            url = run_git(
                ("config", "--get", "remote.origin.url"),
                cwd=repo_path,
                allow_failure=True,
            ).strip()
        except (GitCommandFailed, GitNotInstalled):
            return None
        return url or None

    # ----- status ----------------------------------------------------- #

    def status(self, repo: Repo) -> WorkingCopyStatus:
        out = run_git(P.STATUS_PORCELAIN_V2_ARGS, cwd=repo.path)
        return P.parse_status_porcelain_v2(out)

    # ----- log -------------------------------------------------------- #

    def log(
        self,
        repo: Repo,
        *,
        revision_range: str = "",
        max_count: int | None = None,
    ) -> tuple[CommitRef, ...]:
        args: list[str] = ["log", f"--format={P.LOG_PRETTY_FORMAT}"]
        if max_count is not None and max_count >= 0:
            args.append(f"--max-count={max_count}")
        if revision_range:
            args.append(revision_range)
        out = run_git(args, cwd=repo.path)
        return P.parse_log_records(out)

    # ----- diff ------------------------------------------------------- #

    def diff(
        self,
        repo: Repo,
        *,
        paths: Sequence[Path] = (),
        revision_range: str = "",
    ) -> DiffSummary:
        # Use --shortstat for counts.
        stat_args: list[str] = ["diff", "--shortstat"]
        if revision_range:
            stat_args.append(revision_range)
        if paths:
            stat_args.append("--")
            stat_args.extend(str(p) for p in paths)
        stat_out = run_git(stat_args, cwd=repo.path)
        files, ins, dels = P.parse_shortstat(stat_out)

        # Sha256 of the diff content for §6.8 lifecycle change-detection.
        # Empty diff → empty hash (per `DiffSummary` invariant).
        if files == 0 and ins == 0 and dels == 0:
            return DiffSummary(
                files_changed=0, insertions=0, deletions=0, content_hash=""
            )

        diff_args: list[str] = ["diff"]
        if revision_range:
            diff_args.append(revision_range)
        if paths:
            diff_args.append("--")
            diff_args.extend(str(p) for p in paths)
        diff_out = run_git(diff_args, cwd=repo.path)
        import hashlib
        content_hash = hashlib.sha256(diff_out.encode("utf-8")).hexdigest()

        return DiffSummary(
            files_changed=files,
            insertions=ins,
            deletions=dels,
            content_hash=content_hash,
        )

    # ----- branches --------------------------------------------------- #

    def branches(self, repo: Repo) -> tuple[BranchInfo, ...]:
        out = run_git(P.BRANCH_LIST_ARGS, cwd=repo.path)
        result = P.parse_branch_list(out)
        # Sort: current branch first, then alphabetically.
        return tuple(sorted(result, key=lambda b: (not b.is_current, b.name)))

    def current_branch(self, repo: Repo) -> BranchInfo | None:
        # `symbolic-ref HEAD` returns refs/heads/<branch>; or fails with a
        # detached-HEAD state.
        head = run_git(
            ("symbolic-ref", "--short", "HEAD"),
            cwd=repo.path,
            allow_failure=True,
        ).strip()
        if not head:
            return None
        for b in self.branches(repo):
            if b.name == head:
                return b
        return None

    # ----- remotes ---------------------------------------------------- #

    def remotes(self, repo: Repo) -> tuple[RemoteInfo, ...]:
        out = run_git(P.REMOTE_LIST_ARGS, cwd=repo.path)
        return P.parse_remotes(out)

    # ----- tags ------------------------------------------------------- #

    def tags(self, repo: Repo) -> tuple[TagInfo, ...]:
        out = run_git(P.TAG_LIST_ARGS, cwd=repo.path)
        return P.parse_tag_list(out)

    # ----- show commit ------------------------------------------------ #

    def show_commit(self, repo: Repo, sha: str) -> CommitRef:
        if not sha:
            raise DriverError("show_commit requires a non-empty SHA")
        out = run_git(
            ("log", f"--format={P.LOG_PRETTY_FORMAT}", "-n", "1", sha),
            cwd=repo.path,
        )
        records = P.parse_log_records(out)
        if not records:
            raise DriverError(f"commit {sha} not found in {repo.path}")
        return records[0]

    # ----- write methods (T-005 will fill these in) ------------------ #

    def add(self, repo: Repo, paths: Sequence[Path]) -> None:
        raise NotImplementedError("T-005 — GitDriver write operations")

    def remove(self, repo: Repo, paths: Sequence[Path], *, force: bool = False) -> None:
        raise NotImplementedError("T-005 — GitDriver write operations")

    def revert_working_copy(self, repo: Repo, paths: Sequence[Path]) -> None:
        raise NotImplementedError("T-005 — GitDriver write operations")

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
        raise NotImplementedError("T-005 — GitDriver write operations")

    def branch_create(self, repo: Repo, name: str, *, base: str = "") -> BranchInfo:
        raise NotImplementedError("T-005 — GitDriver write operations")

    def branch_delete(self, repo: Repo, name: str, *, force: bool = False) -> None:
        raise NotImplementedError("T-005 — GitDriver write operations")

    def switch(self, repo: Repo, branch: str) -> BranchInfo:
        raise NotImplementedError("T-005 — GitDriver write operations")

    def fetch(self, repo: Repo, remote: str = "") -> None:
        raise NotImplementedError("T-005 — GitDriver write operations")

    def pull(self, repo: Repo, remote: str = "") -> None:
        raise NotImplementedError("T-005 — GitDriver write operations")

    def push(
        self,
        repo: Repo,
        *,
        remote: str = "",
        branch: str = "",
        force: bool = False,
        force_with_lease: bool = False,
    ):
        raise NotImplementedError("T-005 — GitDriver write operations")

    def tag_create(
        self,
        repo: Repo,
        name: str,
        *,
        target_sha: str = "",
        message: str = "",
        sign: bool = False,
    ) -> TagInfo:
        raise NotImplementedError("T-005 — GitDriver write operations")

    def tag_delete(self, repo: Repo, name: str) -> None:
        raise NotImplementedError("T-005 — GitDriver write operations")


__all__ = ["GitDriver", "GitRepoNotFound"]
