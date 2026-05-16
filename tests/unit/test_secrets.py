"""Tests for `sange.core.secrets` — §6.10 secret resolver chain."""

from __future__ import annotations

import os
import socket
import stat as _stat
import sys
from pathlib import Path

import pytest

from sange.core.secrets import (
    ChainResolver,
    EnvVarResolver,
    FileResolver,
    KeyringResolver,
    ResolutionError,
    Resolver,
    Secret,
    SshAgentResolver,
    redact,
)

# --------------------------------------------------------------------------- #
# Secret model
# --------------------------------------------------------------------------- #


class TestSecretModel:
    def test_construct(self) -> None:
        s = Secret(name="api", provider="env", lookup_key="API_KEY")
        assert s.name == "api"
        assert s.provider == "env"

    def test_repr_redacts_lookup_key(self) -> None:
        s = Secret(
            name="api", provider="vault",
            lookup_key="secret/v1/team-secrets/api-key-prod",
        )
        r = repr(s)
        assert "secret/v1/team-secrets" not in r
        assert "api" in r
        assert "vault" in r

    def test_empty_name_rejected(self) -> None:
        with pytest.raises(ValueError, match="non-empty"):
            Secret(name="", provider="env")

    def test_newline_in_name_rejected(self) -> None:
        with pytest.raises(ValueError, match="newline"):
            Secret(name="a\nb", provider="env")

    def test_newline_in_lookup_rejected(self) -> None:
        with pytest.raises(ValueError, match="newline"):
            Secret(name="a", provider="env", lookup_key="X=Y\nINJECT")

    def test_frozen(self) -> None:
        s = Secret(name="api", provider="env")
        with pytest.raises(Exception):
            s.name = "x"  # type: ignore[misc]


class TestRedact:
    def test_redacts_string(self) -> None:
        assert redact("super-secret-token") == "<redacted>"

    def test_redacts_bytes(self) -> None:
        assert redact(b"binary-secret") == "<redacted>"

    def test_redacts_none(self) -> None:
        assert redact(None) == "<redacted>"


# --------------------------------------------------------------------------- #
# EnvVarResolver
# --------------------------------------------------------------------------- #


class TestEnvVarResolver:
    def test_resolves_present_var(self) -> None:
        r = EnvVarResolver(env={"FOO": "value-of-foo"})
        s = Secret(name="foo", provider="env", lookup_key="FOO")
        assert r.resolve(s) == "value-of-foo"

    def test_missing_var_returns_none(self) -> None:
        r = EnvVarResolver(env={})
        s = Secret(name="foo", provider="env", lookup_key="MISSING")
        assert r.resolve(s) is None

    def test_empty_var_treated_as_none(self) -> None:
        r = EnvVarResolver(env={"FOO": ""})
        s = Secret(name="foo", provider="env", lookup_key="FOO")
        assert r.resolve(s) is None

    def test_wrong_provider_returns_none(self) -> None:
        r = EnvVarResolver(env={"FOO": "x"})
        s = Secret(name="foo", provider="file", lookup_key="FOO")
        assert r.resolve(s) is None

    def test_missing_lookup_key_raises(self) -> None:
        r = EnvVarResolver(env={})
        s = Secret(name="foo", provider="env", lookup_key="")
        with pytest.raises(ResolutionError, match="lookup_key"):
            r.resolve(s)

    def test_resolver_satisfies_protocol(self) -> None:
        r = EnvVarResolver()
        assert isinstance(r, Resolver)


# --------------------------------------------------------------------------- #
# FileResolver
# --------------------------------------------------------------------------- #


@pytest.fixture
def mounted_secret(tmp_path: Path) -> Path:
    """Mimic a BuildKit /run/secrets/<name> tmpfs mount."""

    path = tmp_path / "api-token"
    path.write_text("api-token-value\n")
    path.chmod(0o600)
    return path


