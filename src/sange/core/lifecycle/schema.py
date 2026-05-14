"""`CommitJSON` Pydantic v2 schema — §6.8.3 of the architecture prompt.

Every commit JSON file on disk validates against `CommitJSON`. Each file
represents one lifecycle-tracked commit message; the file's lifetime
spans the §6.8.2 state machine from `draft` to `archived`.

JSON-Schema-versioned via `schema_version` integer (separate from the
SangeConfig schema version) — bumping is a SemVer-breaking change to
the commit-store format.

State transitions are NOT enforced at this model level. The model only
declares that `status` is one of the eight valid values; T-007's state
machine enforces forward-only transitions + the reopen exception.
"""

from __future__ import annotations

import datetime as _dt
import enum
import re
import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


SCHEMA_VERSION = 1


# --------------------------------------------------------------------------- #
# State machine — enumerated states only, no transitions
# --------------------------------------------------------------------------- #


class CommitStatus(str, enum.Enum):
    """The eight lifecycle states per §6.8.2.

    Transitions are owned by `sange.core.lifecycle.state_machine` (T-007);
    here we only declare that these are the valid values.
    """

    DRAFT = "draft"
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    COMMITTED = "committed"
    PUSHED = "pushed"
    ARCHIVED = "archived"
    DISCARDED = "discarded"


# Conventional Commits 1.0.0 types (same set as Appendix G presets).
ConventionalType = Literal[
    "feat", "fix", "docs", "style", "refactor",
    "perf", "test", "build", "ci", "chore", "revert",
]


# --------------------------------------------------------------------------- #
# Sub-models
# --------------------------------------------------------------------------- #


_SCOPE_RE = re.compile(r"^[a-z0-9](-?[a-z0-9])*$")


class CommitMessage(BaseModel):
    """The Conventional-Commits-shaped commit-message body.

    Per §6.8.3 the structured form is the source of truth; `rendered` is
    computed from the other fields and stored for grep-ability.
    """

    type: ConventionalType
    scope: str = Field(default="", max_length=60)
    subject: str = Field(min_length=1, max_length=120)
    body: str = Field(default="")
    footer: str = Field(default="")
    breaking_change: bool = Field(default=False)
    co_authors: list[str] = Field(default_factory=list)
    references: list[str] = Field(default_factory=list)
    rendered: str = Field(default="", description="Rendered subject + body + footer; computed by the lifecycle layer.")

    model_config = ConfigDict(extra="forbid", frozen=False)

    @field_validator("scope")
    @classmethod
    def _scope_is_slug_like(cls, value: str) -> str:
        if not value:
            return value
        if not _SCOPE_RE.match(value):
            raise ValueError(
                f"commit scope {value!r} must be lowercase letters / digits / hyphens"
            )
        return value

    @field_validator("subject")
    @classmethod
    def _subject_single_line(cls, value: str) -> str:
        if "\r" in value or "\n" in value:
            raise ValueError("commit subject must be single-line")
        return value


class CommitDiff(BaseModel):
    """Aggregate diff statistics — mirrors `sange.core.models.DiffSummary`.

    Kept as a separate Pydantic model rather than re-using `DiffSummary`
    because Pydantic validates on construction; the Domain `DiffSummary`
    is constructed by Adapters (already validated input). The two can be
    converted via `from_diff_summary()` / `.to_diff_summary()` round-trip.
    """

    files_changed: int = Field(default=0, ge=0)
    insertions: int = Field(default=0, ge=0)
    deletions: int = Field(default=0, ge=0)
    content_hash: str = Field(default="")

    model_config = ConfigDict(extra="forbid", frozen=False)

    @field_validator("content_hash")
    @classmethod
    def _content_hash_is_sha256_or_empty(cls, value: str) -> str:
        if value and len(value) != 64:
            raise ValueError(
                f"content_hash must be 64-char sha256 or empty; got {len(value)} chars"
            )
        return value


class AIProvenance(BaseModel):
    """AI provenance for AI-generated commit messages.

    Empty when the message was authored by a human. Populated by the
    §6.7.1 prompt enhancer after each successful AI call.
    """

    generated: bool = Field(default=False)
    provider: str = Field(default="")
    model: str = Field(default="")
    prompt_version: str = Field(default="")
    template_id: str = Field(default="")
    cost_estimate_usd: float = Field(default=0.0, ge=0.0)
    tokens_in: int = Field(default=0, ge=0)
    tokens_out: int = Field(default=0, ge=0)
    enhancer_version: str = Field(default="")

    model_config = ConfigDict(extra="forbid", frozen=False)

    @model_validator(mode="after")
    def _generated_iff_provider(self) -> AIProvenance:
        # If `generated=True` we expect provider + model populated; if
        # `generated=False` we expect all fields empty.
        if self.generated and not (self.provider and self.model):
            raise ValueError(
                "AIProvenance.generated=True requires provider + model populated"
            )
        if not self.generated and (
            self.provider or self.model or self.tokens_in or self.tokens_out
        ):
            raise ValueError(
                "AIProvenance fields are populated but generated=False — inconsistent"
            )
        return self


