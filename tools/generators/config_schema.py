"""Generate docs/reference/config-schema.md from src/sange/core/config/models.

T-G-011 — introspects the `SangeConfig` Pydantic v2 model tree (T-002),
emits the canonical reference with §16.4.1 frontmatter. Per §6.3 +
ADR-023 (deterministic, hash-emitting).

Strategy:
  * `SangeConfig.model_json_schema()` produces a JSON Schema draft.
  * Walk the schema's `$defs` block to enumerate each sub-model.
  * For every model, render a section with: description, required fields,
    optional fields, defaults, validators (where exposed in `description`).
  * The default-minimal config is rendered as a TOML example so the reader
    can copy-paste a starting point.

Determinism (ADR-023):
  * The model itself is the input — the canonical JSON-schema export is
    stable across runs of the same pydantic version.
  * `input_sha256` hashes the canonical JSON schema; any model edit
    invalidates the cached output.
"""

from __future__ import annotations

import datetime as _dt
import json
import sys
from pathlib import Path
from typing import Any

# --- Path bootstrap ------------------------------------------------------- #
HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent.parent
SRC_DIR = REPO_ROOT / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from _lib import markdown  # noqa: E402
from _lib.fingerprint import sha256_text  # noqa: E402
from _lib.output import (  # noqa: E402
    GeneratorMetadata,
    WriteMode,
    WriteOutcome,
    write_generated_file,
)

from sange.core.config import SangeConfig  # noqa: E402

GENERATOR_VERSION = "1.0.0"
GENERATED_BY = "tools/generators/config_schema.py"
OUTPUT_PATH = REPO_ROOT / "docs" / "reference" / "config-schema.md"


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _format_default(value: Any) -> str:
    """Render a default value as a Markdown-friendly string."""

    if isinstance(value, (list, tuple)):
        if not value:
            return "`[]`"
        if len(value) <= 4:
            return "`" + json.dumps(list(value)) + "`"
        return f"_({len(value)} items)_"
    if isinstance(value, dict):
        if not value:
            return "`{}`"
        keys = list(value.keys())[:3]
        return f"_(dict with keys: `{', '.join(keys)}`{'…' if len(value) > 3 else ''})_"
    if value is None:
        return "—"
    if isinstance(value, bool):
        return "`true`" if value else "`false`"
    return f"`{json.dumps(value)}`"


def _format_type(prop: dict[str, Any]) -> str:
    """Render the type column."""

    if "$ref" in prop:
        return f"[`{prop['$ref'].rsplit('/', 1)[-1]}`](#{prop['$ref'].rsplit('/', 1)[-1].lower()})"
    if "anyOf" in prop:
        return " ∪ ".join(_format_type(o) for o in prop["anyOf"])
    t = prop.get("type", "any")
    if t == "array" and "items" in prop:
        return f"list[{_format_type(prop['items'])}]"
    if t == "object" and "additionalProperties" in prop:
        ap = prop["additionalProperties"]
        return f"dict[str, {_format_type(ap) if isinstance(ap, dict) else 'any'}]"
    if "enum" in prop:
        return "literal[" + " \\| ".join(repr(v) for v in prop["enum"]) + "]"
    return f"`{t}`"


def _render_model_section(
    name: str,
    schema: dict[str, Any],
    defaults: dict[str, Any] | None,
) -> str:
    """Render one model's docs."""

    parts: list[str] = []
    parts.append(markdown.heading(3, f"`{name}`", anchor=name.lower()))
    description = schema.get("description") or ""
    if description:
        # Take only the first paragraph for the doc — full docstring lives
        # in the source file.
        first = description.strip().split("\n\n", 1)[0]
        parts.append(first)
        parts.append("")

    properties = schema.get("properties", {})
    required = set(schema.get("required", []))
    if not properties:
        parts.append("_(no fields)_\n")
        return "\n".join(parts)

    rows = []
    for prop_name, prop_schema in properties.items():
        default = "—"
        if defaults and prop_name in defaults:
            default = _format_default(defaults[prop_name])
        elif "default" in prop_schema:
            default = _format_default(prop_schema["default"])
        req = "yes" if prop_name in required else "no"
        rows.append(
            [
                f"`{prop_name}`",
                _format_type(prop_schema),
                req,
                default,
                prop_schema.get("description", "—"),
            ]
        )
    parts.append(
        markdown.table(
            ["Field", "Type", "Required", "Default", "Description"],
            rows,
        )
    )
    return "\n".join(parts)


