"""`PurgePlan` model + persistence (§6.11).

The plan is the persistent representation of one purge operation —
what to remove, from which repo, in which VCS, and where it sits in
the §6.11.2 lifecycle. One plan lives at
`<repo>/.sange/purge/<plan-id>/plan.json`; the directory also holds
the mirror clone + backup tarball + scanner reports in later slices.

This module owns:
  * The Pydantic v2 model (`PurgePlan` + sub-models).
  * Atomic JSON persistence via `PurgePlanStore` (tmp+fsync+rename).
  * `new_plan_id()` generator.

It does NOT own:
  * Audit-chain integration — the CLI layer pairs each
    `plan.transition(...)` with `chain.append(EventKind.PURGE_PLAN, ...)`
    so the two concerns stay independent.
  * State-machine logic — `transition()` delegates to
    `sange.core.purge.state.assert_transition`.
"""

from __future__ import annotations

import datetime as _dt
import os
import re
import secrets
import tempfile
from pathlib import Path
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from sange.core.purge.state import (
    PurgeState,
    assert_transition,
)

SCHEMA_VERSION = 1

VCSKind = Literal["git", "svn", "hg", "p4"]

# Canonical plan-id format: `purge-<UTC-ISO>-<8-hex>`.
# The dashes inside the timestamp replace the `:` that the OS forbids
# on Windows filenames + that confuses URL parsers.
_PLAN_ID_RE = re.compile(
    r"^purge-\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}Z-[0-9a-f]{8}$"
)


def _utcnow_iso() -> str:
    """ISO 8601 UTC second-precision — matches the audit chain's format."""

    return _dt.datetime.now(tz=_dt.UTC).replace(microsecond=0).isoformat()


def new_plan_id(*, clock: _dt.datetime | None = None) -> str:
    """Generate a canonical plan id.

    Format: `purge-<YYYY-MM-DDTHH-MM-SSZ>-<8-hex>`. The 8-hex nonce is
    `secrets.token_hex(4)` — 32 bits of randomness, plenty for the
    "two purges started in the same second" case while staying short
    enough to type from memory.
    """

    moment = clock or _dt.datetime.now(tz=_dt.UTC)
    ts = moment.strftime("%Y-%m-%dT%H-%M-%SZ")
    nonce = secrets.token_hex(4)
    return f"purge-{ts}-{nonce}"


# --------------------------------------------------------------------------- #
# Sub-models
# --------------------------------------------------------------------------- #


class PurgeFilters(BaseModel):
    """What the plan purges.

    At least one of the three lists must be non-empty — an empty filter
    set is a configuration error, not a "remove nothing" no-op.

    * `paths` — exact relative paths (the safest, most precise form).
    * `globs` — gitignore-style globs (covers renamed-over-time files).
    * `replace_text_hashes` — sha256 hex hashes of strings to redact
      from blob contents. Hash-only so the raw secret never appears
      in the plan file (which is gitignored but still readable).
    """

    model_config = ConfigDict(extra="forbid", frozen=False)

    paths: list[str] = Field(default_factory=list)
    globs: list[str] = Field(default_factory=list)
    replace_text_hashes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _require_at_least_one(self) -> Self:
        if not (self.paths or self.globs or self.replace_text_hashes):
            raise ValueError(
                "PurgeFilters: at least one of paths / globs / "
                "replace_text_hashes must be non-empty"
            )
        return self


class RepoMeta(BaseModel):
    """The repository the purge targets."""

    model_config = ConfigDict(extra="forbid", frozen=False)

    path: str  # absolute path to the working repo (not the mirror)
    remote: str = ""  # e.g. git@github.com:foo/bar.git
    slug: str = ""  # short cross-host identifier (e.g. foo/bar)


class ToolMeta(BaseModel):
    """The actual rewrite tool the executor invokes.

    Populated when the plan reaches `executing` — empty/unknown until
    then. Examples: `git filter-repo` 2.47.0, `bfg` 1.14.0,
    `svnadmin` 1.14.3, `hg convert`, `p4 obliterate`.
    """

    model_config = ConfigDict(extra="forbid", frozen=False)

    name: str
    version: str = ""


class PreflightCheck(BaseModel):
    """One pre-flight gate result (§6.11.4)."""

    model_config = ConfigDict(extra="forbid", frozen=False)

    name: str
    status: Literal["green", "red", "yellow", "skipped"]
    detail: str = ""


# --------------------------------------------------------------------------- #
# Root model
# --------------------------------------------------------------------------- #


