"""PromptEnhancer — the §6.7.1 orchestration.

User input flows through:

  1. **Redaction** — `Redactor.scrub()` runs on every string variable
     before they're interpolated into a template (T-030 mitigation).
     Variables that are explicitly marked "trusted" via the
     `trusted_vars` set bypass redaction (e.g. internal template names,
     enum values).

  2. **Template rendering** — `TemplateRegistry.render()` produces a
     `RenderedPrompt` with system+user text and an optional output
     schema. Cycle detection + missing-variable detection happens here.

  3. **Provider formatting** — `for_provider(name).format()` wraps the
     rendered prompt in provider-appropriate delimiters (XML for
     Claude, JSON for OpenAI, markdown for the rest).

  4. **Provider call** — `provider.complete(request)` (streaming is
     wrapped separately by callers who want incremental output).

  5. **Validation** — when the template declared an `output_schema`,
     the response text is JSON-decoded and checked against the schema.
     One retry on failure (with an explicit "your previous response
     wasn't valid JSON" appended to the user message); subsequent
     failures raise `EnhancerValidationError`.

  6. **Audit record** — every call produces an `AuditRecord` with the
     prompt+response, the template `(id, version)`, the provider+model,
     and the `Usage`. The §11 audit chain consumes these.

Per §6.7.1 the enhancer is **deterministic for a fixed input + fixed
provider + temperature=0** — this is essential for the `MockProvider`
test path and for prompt-version regression-testing.

Schema validation uses a minimal pure-Python validator (top-level
type+required-keys+property-types). The §15 v0.5 milestone may swap in
`jsonschema` for full Draft-2020-12 conformance; the v0.1 contract is
just "shape is correct; required fields present".
"""

from __future__ import annotations

import json
import time
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from sange.adapters.ai._protocol import (
    AIProvider,
    CompletionRequest,
    CompletionResponse,
    Message,
    MessageRole,
    ResponseFormat,
    Usage,
    get_provider,
)
from sange.core.enhancer.formatting import (
    FormattedRequest,
    FormattingStrategy,
    for_provider as default_strategy_for,
)
from sange.core.enhancer.redaction import Redactor
from sange.core.enhancer.templates import RenderedPrompt, TemplateRegistry

if TYPE_CHECKING:
    from sange.core.telemetry.collector import TelemetryCollector


# --------------------------------------------------------------------------- #
# Exceptions
# --------------------------------------------------------------------------- #


class EnhancerError(Exception):
    """Base for enhancer-pipeline errors."""


class EnhancerValidationError(EnhancerError):
    """Raised when the response failed schema validation even after retry."""


# --------------------------------------------------------------------------- #
# Audit record + result
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class AuditRecord:
    """Provenance for one enhancer invocation.

    The §11 audit chain consumes these. `redaction_count` tells the
    operator whether T-030 mitigation actually fired (zero is fine for
    a non-sensitive task; non-zero proves the layer is awake).
    """

    template_id: str
    template_version: str
    provider: str
    model: str
    redaction_count: int
    redaction_labels: frozenset[str]
    usage: Usage
    retries: int = 0


@dataclass(frozen=True)
class EnhancedResult:
    """The thing callers actually receive.

    Fields:
      * `text`      — the raw response text. Always populated.
      * `data`      — when the template declared a schema, the parsed
                       + validated dict. `None` otherwise.
      * `response`  — the underlying `CompletionResponse` (for raw
                       access to `finish_reason` etc.).
      * `audit`     — provenance record for the audit chain.
    """

    text: str
    response: CompletionResponse
    audit: AuditRecord
    data: dict[str, Any] | None = None


# --------------------------------------------------------------------------- #
# Minimal JSON-Schema validator (top-level shape only)
# --------------------------------------------------------------------------- #


_TYPE_MAP: dict[str, type | tuple[type, ...]] = {
    "object": dict,
    "array": list,
    "string": str,
    "number": (int, float),
    "integer": int,
    "boolean": bool,
    "null": type(None),
}


