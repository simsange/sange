"""Mirror clone for §6.11.4 gate 2 — fresh, off-the-user's-repo.

> "Sange refuses to run against the user's working repo. Auto-creates
> a mirror under `.sange/purge/<ts>/work.git/` from the configured
> remote unless `--mirror <path>` is supplied. The mirror is verified
> to be untouched (no extra refs, no local-only objects, clean
> `for-each-ref` snapshot)." — §6.11.4

This module wraps the operation in `create_mirror()`:

  1. Resolve source URL (caller-supplied or `plan.target_repo.remote`).
  2. Refuse to clobber an existing mirror dir — the operator must
     remove it explicitly to retry.
  3. Run `git clone --mirror <source> <dest>` via `run_streamed` so
     the clone subprocess's stdout/stderr lands in the audit chain
     + a per-event transcript.
  4. Run `git fsck --full --strict` against the mirror — refuse to
     proceed if integrity is red.
  5. Capture the `for-each-ref` snapshot as the baseline against
     which `verify_mirror()` detects concurrent writes later.
  6. Return `MirrorResult` with the audit event ids + ref baseline.

The destructive purge subsystem (T-203+ v1.0) never operates against
the user's working repo — it operates against this mirror. Sange's
"all-or-nothing" invariant relies on the backup tarball (T-111
gate 3) being a snapshot of THIS mirror, not of the working repo.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from sange.core.audit import AuditChain, EventKind
from sange.core.purge.plan import PurgePlan
from sange.core.streaming import StreamResult, run_streamed


class MirrorError(Exception):
    """Raised when the mirror operation can't proceed."""


@dataclass(frozen=True)
class MirrorResult:
    """Outcome of `create_mirror`.

    Fields:
      * `path`             — absolute path to the mirror directory.
      * `source_url`       — what was cloned (file://path or git@host:repo.git).
      * `clone_event_id`   — audit event id for the `git clone --mirror`
                             subprocess (transcript at
                             `<audit_dir>/transcripts/<id>.log`).
      * `fsck_event_id`    — audit event id for `git fsck --full --strict`.
      * `fsck_passed`      — `True` iff fsck exit was 0.
      * `refs`             — tuple of `(refname, sha)` pairs from
                             `for-each-ref`. The baseline against which
                             `verify_mirror()` detects concurrent
                             upstream writes.
      * `ref_count`        — `len(refs)`. Stored for telemetry.
    """

    path: Path
    source_url: str
    clone_event_id: str
    fsck_event_id: str
    fsck_passed: bool
    refs: tuple[tuple[str, str], ...]
    ref_count: int


@dataclass(frozen=True)
class MirrorVerification:
    """Outcome of `verify_mirror` — drift detection result.

    Fields:
      * `passed`           — True iff every ref matches the baseline.
      * `added_refs`       — refs present now but absent in baseline.
      * `removed_refs`     — refs in baseline but absent now.
      * `changed_refs`     — refs in both but with a different sha.
      * `current_event_id` — audit id for the comparison subprocess.
    """

    passed: bool
    added_refs: tuple[str, ...]
    removed_refs: tuple[str, ...]
    changed_refs: tuple[tuple[str, str, str], ...]  # (ref, old_sha, new_sha)
    current_event_id: str


def _mirror_path_for(plan: PurgePlan, repo_root: Path) -> Path:
    return Path(repo_root).resolve() / ".sange" / "purge" / plan.plan_id / "work.git"


def create_mirror(
    plan: PurgePlan,
    repo_root: Path,
    *,
    audit_chain: AuditChain,
    actor: str,
    source_url: str | None = None,
    clone_timeout: float = 600.0,
    fsck_timeout: float = 120.0,
) -> MirrorResult:
    """Create a verified mirror clone under the plan's working dir.

    Args:
      plan:          the active `PurgePlan` (used for plan_id + remote).
      repo_root:     parent of `.sange/` — the operator's working repo
                     (the clone *source*, never modified by this call).
      audit_chain:   chain to thread the clone + fsck + ref-baseline
                     events onto.
      actor:         audit-entry actor (e.g. `alice@cli`).
      source_url:    optional override; defaults to `plan.target_repo.remote`
                     (or, if empty, `file://<repo_root>` so a local repo
                     can be its own clone source).
      clone_timeout: seconds before SIGTERM cascade fires on the clone.
      fsck_timeout:  seconds before SIGTERM on the fsck.

    Raises:
      MirrorError: destination already exists / source URL unresolvable /
        clone exits non-zero / fsck reports breakage.
    """

    if plan.target_vcs != "git":
        raise MirrorError(
            f"mirror clone only supports git (got {plan.target_vcs!r}); "
            f"SVN/Hg/P4 mirrors land in v1.0+"
        )

    repo_root_path = Path(repo_root).resolve()
    dest = _mirror_path_for(plan, repo_root_path)

    if dest.exists():
        raise MirrorError(
            f"mirror destination already exists: {dest} "
            f"(remove it manually to retry)"
        )

    resolved_source = _resolve_source_url(plan, repo_root_path, source_url)

    # Ensure the parent dir exists; git won't auto-create it.
    dest.parent.mkdir(parents=True, exist_ok=True)

    clone_result = run_streamed(
        ["git", "clone", "--mirror", resolved_source, str(dest)],
        audit_chain=audit_chain,
        actor=actor,
        event_kind=EventKind.GENERIC,
        payload={
            "phase": "mirror-clone",
            "plan_id": plan.plan_id,
            "source": resolved_source,
            "dest": str(dest.relative_to(repo_root_path))
            if dest.is_relative_to(repo_root_path)
            else str(dest),
        },
        timeout=clone_timeout,
    )
    if clone_result.returncode != 0:
        raise MirrorError(
            f"git clone --mirror exited {clone_result.returncode}; "
            f"see transcript at {clone_result.transcript_path}"
        )

    fsck_result = _run_fsck(dest, audit_chain, actor, plan, fsck_timeout)
    if not fsck_result.succeeded:
        raise MirrorError(
            f"git fsck --full --strict failed (exit {fsck_result.returncode}); "
            f"see transcript at {fsck_result.transcript_path}"
        )

    refs = _capture_refs(dest, audit_chain, actor, plan, fsck_timeout)

    return MirrorResult(
        path=dest,
        source_url=resolved_source,
        clone_event_id=clone_result.event_id,
        fsck_event_id=fsck_result.event_id,
        fsck_passed=True,
        refs=refs.refs,
        ref_count=len(refs.refs),
    )


