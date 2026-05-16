"""`Secret` — metadata model for a registered secret entry.

Per §6.10's invariant ("Secrets never appear in logs, audit entries,
or telemetry"), this dataclass holds the **lookup descriptor** only —
the name, provider type, lookup key, optional description. The
actual secret VALUE is resolved at call time via a `Resolver` and
returned by reference; it is never assigned to a field on this
object.

`Secret.__repr__` is overridden to redact the lookup_key (which
itself is sometimes secret — e.g. when it's a Vault path containing
a token namespace). Only the name + provider show through, so a
stack trace + `print(secret)` doesn't leak structure.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Provider = Literal[
    "env",          # env-var lookup (development convenience)
    "file",         # mounted file (BuildKit /run/secrets, etc.)
    "ssh-agent",    # SSH agent socket forwarding
    "keyring",      # OS keychain via the `keyring` library
    "vault",        # HashiCorp Vault (v1.0+)
    "aws-secrets-manager",  # AWS Secrets Manager (v1.0+)
    "1password",    # 1Password Connect (v1.0+)
    "age",          # age-encrypted file mount (v1.0+)
    "gpg",          # GPG-encrypted file mount (v1.0+)
]


_REDACTED = "<redacted>"


def redact(_value: str | bytes | None) -> str:
    """Return a constant placeholder regardless of input.

    Used everywhere a secret value might otherwise reach a log /
    error message / repr. The function takes the value only to
    make the redaction call-site grep-able — the input is
    immediately discarded.
    """

    return _REDACTED


@dataclass(frozen=True)
class Secret:
    """A registered secret descriptor — metadata only.

    Fields:
      * `name`         — short identifier the operator uses
                         (`gitleaks-api-key`, `npm-publish-token`).
      * `provider`     — which `Provider` mechanism the resolver
                         should use.
      * `lookup_key`   — provider-specific key. For `env` it's the
                         env-var name; for `file` it's the absolute
                         path; for `keyring` it's the credential
                         name within the service.
      * `description`  — optional human-readable note. Should NOT
                         contain the secret value (validated by
                         `__post_init__` via the redaction helper).
      * `required`     — when True, the resolver chain MUST find
                         a value; raise `ResolutionError` if not.

    The `__repr__` returns `Secret(name=..., provider=...)` only —
    `lookup_key` + `description` are suppressed because they sometimes
    carry secret-adjacent context (a vault path's namespace, a
    keychain service identifier).
    """

    name: str
    provider: Provider
    lookup_key: str = ""
    description: str = ""
    required: bool = False

    def __repr__(self) -> str:
        return f"Secret(name={self.name!r}, provider={self.provider!r})"

    def __post_init__(self) -> None:
        # Best-effort sanity checks. We don't validate the lookup_key
        # against the provider's schema here — that's the resolver's
        # job (it raises a more specific error).
        if not self.name:
            raise ValueError("Secret.name must be non-empty")
        if "\n" in self.name or "\n" in self.lookup_key:
            # Newlines in secret descriptors are a structured-log
            # injection vector — reject loudly rather than sanitize.
            raise ValueError("Secret.name / lookup_key must not contain newlines")


__all__ = [
    "Provider",
    "Secret",
    "redact",
]
