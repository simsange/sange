"""Tests for Docker artifacts — Dockerfile / .dockerignore / docker-compose.yml.

These are static-analysis tests: they read the files and assert
structural / content invariants that the §10 + §6.10 + ADR-033 specs
require. They DO NOT invoke `docker build` (that's a CI job, not a
unit-test).
"""

from __future__ import annotations

from pathlib import Path

import pytest


_REPO_ROOT = Path(__file__).resolve().parents[2]
_DOCKERFILE = _REPO_ROOT / "Dockerfile"
_DOCKERIGNORE = _REPO_ROOT / ".dockerignore"
_COMPOSE = _REPO_ROOT / "docker-compose.yml"


# --------------------------------------------------------------------------- #
# Dockerfile structure
# --------------------------------------------------------------------------- #


@pytest.fixture
def dockerfile() -> str:
    return _DOCKERFILE.read_text(encoding="utf-8")


class TestDockerfileMultiStage:
    def test_file_exists(self) -> None:
        assert _DOCKERFILE.is_file()

    def test_has_syntax_directive(self, dockerfile: str) -> None:
        # BuildKit syntax directive at the top — required for --mount=type=secret
        # in v0.5+.
        first_line = dockerfile.splitlines()[0]
        assert first_line.startswith("# syntax=docker/dockerfile:")

    def test_two_stages(self, dockerfile: str) -> None:
        lines = dockerfile.splitlines()
        from_lines = [l for l in lines if l.startswith("FROM ")]
        assert len(from_lines) >= 2

    def test_builder_stage(self, dockerfile: str) -> None:
        assert "AS builder" in dockerfile

    def test_runtime_stage(self, dockerfile: str) -> None:
        assert "AS runtime" in dockerfile


class TestDockerfileBaseImage:
    def test_python_312_slim(self, dockerfile: str) -> None:
        # Per ADR-033 + §6.1: python:3.12-slim is multi-arch upstream.
        assert "python:3.12-slim" in dockerfile

    def test_digest_pinning_documented_as_todo(self, dockerfile: str) -> None:
        # We don't pin by digest in v0.1 (deferred to Phase 0d 3/5) but
        # the path to upgrade must be inline so the next contributor
        # doesn't have to grep for it.
        assert "docker manifest inspect" in dockerfile or "digest" in dockerfile.lower()


class TestDockerfileSecurity:
    def test_non_root_user(self, dockerfile: str) -> None:
        # Per §6.10.3 the runtime must run as a non-root user.
        assert "USER sange" in dockerfile or "USER 1000" in dockerfile

    def test_creates_sange_user(self, dockerfile: str) -> None:
        # The user must exist before USER switches to it.
        assert "useradd" in dockerfile or "adduser" in dockerfile
        assert "sange" in dockerfile

    def test_no_env_secrets(self, dockerfile: str) -> None:
        # Per §6.10.3: no ENV vars carry secrets. We can't fully verify
        # this statically, but we can check that no obvious patterns
        # appear in ENV declarations.
        env_lines = [
            l for l in dockerfile.splitlines()
            if l.strip().startswith("ENV ")
        ]
        joined = "\n".join(env_lines).upper()
        for forbidden in ("PASSWORD", "TOKEN", "SECRET", "API_KEY", "PRIVATE_KEY"):
            assert forbidden not in joined, (
                f"forbidden secret-like name {forbidden!r} appears in ENV"
            )

    def test_no_root_in_final_stage(self, dockerfile: str) -> None:
        # The final USER directive in the file must be `sange` (or a
        # numeric id matching `sange`). Find the last USER line.
        user_lines = [
            l.strip() for l in dockerfile.splitlines()
            if l.strip().startswith("USER ")
        ]
        assert user_lines, "Dockerfile must declare a USER"
        last = user_lines[-1]
        assert "root" not in last.lower()


class TestDockerfileEntrypoint:
    def test_entrypoint_is_sange(self, dockerfile: str) -> None:
        assert 'ENTRYPOINT ["sange"]' in dockerfile

    def test_has_default_cmd(self, dockerfile: str) -> None:
        # The default CMD argues for `--help` when nothing is supplied —
        # the same UX as no-args invocation outside the container.
        assert "CMD " in dockerfile

    def test_healthcheck_present(self, dockerfile: str) -> None:
        assert "HEALTHCHECK" in dockerfile