def _render_toml_example() -> str:
    """Render the default-minimal SangeConfig as a TOML example block."""

    c = SangeConfig()
    lines: list[str] = []
    lines.append("# Default-minimal `.sange/config.toml` — every field is optional.")
    lines.append("# Sange behaves identically without this file present.")
    lines.append("")
    lines.append("[schema_version]")
    lines.append(f"major = {c.schema_version.major}")
    lines.append(f"minor = {c.schema_version.minor}")
    lines.append("")
    lines.append("[variants]")
    lines.append(f"stages = {json.dumps(c.variants.stages)}")
    lines.append(f'default_stage = "{c.variants.default_stage}"')
    lines.append(f'publish_stage = "{c.variants.publish_stage}"')
    lines.append("")
    lines.append("[audit]")
    lines.append(f"enabled = {str(c.audit.enabled).lower()}")
    lines.append(f'verbosity = "{c.audit.verbosity}"')
    lines.append(f"rotation_days = {c.audit.rotation_days}")
    lines.append("")
    lines.append("[telemetry]")
    lines.append(f"enabled = {str(c.telemetry.enabled).lower()}")
    lines.append(f"external_send_enabled = {str(c.telemetry.external_send_enabled).lower()}")
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Body
# --------------------------------------------------------------------------- #


