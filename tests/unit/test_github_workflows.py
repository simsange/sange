"""Tests for `.github/workflows/*.yml` + `.github/dependabot.yml`.

Static-analysis tests asserting structural / content invariants that
the §16 release engineering + ADR-033 multi-arch + global CLAUDE.md
conventions require. These tests do NOT invoke a workflow runner —
that's GitHub Actions's job.
"""

from __future__ import annotations

from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_CI = _REPO_ROOT / ".github" / "workflows" / "ci.yml"
_RELEASE = _REPO_ROOT / ".github" / "workflows" / "release.yml"
_DEPENDABOT = _REPO_ROOT / ".github" / "dependabot.yml"


# --------------------------------------------------------------------------- #
# Files exist
# --------------------------------------------------------------------------- #


class TestFilesExist:
    def test_ci_exists(self) -> None:
        assert _CI.is_file()

    def test_release_exists(self) -> None:
        assert _RELEASE.is_file()

    def test_dependabot_exists(self) -> None:
        assert _DEPENDABOT.is_file()


# --------------------------------------------------------------------------- #
# CI workflow
# --------------------------------------------------------------------------- #


@pytest.fixture
def ci_yaml() -> dict:
    try:
        import yaml
    except ImportError:
        pytest.skip("PyYAML not installed")
    return yaml.safe_load(_CI.read_text(encoding="utf-8"))


class TestCIWorkflow:
    def test_parses(self, ci_yaml: dict) -> None:
        assert isinstance(ci_yaml, dict)

    def test_triggered_on_push_and_pr(self, ci_yaml: dict) -> None:
        # YAML's `on` key gets parsed to True by PyYAML's safe_load
        # because `on` is a YAML 1.1 boolean. Use `or` to handle both.
        on = ci_yaml.get("on") or ci_yaml.get(True)
        assert on is not None
        assert "push" in on
        assert "pull_request" in on

    def test_has_test_job(self, ci_yaml: dict) -> None:
        assert "test" in ci_yaml["jobs"]

    def test_matrix_covers_python_versions(self, ci_yaml: dict) -> None:
        matrix = ci_yaml["jobs"]["test"]["strategy"]["matrix"]
        # The matrix must include 3.12 (project floor per
        # pyproject.toml::requires-python) and at least one newer
        # version. PyYAML parses "3.10" → "3.10" (string).
        versions = [str(v) for v in matrix["python"]]
        assert "3.12" in versions, "matrix must include the project floor (3.12)"
        # At least one newer version covered — 3.13+ today.
        assert len(versions) >= 2, "matrix must test at least 2 versions"

    def test_matrix_covers_native_arm(self, ci_yaml: dict) -> None:
        """ADR-033: native ARM runner required, not QEMU emulation."""

        matrix = ci_yaml["jobs"]["test"]["strategy"]["matrix"]
        runners = matrix["os"]
        # GitHub provides ubuntu-24.04-arm for native ARM.
        assert any("arm" in r for r in runners), (
            "ADR-033 requires a native ARM runner in the matrix"
        )

    def test_has_lint_job(self, ci_yaml: dict) -> None:
        assert "lint" in ci_yaml["jobs"]
        # ruff is the pinned linter per ADR-019.
        steps = ci_yaml["jobs"]["lint"]["steps"]
        joined = " ".join(s.get("run", "") for s in steps)
        assert "ruff" in joined

    def test_has_typecheck_job(self, ci_yaml: dict) -> None:
        assert "typecheck" in ci_yaml["jobs"]
        steps = ci_yaml["jobs"]["typecheck"]["steps"]
        joined = " ".join(s.get("run", "") for s in steps)
        assert "mypy" in joined

    def test_has_generators_verify_job(self, ci_yaml: dict) -> None:
        assert "generators" in ci_yaml["jobs"]
        steps = ci_yaml["jobs"]["generators"]["steps"]
        joined = " ".join(s.get("run", "") for s in steps)
        assert "verify_session_log" in joined
        assert "verify_generated" in joined

    def test_has_build_job(self, ci_yaml: dict) -> None:
        assert "build" in ci_yaml["jobs"]

    def test_has_docker_sanity_job(self, ci_yaml: dict) -> None:
        # Single-arch sanity build per the Dockerfile spec.
        assert "docker" in ci_yaml["jobs"]


# --------------------------------------------------------------------------- #
# Release workflow
# --------------------------------------------------------------------------- #


@pytest.fixture
def release_yaml() -> dict:
    try:
        import yaml
    except ImportError:
        pytest.skip("PyYAML not installed")
    return yaml.safe_load(_RELEASE.read_text(encoding="utf-8"))