def _validate_against_schema(payload: Any, schema: Mapping[str, Any]) -> None:
    """Best-effort top-level type+required-keys+property-types check.

    Sufficient for v0.1 commit-message-shape validation; full
    Draft-2020-12 conformance is a v0.5 upgrade. The intentional
    scope-cap keeps `jsonschema` out of the runtime-required deps."""

    expected_type = schema.get("type")
    if expected_type is not None:
        py_type = _TYPE_MAP.get(expected_type)
        if py_type is None:
            raise EnhancerValidationError(
                f"schema declares unsupported type {expected_type!r}"
            )
        if not isinstance(payload, py_type):
            raise EnhancerValidationError(
                f"expected {expected_type!r}; got {type(payload).__name__}"
            )

    if expected_type == "object" and isinstance(payload, dict):
        required = schema.get("required", [])
        missing = [k for k in required if k not in payload]
        if missing:
            raise EnhancerValidationError(
                f"missing required key(s): {sorted(missing)!r}"
            )
        properties = schema.get("properties", {})
        for key, sub_schema in properties.items():
            if key in payload and "type" in sub_schema:
                sub_type = _TYPE_MAP.get(sub_schema["type"])
                if sub_type is None:
                    continue  # unsupported type — ignore.
                if not isinstance(payload[key], sub_type):
                    raise EnhancerValidationError(
                        f"property {key!r}: expected {sub_schema['type']!r}; "
                        f"got {type(payload[key]).__name__}"
                    )


# --------------------------------------------------------------------------- #
# PromptEnhancer
# --------------------------------------------------------------------------- #


@dataclass
class _ProviderResolution:
    name: str
    instance: AIProvider
    strategy: FormattingStrategy
    model: str
    temperature: float = 0.0


