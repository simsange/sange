"""`sange.core.secrets` — runtime secret resolution per §6.10.

The §6.10 spec enumerates five mechanisms in preference order:

  1. SSH agent forwarding (host's `SSH_AUTH_SOCK` mounted into the
     container at runtime). Default for local dev.
  2. Docker secrets / BuildKit secrets (mounted as in-memory tmpfs
     files at `/run/secrets/<name>`).
  3. OS keychain pass-through (Sange daemon over Unix socket — v1.0+).
  4. External secret manager (Vault, AWS Secrets Manager, 1Password —
     v1.0+).
  5. Encrypted file mount (age- or GPG-encrypted — v1.0+).

This v0.5 slice ships mechanisms 1, 2, and a keychain resolver (via
the `keyring` lib already pinned in pyproject), plus an env-var
resolver for development. Mechanisms 3-5 land in v1.0+ when the
daemon + external integrations exist.

Public surface:

  * `Secret`              — metadata-only model (name + provider +
                            lookup key + description). NEVER holds
                            the value itself.
  * `Resolver`            — Protocol: `resolve(secret) -> str | None`.
  * `EnvVarResolver`      — reads `os.environ[secret.lookup_key]`.
  * `FileResolver`        — reads bytes from a mounted file path.
                            Default `/run/secrets/<name>` (Docker /
                            BuildKit convention).
  * `SshAgentResolver`    — validates `SSH_AUTH_SOCK` exists + is a
                            socket. Does NOT decrypt or read the key
                            material; that's the SSH client's job.
                            Returns the socket path so callers can
                            forward `SSH_AUTH_SOCK` to child
                            processes.
  * `KeyringResolver`     — `keyring.get_password(service, key)`.
                            Service name defaults to `"sange"`.
  * `ChainResolver`       — walks a tuple of resolvers, returns the
                            first non-None result.
  * `ResolutionError`     — raised when chain reaches end + still
                            unresolved AND `strict=True`.

Invariants:
  * Resolved values are NEVER stored on `Secret` instances.
  * `resolve()` returns the value at call time; the caller is
    responsible for not stashing the result.
  * `Secret.__repr__` redacts everything but the name + provider
    (so a `print(secret)` in a stack trace doesn't leak the lookup
    key).
  * No resolver logs the resolved value. The fact that a secret
    WAS resolved (and via which resolver) IS auditable via the
    `resolved_via` field in `ResolutionResult`.
"""

from __future__ import annotations

from sange.core.secrets.model import Secret, redact
from sange.core.secrets.resolver import (
    ChainResolver,
    EnvVarResolver,
    FileResolver,
    KeyringResolver,
    ResolutionError,
    ResolutionResult,
    Resolver,
    SshAgentResolver,
)

__all__ = [
    "ChainResolver",
    "EnvVarResolver",
    "FileResolver",
    "KeyringResolver",
    "ResolutionError",
    "ResolutionResult",
    "Resolver",
    "Secret",
    "SshAgentResolver",
    "redact",
]