class PurgePlan(BaseModel):
    """The persistent declaration of one purge operation.

    `state` is held in the model for transparency but mutated only via
    `transition()` which delegates to `assert_transition`. Constructing
    a `PurgePlan` with a non-default `state` is legal — that's how the
    store rehydrates a plan partway through its lifecycle.
    """

    model_config = ConfigDict(extra="forbid", frozen=False)

    schema_version: int = SCHEMA_VERSION
    plan_id: str = Field(default_factory=new_plan_id)
    created_at: str = Field(default_factory=_utcnow_iso)
    updated_at: str = Field(default_factory=_utcnow_iso)
    created_by: str
    state: PurgeState = PurgeState.PLANNED
    target_vcs: VCSKind
    target_repo: RepoMeta
    filters: PurgeFilters
    counts: dict[str, int] = Field(default_factory=dict)
    scanner_results: dict[str, int] = Field(default_factory=dict)
    preflight_checks: list[PreflightCheck] = Field(default_factory=list)
    tool: ToolMeta | None = None
    backup_path: str = ""
    mirror_path: str = ""
    dry_run: bool = False
    batch: bool = False
    notes: str = ""
    aborted_reason: str = ""
    rolled_back_reason: str = ""

    @model_validator(mode="after")
    def _validate(self) -> Self:
        if not _PLAN_ID_RE.match(self.plan_id):
            raise ValueError(
                f"plan_id does not match canonical format "
                f"`purge-<UTC-ISO>-<8-hex>`: {self.plan_id}"
            )
        if self.updated_at < self.created_at:
            raise ValueError("updated_at must be >= created_at")
        return self

    def transition(self, new_state: PurgeState, *, reason: str = "") -> None:
        """Validate + apply a state transition.

        Raises `IllegalTransition` if the transition isn't legal per
        §6.11.2. Updates `updated_at`. Records `reason` on the
        terminal aborted/rolled_back transitions so the post-mortem
        is in-band rather than needing the audit log.
        """

        assert_transition(self.state, new_state)
        self.state = new_state
        self.updated_at = _utcnow_iso()
        if new_state is PurgeState.ABORTED:
            self.aborted_reason = reason
        elif new_state is PurgeState.ROLLED_BACK:
            self.rolled_back_reason = reason


# --------------------------------------------------------------------------- #
# Persistence
# --------------------------------------------------------------------------- #


class PurgePlanNotFound(Exception):
    """Raised by `PurgePlanStore.load()` when the plan doesn't exist."""

    def __init__(self, plan_id: str) -> None:
        super().__init__(f"purge plan not found: {plan_id}")
        self.plan_id = plan_id


class PurgePlanStore:
    """Per-repo store at `<repo>/.sange/purge/<plan-id>/plan.json`.

    The plan dir is the operating-set root for everything else in the
    lifecycle (mirror clone, backup tarball, scanner reports, transcripts).
    Later slices add sibling files; this slice owns `plan.json` only.
    """

    def __init__(self, repo_root: Path) -> None:
        self._repo_root = Path(repo_root).resolve()

    @property
    def repo_root(self) -> Path:
        return self._repo_root

    @property
    def root_dir(self) -> Path:
        return self._repo_root / ".sange" / "purge"

    def plan_dir(self, plan_id: str) -> Path:
        if not _PLAN_ID_RE.match(plan_id):
            raise ValueError(f"invalid plan_id: {plan_id}")
        return self.root_dir / plan_id

    def plan_path(self, plan_id: str) -> Path:
        return self.plan_dir(plan_id) / "plan.json"

    def exists(self, plan_id: str) -> bool:
        return self.plan_path(plan_id).is_file()

    def save(self, plan: PurgePlan) -> Path:
        """Atomic write of `plan.json`.

        Uses tmp+fsync+rename so a crash mid-write leaves either the
        old plan or the new plan on disk — never a half-written one.
        Mirrors `sange.core.lifecycle.store._atomic_write` and the
        T-101 swap engine's discipline.
        """

        target_dir = self.plan_dir(plan.plan_id)
        target_dir.mkdir(parents=True, exist_ok=True)
        target = self.plan_path(plan.plan_id)

        text = plan.model_dump_json(indent=2) + "\n"

        fd, tmp_path_str = tempfile.mkstemp(
            dir=str(target_dir),
            prefix=".plan-",
            suffix=".tmp",
        )
        tmp_path = Path(tmp_path_str)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fp:
                fp.write(text)
                fp.flush()
                os.fsync(fp.fileno())
            os.replace(tmp_path, target)
        except OSError:
            # Best-effort cleanup of the half-written tmp.
            try:
                tmp_path.unlink()
            except OSError:
                pass
            raise
        return target

    def load(self, plan_id: str) -> PurgePlan:
        """Read + validate a plan from disk."""

        if not self.exists(plan_id):
            raise PurgePlanNotFound(plan_id)
        text = self.plan_path(plan_id).read_text(encoding="utf-8")
        return PurgePlan.model_validate_json(text)

    def list_plans(self) -> list[str]:
        """All plan ids on disk, sorted oldest-first.

        The canonical id format sorts lexicographically === chronologically
        within a single year because the embedded timestamp is ISO-8601.
        """

        if not self.root_dir.is_dir():
            return []
        ids: list[str] = []
        for entry in sorted(self.root_dir.iterdir()):
            if (
                entry.is_dir()
                and _PLAN_ID_RE.match(entry.name)
                and (entry / "plan.json").is_file()
            ):
                ids.append(entry.name)
        return ids


__all__ = [
    "SCHEMA_VERSION",
    "PreflightCheck",
    "PurgeFilters",
    "PurgePlan",
    "PurgePlanNotFound",
    "PurgePlanStore",
    "RepoMeta",
    "ToolMeta",
    "VCSKind",
    "new_plan_id",
]
