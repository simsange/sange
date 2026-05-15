"""Commit-message generation template — Conventional Commits 1.0.0.

Per §6.7.1 + §6.8: this is the first concrete `PromptTemplate` shipped
with v0.1, and the one the `sange commit` command (T-040+) will wire
into the lifecycle (§6.8) to generate the initial DRAFT message.

Contract:

  * **Input** — a staged diff (text), optional scope override,
    optional repo context (recent commit messages on the branch, the
    branch name, files-changed count).
  * **Output** — a structured `CommitMessageResult` with the parsed
    Conventional Commits fields: `type` (one of the canonical 11),
    `scope`, `subject` (≤ 72 chars per §6.8.5), optional `body`, and
    `breaking_change` flag. The shape matches `CommitMessage` from
    `sange.core.lifecycle.schema` so the result can be promoted into
    a `CommitJSON` without translation.

The template is **versioned**. v1.0.0 is the production shape; any
material change to the prompt or schema bumps the version so prompt
regression-tests can pin a specific revision.

Redaction (T-030 mitigation) happens automatically when the template
is consumed through `PromptEnhancer.enhance()`; this module never
sees the raw diff. The enhancer scrubs each string variable BEFORE
interpolation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from sange.core.enhancer.enhancer import EnhancedResult, PromptEnhancer
from sange.core.enhancer.templates import PromptTemplate, TemplateRegistry

if TYPE_CHECKING:
    from sange.core.telemetry.collector import TelemetryCollector


# --------------------------------------------------------------------------- #
# Canonical Conventional Commits types — must match
# `tools/generators/commit_templates.py::CC_TYPES` exactly.
# --------------------------------------------------------------------------- #


CONVENTIONAL_COMMIT_TYPES: tuple[str, ...] = (
    "feat", "fix", "docs", "style", "refactor", "perf",
    "test", "build", "ci", "chore", "revert",
)


# --------------------------------------------------------------------------- #
# Template constants
# --------------------------------------------------------------------------- #


TEMPLATE_ID = "commit-message"
TEMPLATE_VERSION = "1.0.0"

_SYSTEM_PROMPT = (
    "You are an expert Conventional Commits 1.0.0 author. "
    "You produce concise, accurate commit messages that follow the spec exactly: "
    "imperative mood subject, no trailing punctuation, ≤ 72 chars, "
    "and a precise scope. You never invent context that isn't in the diff."
)

_USER_PROMPT = """\
Write a Conventional Commits 1.0.0 message for the staged changes below.

## Constraints

- `type`: choose ONE of: feat, fix, docs, style, refactor, perf, test, build, ci, chore, revert.
- `scope`: a single lowercase kebab-case token describing the subsystem touched (or empty if no clear scope).
- `subject`: imperative mood, ≤ 72 chars, no trailing punctuation. Examples: "add passkey login", "fix race in token refresh".
- `body`: optional. Two-or-more sentences explaining the *why*, not the *what*. Wrap at 72 columns. Empty string if not needed.
- `breaking_change`: true ONLY if the change is API-incompatible. Document the break in the body if true.

## Repo context

- Branch: {branch}
- Recent commits on this branch:
{recent_commits}

## Files changed ({files_changed_count})

{files_changed_summary}

## Staged diff

```
{diff}
```