def verify_mirror(
    plan: PurgePlan,
    repo_root: Path,
    *,
    audit_chain: AuditChain,
    actor: str,
    baseline_refs: tuple[tuple[str, str], ...],
    timeout: float = 120.0,
) -> MirrorVerification:
    """Re-snapshot the mirror's refs and diff against the baseline.

    Used to detect concurrent writes (`§6.11 Red-Team Pass #2`) between
    `analyzed` and `executing`. If anything drifted, the operation
    must be re-analyzed + re-confirmed.
    """

    dest = _mirror_path_for(plan, Path(repo_root).resolve())
    if not dest.is_dir():
        raise MirrorError(f"mirror not found: {dest}")

    snapshot = _capture_refs(dest, audit_chain, actor, plan, timeout)
    baseline_map = dict(baseline_refs)
    current_map = dict(snapshot.refs)

    added = tuple(sorted(set(current_map) - set(baseline_map)))
    removed = tuple(sorted(set(baseline_map) - set(current_map)))
    changed = tuple(
        sorted(
            (ref, baseline_map[ref], current_map[ref])
            for ref in set(baseline_map) & set(current_map)
            if baseline_map[ref] != current_map[ref]
        )
    )

    return MirrorVerification(
        passed=not (added or removed or changed),
        added_refs=added,
        removed_refs=removed,
        changed_refs=changed,
        current_event_id=snapshot.event_id,
    )


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _resolve_source_url(
    plan: PurgePlan,
    repo_root: Path,
    override: str | None,
) -> str:
    """Pick the clone source URL — override > plan.remote > local repo."""

    if override:
        return override
    if plan.target_repo.remote:
        return plan.target_repo.remote
    # Last-resort fallback: the local working repo itself. The repo is
    # the clone source, never modified — `git clone --mirror file://...`
    # is read-only from the source's perspective.
    return f"file://{repo_root}"


def _run_fsck(
    mirror_path: Path,
    audit_chain: AuditChain,
    actor: str,
    plan: PurgePlan,
    timeout: float,
) -> StreamResult:
    return run_streamed(
        [
            "git",
            "--git-dir",
            str(mirror_path),
            "fsck",
            "--full",
            "--strict",
            "--no-progress",
        ],
        audit_chain=audit_chain,
        actor=actor,
        event_kind=EventKind.GENERIC,
        payload={
            "phase": "mirror-fsck",
            "plan_id": plan.plan_id,
            "mirror_path": str(mirror_path),
        },
        timeout=timeout,
    )


@dataclass(frozen=True)
class _RefSnapshot:
    refs: tuple[tuple[str, str], ...]
    event_id: str


def _capture_refs(
    mirror_path: Path,
    audit_chain: AuditChain,
    actor: str,
    plan: PurgePlan,
    timeout: float,
) -> _RefSnapshot:
    """Run `git for-each-ref` and parse the (ref, sha) pairs.

    Output format is `<sha> <type> <ref>` per line (default `for-each-ref`
    format). We keep (ref, sha) pairs sorted lexicographically by ref
    so the snapshot tuple is canonical.
    """

    result = run_streamed(
        [
            "git",
            "--git-dir",
            str(mirror_path),
            "for-each-ref",
            "--format=%(objectname) %(refname)",
        ],
        audit_chain=audit_chain,
        actor=actor,
        event_kind=EventKind.GENERIC,
        payload={
            "phase": "mirror-for-each-ref",
            "plan_id": plan.plan_id,
            "mirror_path": str(mirror_path),
        },
        timeout=timeout,
    )
    if result.returncode != 0:
        raise MirrorError(
            f"git for-each-ref exited {result.returncode} on {mirror_path}; "
            f"see transcript at {result.transcript_path}"
        )

    pairs: list[tuple[str, str]] = []
    transcript = result.transcript_path.read_text(encoding="utf-8")
    for raw_line in transcript.splitlines():
        # The transcript prefixes every line with "[stdout] " or
        # "[stderr] " (§7.0.6 lossless retention format). Only stdout
        # lines carry the parseable refs.
        if not raw_line.startswith("[stdout] "):
            continue
        payload = raw_line[len("[stdout] "):].rstrip("\n")
        if not payload:
            continue
        parts = payload.split(" ", 1)
        if len(parts) != 2:
            continue
        sha, ref = parts
        pairs.append((ref, sha))

    pairs.sort(key=lambda pair: pair[0])
    return _RefSnapshot(refs=tuple(pairs), event_id=result.event_id)


__all__ = [
    "MirrorError",
    "MirrorResult",
    "MirrorVerification",
    "create_mirror",
    "verify_mirror",
]
