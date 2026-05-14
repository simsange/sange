"""SangeConfig Pydantic v2 model tree.

The keystone of Phase 0b — every subsystem reads from `SangeConfig`.
Per §6.3 + §6.5.2 + §6.7 + §6.10 + §11 + §12 of the architecture prompt.

Design rules:

  * Every sub-model uses Pydantic v2's `BaseModel`. `frozen=False` so the
    loader can patch values during the precedence-chain merge (the merged
    object is then validated and treated as immutable at the application
    boundary).
  * Defaults are explicit and conservative. Calling `SangeConfig()` with no
    arguments produces a valid object representing the **default-minimal**
    configuration (binary dev/prod axis per ADR-032 fallback, no AI
    providers configured, no secrets resolver, local-only telemetry).
  * Forbid extra fields (`model_config = ConfigDict(extra="forbid")`) so
    typos in user TOML/JSON surface immediately.
  * Validators enforce cross-field invariants (e.g. `publish_stage` ∈
    `stages`).
  * Schema versioning per `SchemaVersion`. Bumping `SCHEMA_CURRENT` is a
    breaking change — the loader auto-migrates with a backup.

v0.1 MVP scope (this module):
  * `ProjectMeta` — name, version, license, maintainer.
  * `VariantConfig` — stages + dimensions + filters + branch_map + per-stage
    overrides (the full ADR-032 surface).
  * `GitignoreConfig` — dev/prod profile lists + policy.
  * `AIConfig` — providers + redaction + MCP allowlist (§6.7).
  * `SecretsConfig` — resolver picks per-stage (§6.10).
  * `AuditConfig` — hash-chained audit settings (§7.0.7).
  * `TelemetryConfig` — local-only collector (§12).

v0.5+/v1.0 extension points (TODO comments in this module):
  * `BundleConfig` — release-bundle destinations (§6.9).
  * `WebUIConfig` — bind address, auth, remote topology (§8).
  * `PurgeConfig` — purge subsystem defaults (§6.11).
  * `PluginConfig` — plugin marketplace + signature policy (§7.9).
"""

from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


# --------------------------------------------------------------------------- #
# Schema versioning
# --------------------------------------------------------------------------- #


class SchemaVersion(BaseModel):
    """Tracks the SangeConfig schema version for migration purposes.

    Bumped on every breaking change to the model tree. The loader compares
    the on-disk `schema_version` to `SCHEMA_CURRENT` and either accepts
    (==), auto-migrates (older), or refuses (newer — likely a config from
    a future Sange version).
    """

    major: int = Field(default=1, ge=1)
    minor: int = Field(default=0, ge=0)

    model_config = ConfigDict(extra="forbid", frozen=False)

    def as_tuple(self) -> tuple[int, int]:
        return (self.major, self.minor)

    def is_compatible_with(self, current: SchemaVersion) -> bool:
        """Same major version + same-or-older minor."""

        return self.major == current.major and self.minor <= current.minor

    def is_newer_than(self, current: SchemaVersion) -> bool:
        return self.as_tuple() > current.as_tuple()


SCHEMA_CURRENT = SchemaVersion(major=1, minor=0)


# --------------------------------------------------------------------------- #
# Project metadata
# --------------------------------------------------------------------------- #


_NAME_RE = re.compile(r"^[a-z0-9](-?[a-z0-9])*$")


class ProjectMeta(BaseModel):
    """Project-level metadata. Optional — `SangeConfig` works without it."""

    name: str = Field(default="", max_length=120)
    description: str = Field(default="", max_length=240)
    homepage: str = Field(default="", description="HTTPS URL; never a local path.")

    model_config = ConfigDict(extra="forbid", frozen=False)

    @field_validator("name")
    @classmethod
    def _name_is_slug_like(cls, value: str) -> str:
        if not value:
            return value
        if not _NAME_RE.match(value):
            raise ValueError(
                f"project name {value!r} must be lowercase letters / digits / hyphens"
            )
        return value


# --------------------------------------------------------------------------- #
# Variant matrix (ADR-032; §6.5.2)
# --------------------------------------------------------------------------- #


