"""Concrete resolvers + `ChainResolver` per §6.10.

The `Resolver` protocol is intentionally tiny:

    def resolve(self, secret: Secret) -> str | None: ...

Returns `None` to mean "I can't resolve this — try the next
resolver in the chain". Raises `ResolutionError` only for
configuration-time failures (e.g. asked to resolve a `keyring`
secret with no `lookup_key` set) — runtime "not found" cases
return `None`.

Each concrete resolver checks `secret.provider` first to short-
circuit when the secret is intended for a different resolver.
A resolver that returns `None` for the wrong provider type means
the chain can compose resolvers without an explicit dispatch table.

Security invariants:
  * No resolver logs the resolved value.
  * No resolver caches the resolved value in instance state.
  * Resolvers do NOT eagerly probe a secret store at construct
    time — they resolve only when called.
"""

from __future__ import annotations

import os
import stat as _stat
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable

from sange.core.secrets.model import Secret


class ResolutionError(Exception):
    """Raised when a chain cannot resolve a required secret.

    Also raised by individual resolvers on misconfiguration
    (missing `lookup_key`, malformed path, etc.).
    """


@dataclass(frozen=True)
class ResolutionResult:
    """The outcome of `ChainResolver.resolve_detailed`.

    Carries the secret name + which resolver succeeded; the value
    itself is on the dataclass only briefly so the caller can read
    it. Per the §6.10 audit-invariant we record the resolver NAME
    used (so the audit chain knows "we resolved gitleaks-key via
    keyring at 14:32") without recording the value itself.
    """

    secret_name: str
    value: str | None
    resolved_via: str          # e.g. "env", "file:/run/secrets/x", "keyring:sange"
    found: bool

    def __repr__(self) -> str:
        # Never log the value, even in repr.
        return (
            f"ResolutionResult(secret_name={self.secret_name!r}, "
            f"resolved_via={self.resolved_via!r}, found={self.found})"
        )


@runtime_checkable
class Resolver(Protocol):
    """Resolve a `Secret` to its value at call time.

    Implementations:
      * Return the value as a string when found.
      * Return `None` when this resolver doesn't apply to the
        secret OR when the value is genuinely absent.
      * Raise `ResolutionError` only for configuration errors
        that the caller can fix (missing required arg, etc.).
    """

    @property
    def name(self) -> str:
        """Human-readable resolver name for audit trails."""

        ...

    def resolve(self, secret: Secret) -> str | None:
        ...


# --------------------------------------------------------------------------- #
# Concrete resolvers
# --------------------------------------------------------------------------- #


class EnvVarResolver:
    """Resolve secrets whose `provider == "env"`.

    `secret.lookup_key` is the env-var name. Returns `None` if the
    var is unset OR empty. (An empty env var is treated as "not
    set" — operators sometimes export blank vars by accident; a
    blank "secret" is never the right answer.)

    Dev-convenience-grade only; production should prefer `file` /
    `keyring` / `ssh-agent`.
    """

    name = "env"

    def __init__(self, env: dict[str, str] | None = None) -> None:
        self._env = env

    def resolve(self, secret: Secret) -> str | None:
        if secret.provider != "env":
            return None
        if not secret.lookup_key:
            raise ResolutionError(
                f"EnvVarResolver requires lookup_key for {secret.name!r}"
            )
        source = self._env if self._env is not None else os.environ
        value = source.get(secret.lookup_key, "")
        return value or None


class FileResolver:
    """Resolve secrets whose `provider == "file"`.

    `secret.lookup_key` is the absolute file path. Default
    convention is `/run/secrets/<name>` (Docker / BuildKit). The
    file is read in binary mode + stripped of trailing whitespace
    (most BuildKit-mounted secrets end in `\\n` which the
    operator's tool didn't intend).

    Security: refuses to read a file with mode > `0644` — if the
    file is world-writable or group-writable, that's a deployment
    bug, not a secret. Refuses to read a file owned by a different
    user than the running process unless `strict_ownership=False`
    is set.
    """

    name = "file"

    def __init__(self, *, strict_ownership: bool = True) -> None:
        self._strict_ownership = strict_ownership

    def resolve(self, secret: Secret) -> str | None:
        if secret.provider != "file":
            return None
        if not secret.lookup_key:
            raise ResolutionError(
                f"FileResolver requires lookup_key (path) for {secret.name!r}"
            )
        path = Path(secret.lookup_key)
        if not path.is_file():
            return None
        try:
            st = path.stat()
        except OSError as exc:
            raise ResolutionError(
                f"FileResolver cannot stat {path}: {exc}"
            ) from exc

        mode = _stat.S_IMODE(st.st_mode)
        # World- or group-writable bits set → deployment bug.
        if mode & (_stat.S_IWOTH | _stat.S_IWGRP):
            raise ResolutionError(
                f"FileResolver refuses to read {path}: mode {oct(mode)} is "
                f"writable beyond the owner — fix to 0400 or 0600"
            )
        if self._strict_ownership and hasattr(os, "geteuid"):
            if st.st_uid != os.geteuid():
                raise ResolutionError(
                    f"FileResolver refuses to read {path}: owned by uid "
                    f"{st.st_uid}, not the running uid {os.geteuid()}"
                )

        try:
            data = path.read_bytes()
        except OSError as exc:
            raise ResolutionError(
                f"FileResolver cannot read {path}: {exc}"
            ) from exc
        text = data.decode("utf-8", errors="strict").rstrip("\r\n").rstrip()
        return text or None