class Approval(BaseModel):
    """A single approval event for a commit JSON.

    Per §6.8.3: actor identity + timestamp + the surface they approved
    through (`cli`, `tui`, `web`, `mcp`). The audit log mirrors every
    approval for forensic queries.
    """

    actor: str = Field(min_length=1, max_length=120)
    at: _dt.datetime
    via: Literal["cli", "tui", "web", "mcp"] = "cli"

    model_config = ConfigDict(extra="forbid", frozen=False)


class Rejection(BaseModel):
    """A single rejection event for a commit JSON."""

    actor: str = Field(min_length=1, max_length=120)
    at: _dt.datetime
    reason: str = Field(min_length=1, max_length=480)
    via: Literal["cli", "tui", "web", "mcp"] = "cli"

    model_config = ConfigDict(extra="forbid", frozen=False)


class Author(BaseModel):
    """Optional commit author — overrides `git config user.{name,email}` when set."""

    name: str = Field(default="")
    email: str = Field(default="")

    model_config = ConfigDict(extra="forbid", frozen=False)


# --------------------------------------------------------------------------- #
# Root model — `CommitJSON`
# --------------------------------------------------------------------------- #


class CommitJSON(BaseModel):
    """The complete commit-message JSON file per §6.8.3.

    Lifecycle:
      * Created in `DRAFT` state when the user runs `sange commits new`
        or `sange commits ai`.
      * Transitions through `PENDING_REVIEW` / `APPROVED` / `COMMITTED` /
        `PUSHED` / `ARCHIVED` over time.
      * `REJECTED` / `DISCARDED` are terminal.

    On-disk filename: `NNNN-<type>-<scope>-<short-subject>.json` where
    `NNNN` comes from the per-repo monotonic counter.
    """

    schema_version: int = Field(default=SCHEMA_VERSION, ge=1)
    id: str = Field(
        default_factory=lambda: uuid.uuid4().hex,
        description="ULID-like unique id (uuid4 hex by default).",
    )
    counter: int = Field(ge=1)
    status: CommitStatus = Field(default=CommitStatus.DRAFT)
    created_at: _dt.datetime
    updated_at: _dt.datetime
    repo_slug: str = Field(default="")
    repo_path: str = Field(default="")
    branch: str = Field(default="")
    message: CommitMessage
    diff: CommitDiff = Field(default_factory=CommitDiff)
    author: Author = Field(default_factory=Author)
    ai: AIProvenance = Field(default_factory=AIProvenance)
    approvals: list[Approval] = Field(default_factory=list)
    rejections: list[Rejection] = Field(default_factory=list)
    template_id: str = Field(default="")
    tags: list[str] = Field(default_factory=list)
    committed_sha: str = Field(
        default="",
        description="Populated once the lifecycle transitions to COMMITTED.",
    )
    pushed_remote: str = Field(default="")

    model_config = ConfigDict(extra="forbid", frozen=False)

    # ----- validators ------------------------------------------------- #

    @model_validator(mode="after")
    def _updated_at_not_before_created(self) -> CommitJSON:
        if self.updated_at < self.created_at:
            raise ValueError(
                f"updated_at ({self.updated_at}) < created_at ({self.created_at})"
            )
        return self

    @model_validator(mode="after")
    def _committed_sha_iff_committed_or_later(self) -> CommitJSON:
        post_commit_states = {
            CommitStatus.COMMITTED, CommitStatus.PUSHED, CommitStatus.ARCHIVED,
        }
        if self.status in post_commit_states:
            if not self.committed_sha:
                raise ValueError(
                    f"status={self.status.value} but committed_sha is empty"
                )
        else:
            if self.committed_sha:
                raise ValueError(
                    f"status={self.status.value} but committed_sha is set "
                    "(set only on COMMITTED+)"
                )
        return self

    @model_validator(mode="after")
    def _pushed_remote_iff_pushed_or_archived(self) -> CommitJSON:
        post_push_states = {CommitStatus.PUSHED, CommitStatus.ARCHIVED}
        if self.status in post_push_states:
            if not self.pushed_remote:
                raise ValueError(
                    f"status={self.status.value} but pushed_remote is empty"
                )
        else:
            if self.pushed_remote:
                raise ValueError(
                    f"status={self.status.value} but pushed_remote is set "
                    "(set only on PUSHED+)"
                )
        return self


__all__ = [
    "AIProvenance",
    "Approval",
    "Author",
    "CommitDiff",
    "CommitJSON",
    "CommitMessage",
    "CommitStatus",
    "ConventionalType",
    "Rejection",
    "SCHEMA_VERSION",
]