Respond with a JSON object exactly matching the declared schema. Do not include prose outside the JSON.
"""

_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["type", "subject", "scope", "body", "breaking_change"],
    "properties": {
        "type": {"type": "string"},
        "scope": {"type": "string"},
        "subject": {"type": "string"},
        "body": {"type": "string"},
        "breaking_change": {"type": "boolean"},
    },
}


# --------------------------------------------------------------------------- #
# Request / Result dataclasses
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class CommitMessageRequest:
    """Input to `generate_commit_message()`.

    Fields:
      * `diff`                 — the staged diff text (required).
      * `branch`               — current branch name. Empty fallback OK.
      * `recent_commits`       — up to ~5 recent commit subjects on
                                  this branch, newline-separated.
                                  Empty fallback OK.
      * `files_changed`        — list of relative paths the diff
                                  touches. Used to build the
                                  `files_changed_summary`. Empty OK.
      * `scope_override`       — when set, the caller has a specific
                                  scope in mind; the prompt is
                                  augmented with `Scope: {override}`
                                  to bias the model.
    """

    diff: str
    branch: str = ""
    recent_commits: str = ""
    files_changed: tuple[str, ...] = field(default_factory=tuple)
    scope_override: str = ""

    def __post_init__(self) -> None:
        if not self.diff:
            raise ValueError("CommitMessageRequest.diff must be non-empty")


@dataclass(frozen=True)
class CommitMessageResult:
    """The structured commit-message payload returned by the model.

    Mirrors `CommitMessage` from `sange.core.lifecycle.schema` so the
    result can be promoted directly into a `CommitJSON` row.
    """

    type: str
    subject: str
    scope: str = ""
    body: str = ""
    breaking_change: bool = False
    raw_response: str = ""
    audit_id: str = ""

    def __post_init__(self) -> None:
        if self.type not in CONVENTIONAL_COMMIT_TYPES:
            raise ValueError(
                f"CommitMessageResult.type must be one of {CONVENTIONAL_COMMIT_TYPES!r}; "
                f"got {self.type!r}"
            )
        if not self.subject:
            raise ValueError("CommitMessageResult.subject must be non-empty")
        if len(self.subject) > 72:
            raise ValueError(
                f"CommitMessageResult.subject must be ≤ 72 chars; got {len(self.subject)}"
            )
        if "\n" in self.subject:
            raise ValueError("CommitMessageResult.subject must be single-line")


# --------------------------------------------------------------------------- #
# Template builder
# --------------------------------------------------------------------------- #


def build_commit_message_template() -> PromptTemplate:
    """Return the v1.0.0 commit-message `PromptTemplate`."""

    return PromptTemplate(
        id=TEMPLATE_ID,
        version=TEMPLATE_VERSION,
        task="commit-msg",
        system_template=_SYSTEM_PROMPT,
        user_template=_USER_PROMPT,
        description=(
            "Generates a Conventional Commits 1.0.0 message from a "
            "staged diff + repo context."
        ),
        required_vars=(
            "diff",
            "branch",
            "recent_commits",
            "files_changed_count",
            "files_changed_summary",
        ),
        output_schema=_OUTPUT_SCHEMA,
    )


# --------------------------------------------------------------------------- #
# High-level convenience — wire enhancer + template + parse result.
# --------------------------------------------------------------------------- #


def generate_commit_message(
    request: CommitMessageRequest,
    *,
    enhancer: PromptEnhancer | None = None,
    provider: str | None = None,
    model: str | None = None,
    collector: TelemetryCollector | None = None,
) -> CommitMessageResult:
    """Run the full pipeline and return a typed result.

    Args:
      request:  the `CommitMessageRequest` carrying diff + context.
      enhancer: optional pre-built `PromptEnhancer`. When `None`, a
                fresh enhancer with a default-policy redactor is built
                and the commit-message template auto-registered. Tests
                inject their own; production code typically reuses a
                long-lived enhancer.
      provider: optional provider name override.
      model:    optional model name override.

    Raises:
      `sange.core.enhancer.EnhancerValidationError` if the model's
      response doesn't match the declared schema (after one retry).
      `ValueError` if the response shape is valid but the values fail
      the stricter `CommitMessageResult` validators (e.g. unknown
      type, subject too long).
    """

    if enhancer is None:
        registry = TemplateRegistry([build_commit_message_template()])
        enhancer = PromptEnhancer(templates=registry, collector=collector)
    elif not enhancer._templates.has(TEMPLATE_ID, TEMPLATE_VERSION):  # type: ignore[attr-defined]
        enhancer._templates.register(build_commit_message_template())  # type: ignore[attr-defined]

    files_changed_summary = (
        "\n".join(f"- {p}" for p in request.files_changed)
        if request.files_changed
        else "(no files listed)"
    )

    variables: dict[str, Any] = {
        "diff": request.diff,
        "branch": request.branch or "(unknown)",
        "recent_commits": request.recent_commits or "(none)",
        "files_changed_count": str(len(request.files_changed)),
        "files_changed_summary": files_changed_summary,
    }
    if request.scope_override:
        # The override is a hint, not a constraint — the model still
        # picks the scope, but a leading "Suggested scope" line nudges it.
        variables["diff"] = (
            f"Suggested scope: {request.scope_override}\n\n{request.diff}"
        )

    result: EnhancedResult = enhancer.enhance(
        TEMPLATE_ID,
        variables,
        provider=provider,
        model=model,
        # `branch`, `recent_commits`, `files_changed_summary` describe
        # repo metadata (not user-secret-bearing); marking them trusted
        # keeps the redactor focused on the diff itself, where the
        # T-030 threat actually lives. Filenames in summary are not
        # secrets; branch names occasionally contain ticket IDs that
        # aren't sensitive.
        trusted_vars={
            "branch",
            "recent_commits",
            "files_changed_count",
            "files_changed_summary",
        },
    )

    if result.data is None:
        raise ValueError(
            "commit-message template returned no structured data; "
            "ensure the provider response was parseable JSON"
        )

    data = result.data
    return CommitMessageResult(
        type=data["type"],
        scope=data.get("scope", "") or "",
        subject=data["subject"],
        body=data.get("body", "") or "",
        breaking_change=bool(data.get("breaking_change", False)),
        raw_response=result.text,
        audit_id=f"{result.audit.template_id}@{result.audit.template_version}",
    )


__all__ = [
    "CONVENTIONAL_COMMIT_TYPES",
    "TEMPLATE_ID",
    "TEMPLATE_VERSION",
    "CommitMessageRequest",
    "CommitMessageResult",
    "build_commit_message_template",
    "generate_commit_message",
]