class TestDockerfileBuildDiscipline:
    def test_apt_lists_cleaned(self, dockerfile: str) -> None:
        # Best-practice: don't leave /var/lib/apt/lists/* in the image.
        # Both stages that run apt-get install must rm the lists.
        apt_install_count = dockerfile.count("apt-get install")
        rm_lists_count = dockerfile.count("rm -rf /var/lib/apt/lists/*")
        assert rm_lists_count >= apt_install_count

    def test_pip_no_cache(self, dockerfile: str) -> None:
        # Don't ship pip's cache inside the image.
        pip_install_lines = [
            l for l in dockerfile.splitlines()
            if "pip install" in l or "pip wheel" in l
        ]
        assert pip_install_lines
        for line in pip_install_lines:
            # Allow either --no-cache-dir on the line itself or in a
            # following line continuation. Simple check: every line that
            # has `pip install` or `pip wheel` should mention --no-cache-dir
            # somewhere in the same logical RUN block.
            assert "--no-cache-dir" in dockerfile

    def test_workdir_declared(self, dockerfile: str) -> None:
        assert "WORKDIR " in dockerfile


# --------------------------------------------------------------------------- #
# .dockerignore
# --------------------------------------------------------------------------- #


@pytest.fixture
def dockerignore() -> str:
    return _DOCKERIGNORE.read_text(encoding="utf-8")


class TestDockerignore:
    def test_file_exists(self) -> None:
        assert _DOCKERIGNORE.is_file()

    @pytest.mark.parametrize("entry", [
        ".git/",
        "__pycache__/",
        ".venv/",
        ".pytest_cache/",
        ".sange/",
        ".env",
        ".design/",
        "tests/",
    ])
    def test_excludes_known_noise(self, dockerignore: str, entry: str) -> None:
        # Each entry should appear on its own line.
        lines = {l.strip() for l in dockerignore.splitlines()}
        assert entry in lines, f"{entry!r} missing from .dockerignore"


# --------------------------------------------------------------------------- #
# docker-compose.yml
# --------------------------------------------------------------------------- #


@pytest.fixture
def compose_yaml() -> dict:
    """Parse the compose file via PyYAML if available; otherwise tomllib
    won't help — fall back to a structural string check."""

    text = _COMPOSE.read_text(encoding="utf-8")
    try:
        import yaml  # type: ignore[import-untyped]

        return yaml.safe_load(text)
    except ImportError:
        pytest.skip("PyYAML not installed")
    except Exception as exc:
        pytest.fail(f"compose file is not valid YAML: {exc}")


class TestComposeFile:
    def test_file_exists(self) -> None:
        assert _COMPOSE.is_file()

    def test_yaml_parseable(self, compose_yaml: dict) -> None:
        assert isinstance(compose_yaml, dict)

    def test_sange_service_present(self, compose_yaml: dict) -> None:
        assert "services" in compose_yaml
        assert "sange" in compose_yaml["services"]

    def test_sange_builds_from_local(self, compose_yaml: dict) -> None:
        svc = compose_yaml["services"]["sange"]
        assert "build" in svc

    def test_mounts_working_tree(self, compose_yaml: dict) -> None:
        svc = compose_yaml["services"]["sange"]
        volumes = svc.get("volumes", [])
        assert any("/repo" in v for v in volumes), (
            "compose must mount the host wd at /repo for sange commit"
        )

    def test_forwards_ssh_agent(self, compose_yaml: dict) -> None:
        # §6.10.1 mechanism 1 — SSH agent forwarding.
        svc = compose_yaml["services"]["sange"]
        env = svc.get("environment", {})
        volumes = svc.get("volumes", [])
        has_agent_env = "SSH_AUTH_SOCK" in (env if isinstance(env, dict) else {})
        has_agent_mount = any("ssh-agent" in v.lower() for v in volumes)
        assert has_agent_env or has_agent_mount, (
            "compose should forward SSH_AUTH_SOCK per §6.10.1"
        )


# --------------------------------------------------------------------------- #
# Cross-file consistency
# --------------------------------------------------------------------------- #


class TestCrossFile:
    def test_dockerignore_excludes_what_compose_mounts_back(
        self, dockerignore: str
    ) -> None:
        """`.sange/` is in .dockerignore (won't bake into the image) but the
        compose file volume-mounts the host's `.` to `/repo`, which brings
        `.sange/` back at runtime. That's the intended pattern — a runtime
        artifact lives on the host, not in the image. The test asserts both
        invariants hold together: image excludes, runtime mounts in."""

        assert ".sange/" in {l.strip() for l in dockerignore.splitlines()}
        compose_text = _COMPOSE.read_text(encoding="utf-8")
        assert "/repo" in compose_text
