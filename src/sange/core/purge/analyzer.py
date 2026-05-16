"""`analyze_mirror` — the §6.11 read-only `--analyze` capability.

Reads the mirror, applies the plan's filters, computes what *would*
be purged. Populates the `counts` dict per §6.11.6:

    {"affected_commits": 47,
     "affected_refs":    12,   # NOT in this slice; lands in T-111d
     "deleted_objects":  1203,
     "size_delta_bytes": -85234112}

The result is bound to the audit chain via three streamed
subprocesses (rev-list, cat-file, log) — each lands one chain
entry + a 0600 transcript. The pipeline:

  1. `git rev-list --all --objects` — enumerate every reachable
     object with its path-when-applicable. Builds the map
     `path → set[sha]`.

  2. Filter the paths via `plan.filters.paths` (exact) + `globs`
     (`fnmatch`). The matched-paths set is the v0.5 "what we'd
     remove" surface.

  3. `git cat-file --batch-check='%(objecttype) %(objectsize)
     %(objectname)' --batch-all-objects` — enumerates every object
     in the repo with its type + size in one syscall. We
     intersect with the candidate shas from step 1 + 2 and keep
     the blob-typed ones, summing their sizes.

  4. `git log --all --pretty=format:%H -- <matched_paths>` — set
     of commits that ever touched a matched path. Deduped to a
     count.

`affected_refs` requires per-ref reachability checks (`merge-base
--is-ancestor` over every ref vs every affected commit) and is
deferred to T-111d. The v0.5 audit-counts dict ships with the
three populated keys + a `None` placeholder if a caller needs the
key present.
"""

from __future__ import annotations

import collections
import fnmatch
from dataclasses import dataclass
from pathlib import Path

from sange.core.audit import AuditChain, EventKind
from sange.core.purge.plan import PurgeFilters, PurgePlan
from sange.core.streaming import run_streamed


class AnalysisError(Exception):
    """Raised when analyze_mirror can't proceed (e.g. git exits non-zero)."""


@dataclass(frozen=True)
class AnalysisResult:
    """Per-plan analysis outcome.

    Fields:
      * `affected_commits`   — distinct commit shas whose tree referenced
                               at least one matched path.
      * `matched_blob_shas`  — sorted tuple of blob shas the filters cover.
      * `matched_paths`      — sorted tuple of paths the filters matched.
      * `size_delta_bytes`   — negative integer: total bytes that would
                               be reclaimed.
      * `revlist_event_id` / `catfile_event_id` / `log_event_id` —
        audit chain ids for the three streamed subprocesses (the third
        is "" if `matched_paths` is empty, since the `git log` skip
        is intentional).

    `deleted_objects` is a `property` so the audit-counts dict can read
    it without redundant storage; `as_counts()` returns the §6.11.6
    counts-dict shape.
    """

    affected_commits: int
    matched_blob_shas: tuple[str, ...]
    matched_paths: tuple[str, ...]
    size_delta_bytes: int
    revlist_event_id: str
    catfile_event_id: str
    log_event_id: str

    @property
    def deleted_objects(self) -> int:
        return len(self.matched_blob_shas)

    def as_counts(self) -> dict[str, int]:
        """The `counts` payload per §6.11.6, ready to merge into `plan.counts`."""

        return {
            "affected_commits": self.affected_commits,
            "deleted_objects": self.deleted_objects,
            "size_delta_bytes": self.size_delta_bytes,
        }


