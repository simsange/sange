"""Tests for src/sange/core/config/loader.py — precedence chain + ENV + discovery."""

from __future__ import annotations

from pathlib import Path

import pytest

from sange.core.config import (
    SangeConfig,
    discover_repo_config,
    load_config,
)
from sange.core.config.loader import (
    ConfigError,
    EnvOverrideError,
    SchemaVersionError,
    _deep_merge,
    env_overrides,
)

# --------------------------------------------------------------------------- #
# _deep_merge
# --------------------------------------------------------------------------- #


class TestDeepMerge:
    def test_right_wins_on_scalar(self) -> None:
        assert _deep_merge({"a": 1}, {"a": 2}) == {"a": 2}

    def test_dicts_merge_recursively(self) -> None:
        merged = _deep_merge(
            {"a": {"b": 1, "c": 2}},
            {"a": {"c": 3, "d": 4}},
        )
        assert merged == {"a": {"b": 1, "c": 3, "d": 4}}

    def test_lists_replace_not_extend(self) -> None:
        merged = _deep_merge({"x": [1, 2]}, {"x": [3]})
        assert merged == {"x": [3]}

    def test_immutable_inputs(self) -> None:
        base = {"a": {"b": 1}}
        override = {"a": {"c": 2}}
        merged = _deep_merge(base, override)
        # The inputs must not be mutated.
        assert base == {"a": {"b": 1}}
        assert override == {"a": {"c": 2}}
        assert merged == {"a": {"b": 1, "c": 2}}


# --------------------------------------------------------------------------- #
# env_overrides
# --------------------------------------------------------------------------- #


class TestEnvOverrides:
    def test_empty_when_no_matching_vars(self) -> None:
        assert env_overrides({"PATH": "/usr/bin", "HOME": "/home/me"}) == {}

    def test_simple_override(self) -> None:
        out = env_overrides({"SANGE__AUDIT__VERBOSITY": "minimal"})
        assert out == {"audit": {"verbosity": "minimal"}}

    def test_bool_cast(self) -> None:
        out = env_overrides({
            "SANGE__AUDIT__ENABLED": "false",
            "SANGE__TELEMETRY__ENABLED": "true",
        })
        assert out["audit"]["enabled"] is False
        assert out["telemetry"]["enabled"] is True

    def test_int_cast(self) -> None:
        out = env_overrides({"SANGE__AUDIT__ROTATION_DAYS": "14"})
        assert out["audit"]["rotation_days"] == 14

    def test_float_cast(self) -> None:
        out = env_overrides({"SANGE__AI__COST_ALERT_THRESHOLD_USD": "12.50"})
        assert out["ai"]["cost_alert_threshold_usd"] == 12.50

    def test_comma_list_cast(self) -> None:
        out = env_overrides({"SANGE__VARIANTS__STAGES": "dev,staging,production"})
        assert out["variants"]["stages"] == ["dev", "staging", "production"]

    def test_deeply_nested(self) -> None:
        out = env_overrides({"SANGE__VARIANTS__BRANCH_MAP__MAIN": "production"})
        assert out["variants"]["branch_map"]["main"] == "production"

    def test_malformed_key_raises(self) -> None:
        with pytest.raises(EnvOverrideError):
            env_overrides({"SANGE__lowercase__SECTION": "x"})

    def test_deterministic_ordering(self) -> None:
        """Same env → same dict — important for reproducibility."""

        env = {
            "SANGE__AUDIT__VERBOSITY": "minimal",
            "SANGE__TELEMETRY__ENABLED": "false",
            "SANGE__AUDIT__ROTATION_DAYS": "14",
        }
        a = env_overrides(env)
        b = env_overrides(env)
        assert a == b


# --------------------------------------------------------------------------- #
# load_config — precedence chain
# --------------------------------------------------------------------------- #


def _isolated(tmp_path: Path) -> dict:
    """Make load_config invocations hermetic — no real /etc/sange, no ~/.sange."""

    return {
        "system_dir": tmp_path / "_no_system",
        "user_dir": tmp_path / "_no_user",
        "skip_discovery": True,
        "environ": {},
    }