class PromptEnhancer:
    """Orchestrates the §6.7.1 pipeline.

    Construction:
      * `templates`  — a `TemplateRegistry` (the caller pre-loads it).
      * `redactor`   — a `Redactor`. If `None`, a default-policy
                        redactor is created.
      * `providers`  — a dict of provider-name → `AIProvider`. If
                        absent, providers are constructed on-demand
                        via `get_provider(name)`.
      * `default_provider` — name used when `enhance()` is called
                        without an explicit provider.
      * `default_model`    — model used when no per-call model is
                        provided. The factory passes this through
                        unchanged; providers that need their own
                        default reject empty model.
      * `max_retries`      — number of schema-validation retries
                        (default 1 per §6.7.1 "failed validations
                        trigger a single retry then surface to the
                        user").
    """

    def __init__(
        self,
        *,
        templates: TemplateRegistry,
        redactor: Redactor | None = None,
        providers: Mapping[str, AIProvider] | None = None,
        default_provider: str = "mock",
        default_model: str = "mock-1",
        max_retries: int = 1,
        collector: TelemetryCollector | None = None,
    ) -> None:
        if not isinstance(templates, TemplateRegistry):
            raise TypeError("templates must be a TemplateRegistry instance")
        if max_retries < 0:
            raise ValueError(f"max_retries must be >= 0; got {max_retries}")
        self._templates = templates
        self._redactor = redactor if redactor is not None else Redactor()
        self._providers: dict[str, AIProvider] = dict(providers or {})
        self._default_provider = default_provider
        self._default_model = default_model
        self._max_retries = max_retries
        self._collector = collector

    # ----- public API ----------------------------------------------- #

    def enhance(
        self,
        template_id: str,
        variables: Mapping[str, Any] | None = None,
        *,
        template_version: str | None = None,
        provider: str | None = None,
        model: str | None = None,
        temperature: float = 0.0,
        trusted_vars: frozenset[str] | set[str] = frozenset(),
    ) -> EnhancedResult:
        """Run the full pipeline and return a validated result."""

        provider_name = provider or self._default_provider
        resolution = self._resolve_provider(
            provider_name,
            model=model or self._default_model,
            temperature=temperature,
        )

        # Redact every string variable (except trusted ones).
        scrubbed_vars, redaction_count, redaction_labels = self._redact_variables(
            dict(variables or {}), trusted=set(trusted_vars)
        )

        # Render template → format for provider → call provider → validate.
        rendered = self._templates.render(
            template_id, scrubbed_vars, version=template_version
        )
        formatted = resolution.strategy.format(rendered)

        retries = 0
        t0 = time.perf_counter()
        response = self._call_provider(resolution, formatted, rendered)
        data, last_error = self._maybe_validate(rendered, response.text)

        # If validation fails AND we have retries left, retry once with
        # an explicit "your previous response wasn't valid; here is the
        # error" suffix.
        retry_messages = formatted.messages
        retry_used = False
        while data is _RETRY_SENTINEL and retries < self._max_retries:
            retries += 1
            retry_used = True
            retry_messages = self._build_retry_messages(retry_messages, response.text)
            response = self._call_provider_with_messages(
                resolution, retry_messages, rendered, formatted.requires_json
            )
            data, last_error = self._maybe_validate(rendered, response.text)

        latency_ms = int((time.perf_counter() - t0) * 1000)

        if data is _RETRY_SENTINEL:
            # Validation failed terminally — surface an ErrorEvent before
            # raising so the audit feed records the failure.
            self._record_error(
                template_id=rendered.template_id,
                provider=provider_name,
                error_type="EnhancerValidationError",
                error_message=f"schema validation failed after {retries} retry(ies): {last_error}",
            )
            raise EnhancerValidationError(
                f"response from {provider_name!r} did not match schema after "
                f"{retries} retry(ies): {last_error}; "
                f"last response: {response.text[:200]!r}"
            )

        audit = AuditRecord(
            template_id=rendered.template_id,
            template_version=rendered.template_version,
            provider=provider_name,
            model=resolution.model,
            redaction_count=redaction_count,
            redaction_labels=redaction_labels,
            usage=response.usage,
            retries=retries if retry_used else 0,
        )

        self._record_audit(audit, latency_ms=latency_ms)

        return EnhancedResult(
            text=response.text,
            response=response,
            audit=audit,
            data=data if isinstance(data, dict) else None,
        )

    def preview(
        self,
        template_id: str,
        variables: Mapping[str, Any] | None = None,
        *,
        template_version: str | None = None,
        provider: str | None = None,
        trusted_vars: frozenset[str] | set[str] = frozenset(),
    ) -> FormattedRequest:
        """Render + format WITHOUT calling the provider — backs
        `sange ai preview` per §6.7.1 "inspectable"."""

        provider_name = provider or self._default_provider
        strategy = default_strategy_for(provider_name)

        scrubbed_vars, _, _ = self._redact_variables(
            dict(variables or {}), trusted=set(trusted_vars)
        )
        rendered = self._templates.render(
            template_id, scrubbed_vars, version=template_version
        )
        return strategy.format(rendered)

    # ----- internals ----------------------------------------------- #

    def _redact_variables(
        self,
        variables: dict[str, Any],
        *,
        trusted: set[str],
    ) -> tuple[dict[str, Any], int, frozenset[str]]:
        total_count = 0
        all_labels: set[str] = set()
        scrubbed: dict[str, Any] = {}
        for key, value in variables.items():
            if key in trusted or not isinstance(value, str):
                scrubbed[key] = value
                continue
            result = self._redactor.scrub(value)
            scrubbed[key] = result.text
            total_count += result.redactions
            all_labels |= result.labels_applied
        return scrubbed, total_count, frozenset(all_labels)

    def _resolve_provider(
        self,
        name: str,
        *,
        model: str,
        temperature: float,
    ) -> _ProviderResolution:
        if name in self._providers:
            instance = self._providers[name]
        else:
            instance = get_provider(name)
            self._providers[name] = instance
        return _ProviderResolution(
            name=name,
            instance=instance,
            strategy=default_strategy_for(name),
            model=model,
            temperature=temperature,
        )

    def _call_provider(
        self,
        resolution: _ProviderResolution,
        formatted: FormattedRequest,
        rendered: RenderedPrompt,
    ) -> CompletionResponse:
        return self._call_provider_with_messages(
            resolution, formatted.messages, rendered, formatted.requires_json
        )

    def _call_provider_with_messages(
        self,
        resolution: _ProviderResolution,
        messages: tuple[Message, ...],
        rendered: RenderedPrompt,
        requires_json: bool,
    ) -> CompletionResponse:
        request = CompletionRequest(
            model=resolution.model,
            messages=messages,
            temperature=resolution.temperature,
            response_format=(
                ResponseFormat.JSON_OBJECT if requires_json else ResponseFormat.TEXT
            ),
        )
        return resolution.instance.complete(request)

    def _maybe_validate(
        self,
        rendered: RenderedPrompt,
        text: str,
    ) -> tuple[Any, str]:
        """Return `(parsed, last_error_message)`.

        * `(None, "")`            — no schema declared.
        * `(dict, "")`            — schema declared + payload validated.
        * `(_RETRY_SENTINEL, msg)` — payload failed validation. `msg`
                                     carries the underlying reason so
                                     the wrapping error can surface it.
        """

        if rendered.output_schema is None:
            return None, ""

        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            return _RETRY_SENTINEL, f"invalid JSON: {exc}"

        try:
            _validate_against_schema(payload, rendered.output_schema)
        except EnhancerValidationError as exc:
            return _RETRY_SENTINEL, str(exc)

        if not isinstance(payload, dict):
            # Top-level shape is something other than an object — keep
            # it accessible via `text` but don't fit it into `.data`.
            return None, ""
        return payload, ""

    # ----- telemetry hooks ------------------------------------------ #

    def _record_audit(self, audit: AuditRecord, *, latency_ms: int) -> None:
        """Fire-and-forget record into the operator's collector, if any."""

        if self._collector is None:
            return
        try:
            from sange.core.telemetry.collector import TelemetryCollector

            event = TelemetryCollector.from_audit(audit, latency_ms=latency_ms)
            self._collector.record(event)
        except Exception:  # noqa: BLE001 — telemetry must never break the call path.
            pass

    def _record_error(
        self,
        *,
        template_id: str,
        provider: str,
        error_type: str,
        error_message: str,
    ) -> None:
        """Record an `ErrorEvent` for a terminal-failure enhance() call."""

        if self._collector is None:
            return
        try:
            from sange.core.telemetry.events import ErrorEvent

            event = ErrorEvent(
                command_path=f"enhance.{template_id}",
                error_type=error_type,
                error_message=error_message,
            )
            self._collector.record(event)
        except Exception:  # noqa: BLE001 — telemetry must never break the call path.
            pass

    # ----- internals ----------------------------------------------- #

    @staticmethod
    def _build_retry_messages(
        prior_messages: tuple[Message, ...],
        prior_response: str,
    ) -> tuple[Message, ...]:
        """Append the failed response + a corrective instruction so
        the model can correct its own output."""

        retry_instruction = (
            "Your previous response was not valid JSON or did not match the "
            "declared schema. Re-emit ONLY valid JSON matching the schema; "
            "do not include any prose, fenced code, or explanatory text."
        )
        return prior_messages + (
            Message(role=MessageRole.ASSISTANT, content=prior_response or " "),
            Message(role=MessageRole.USER, content=retry_instruction),
        )


# Sentinel that distinguishes "retry" from "no schema" / "valid".
_RETRY_SENTINEL = object()


__all__ = [
    "AuditRecord",
    "EnhancedResult",
    "EnhancerError",
    "EnhancerValidationError",
    "PromptEnhancer",
]
