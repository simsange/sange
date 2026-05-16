"""Tests for `sange.core.doctor.container` + `sange doctor --container`."""

from __future__ import annotations

import json as _json
import sys
from pathlib import Path

import pytest
from typer.testing import CliRunner

from sange.cli import app
from sange.core.doctor import (
    check_in_container,
    check_leaky_env_vars,
    check_non_root,
    check_secret_mount_perms,
    check_ssh_key_perms,
)

pytestmark = pytest.mark.skipif(
    sys.platform == "win32", reason="POSIX-only checks (mode bits, uid)",
)


# --------------------------------------------------------------------------- #
# check_in_container
# --------------------------------------------------------------------------- #


class TestCheckInContainer:
    def test_docker_marker_path(self, tmp_path: Path) -> None:
        marker = tmp_path / ".dockerenv"
        marker.write_text("")
        result = check_in_container(
            env={}, marker_paths=(str(marker),),
        )
        assert result.ok
        assert "running in container" in result.message
        assert any(f["signal"] == str(marker) for f in result.findings)

    def test_kubernetes_env(self) -> None:
        result = check_in_container(
            env={"KUBERNETES_SERVICE_HOST": "10.0.0.1"},
            marker_paths=(),
        )
        assert result.ok
        assert "KUBERNETES_SERVICE_HOST" in result.message

    def test_systemd_container_env(self) -> None:
        result = check_in_container(
            env={"container": "podman"},
            marker_paths=(),
        )
        assert result.ok

    def test_no_signals_fails(self) -> None:
        result = check_in_container(env={}, marker_paths=())
        assert not result.ok
        assert "not inside a container" in result.message


# --------------------------------------------------------------------------- #
# check_non_root
# --------------------------------------------------------------------------- #


class TestCheckNonRoot:
    def test_root_fails(self) -> None:
        result = check_non_root(uid_fn=lambda: 0)
        assert not result.ok
        assert "uid 0" in result.message

    def test_non_root_passes(self) -> None:
        result = check_non_root(uid_fn=lambda: 1000)
        assert result.ok
        assert "1000" in result.message
        assert result.findings == [{"uid": 1000}]

    def test_uid_fn_default_uses_geteuid(self) -> None:
        # No override — should use os.geteuid which always exists on POSIX.
        result = check_non_root()
        assert result.name == "non-root"


# --------------------------------------------------------------------------- #
# check_leaky_env_vars
# --------------------------------------------------------------------------- #


class TestCheckLeakyEnvVars:
    def test_no_secret_vars(self) -> None:
        result = check_leaky_env_vars(env={"PATH": "/usr/bin", "HOME": "/home/x"})
        assert result.ok
        assert result.findings == []

    def test_detects_token_suffix(self) -> None:
        result = check_leaky_env_vars(
            env={"GITHUB_TOKEN": "ghp_abc123", "PATH": "/bin"},
        )
        assert not result.ok
        assert any(f["var"] == "GITHUB_TOKEN" for f in result.findings)

    def test_detects_password_suffix(self) -> None:
        result = check_leaky_env_vars(env={"DATABASE_PASSWORD": "secret"})
        assert not result.ok

    def test_empty_value_not_flagged(self) -> None:
        # Var name matches pattern but value is empty — not a leak.
        result = check_leaky_env_vars(env={"GITHUB_TOKEN": ""})
        assert result.ok

    def test_value_never_in_findings(self) -> None:
        """The most important security invariant."""
        result = check_leaky_env_vars(
            env={"API_KEY": "this-secret-value-must-not-leak"},
        )
        assert not result.ok
        # Findings carry only name + length, never the value.
        for finding in result.findings:
            for key, val in finding.items():
                assert "this-secret-value" not in str(val), key
                assert "must-not-leak" not in str(val), key
            assert "var" in finding
            assert "length" in finding

    def test_allowlist_skips_known_safe(self) -> None:
        result = check_leaky_env_vars(
            env={"SSH_KEY_PATH": "/home/x/.ssh/id_rsa"},  # a PATH, not a key
        )
        assert result.ok  # SSH_KEY_PATH is in default allowlist

    def test_case_insensitive_matching(self) -> None:
        result = check_leaky_env_vars(env={"github_token": "x"})
        assert not result.ok


