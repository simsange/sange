"""Concrete `PromptTemplate`s shipped with v0.1.

v0.5+ will load these from `.sange/prompts/*.toml`; the v0.1 contract
keeps them in code so the bootstrap path is deterministic and the
templates are exercised by the test suite at every CI run.

Each module exposes a `build_*_template()` function that returns a
`PromptTemplate` ready for `TemplateRegistry.register()`. Higher-level
modules also expose a convenience `generate_*()` function that wires
template + registry + enhancer together for callers that don't need
fine-grained control.

Tasks shipped in v0.1:

  * `commit_message` — Conventional Commits 1.0.0 message generation
                        from a diff + repo context.

Future tasks (v0.5+): pr-description, changelog, code-review,
branch-name, release-notes, diff-summary.
"""

from __future__ import annotations

from sange.core.enhancer.tasks.commit_message import (
    CONVENTIONAL_COMMIT_TYPES,
    CommitMessageRequest,
    CommitMessageResult,
    build_commit_message_template,
    generate_commit_message,
)

__all__ = [
    "CONVENTIONAL_COMMIT_TYPES",
    "CommitMessageRequest",
    "CommitMessageResult",
    "build_commit_message_template",
    "generate_commit_message",
]