class DimensionConfig(BaseModel):
    """A single flavor dimension (e.g. `audience`, `surface`, `region`)."""

    flavors: list[str] = Field(default_factory=list, min_length=1)
    default: str = Field(default="")

    model_config = ConfigDict(extra="forbid", frozen=False)

    @model_validator(mode="after")
    def _default_in_flavors(self) -> DimensionConfig:
        if not self.flavors:
            return self
        if not self.default:
            # Pick the first flavor as the implicit default.
            object.__setattr__(self, "default", self.flavors[0])
        elif self.default not in self.flavors:
            raise ValueError(
                f"dimension default {self.default!r} not in flavors {self.flavors}"
            )
        return self


class VariantFilter(BaseModel):
    """A filter that excludes an impossible (stage, *flavor) combination.

    See §6.5.2.2: `[[variants.filter]] match = {audience='internal',
    stage='production'} reason='internal builds never ship to production'`.
    """

    match: dict[str, str] = Field(default_factory=dict)
    reason: str = Field(default="", max_length=240)

    model_config = ConfigDict(extra="forbid", frozen=False)

    @field_validator("match")
    @classmethod
    def _match_non_empty(cls, value: dict[str, str]) -> dict[str, str]:
        if not value:
            raise ValueError("VariantFilter.match must declare at least one axis")
        return value


class StageConfig(BaseModel):
    """Per-stage overrides — secrets resolver, AI provider, audit verbosity."""

    ai_provider: str = Field(default="")
    secrets_resolver: Literal["dotenv", "keyring", "aws-secrets-manager",
                              "vault", "1password", "age", "gpg", ""] = ""
    audit_verbosity: Literal["minimal", "normal", "elevated", ""] = ""
    signing_required: bool = Field(default=False)

    model_config = ConfigDict(extra="forbid", frozen=False)


# Default branch map references only the default-minimal stages
# (dev, production). When a user declares `staging` (or other stages), they
# add the matching branch-map entries — the validator enforces consistency.
_BRANCH_MAP_DEFAULT: dict[str, str] = {
    "main": "production",
    "master": "production",
    "develop": "dev",
    "release/*": "production",
    "hotfix/*": "production",
}


class VariantConfig(BaseModel):
    """Multi-dimensional variant matrix per ADR-032.

    Default-minimal: `stages=['dev','production']` + zero flavor dimensions
    reproduces the v0.5 binary axis behavior; existing repos need no
    config.
    """

    stages: list[str] = Field(default_factory=lambda: ["dev", "production"])
    default_stage: str = Field(default="dev")
    publish_stage: str = Field(default="production")
    dimensions: dict[str, DimensionConfig] = Field(default_factory=dict)
    filter: list[VariantFilter] = Field(default_factory=list)
    branch_map: dict[str, str] = Field(default_factory=lambda: dict(_BRANCH_MAP_DEFAULT))
    stage: dict[str, StageConfig] = Field(default_factory=dict)

    model_config = ConfigDict(extra="forbid", frozen=False)

    @model_validator(mode="after")
    def _publish_stage_in_stages(self) -> VariantConfig:
        if self.default_stage not in self.stages:
            raise ValueError(
                f"variants.default_stage={self.default_stage!r} not in stages={self.stages}"
            )
        if self.publish_stage not in self.stages:
            raise ValueError(
                f"variants.publish_stage={self.publish_stage!r} not in stages={self.stages}"
            )
        # Per-stage overrides must reference real stages
        for stage_name in self.stage:
            if stage_name not in self.stages:
                raise ValueError(
                    f"variants.stage.{stage_name!r}: not a declared stage "
                    f"(declared: {self.stages})"
                )
        # branch_map targets must be valid stages
        for branch_pattern, mapped_stage in self.branch_map.items():
            if mapped_stage not in self.stages:
                raise ValueError(
                    f"variants.branch_map[{branch_pattern!r}]={mapped_stage!r}: "
                    f"not a declared stage"
                )
        # Filter `match` keys must be either "stage" or a declared dimension
        valid_axes = {"stage", *self.dimensions.keys()}
        for f in self.filter:
            for axis in f.match:
                if axis not in valid_axes:
                    raise ValueError(
                        f"variants.filter: axis {axis!r} not in {sorted(valid_axes)}"
                    )
            if "stage" in f.match and f.match["stage"] not in self.stages:
                raise ValueError(
                    f"variants.filter.match.stage={f.match['stage']!r}: "
                    f"not a declared stage"
                )
        return self