class TestLoadPrecedence:
    def test_no_files_returns_default(self, tmp_path: Path) -> None:
        cfg = load_config(repo_root=tmp_path, **_isolated(tmp_path))
        default = SangeConfig()
        assert cfg.variants.stages == default.variants.stages

    def test_repo_config_toml_loads(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        sd = repo / ".sange"
        sd.mkdir(parents=True)
        (sd / "config.toml").write_text(
            '[audit]\nverbosity = "elevated"\nrotation_days = 30\n',
            encoding="utf-8",
        )
        cfg = load_config(
            repo_root=repo,
            system_dir=tmp_path / "_no_system",
            user_dir=tmp_path / "_no_user",
            skip_discovery=True,
            environ={},
        )
        assert cfg.audit.verbosity == "elevated"
        assert cfg.audit.rotation_days == 30

    def test_repo_config_json_loads(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        sd = repo / ".sange"
        sd.mkdir(parents=True)
        (sd / "config.json").write_text(
            '{"audit": {"verbosity": "minimal"}}',
            encoding="utf-8",
        )
        cfg = load_config(
            repo_root=repo,
            system_dir=tmp_path / "_no_system",
            user_dir=tmp_path / "_no_user",
            skip_discovery=True,
            environ={},
        )
        assert cfg.audit.verbosity == "minimal"

    def test_json_wins_over_toml_at_same_level(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        sd = repo / ".sange"
        sd.mkdir(parents=True)
        (sd / "config.toml").write_text(
            '[audit]\nverbosity = "minimal"\n', encoding="utf-8"
        )
        (sd / "config.json").write_text(
            '{"audit": {"verbosity": "elevated"}}', encoding="utf-8"
        )
        with pytest.warns(UserWarning, match="JSON wins"):
            cfg = load_config(
                repo_root=repo,
                system_dir=tmp_path / "_no_system",
                user_dir=tmp_path / "_no_user",
                skip_discovery=True,
                environ={},
            )
        assert cfg.audit.verbosity == "elevated"

    def test_env_overrides_repo_config(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        sd = repo / ".sange"
        sd.mkdir(parents=True)
        (sd / "config.toml").write_text(
            '[audit]\nverbosity = "elevated"\n', encoding="utf-8"
        )
        cfg = load_config(
            repo_root=repo,
            system_dir=tmp_path / "_no_system",
            user_dir=tmp_path / "_no_user",
            skip_discovery=True,
            environ={"SANGE__AUDIT__VERBOSITY": "minimal"},
        )
        assert cfg.audit.verbosity == "minimal"

    def test_cli_overrides_env(self, tmp_path: Path) -> None:
        cfg = load_config(
            repo_root=tmp_path,
            system_dir=tmp_path / "_no_system",
            user_dir=tmp_path / "_no_user",
            skip_discovery=True,
            environ={"SANGE__AUDIT__VERBOSITY": "minimal"},
            cli_overrides={"audit": {"verbosity": "elevated"}},
        )
        assert cfg.audit.verbosity == "elevated"

    def test_user_dir_overrides_system_dir(self, tmp_path: Path) -> None:
        sys_dir = tmp_path / "etc-sange"
        sys_dir.mkdir()
        (sys_dir / "config.toml").write_text(
            '[audit]\nverbosity = "elevated"\nrotation_days = 90\n',
            encoding="utf-8",
        )
        usr_dir = tmp_path / "user-sange"
        usr_dir.mkdir()
        (usr_dir / "config.toml").write_text(
            '[audit]\nverbosity = "minimal"\n',
            encoding="utf-8",
        )
        cfg = load_config(
            repo_root=tmp_path,
            system_dir=sys_dir,
            user_dir=usr_dir,
            skip_discovery=True,
            environ={},
        )
        # user overrides system on `verbosity`; system's rotation_days survives.
        assert cfg.audit.verbosity == "minimal"
        assert cfg.audit.rotation_days == 90

    def test_invalid_value_raises_config_error(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        sd = repo / ".sange"
        sd.mkdir(parents=True)
        (sd / "config.toml").write_text(
            '[audit]\nverbosity = "not-a-real-level"\n',
            encoding="utf-8",
        )
        with pytest.raises(ConfigError):
            load_config(
                repo_root=repo,
                system_dir=tmp_path / "_no_system",
                user_dir=tmp_path / "_no_user",
                skip_discovery=True,
                environ={},
            )


# --------------------------------------------------------------------------- #
# Repo discovery
# --------------------------------------------------------------------------- #


class TestRepoDiscovery:
    def test_finds_config_in_immediate_parent(self, tmp_path: Path) -> None:
        sd = tmp_path / ".sange"
        sd.mkdir()
        (sd / "config.toml").write_text("[audit]\n", encoding="utf-8")
        found = discover_repo_config(start=tmp_path)
        assert found == sd / "config.toml"

    def test_walks_upward(self, tmp_path: Path) -> None:
        sd = tmp_path / ".sange"
        sd.mkdir()
        (sd / "config.toml").write_text("", encoding="utf-8")
        deep = tmp_path / "a" / "b" / "c"
        deep.mkdir(parents=True)
        found = discover_repo_config(start=deep)
        assert found == sd / "config.toml"

    def test_returns_none_when_nothing(self, tmp_path: Path) -> None:
        deep = tmp_path / "a" / "b"
        deep.mkdir(parents=True)
        # No .sange/ anywhere; eventually walks past tmp_path to /.
        # We can't assert None at the OS root (some hosts have /etc/sange).
        # Instead, assert the walk terminates without hanging:
        result = discover_repo_config(start=deep)
        # Either None or a path outside tmp_path is fine.
        assert result is None or not str(result).startswith(str(tmp_path))


# --------------------------------------------------------------------------- #
# Schema versioning
# --------------------------------------------------------------------------- #


class TestSchemaVersionInLoader:
    def test_current_version_accepted(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        sd = repo / ".sange"
        sd.mkdir(parents=True)
        (sd / "config.toml").write_text(
            '[schema_version]\nmajor = 1\nminor = 0\n',
            encoding="utf-8",
        )
        cfg = load_config(
            repo_root=repo,
            system_dir=tmp_path / "_no_system",
            user_dir=tmp_path / "_no_user",
            skip_discovery=True,
            environ={},
        )
        assert cfg.schema_version.as_tuple() == (1, 0)

    def test_newer_version_refused(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        sd = repo / ".sange"
        sd.mkdir(parents=True)
        (sd / "config.toml").write_text(
            '[schema_version]\nmajor = 99\nminor = 0\n',
            encoding="utf-8",
        )
        with pytest.raises(SchemaVersionError, match="newer"):
            load_config(
                repo_root=repo,
                system_dir=tmp_path / "_no_system",
                user_dir=tmp_path / "_no_user",
                skip_discovery=True,
                environ={},
            )
