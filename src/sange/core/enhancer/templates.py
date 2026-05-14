"""PromptTemplate + TemplateRegistry — composable prompt templates.

A `PromptTemplate` is a versioned, named, schema-aware skeleton with
two text parts (system + user) and an output schema. Templates use
Python's `str.format()` for variable interpolation; composition is
explicit via `includes` — a template can name other templates to
inline at well-defined `{{include:name}}` markers.

Composition rules (per §6.7.1 "composable; circular includes detected
and refused"):

  * Includes are resolved recursively.
  * A cycle anywhere in the include graph raises `TemplateCycleError`.
  * Missing includes raise `TemplateNotFoundError`.
  * Variable interpolation uses `{name}` (single-brace, str.format
    semantics); include markers use `{{include:name}}` (double-brace
    to disambiguate from variables).

Each template is keyed by `(id, version)` so prompt-history audits can
reproduce a past run exactly. The registry rejects duplicate
`(id, version)` registrations with `TemplateConflictError`.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any


# --------------------------------------------------------------------------- #
# Exceptions
# --------------------------------------------------------------------------- #


class TemplateError(Exception):
    """Base for template-system errors."""


class TemplateNotFoundError(TemplateError):
    """Raised when a referenced template-id isn't registered."""


class TemplateCycleError(TemplateError):
    """Raised when include resolution detects a cycle."""


class TemplateConflictError(TemplateError):
    """Raised when register() is called with an existing (id, version)."""


class TemplateMissingVariableError(TemplateError):
    """Raised when a variable required by the template isn't provided."""


# --------------------------------------------------------------------------- #
# PromptTemplate
# --------------------------------------------------------------------------- #


# `{{include:foo}}` — double-brace to keep them out of str.format's
# single-brace variable parser.
_INCLUDE_PATTERN = re.compile(r"\{\{include:([a-z][a-z0-9_-]*)\}\}")

# `{name}` (or `{name!s:>10}` etc.) — the var-extraction regex is
# best-effort: it picks up names that aren't escaped (`{{`). We don't
# need to fully parse format spec — we only need the name.
_VAR_PATTERN = re.compile(r"(?<!\{)\{([a-zA-Z_][a-zA-Z0-9_]*)(?:[!:][^}]*)?\}")


@dataclass(frozen=True)
class PromptTemplate:
    """A versioned prompt template.

    Fields:
      * `id`               — kebab-case template identifier.
      * `version`          — semver-like version (e.g. `"1.0.0"`). The
                              audit trail records `(id, version)` for
                              every enhanced prompt.
      * `task`             — task class this serves (`"commit-msg"`,
                              `"changelog"`, `"code-review"`, …).
      * `system_template`  — the system message body. Empty if not
                              applicable.
      * `user_template`    — the user message body. Required.
      * `description`      — human-readable summary for `sange ai preview`.
      * `required_vars`    — names the caller MUST supply at render
                              time. Validated up-front before any
                              interpolation.
      * `output_schema`    — JSON-Schema-shaped dict the response must
                              conform to. `None` means free-form text.
    """

    id: str
    version: str
    task: str
    user_template: str
    system_template: str = ""
    description: str = ""
    required_vars: tuple[str, ...] = field(default_factory=tuple)
    output_schema: dict[str, Any] | None = None

    _ID_PATTERN: re.Pattern[str] = field(
        init=False, repr=False, compare=False,
        default=re.compile(r"^[a-z][a-z0-9-]*$"),
    )

    def __post_init__(self) -> None:
        if not self._ID_PATTERN.match(self.id):
            raise ValueError(
                f"PromptTemplate.id must be kebab-case; got {self.id!r}"
            )
        if not self.version:
            raise ValueError("PromptTemplate.version must be non-empty")
        if not self.task:
            raise ValueError("PromptTemplate.task must be non-empty")
        if not self.user_template:
            raise ValueError("PromptTemplate.user_template must be non-empty")
        # Static dependency check: every required_var must appear in at
        # least one of the templates. Templates with includes are
        # excused — the included template may carry the variable, and
        # we can't statically resolve includes at construction time
        # (the registry isn't available yet).
        has_includes = bool(
            _INCLUDE_PATTERN.search(self.system_template)
            or _INCLUDE_PATTERN.search(self.user_template)
        )
        if not has_includes:
            for var in self.required_vars:
                in_system = var in _extract_vars(self.system_template)
                in_user = var in _extract_vars(self.user_template)
                if not (in_system or in_user):
                    raise ValueError(
                        f"PromptTemplate.required_vars: {var!r} is declared but "
                        f"never referenced in system/user templates"
                    )

    @property
    def key(self) -> tuple[str, str]:
        """Unique identity for the registry — `(id, version)`."""

        return (self.id, self.version)

    def includes(self) -> frozenset[str]:
        """Names of templates this one transitively references."""

        return frozenset(
            _INCLUDE_PATTERN.findall(self.system_template)
            + _INCLUDE_PATTERN.findall(self.user_template)
        )