class TestFileResolver:
    def test_reads_secret_file(self, mounted_secret: Path) -> None:
        r = FileResolver(strict_ownership=False)
        s = Secret(name="api", provider="file", lookup_key=str(mounted_secret))
        assert r.resolve(s) == "api-token-value"

    def test_strips_trailing_newline(
        self, mounted_secret: Path,
    ) -> None:
        # The BuildKit-mounted file ends with `\n` — must be stripped.
        r = FileResolver(strict_ownership=False)
        s = Secret(name="api", provider="file", lookup_key=str(mounted_secret))
        result = r.resolve(s)
        assert result is not None
        assert not result.endswith("\n")

    def test_missing_file_returns_none(self, tmp_path: Path) -> None:
        r = FileResolver(strict_ownership=False)
        s = Secret(
            name="api", provider="file",
            lookup_key=str(tmp_path / "nope"),
        )
        assert r.resolve(s) is None

    def test_world_writable_refused(self, tmp_path: Path) -> None:
        path = tmp_path / "leaky-secret"
        path.write_text("x")
        path.chmod(0o666)
        r = FileResolver(strict_ownership=False)
        s = Secret(name="x", provider="file", lookup_key=str(path))
        with pytest.raises(ResolutionError, match="writable beyond"):
            r.resolve(s)

    def test_group_writable_refused(self, tmp_path: Path) -> None:
        path = tmp_path / "group-leaky"
        path.write_text("x")
        path.chmod(0o660)
        r = FileResolver(strict_ownership=False)
        s = Secret(name="x", provider="file", lookup_key=str(path))
        with pytest.raises(ResolutionError, match="writable beyond"):
            r.resolve(s)

    def test_wrong_provider_returns_none(self, mounted_secret: Path) -> None:
        r = FileResolver(strict_ownership=False)
        s = Secret(name="api", provider="env", lookup_key=str(mounted_secret))
        assert r.resolve(s) is None

    def test_missing_lookup_key_raises(self) -> None:
        r = FileResolver()
        s = Secret(name="api", provider="file", lookup_key="")
        with pytest.raises(ResolutionError, match="path"):
            r.resolve(s)


# --------------------------------------------------------------------------- #
# SshAgentResolver
# --------------------------------------------------------------------------- #


pytestmark_posix = pytest.mark.skipif(
    sys.platform == "win32", reason="POSIX sockets only",
)


@pytestmark_posix
class TestSshAgentResolver:
    def test_returns_socket_path_when_present(self) -> None:
        # Unix socket path has a ~108 char limit on most kernels;
        # pytest's tmp_path under /private/var/folders/... can be
        # too long, so use a short path under /tmp + clean up manually.
        import uuid as _uuid
        short = Path("/tmp") / f"s-{_uuid.uuid4().hex[:8]}.sock"
        srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        srv.bind(str(short))
        try:
            r = SshAgentResolver(env={"SSH_AUTH_SOCK": str(short)})
            s = Secret(name="ssh", provider="ssh-agent")
            assert r.resolve(s) == str(short)
        finally:
            srv.close()
            short.unlink(missing_ok=True)

    def test_no_env_var_returns_none(self) -> None:
        r = SshAgentResolver(env={})
        s = Secret(name="ssh", provider="ssh-agent")
        assert r.resolve(s) is None

    def test_path_not_a_socket_returns_none(
        self, tmp_path: Path,
    ) -> None:
        regular = tmp_path / "regular-file"
        regular.write_text("not a socket")
        r = SshAgentResolver(env={"SSH_AUTH_SOCK": str(regular)})
        s = Secret(name="ssh", provider="ssh-agent")
        assert r.resolve(s) is None

    def test_nonexistent_path_returns_none(
        self, tmp_path: Path,
    ) -> None:
        r = SshAgentResolver(
            env={"SSH_AUTH_SOCK": str(tmp_path / "absent.sock")},
        )
        s = Secret(name="ssh", provider="ssh-agent")
        assert r.resolve(s) is None

    def test_wrong_provider_returns_none(self) -> None:
        r = SshAgentResolver(env={"SSH_AUTH_SOCK": "/tmp/x"})
        s = Secret(name="x", provider="env")
        assert r.resolve(s) is None


# --------------------------------------------------------------------------- #
# KeyringResolver
# --------------------------------------------------------------------------- #