# --------------------------------------------------------------------------- #
# Gitignore (ADR-026; §6.5.1)
# --------------------------------------------------------------------------- #


class GitignorePolicy(BaseModel):
    allow_safety_off: bool = Field(default=False)
    detect_on_init: bool = Field(default=True)
    override_extends: list[str] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid", frozen=False)


class GitignoreConfig(BaseModel):
    """Per-stage gitignore profile composition + policy.

    The `dev` / `prod` keys map to stage names — for the default-minimal
    config they happen to be `dev` and `production` (matching the
    `VariantConfig.stages` default). For multi-stage projects the user
    declares one entry per stage; the swap engine consults the active
    variant's stage when composing the effective `.gitignore`.
    """

    dev: list[str] = Field(
        default_factory=lambda: [
            "_core/secrets",
            "_core/editor-noise",
            "_core/license",
        ]
    )
    prod: list[str] = Field(
        default_factory=lambda: [
            "_core/secrets",
            "_core/license",
        ]
    )
    policy: GitignorePolicy = Field(default_factory=GitignorePolicy)

    model_config = ConfigDict(extra="forbid", frozen=False)

    @field_validator("dev", "prod")
    @classmethod
    def _profiles_look_like_slugs(cls, value: list[str]) -> list[str]:
        pattern = re.compile(r"^(_core|lang|framework|infra|cloud|ci|release|"
                             r"security|ai|db|editor|os|domain|type|workflow)/[\w\-]+$")
        offenders = [p for p in value if not pattern.match(p)]
        if offenders:
            raise ValueError(
                f"gitignore profile slugs must be `<category>/<name>` "
                f"per §10.4; offenders: {offenders}"
            )
        return value


# --------------------------------------------------------------------------- #
# AI subsystem (§6.7)
# --------------------------------------------------------------------------- #


class AIProviderConfig(BaseModel):
    """Per-AI-provider configuration.

    `api_key_env_var` names the environment variable the secrets resolver
    looks up. The API key value itself never appears in this model.
    """

    name: Literal["anthropic", "openai", "ollama", "gemini",
                  "bedrock", "azure-openai", "mcp"]
    enabled: bool = Field(default=True)
    api_key_env_var: str = Field(default="")
    default_model: str = Field(default="")
    cost_limit_usd_per_day: float = Field(default=0.0, ge=0.0)

    model_config = ConfigDict(extra="forbid", frozen=False)


class AIConfig(BaseModel):
    """AI subsystem config — providers + redaction + MCP allowlist."""

    providers: list[AIProviderConfig] = Field(default_factory=list)
    default_provider: str = Field(default="")
    redaction_patterns: list[str] = Field(
        default_factory=lambda: [
            r"AKIA[0-9A-Z]{16}",  # AWS access key
            r"ghp_[0-9a-zA-Z]{36}",  # GitHub personal access token
            r"sk-[0-9a-zA-Z]{48}",  # OpenAI / Anthropic-like API key
            r"-----BEGIN (RSA|EC|DSA|OPENSSH) PRIVATE KEY-----",
        ],
        description="Regex patterns scrubbed from diffs before AI egress.",
    )
    mcp_allowlist: list[str] = Field(
        default_factory=list,
        description="MCP server URLs allowed for this project.",
    )
    cost_alert_threshold_usd: float = Field(default=5.0, ge=0.0)

    model_config = ConfigDict(extra="forbid", frozen=False)

    @model_validator(mode="after")
    def _default_provider_in_providers(self) -> AIConfig:
        if not self.providers:
            return self
        names = {p.name for p in self.providers}
        if not self.default_provider:
            object.__setattr__(self, "default_provider", self.providers[0].name)
        elif self.default_provider not in names:
            raise ValueError(
                f"ai.default_provider={self.default_provider!r} "
                f"not in configured providers {sorted(names)}"
            )
        return self


# --------------------------------------------------------------------------- #
# Secrets (§6.10)
# --------------------------------------------------------------------------- #


