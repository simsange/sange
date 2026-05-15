"""Sange Domain models — VCS-agnostic data shapes.

Per §6.2 of the architecture prompt the Domain layer is pure data + behavior
with NO knowledge of which VCS is in use. Adapters (`sange.adapters.vcs.*`)
translate between VCS-specific concepts and these abstract types.

Dataclasses (not Pydantic) because:
  * The Domain entities are constructed by Adapters which already validate
    the input (file paths exist, SHAs are well-formed). Adding Pydantic
    would double-validate every read.
  * Dataclasses are cheaper to construct (no model_validate overhead).
  * `SangeConfig` (the user-supplied configuration) gets Pydantic
    strictness; the Domain (read by code, written by code) gets the
    lightweight shape.

v0.1 MVP scope: the minimum models the `VCSDriver` Protocol needs.

  * `Repo`              — the repo root + VCS identity.
  * `CommitRef`         — a single commit reference (SHA + author + subject).
  * `BranchInfo`        — branch name + tip + tracking metadata.
  * `RemoteInfo`        — remote name + URL.
  * `WorkingCopyStatus` — collected file states + counts.
  * `FileEntry`         — one entry inside a `WorkingCopyStatus`.
  * `DiffSummary`       — files-changed / insertions / deletions + hash.

v0.5+/v1.0 extension points (not yet stubbed; each lands alongside
the relevant subsystem per docs/governance/roadmap.md):
  * `Release`           — release bundle metadata (§6.9), v0.5+.
  * `Bundle`            — versioned signed artifact (§6.9), v0.5+.
  * `PurgePlan`         — history-rewrite plan (§6.11), v0.5 read-only / v1.0 destructive.
  * `Approval`          — multi-actor approval chain (§6.8); a v0.1 single-
                          actor `Approval` already exists in
                          `sange.core.lifecycle.schema` for the lifecycle
                          state-machine — the §6.8 multi-actor extension is v0.5+.
  * `AuditEntry`        — hash-chained JSONL row (§7.0.7), v0.5+.
  * `CommitTemplate`    — Conventional-Commits-shaped preset (already in
                          `templates/commit-templates/default.toml`).
"""

from __future__ import annotations

from sange.core.models.branch import BranchInfo, RemoteInfo
from sange.core.models.commit import CommitRef, DiffSummary
from sange.core.models.repo import Repo, VCSKind
from sange.core.models.working_copy import FileEntry, FileState, WorkingCopyStatus

__all__ = [
    "BranchInfo",
    "CommitRef",
    "DiffSummary",
    "FileEntry",
    "FileState",
    "RemoteInfo",
    "Repo",
    "VCSKind",
    "WorkingCopyStatus",
]