def _build_body() -> str:
    schema = SangeConfig.model_json_schema()
    defs: dict[str, Any] = schema.get("$defs", {})
    default_instance = SangeConfig()
    default_dump = default_instance.model_dump()

    parts: list[str] = []
    parts.append(markdown.heading(1, "Sange configuration schema"))
    parts.append(
        "> Generated by `tools/generators/config_schema.py` (T-G-011) "
        "from `src/sange/core/config/models.py`. Source-of-truth: §6.3 + "
        "§6.5.2 + §6.7 + §6.10 + §11 + §12 of `.design/sange-architecture-prompt.md`.\n"
    )
    parts.append(
        "The single `SangeConfig` Pydantic v2 model is the only configuration "
        "surface every Sange subsystem reads from. `SangeConfig()` with no "
        "arguments yields a valid object representing the **default-minimal** "
        "configuration; `.sange/config.toml` is entirely optional.\n"
    )

    parts.append(markdown.heading(2, "Precedence chain"))
    parts.append(
        "Per §6.3, configuration layers merge with **rightmost wins** on conflict:"
    )
    parts.append("")
    parts.append(
        markdown.code_block(
            "built-in defaults\n"
            "  ← /etc/sange/config.{toml,json}\n"
            "    ← ~/.sange/config.{toml,json}\n"
            "      ← ${repo}/.sange/config.{toml,json}\n"
            "        ← SANGE__SECTION__FIELD environment variables\n"
            "          ← CLI flags",
            lang="text",
        )
    )
    parts.append(
        "JSON wins over TOML at the same level when both exist (machine-"
        "authoritative per ADR-009). The loader emits a warning on conflict."
    )
    parts.append("")

    parts.append(markdown.heading(2, "Environment-variable overrides"))
    parts.append(
        "Environment variables matching `SANGE__SECTION__FIELD=value` map onto "
        "the nested model. `__` (two underscores) is the nesting separator. "
        "Examples:"
    )
    parts.append("")
    parts.append(
        markdown.code_block(
            "SANGE__VARIANTS__DEFAULT_STAGE=staging\n"
            "SANGE__AUDIT__VERBOSITY=elevated\n"
            "SANGE__AUDIT__ROTATION_DAYS=30\n"
            "SANGE__TELEMETRY__ENABLED=false\n"
            "SANGE__VARIANTS__STAGES=dev,staging,production   # comma-list",
            lang="bash",
        )
    )
    parts.append("")

    parts.append(markdown.heading(2, "Default-minimal `.sange/config.toml`"))
    parts.append(
        "Every field is optional. The block below is what Sange would write "
        "as a fresh `.sange/config.toml` (you don't have to create one)."
    )
    parts.append("")
    parts.append(markdown.code_block(_render_toml_example(), lang="toml"))
    parts.append("")

    parts.append(markdown.heading(2, "Model reference"))
    parts.append(
        "Every sub-model with its fields, types, defaults, and constraints. "
        "Field names match the TOML key names exactly."
    )
    parts.append("")

    # Root model first.
    root_props = schema.get("properties", {})
    parts.append(markdown.heading(3, "`SangeConfig` (root)"))
    rows = []
    for prop_name, prop_schema in root_props.items():
        default = _format_default(default_dump.get(prop_name))
        rows.append(
            [
                f"`{prop_name}`",
                _format_type(prop_schema),
                "no",
                default,
                prop_schema.get("description", "—"),
            ]
        )
    parts.append(
        markdown.table(
            ["Field", "Type", "Required", "Default", "Description"],
            rows,
        )
    )
    parts.append("")

    # Sub-models in deterministic order.
    seen_models = set()
    # Order: schema_version, project, variants, gitignore, ai, secrets, audit, telemetry
    # Plus nested types referenced from those.
    primary_order = [
        "SchemaVersion", "ProjectMeta", "VariantConfig", "DimensionConfig",
        "VariantFilter", "StageConfig", "GitignoreConfig", "GitignorePolicy",
        "AIConfig", "AIProviderConfig", "SecretsConfig", "AuditConfig",
        "TelemetryConfig",
    ]
    for model_name in primary_order:
        if model_name not in defs:
            continue
        parts.append(_render_model_section(model_name, defs[model_name], None))
        parts.append("")
        seen_models.add(model_name)
    # Any other models (catch-all).
    for model_name, model_schema in sorted(defs.items()):
        if model_name in seen_models:
            continue
        parts.append(_render_model_section(model_name, model_schema, None))
        parts.append("")

    parts.append(markdown.heading(2, "How this doc is generated"))
    parts.append(
        markdown.bullet_list(
            [
                "Edit `src/sange/core/config/models.py` to add or modify a field.",
                "Regenerate this doc → `python tools/generators/all.py --only T-G-011 --write`.",
                "CI's `verify_generated.py` enforces that the on-disk doc matches the model's current shape.",
                "Schema version bumps live in `models.py::SCHEMA_CURRENT`; breaking model changes trigger loader-side migration.",
            ]
        )
    )
    return "\n".join(parts)


# --------------------------------------------------------------------------- #
# Generator entry-point
# --------------------------------------------------------------------------- #


def _input_sha256() -> str:
    """Canonical sha256 of the model's JSON-schema representation."""

    schema = SangeConfig.model_json_schema()
    return sha256_text(json.dumps(schema, sort_keys=True))


def run(
    *,
    mode: WriteMode,
    clock: _dt.datetime,
    output_path: Path | None = None,
) -> list[WriteOutcome]:
    target = output_path or OUTPUT_PATH
    meta = GeneratorMetadata(
        generated_by=GENERATED_BY,
        generator_version=GENERATOR_VERSION,
        input_sha256=_input_sha256(),
        manual_edits_allowed=False,
        generated_at=clock,
    )
    return [write_generated_file(target, _build_body(), meta, mode=mode)]


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if not (args.write or args.check):
        args.write = True
    mode = WriteMode.WRITE if args.write else WriteMode.CHECK

    results = run(mode=mode, clock=_dt.datetime.now(tz=_dt.UTC))
    rc = 0
    for r in results:
        if r.result is not None and r.result.value != "match":
            rc = 66
        line = f"[{mode.value}] {r.path}  sha256={r.output_sha256}"
        if r.result is not None:
            line += f"  ({r.result.value})"
        print(line)
    raise SystemExit(rc)