class SecretsConfig(BaseModel):
    """Secret resolver configuration.

    Secret VALUES are never in this model — only the resolver type + lookup
    keys. Resolution happens at use-time via §6.10's mechanisms.
    """

    resolver: Literal["dotenv", "keyring", "aws-secrets-manager",
                      "vault", "1password", "age", "gpg"] = "keyring"
    keyring_service: str = Field(default="sange")
    dotenv_path: str = Field(default=".env")
    vault_url: str = Field(default="")
    vault_mount: str = Field(default="secret")
    onepassword_vault: str = Field(default="")

    model_config = ConfigDict(extra="forbid", frozen=False)


# --------------------------------------------------------------------------- #
# Audit (§7.0.7)
# --------------------------------------------------------------------------- #


class AuditConfig(BaseModel):
    """Hash-chained audit log settings.

    The audit log itself is a write-only sink; this config governs verbosity,
    retention, and optional external forwarding (§13).
    """

    enabled: bool = Field(default=True)
    verbosity: Literal["minimal", "normal", "elevated"] = "normal"
    log_dir: str = Field(default=".sange/audit")
    global_mirror_dir: str = Field(default="~/.sange/audit")
    rotation_days: int = Field(default=7, ge=1)
    siem_forward_url: str = Field(default="")

    model_config = ConfigDict(extra="forbid", frozen=False)


# --------------------------------------------------------------------------- #
# Telemetry (§12)
# --------------------------------------------------------------------------- #


class TelemetryConfig(BaseModel):
    """Local telemetry collector. External send is OFF by default per ADR-008."""

    enabled: bool = Field(default=True)
    log_dir: str = Field(default=".sange/telemetry")
    hash_sensitive_fields: bool = Field(default=True)
    external_send_enabled: bool = Field(default=False)
    external_send_endpoint: str = Field(default="")
    aggregation_window_hours: int = Field(default=24, ge=24)

    model_config = ConfigDict(extra="forbid", frozen=False)


# --------------------------------------------------------------------------- #
# Root SangeConfig
# --------------------------------------------------------------------------- #


class SangeConfig(BaseModel):
    """The single Sange configuration object.

    Every subsystem takes a `SangeConfig` and reads its sub-models. There's
    no other "config" surface — env vars merge into this; CLI flags merge
    into this; the variant resolver consults this.

    The default constructor (`SangeConfig()`) yields a valid object
    representing the default-minimal configuration. Calling
    `model_dump()` on that object produces the canonical TOML/JSON
    payload a fresh `.sange/config.toml` could contain.
    """

    schema_version: SchemaVersion = Field(default_factory=lambda: SCHEMA_CURRENT)
    project: ProjectMeta = Field(default_factory=ProjectMeta)
    variants: VariantConfig = Field(default_factory=VariantConfig)
    gitignore: GitignoreConfig = Field(default_factory=GitignoreConfig)
    ai: AIConfig = Field(default_factory=AIConfig)
    secrets: SecretsConfig = Field(default_factory=SecretsConfig)
    audit: AuditConfig = Field(default_factory=AuditConfig)
    telemetry: TelemetryConfig = Field(default_factory=TelemetryConfig)

    model_config = ConfigDict(extra="forbid", frozen=False)

    # ----- Convenience accessors ---------------------------------------- #

    def active_stage_config(self, stage: str) -> StageConfig:
        """Return the per-stage override block for `stage`, or an empty default."""

        return self.variants.stage.get(stage, StageConfig())

    def is_publish_stage(self, stage: str) -> bool:
        return stage == self.variants.publish_stage

    def all_declared_stages(self) -> list[str]:
        return list(self.variants.stages)

    def all_declared_dimensions(self) -> list[str]:
        return sorted(self.variants.dimensions.keys())


__all__ = [
    "SCHEMA_CURRENT",
    "AIConfig",
    "AIProviderConfig",
    "AuditConfig",
    "DimensionConfig",
    "GitignoreConfig",
    "GitignorePolicy",
    "ProjectMeta",
    "SangeConfig",
    "SchemaVersion",
    "SecretsConfig",
    "StageConfig",
    "TelemetryConfig",
    "VariantConfig",
    "VariantFilter",
]
