"""Tests for docs/release.md — the operator-facing release recipe."""

from __future__ import annotations

from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_RELEASE_MD = _REPO_ROOT / "docs" / "release.md"


@pytest.fixture
def text() -> str:
    return _RELEASE_MD.read_text(encoding="utf-8")


class TestExists:
    def test_file_present(self) -> None:
        # phase-0c.md + release.yml both reference docs/release.md;
        # it must exist.
        assert _RELEASE_MD.is_file()


# --------------------------------------------------------------------------- #
# Required-section coverage
# --------------------------------------------------------------------------- #


class TestStructure:
    @pytest.mark.parametrize("section", [
        "One-time setup",
        "Per-release procedure",
        "Recovery",
        "Pre-release versions",
        "After the release",
    ])
    def test_section_present(self, text: str, section: str) -> None:
        assert section in text


# --------------------------------------------------------------------------- #
# OIDC setup recipe
# --------------------------------------------------------------------------- #


class TestOidcSetup:
    def test_mentions_trusted_publisher(self, text: str) -> None:
        assert "trusted publisher" in text.lower() or "trusted-publisher" in text.lower()

    def test_names_the_pypi_environment(self, text: str) -> None:
        # The release workflow uses an environment named "pypi"; docs
        # must match.
        assert "pypi" in text.lower()

    def test_mentions_id_token_write(self, text: str) -> None:
        assert "id-token" in text

    def test_links_to_pypi_publishing_page(self, text: str) -> None:
        assert "pypi.org/manage/account/publishing" in text or "trusted-publishers" in text


# --------------------------------------------------------------------------- #
# GHCR setup
# --------------------------------------------------------------------------- #


class TestGhcrSetup:
    def test_mentions_ghcr(self, text: str) -> None:
        assert "GHCR" in text or "ghcr.io" in text

    def test_uses_simsange_org(self, text: str) -> None:
        # Per the URL migration discipline.
        assert "simsange/sange" in text
        assert "simtabi/sange" not in text


# --------------------------------------------------------------------------- #
# Per-release procedure — six steps
# --------------------------------------------------------------------------- #


class TestProcedure:
    @pytest.mark.parametrize("step", [
        "Pre-release smoke",
        "Bump the version",
        "Regenerate the changelog",
        "Tag",
        "Push",
        "Verify",
    ])
    def test_step_named(self, text: str, step: str) -> None:
        assert step in text

    def test_mentions_smoke_script(self, text: str) -> None:
        # The pre-release smoke uses scripts/smoke_v01.sh.
        assert "smoke_v01.sh" in text

    def test_mentions_version_file(self, text: str) -> None:
        assert "_version.py" in text

    def test_tag_command_shown(self, text: str) -> None:
        # The exact git command — operator copy-pastes it.
        assert "git tag -a v" in text

    def test_push_origin_main_shown(self, text: str) -> None:
        assert "git push origin main" in text

    def test_push_tag_shown(self, text: str) -> None:
        assert "git push origin v" in text


# --------------------------------------------------------------------------- #
# Recovery section
# --------------------------------------------------------------------------- #


class TestRecovery:
    def test_mentions_post_release_fix(self, text: str) -> None:
        # PEP 440 .postN is the canonical fix-forward.
        assert "v0.1.0.post1" in text or ".postN" in text

    def test_mentions_pep_440(self, text: str) -> None:
        assert "PEP 440" in text or "pep-0440" in text

    def test_warns_against_force_push_pushed_tag(self, text: str) -> None:
        assert "immutable" in text.lower() or "force" in text.lower()

    def test_delete_local_tag_recipe(self, text: str) -> None:
        # The not-yet-pushed case: git tag -d is safe + documented.
        assert "git tag -d" in text


# --------------------------------------------------------------------------- #
# Pre-release suffixes
# --------------------------------------------------------------------------- #


class TestPreRelease:
    def test_lists_pre_release_suffixes(self, text: str) -> None:
        # PEP 440: alpha / beta / rc.
        for suffix in ("rc", "b", "a"):
            assert f"-{suffix}1" in text


# --------------------------------------------------------------------------- #
# Cross-references — every linked artifact actually exists
# --------------------------------------------------------------------------- #


class TestCrossReferences:
    @pytest.mark.parametrize("artifact", [
        ".github/workflows/release.yml",
        "tools/generators/changelog_from_commits.py",
        "docs/adr/0033-multi-arch-docker.md",
    ])
    def test_referenced_artifact_exists(self, text: str, artifact: str) -> None:
        # The doc mentions these paths; verify they're actual files
        # in the repo so the doc doesn't go stale.
        assert artifact in text
        assert (_REPO_ROOT / artifact).is_file(), (
            f"docs/release.md references {artifact} but it doesn't exist"
        )


# --------------------------------------------------------------------------- #
# Workflow ↔ doc consistency — the doc names what release.yml does
# --------------------------------------------------------------------------- #


class TestWorkflowConsistency:
    def test_doc_names_workflow_jobs(self, text: str) -> None:
        """release.yml has jobs named build / pypi / docker / release.
        The doc's Recovery section refers to them by name."""

        for job in ("build", "pypi", "docker", "release"):
            # Match `build` (lowercase) since the workflow file is
            # canonical; docs reference the names verbatim.
            assert f"`{job}`" in text, f"job name `{job}` missing"

    def test_doc_mentions_release_yml_path(self, text: str) -> None:
        assert ".github/workflows/release.yml" in text