class TestKeyringResolver:
    def test_wrong_provider_returns_none(self) -> None:
        r = KeyringResolver()
        s = Secret(name="x", provider="env", lookup_key="FOO")
        assert r.resolve(s) is None

    def test_missing_lookup_key_raises(self) -> None:
        r = KeyringResolver()
        s = Secret(name="x", provider="keyring", lookup_key="")
        with pytest.raises(ResolutionError, match="lookup_key"):
            r.resolve(s)

    def test_service_name_in_resolver_name(self) -> None:
        r = KeyringResolver(service="my-app")
        assert r.name == "keyring:my-app"

    def test_resolves_when_keyring_has_credential(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # Inject a fake keyring module that returns a known credential.
        import sys as _sys
        import types

        fake = types.ModuleType("keyring")
        fake_errors = types.ModuleType("keyring.errors")

        class FakeError(Exception):
            pass

        fake_errors.KeyringError = FakeError  # type: ignore[attr-defined]

        def get_password(service: str, key: str) -> str | None:
            if (service, key) == ("test-svc", "test-key"):
                return "real-secret-value"
            return None

        fake.get_password = get_password  # type: ignore[attr-defined]
        fake.errors = fake_errors  # type: ignore[attr-defined]
        monkeypatch.setitem(_sys.modules, "keyring", fake)
        monkeypatch.setitem(_sys.modules, "keyring.errors", fake_errors)

        r = KeyringResolver(service="test-svc")
        s = Secret(name="x", provider="keyring", lookup_key="test-key")
        assert r.resolve(s) == "real-secret-value"

    def test_returns_none_when_credential_missing(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        import sys as _sys
        import types

        fake = types.ModuleType("keyring")
        fake_errors = types.ModuleType("keyring.errors")

        class FakeError(Exception):
            pass

        fake_errors.KeyringError = FakeError  # type: ignore[attr-defined]
        fake.get_password = lambda _s, _k: None  # type: ignore[attr-defined]
        fake.errors = fake_errors  # type: ignore[attr-defined]
        monkeypatch.setitem(_sys.modules, "keyring", fake)
        monkeypatch.setitem(_sys.modules, "keyring.errors", fake_errors)

        r = KeyringResolver()
        s = Secret(name="x", provider="keyring", lookup_key="missing")
        assert r.resolve(s) is None


# --------------------------------------------------------------------------- #
# ChainResolver
# --------------------------------------------------------------------------- #


class TestChainResolver:
    def test_first_resolver_wins(self, tmp_path: Path) -> None:
        # File resolver wins over env even though env has the value.
        sec_path = tmp_path / "sec"
        sec_path.write_text("from-file")
        sec_path.chmod(0o600)
        chain = ChainResolver(
            FileResolver(strict_ownership=False),
            EnvVarResolver(env={"S": "from-env"}),
        )
        s = Secret(name="s", provider="file", lookup_key=str(sec_path))
        assert chain.resolve(s) == "from-file"

    def test_falls_through_to_second(self) -> None:
        chain = ChainResolver(
            FileResolver(strict_ownership=False),
            EnvVarResolver(env={"S": "from-env"}),
        )
        s = Secret(name="s", provider="env", lookup_key="S")
        assert chain.resolve(s) == "from-env"

    def test_all_miss_returns_none(self) -> None:
        chain = ChainResolver(
            EnvVarResolver(env={}),
        )
        s = Secret(name="s", provider="env", lookup_key="MISSING")
        assert chain.resolve(s) is None

    def test_strict_raises_when_missing(self) -> None:
        chain = ChainResolver(
            EnvVarResolver(env={}),
            strict=True,
        )
        s = Secret(name="s", provider="env", lookup_key="MISSING")
        with pytest.raises(ResolutionError, match="not resolved"):
            chain.resolve(s)

    def test_required_secret_raises_even_without_strict(self) -> None:
        chain = ChainResolver(EnvVarResolver(env={}))
        s = Secret(
            name="s", provider="env", lookup_key="MISSING", required=True,
        )
        with pytest.raises(ResolutionError):
            chain.resolve(s)

    def test_empty_chain_rejected(self) -> None:
        with pytest.raises(ResolutionError, match="at least one"):
            ChainResolver()

    def test_resolve_detailed_records_resolver_name(self) -> None:
        chain = ChainResolver(
            EnvVarResolver(env={"S": "v"}),
        )
        s = Secret(name="s", provider="env", lookup_key="S")
        result = chain.resolve_detailed(s)
        assert result.found is True
        assert result.value == "v"
        assert result.resolved_via == "env"

    def test_resolve_detailed_not_found(self) -> None:
        chain = ChainResolver(
            EnvVarResolver(env={}),
        )
        s = Secret(name="s", provider="env", lookup_key="MISSING")
        result = chain.resolve_detailed(s)
        assert result.found is False
        assert result.value is None
        assert result.resolved_via == ""

    def test_result_repr_does_not_contain_value(self) -> None:
        chain = ChainResolver(
            EnvVarResolver(env={"S": "VERY-SECRET-VALUE"}),
        )
        s = Secret(name="s", provider="env", lookup_key="S")
        result = chain.resolve_detailed(s)
        r = repr(result)
        assert "VERY-SECRET-VALUE" not in r
        assert "s" in r
        assert "env" in r