def _extract_vars(template: str) -> frozenset[str]:
    return frozenset(_VAR_PATTERN.findall(template))


# --------------------------------------------------------------------------- #
# TemplateRegistry
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class RenderedPrompt:
    """The output of `TemplateRegistry.render()` — both message parts
    plus the schema (if any) and the audit-trail key."""

    system: str
    user: str
    template_id: str
    template_version: str
    output_schema: dict[str, Any] | None = None


class TemplateRegistry:
    """In-memory registry. v0.5 will load templates from
    `.sange/prompts/*.toml`; v0.1 keeps it explicit so tests and the
    bootstrap path are deterministic."""

    def __init__(self, templates: Iterable[PromptTemplate] = ()) -> None:
        self._by_key: dict[tuple[str, str], PromptTemplate] = {}
        self._latest: dict[str, str] = {}  # id → highest-registered version
        for t in templates:
            self.register(t)

    # ----- registration --------------------------------------------- #

    def register(self, template: PromptTemplate) -> None:
        if template.key in self._by_key:
            raise TemplateConflictError(
                f"template {template.id!r} version {template.version!r} already registered"
            )
        self._by_key[template.key] = template
        # Track latest by registration order (callers supply versions
        # explicitly — we don't try to interpret semver here).
        self._latest[template.id] = template.version

    def get(self, template_id: str, version: str | None = None) -> PromptTemplate:
        if version is None:
            version = self._latest.get(template_id)
            if version is None:
                raise TemplateNotFoundError(f"no template registered with id={template_id!r}")
        try:
            return self._by_key[(template_id, version)]
        except KeyError as exc:
            raise TemplateNotFoundError(
                f"template {template_id!r} version {version!r} not registered"
            ) from exc

    def has(self, template_id: str, version: str | None = None) -> bool:
        try:
            self.get(template_id, version)
            return True
        except TemplateNotFoundError:
            return False

    def ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._latest.keys()))

    # ----- rendering ------------------------------------------------ #

    def render(
        self,
        template_id: str,
        variables: dict[str, Any] | None = None,
        *,
        version: str | None = None,
    ) -> RenderedPrompt:
        """Resolve includes, validate required vars, interpolate."""

        template = self.get(template_id, version)
        variables = dict(variables or {})

        missing = [v for v in template.required_vars if v not in variables]
        if missing:
            raise TemplateMissingVariableError(
                f"template {template_id!r} requires vars: {sorted(missing)!r}"
            )

        system_expanded = self._expand_includes(template.system_template, _seen=[template.id])
        user_expanded = self._expand_includes(template.user_template, _seen=[template.id])

        return RenderedPrompt(
            system=_safe_format(system_expanded, variables),
            user=_safe_format(user_expanded, variables),
            template_id=template.id,
            template_version=template.version,
            output_schema=template.output_schema,
        )

    # ----- include resolver ----------------------------------------- #

    def _expand_includes(self, body: str, *, _seen: list[str]) -> str:
        def _resolve(match: re.Match[str]) -> str:
            inc_id = match.group(1)
            if inc_id in _seen:
                raise TemplateCycleError(
                    f"template include cycle detected: {' -> '.join(_seen + [inc_id])}"
                )
            inc = self.get(inc_id)  # raises TemplateNotFoundError if absent
            nested = self._expand_includes(
                inc.user_template, _seen=_seen + [inc_id]
            )
            return nested

        return _INCLUDE_PATTERN.sub(_resolve, body)


def _safe_format(template_text: str, variables: dict[str, Any]) -> str:
    """`str.format` that returns the original brace text for unknown
    variables (instead of raising KeyError)."""

    class _LeaveMissing(dict[str, Any]):
        def __missing__(self, key: str) -> str:
            return "{" + key + "}"

    try:
        return template_text.format_map(_LeaveMissing(variables))
    except (IndexError, ValueError) as exc:
        raise TemplateError(f"format error: {exc}") from exc


__all__ = [
    "PromptTemplate",
    "RenderedPrompt",
    "TemplateConflictError",
    "TemplateCycleError",
    "TemplateError",
    "TemplateMissingVariableError",
    "TemplateNotFoundError",
    "TemplateRegistry",
]