class TestReleaseWorkflow:
    def test_parses(self, release_yaml: dict) -> None:
        assert isinstance(release_yaml, dict)

    def test_triggered_on_tag_only(self, release_yaml: dict) -> None:
        on = release_yaml.get("on") or release_yaml.get(True)
        # Must trigger only on tags matching v*.*.* (no branch trigger).
        assert "push" in on
        push = on["push"]
        assert "tags" in push
        assert any("v" in str(t) for t in push["tags"])
        # And NOT on branches (release must be tag-driven).
        assert "branches" not in push

    def test_has_oidc_permission(self, release_yaml: dict) -> None:
        """Trusted-publisher needs id-token: write per PyPI's spec."""

        perms = release_yaml["permissions"]
        assert perms.get("id-token") == "write"

    def test_has_pypi_publish_job(self, release_yaml: dict) -> None:
        assert "pypi" in release_yaml["jobs"]
        pypi_job = release_yaml["jobs"]["pypi"]
        # Uses the official pypa trusted-publisher action.
        steps = pypi_job["steps"]
        joined = " ".join(s.get("uses", "") for s in steps)
        assert "pypa/gh-action-pypi-publish" in joined

    def test_pypi_uses_pypi_environment(self, release_yaml: dict) -> None:
        # OIDC trusted-publisher records require a specific environment.
        pypi_job = release_yaml["jobs"]["pypi"]
        env = pypi_job["environment"]
        if isinstance(env, str):
            assert env == "pypi"
        else:
            assert env["name"] == "pypi"

    def test_has_docker_multi_arch_job(self, release_yaml: dict) -> None:
        """Per ADR-033: release builds linux/amd64 + linux/arm64."""

        assert "docker" in release_yaml["jobs"]
        docker_job = release_yaml["jobs"]["docker"]
        steps = docker_job["steps"]
        # Build step must declare both platforms.
        for step in steps:
            with_ = step.get("with") or {}
            platforms = with_.get("platforms", "")
            if "linux/amd64" in platforms and "linux/arm64" in platforms:
                return
        pytest.fail("no buildx step with linux/amd64,linux/arm64")

    def test_has_github_release_job(self, release_yaml: dict) -> None:
        assert "release" in release_yaml["jobs"]
        # gh release create is the canonical tag → release path.
        steps = release_yaml["jobs"]["release"]["steps"]
        joined = " ".join(s.get("run", "") for s in steps)
        assert "gh release create" in joined

    def test_release_uses_changelog(self, release_yaml: dict) -> None:
        # Per T-G-013: docs/CHANGELOG.md is the source for release notes.
        steps = release_yaml["jobs"]["release"]["steps"]
        joined = " ".join(s.get("run", "") for s in steps)
        assert "CHANGELOG.md" in joined

    def test_smoke_install_wheel(self, release_yaml: dict) -> None:
        # Build job must smoke-install the wheel before handing off to
        # the PyPI publish step (per docs/release.md).
        build_job = release_yaml["jobs"]["build"]
        steps = build_job["steps"]
        joined = " ".join(s.get("run", "") for s in steps)
        assert "sange --version" in joined


# --------------------------------------------------------------------------- #
# Dependabot
# --------------------------------------------------------------------------- #


@pytest.fixture
def dependabot_yaml() -> dict:
    try:
        import yaml
    except ImportError:
        pytest.skip("PyYAML not installed")
    return yaml.safe_load(_DEPENDABOT.read_text(encoding="utf-8"))


class TestDependabot:
    def test_parses(self, dependabot_yaml: dict) -> None:
        assert isinstance(dependabot_yaml, dict)

    def test_version_2(self, dependabot_yaml: dict) -> None:
        assert dependabot_yaml["version"] == 2

    def test_pip_ecosystem(self, dependabot_yaml: dict) -> None:
        ecosystems = {u["package-ecosystem"] for u in dependabot_yaml["updates"]}
        assert "pip" in ecosystems

    def test_github_actions_ecosystem(self, dependabot_yaml: dict) -> None:
        ecosystems = {u["package-ecosystem"] for u in dependabot_yaml["updates"]}
        assert "github-actions" in ecosystems

    def test_docker_ecosystem(self, dependabot_yaml: dict) -> None:
        ecosystems = {u["package-ecosystem"] for u in dependabot_yaml["updates"]}
        assert "docker" in ecosystems

    def test_monday_06_00_america_new_york(self, dependabot_yaml: dict) -> None:
        """Per ~/.claude/CLAUDE.md: weekly Monday 06:00 America/New_York."""

        for update in dependabot_yaml["updates"]:
            schedule = update["schedule"]
            assert schedule["interval"] == "weekly"
            assert schedule["day"] == "monday"
            assert schedule["time"] == "06:00"
            assert schedule["timezone"] == "America/New_York"


# --------------------------------------------------------------------------- #
# Cross-workflow invariants
# --------------------------------------------------------------------------- #


class TestCrossWorkflow:
    def test_no_no_verify(self) -> None:
        """Per CLAUDE.md: never use --no-verify in CI (skips hooks)."""

        for f in (_CI, _RELEASE):
            text = f.read_text(encoding="utf-8")
            assert "--no-verify" not in text, (
                f"{f.name} uses --no-verify; forbidden per CLAUDE.md"
            )

    def test_no_secrets_baked_into_workflow(self) -> None:
        """Sanity-check: tokens / keys are never hard-coded in YAML.
        Real secrets go through `${{ secrets.X }}` or OIDC."""

        forbidden = ("ghp_", "sk-", "AKIA", "BEGIN PRIVATE KEY")
        for f in (_CI, _RELEASE, _DEPENDABOT):
            text = f.read_text(encoding="utf-8")
            for pattern in forbidden:
                assert pattern not in text, (
                    f"{f.name} contains secret-like literal {pattern!r}"
                )