class SshAgentResolver:
    """Validate that `SSH_AUTH_SOCK` is forwarded into the process.

    This resolver doesn't return key material — that's the SSH
    client's job. It returns the SOCKET PATH so callers can verify
    the agent is reachable and forward `SSH_AUTH_SOCK` into child
    processes (git, ssh, scp).

    `secret.lookup_key` is ignored when set; the socket comes from
    the env var.
    """

    name = "ssh-agent"

    def __init__(self, env: dict[str, str] | None = None) -> None:
        self._env = env

    def resolve(self, secret: Secret) -> str | None:
        if secret.provider != "ssh-agent":
            return None
        source = self._env if self._env is not None else os.environ
        sock = source.get("SSH_AUTH_SOCK", "")
        if not sock:
            return None
        path = Path(sock)
        try:
            st = path.stat()
        except OSError:
            return None
        if not _stat.S_ISSOCK(st.st_mode):
            return None
        return sock


class KeyringResolver:
    """Resolve secrets whose `provider == "keyring"` via the OS keychain.

    `secret.lookup_key` is the credential name within the keyring
    service. `service` defaults to `"sange"` so all Sange secrets
    share one service namespace, but a different service name lets
    a single Sange install talk to multiple credential stores.

    Returns `None` if the keyring backend reports the credential
    missing OR if `keyring` itself fails to import (e.g. running
    inside a container without a backend daemon). The chain then
    falls through to the next resolver.
    """

    def __init__(self, service: str = "sange") -> None:
        self._service = service

    @property
    def name(self) -> str:
        return f"keyring:{self._service}"

    def resolve(self, secret: Secret) -> str | None:
        if secret.provider != "keyring":
            return None
        if not secret.lookup_key:
            raise ResolutionError(
                f"KeyringResolver requires lookup_key for {secret.name!r}"
            )
        try:
            import keyring
            import keyring.errors
        except ImportError:
            return None
        try:
            value = keyring.get_password(self._service, secret.lookup_key)
        except keyring.errors.KeyringError:
            return None
        return value or None


# --------------------------------------------------------------------------- #
# Chain
# --------------------------------------------------------------------------- #


class ChainResolver:
    """Walk a tuple of resolvers; return the first non-None result.

    The order matters — put the most preferred mechanism first. The
    §6.10 preference order for production is roughly:

        ChainResolver(
            SshAgentResolver(),       # for SSH-key secrets
            FileResolver(),           # for BuildKit secrets
            KeyringResolver(),        # for OS-keychain secrets
            EnvVarResolver(),         # dev convenience fallback
        )

    `strict=False` (default) returns `None` if no resolver finds
    the value. `strict=True` raises `ResolutionError` instead.
    """

    name = "chain"

    def __init__(
        self,
        *resolvers: Resolver,
        strict: bool = False,
    ) -> None:
        if not resolvers:
            raise ResolutionError("ChainResolver requires at least one resolver")
        self._resolvers: tuple[Resolver, ...] = tuple(resolvers)
        self._strict = strict

    @property
    def resolvers(self) -> Sequence[Resolver]:
        return self._resolvers

    def resolve(self, secret: Secret) -> str | None:
        result = self.resolve_detailed(secret)
        return result.value

    def resolve_detailed(self, secret: Secret) -> ResolutionResult:
        """Return both the value AND which resolver fired.

        The `resolved_via` field is meant for audit logging — record
        that gitleaks-key was sourced from `keyring:sange` without
        recording the value itself.
        """

        for resolver in self._resolvers:
            value = resolver.resolve(secret)
            if value is not None:
                return ResolutionResult(
                    secret_name=secret.name,
                    value=value,
                    resolved_via=resolver.name,
                    found=True,
                )

        if self._strict or secret.required:
            tried = [r.name for r in self._resolvers]
            raise ResolutionError(
                f"secret {secret.name!r} not resolved by any of: "
                f"{tried}"
            )
        return ResolutionResult(
            secret_name=secret.name,
            value=None,
            resolved_via="",
            found=False,
        )


__all__ = [
    "ChainResolver",
    "EnvVarResolver",
    "FileResolver",
    "KeyringResolver",
    "ResolutionError",
    "ResolutionResult",
    "Resolver",
    "SshAgentResolver",
]
