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
    PushResult,
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

    # ----- write methods (T-005) ------------------------------------- #
    #
    # Every write method maps subprocess failure to DriverError via the
    # run_git wrapper. Path arguments are stringified for the command line
    # but stay Path objects in the Domain types.

    def add(self, repo: Repo, paths: Sequence[Path]) -> None:
        """Stage `paths` for the next commit (`git add`).

        Per-path absolute-path rejection: the Protocol declares paths are
        repo-relative. Adapter enforces this so a stray `Path("/etc/passwd")`
        can't sneak into the index.
        """

        if not paths:
            return
        for p in paths:
            if p.is_absolute():
                raise DriverError(
                    f"add: path {p!r} must be relative to repo root"
                )
        run_git(("add", "--", *(str(p) for p in paths)), cwd=repo.path)

    def remove(self, repo: Repo, paths: Sequence[Path], *, force: bool = False) -> None:
        """Remove `paths` from working tree + index (`git rm`).

        `force=True` allows removing files with uncommitted changes
        (otherwise git refuses). The §6.8 commit lifecycle's
        approve-on-destructive gate intercepts before this lands.
        """

        if not paths:
            return
        for p in paths:
            if p.is_absolute():
                raise DriverError(f"remove: path {p!r} must be relative")
        args: list[str] = ["rm"]
        if force:
            args.append("--force")
        args.append("--")
        args.extend(str(p) for p in paths)
        run_git(args, cwd=repo.path)

    def revert_working_copy(self, repo: Repo, paths: Sequence[Path]) -> None:
        """Discard uncommitted changes to `paths` (`git restore`).

        DESTRUCTIVE — the CLI/TUI layer wraps this with a type-to-confirm
        gate per §7.0.5; adapters don't gate (the Protocol is the imperative
        contract, gates are the Application layer).
        """

        if not paths:
            return
        for p in paths:
            if p.is_absolute():
                raise DriverError(
                    f"revert_working_copy: path {p!r} must be relative"
                )
        run_git(
            ("restore", "--source=HEAD", "--worktree", "--staged",
             "--", *(str(p) for p in paths)),
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
        """Create a commit from the staged content.

        `author_name`/`author_email` override the current git identity
        for this commit only (Git's `--author=` flag). `sign=True`
        produces a GPG-signed commit (per the §6.9 release-engineering
        signing path).
        """

        if not message:
            raise DriverError("commit: message must be non-empty")
        # Reject CR/LF in the subject portion (the first line of `message`).
        first_line = message.split("\n", 1)[0]
        if "\r" in first_line:
            raise DriverError("commit: subject must be single-line")

        args: list[str] = ["commit", "-m", message]
        if author_name and author_email:
            args.append(f"--author={author_name} <{author_email}>")
        elif author_name or author_email:
            raise DriverError(
                "commit: author_name and author_email must both be set or both omitted"
            )
        if allow_empty:
            args.append("--allow-empty")
        if sign:
            args.append("-S")

        run_git(args, cwd=repo.path)
        # Return the just-created commit by re-reading HEAD.
        head_sha = run_git(("rev-parse", "HEAD"), cwd=repo.path).strip()
        return self.show_commit(repo, head_sha)

    def branch_create(self, repo: Repo, name: str, *, base: str = "") -> BranchInfo:
        """Create branch `name`, optionally off `base` (default: current branch)."""

        if not name:
            raise DriverError("branch_create: name must be non-empty")
        args: list[str] = ["branch", name]
        if base:
            args.append(base)
        run_git(args, cwd=repo.path)
        # Re-list to find the new branch entry.
        for b in self.branches(repo):
            if b.name == name:
                return b
        # Unreachable on success, but safe fallback.
        raise DriverError(f"branch_create: created {name!r} but couldn't find it")

    def branch_delete(self, repo: Repo, name: str, *, force: bool = False) -> None:
        """Delete branch `name`. `force=True` allows deleting unmerged branches."""

        if not name:
            raise DriverError("branch_delete: name must be non-empty")
        flag = "-D" if force else "-d"
        run_git(("branch", flag, name), cwd=repo.path)

    def switch(self, repo: Repo, branch: str) -> BranchInfo:
        """Switch the working copy to `branch` (`git switch`)."""

        if not branch:
            raise DriverError("switch: branch must be non-empty")
        run_git(("switch", branch), cwd=repo.path)
        cb = self.current_branch(repo)
        if cb is None:
            raise DriverError(
                f"switch: after switching to {branch!r}, HEAD is detached"
            )
        return cb

    def fetch(self, repo: Repo, remote: str = "") -> None:
        """Fetch updates. Empty `remote` → fetch all remotes."""

        args: list[str] = ["fetch"]
        if remote:
            args.append(remote)
        else:
            args.append("--all")
        run_git(args, cwd=repo.path)

    def pull(self, repo: Repo, remote: str = "") -> None:
        """Fetch + integrate from `remote` (or the upstream when empty).

        Defers merge-vs-rebase to the user's `pull.rebase` config (Sange
        does NOT silently override it).
        """

        args: list[str] = ["pull"]
        if remote:
            args.append(remote)
        run_git(args, cwd=repo.path)

    def push(
        self,
        repo: Repo,
        *,
        remote: str = "",
        branch: str = "",
        force: bool = False,
        force_with_lease: bool = False,
    ) -> "PushResult":
        """Push local commits to `remote/branch`.

        Forbids `force=True` AND `force_with_lease=True` together —
        callers must pick one. `--force-with-lease` is preferred when
        either is needed.
        """

        if force and force_with_lease:
            raise DriverError(
                "push: force and force_with_lease are mutually exclusive — pick one"
            )

        args: list[str] = ["push"]
        if force_with_lease:
            args.append("--force-with-lease")
        elif force:
            args.append("--force")
        # Always be explicit about the destination if either is provided.
        target_remote = remote or "origin"
        # Use --porcelain so the no-op / pushed / forced state appears on
        # stdout (where run_git can see it). Without --porcelain git's
        # "Everything up-to-date" status goes to stderr.
        args.append("--porcelain")
        if branch:
            args.extend([target_remote, branch])
        elif remote:
            args.append(target_remote)

        try:
            stdout = run_git(args, cwd=repo.path)
        except GitCommandFailed as exc:
            raise DriverError(
                f"push to {target_remote} failed: {exc.stderr.strip() or '<no stderr>'}"
            ) from exc

        # Parse `git push --porcelain` output: per-ref lines start with a
        # one-character flag:
        #   '='  up to date (no-op)
        #   ' '  successfully pushed fast-forward
        #   '+'  successful forced update
        #   '*'  successfully pushed a new ref
        #   '-'  successfully deleted ref
        #   '!'  rejected or failed
        # Lines beginning with "To " are the header; "Done" is the trailer.
        # was_no_op = every ref line carries the '=' flag.
        ref_lines = [
            line for line in stdout.splitlines()
            if line and not line.startswith("To ") and line != "Done"
        ]
        was_no_op = bool(ref_lines) and all(
            line.startswith("=") for line in ref_lines
        )
        return PushResult(
            remote=target_remote,
            was_no_op=was_no_op,
            forced=force or force_with_lease,
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
        """Create a tag.

        * `target_sha=""` → tag HEAD.
        * `message=""` + `sign=False` → lightweight tag.
        * `message` non-empty OR `sign=True` → annotated tag (signed if
          `sign=True`; signing requires a configured GPG key).
        """

        if not name:
            raise DriverError("tag_create: name must be non-empty")

        args: list[str] = ["tag"]
        annotated = bool(message) or sign
        if sign:
            args.append("-s")
        elif annotated:
            args.append("-a")
        if message:
            args.extend(["-m", message])
        elif sign:
            # Signed tags require a message; default to the tag name.
            args.extend(["-m", name])
        args.append(name)
        if target_sha:
            args.append(target_sha)

        run_git(args, cwd=repo.path)

        # Re-list to find the new tag — picks up the resolved SHA + the
        # is_annotated flag the parser computed.
        for t in self.tags(repo):
            if t.name == name:
                # Patch is_signed since the parser can't tell cheaply.
                if sign and not t.is_signed:
                    t = TagInfo(
                        name=t.name,
                        target_sha=t.target_sha,
                        is_annotated=t.is_annotated,
                        is_signed=True,
                        message=t.message,
                        created_at=t.created_at,
                    )
                return t
        raise DriverError(f"tag_create: created {name!r} but couldn't find it")

    def tag_delete(self, repo: Repo, name: str) -> None:
        """Delete tag `name` from the local repository."""

        if not name:
            raise DriverError("tag_delete: name must be non-empty")
        run_git(("tag", "-d", name), cwd=repo.path)


__all__ = ["GitDriver", "GitRepoNotFound"]
