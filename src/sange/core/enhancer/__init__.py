"""Prompt-enhancer subsystem — §6.7.1.

Application-layer module that turns raw user input into well-structured
provider-appropriate prompts. The enhancer is the **only** path by
which user input reaches an AI provider, per the §11 + threat T-030
contract.

Public surface:

  * `PromptEnhancer`        — the orchestrator (redact → render →
                              format → call → validate → audit).
  * `EnhancedResult`        — what `enhance()` returns.
  * `AuditRecord`           — provenance for the audit chain (§11).
  * `PromptTemplate`        — versioned, schema-aware skeleton.
  * `TemplateRegistry`      — in-memory registry with include
                              composition + cycle detection.
  * `RenderedPrompt`        — intermediate (post-render, pre-format).
  * `Redactor`              — T-030 mitigation (high-entropy +
                              known-pattern + custom-regex scrubber).
  * `RedactionPolicy`       — operator-controlled knobs.
  * `for_provider()`        — provider → formatting-strategy lookup.
  * `XmlFormattingStrategy`, `JsonFormattingStrategy`,
    `MarkdownFormattingStrategy` — the three v0.1 strategies.

Subsystem boundaries:

  * Templates are configuration; live in `.sange/prompts/*.toml` in
    v0.5+. v0.1 keeps them in-memory and explicit so the smoke-test
    path is deterministic.
  * Concrete task templates (commit-msg, changelog, code-review, …)
    land in T-011+. T-010 is just the engine.
"""

from __future__ import annotations

from sange.core.enhancer.enhancer import (
    AuditRecord,
    EnhancedResult,
    EnhancerError,
    EnhancerValidationError,
    PromptEnhancer,
)
from sange.core.enhancer.formatting import (
    FormattedRequest,
    FormattingStrategy,
    JsonFormattingStrategy,
    MarkdownFormattingStrategy,
    XmlFormattingStrategy,
    for_provider,
    register_strategy,
    registered_providers,
)
from sange.core.enhancer.redaction import (
    RedactionPolicy,
    RedactionResult,
    Redactor,
    shannon_entropy,
)
from sange.core.enhancer.templates import (
    PromptTemplate,
    RenderedPrompt,
    TemplateConflictError,
    TemplateCycleError,
    TemplateError,
    TemplateMissingVariableError,
    TemplateNotFoundError,
    TemplateRegistry,
)

__all__ = [
    "AuditRecord",
    "EnhancedResult",
    "EnhancerError",
    "EnhancerValidationError",
    "FormattedRequest",
    "FormattingStrategy",
    "JsonFormattingStrategy",
    "MarkdownFormattingStrategy",
    "PromptEnhancer",
    "PromptTemplate",
    "RedactionPolicy",
    "RedactionResult",
    "Redactor",
    "RenderedPrompt",
    "TemplateConflictError",
    "TemplateCycleError",
    "TemplateError",
    "TemplateMissingVariableError",
    "TemplateNotFoundError",
    "TemplateRegistry",
    "XmlFormattingStrategy",
    "for_provider",
    "register_strategy",
    "registered_providers",
    "shannon_entropy",
]
