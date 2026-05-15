"""SangeConfig — Pydantic v2 configuration model + loader.

Per §6.3 + §6.5.2 of `.design/sange-architecture-prompt.md`. The single
`SangeConfig` object is the only thing the rest of the code reads from;
every subsystem (variant matrix, AI providers, secrets resolver, audit
verbosity, web UI bind address, …) takes a `SangeConfig` and uses it.

Public surface:

  * `SangeConfig` — the root model.
  * `load_config(...)` — precedence-chain loader.
  * `ConfigError` — base exception for config-related failures.

Implementation modules:

  * `models` — the Pydantic v2 model tree.
  * `loader` — file discovery + precedence merge + ENV overrides.

The §6.3 precedence (rightmost wins):

    built-in defaults
      ← /etc/sange/config.{toml,json}
        ← ~/.sange/config.{toml,json}
          ← ${repo}/.sange/config.{toml,json}
            ← SANGE__* environment variables
              ← CLI flags

Secrets are NEVER in the TOML/JSON files; the model carries references
(env-var names, keyring keys, vault paths) and the secrets resolver
resolves them at use-time.
"""

from __future__ import annotations

from sange.core.config.loader import (
    DEFAULT_SYSTEM_DIR,
    DEFAULT_USER_DIR,
    ConfigError,
    EnvOverrideError,
    SchemaVersionError,
    discover_repo_config,
    load_config,
)
from sange.core.config.models import (
    AIConfig,
    AIProviderConfig,
    AuditConfig,
    DimensionConfig,
    GitignoreConfig,
    GitignorePolicy,
    ProjectMeta,
    SangeConfig,
    SchemaVersion,
    SecretsConfig,
    StageConfig,
    TelemetryConfig,
    VariantConfig,
    VariantFilter,
)

__all__ = [
    "DEFAULT_SYSTEM_DIR",
    "DEFAULT_USER_DIR",
    "AIConfig",
    "AIProviderConfig",
    "AuditConfig",
    "ConfigError",
    "DimensionConfig",
    "EnvOverrideError",
    "GitignoreConfig",
    "GitignorePolicy",
    "ProjectMeta",
    "SangeConfig",
    "SchemaVersion",
    "SchemaVersionError",
    "SecretsConfig",
    "StageConfig",
    "TelemetryConfig",
    "VariantConfig",
    "VariantFilter",
    "discover_repo_config",
    "load_config",
]