def analyze_mirror(
    plan: PurgePlan,
    mirror_path: Path,
    *,
    audit_chain: AuditChain,
    actor: str,
    timeout: float = 300.0,
) -> AnalysisResult:
    """Run the read-only --analyze pipeline against the mirror.

    Args:
      plan:         the active `PurgePlan` (used for plan_id + filters).
      mirror_path:  bare-repo dir created by `create_mirror()`
                    (e.g. `<repo>/.sange/purge/<plan_id>/work.git`).
      audit_chain:  chain to thread the three subprocesses' events onto.
      actor:        audit-entry actor.
      timeout:      per-subprocess timeout (default 300s — git rev-list
                    on big repos can take minutes).
    """

    if plan.target_vcs != "git":
        raise AnalysisError(
            f"analyze_mirror only supports git (got {plan.target_vcs!r})"
        )
    if not mirror_path.is_dir():
        raise AnalysisError(f"mirror not found: {mirror_path}")

    # ---- 1. rev-list --all --objects ----------------------------------
    revlist = run_streamed(
        [
            "git",
            "--git-dir",
            str(mirror_path),
            "rev-list",
            "--all",
            "--objects",
        ],
        audit_chain=audit_chain,
        actor=actor,
        event_kind=EventKind.GENERIC,
        payload={
            "phase": "analyze-revlist",
            "plan_id": plan.plan_id,
            "mirror_path": str(mirror_path),
        },
        timeout=timeout,
    )
    if revlist.returncode != 0:
        raise AnalysisError(
            f"git rev-list exited {revlist.returncode}; "
            f"see transcript at {revlist.transcript_path}"
        )

    path_to_shas: dict[str, set[str]] = collections.defaultdict(set)
    for line in _stdout_lines(revlist.transcript_path):
        parts = line.split(" ", 1)
        if len(parts) == 2:
            sha, path = parts
            path_to_shas[path].add(sha)

    # ---- 2. Apply filters ---------------------------------------------
    matched_paths = _match_paths(set(path_to_shas), plan.filters)
    candidate_shas: set[str] = set()
    for path in matched_paths:
        candidate_shas.update(path_to_shas[path])

    # ---- 3. cat-file --batch-all-objects for type+size ----------------
    catfile = run_streamed(
        [
            "git",
            "--git-dir",
            str(mirror_path),
            "cat-file",
            "--batch-check=%(objecttype) %(objectsize) %(objectname)",
            "--batch-all-objects",
        ],
        audit_chain=audit_chain,
        actor=actor,
        event_kind=EventKind.GENERIC,
        payload={
            "phase": "analyze-cat-file",
            "plan_id": plan.plan_id,
            "mirror_path": str(mirror_path),
        },
        timeout=timeout,
    )
    if catfile.returncode != 0:
        raise AnalysisError(
            f"git cat-file exited {catfile.returncode}; "
            f"see transcript at {catfile.transcript_path}"
        )

    matched_blobs: set[str] = set()
    total_size = 0
    for line in _stdout_lines(catfile.transcript_path):
        parts = line.split(" ", 2)
        if len(parts) != 3:
            continue
        obj_type, size_str, sha = parts
        if obj_type != "blob":
            continue
        if sha not in candidate_shas:
            continue
        try:
            blob_size = int(size_str)
        except ValueError:
            continue
        matched_blobs.add(sha)
        total_size += blob_size

    # ---- 4. git log for affected_commits ------------------------------
    log_event_id = ""
    affected_commits = 0
    if matched_paths:
        log_result = run_streamed(
            [
                "git",
                "--git-dir",
                str(mirror_path),
                "log",
                "--all",
                "--pretty=format:%H",
                "--",
                *sorted(matched_paths),
            ],
            audit_chain=audit_chain,
            actor=actor,
            event_kind=EventKind.GENERIC,
            payload={
                "phase": "analyze-log",
                "plan_id": plan.plan_id,
                "mirror_path": str(mirror_path),
                "paths_count": len(matched_paths),
            },
            timeout=timeout,
        )
        if log_result.returncode != 0:
            raise AnalysisError(
                f"git log exited {log_result.returncode}; "
                f"see transcript at {log_result.transcript_path}"
            )
        commit_shas: set[str] = set()
        for line in _stdout_lines(log_result.transcript_path):
            stripped = line.strip()
            if len(stripped) == 40 and all(c in "0123456789abcdef" for c in stripped):
                commit_shas.add(stripped)
        affected_commits = len(commit_shas)
        log_event_id = log_result.event_id

    return AnalysisResult(
        affected_commits=affected_commits,
        matched_blob_shas=tuple(sorted(matched_blobs)),
        matched_paths=tuple(sorted(matched_paths)),
        size_delta_bytes=-total_size,
        revlist_event_id=revlist.event_id,
        catfile_event_id=catfile.event_id,
        log_event_id=log_event_id,
    )


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _stdout_lines(transcript_path: Path) -> list[str]:
    """Read the streaming-helper transcript + return only `[stdout] ` lines.

    Mirrors `mirror._capture_refs`'s parsing — the transcript is the
    spec-mandated single source of truth.
    """

    text = transcript_path.read_text(encoding="utf-8")
    out: list[str] = []
    for raw in text.splitlines():
        if not raw.startswith("[stdout] "):
            continue
        out.append(raw[len("[stdout] "):])
    return out


def _match_paths(all_paths: set[str], filters: PurgeFilters) -> set[str]:
    """Apply `filters.paths` (exact) + `filters.globs` (fnmatch) to `all_paths`.

    `replace_text_hashes` is NOT applied here — that's a redaction
    filter, not a path filter, and lands in the destructive-ops slice
    (T-203+ v1.0) when the rewrite tool actually consumes it.
    """

    matched: set[str] = set()
    exact = set(filters.paths)
    matched.update(all_paths & exact)
    if filters.globs:
        for path in all_paths:
            if path in matched:
                continue
            for pattern in filters.globs:
                if fnmatch.fnmatch(path, pattern):
                    matched.add(path)
                    break
    return matched


__all__ = [
    "AnalysisError",
    "AnalysisResult",
    "analyze_mirror",
]