# --------------------------------------------------------------------------- #
# check_secret_mount_perms
# --------------------------------------------------------------------------- #


class TestCheckSecretMountPerms:
    def test_missing_dir_skipped(self, tmp_path: Path) -> None:
        result = check_secret_mount_perms(tmp_path / "nope")
        assert result.ok
        assert "skipped" in result.message

    def test_correct_mode_passes(self, tmp_path: Path) -> None:
        secret = tmp_path / "api"
        secret.write_text("x")
        secret.chmod(0o400)
        result = check_secret_mount_perms(tmp_path)
        assert result.ok

    def test_overpermissive_mode_fails(self, tmp_path: Path) -> None:
        secret = tmp_path / "api"
        secret.write_text("x")
        secret.chmod(0o644)
        result = check_secret_mount_perms(tmp_path)
        assert not result.ok
        assert len(result.findings) == 1
        assert "0o644" in result.findings[0]["mode"]  # type: ignore[index]

    def test_multiple_bad_files(self, tmp_path: Path) -> None:
        for name in ("a", "b", "c"):
            f = tmp_path / name
            f.write_text("x")
            f.chmod(0o666)
        result = check_secret_mount_perms(tmp_path)
        assert not result.ok
        assert len(result.findings) == 3


# --------------------------------------------------------------------------- #
# check_ssh_key_perms
# --------------------------------------------------------------------------- #


class TestCheckSshKeyPerms:
    def test_no_ssh_dir_skipped(self, tmp_path: Path) -> None:
        result = check_ssh_key_perms(tmp_path)
        assert result.ok
        assert "skipped" in result.message

    def test_correct_mode_key_passes(self, tmp_path: Path) -> None:
        ssh = tmp_path / ".ssh"
        ssh.mkdir()
        key = ssh / "id_rsa"
        key.write_text("PRIVATE KEY DATA")
        key.chmod(0o600)
        result = check_ssh_key_perms(tmp_path)
        assert result.ok

    def test_world_readable_key_fails(self, tmp_path: Path) -> None:
        ssh = tmp_path / ".ssh"
        ssh.mkdir()
        key = ssh / "id_ed25519"
        key.write_text("PRIVATE KEY DATA")
        key.chmod(0o644)
        result = check_ssh_key_perms(tmp_path)
        assert not result.ok
        assert any(
            f["path"].endswith("id_ed25519") for f in result.findings  # type: ignore[union-attr]
        )

    def test_pub_key_not_flagged(self, tmp_path: Path) -> None:
        """`.pub` files CAN be world-readable — that's their job."""
        ssh = tmp_path / ".ssh"
        ssh.mkdir()
        pub = ssh / "id_rsa.pub"
        pub.write_text("PUBLIC")
        pub.chmod(0o644)
        result = check_ssh_key_perms(tmp_path)
        assert result.ok

    def test_non_id_files_ignored(self, tmp_path: Path) -> None:
        """Only `id_<algo>` files get checked, not `known_hosts` etc."""
        ssh = tmp_path / ".ssh"
        ssh.mkdir()
        kh = ssh / "known_hosts"
        kh.write_text("host pubkey")
        kh.chmod(0o644)
        result = check_ssh_key_perms(tmp_path)
        assert result.ok


# --------------------------------------------------------------------------- #
# CLI integration
# --------------------------------------------------------------------------- #


class TestCliContainerFlag:
    def test_default_doctor_excludes_container_checks(self) -> None:
        runner = CliRunner()
        result = runner.invoke(app, ["doctor"])
        # Whatever exit code, the output shouldn't mention container.
        assert "in-container" not in result.output
        assert "non-root" not in result.output

    def test_container_flag_runs_in_container_check(self) -> None:
        """`--container` ALWAYS runs check_in_container first.

        On a host (not in a container) this should fail with the
        precise "not inside a container" message rather than running
        the other container checks.
        """
        runner = CliRunner()
        result = runner.invoke(app, ["doctor", "--container"])
        # The check appears in output regardless of pass/fail.
        assert "in-container" in result.output

    def test_container_flag_json_mode(self) -> None:
        runner = CliRunner()
        result = runner.invoke(app, ["--json", "doctor", "--container"])
        # Whether passing or failing, JSON should be parseable.
        payload = _json.loads(result.output)
        check_names = {c["name"] for c in payload["checks"]}
        assert "in-container" in check_names
