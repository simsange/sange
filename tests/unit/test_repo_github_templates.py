"""Tests for this repo's `.github/` issue + PR templates.

Per `~/.claude/CLAUDE.md` "Required files in every project" — every
repo gets its own copy of ISSUE_TEMPLATE/* + PULL_REQUEST_TEMPLATE.md
(in addition to the org-level defaults under simsange/.github).

These tests assert presence + byte-equality with the org-github seed
(the source of truth) so the two copies don't drift.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_REPO_GH = _REPO_ROOT / ".github"
_ORG_GH = _REPO_ROOT / "org-github" / ".github"


# --------------------------------------------------------------------------- #
# Presence
# --------------------------------------------------------------------------- #


class TestPresence:
    @pytest.mark.parametrize("path", [
        ".github/ISSUE_TEMPLATE/bug_report.yml",
        ".github/ISSUE_TEMPLATE/feature_request.yml",
        ".github/ISSUE_TEMPLATE/config.yml",
        ".github/PULL_REQUEST_TEMPLATE.md",
    ])
    def test_required_file(self, path: str) -> None:
        assert (_REPO_ROOT / path).is_file(), f"missing {path}"


# --------------------------------------------------------------------------- #
# Byte-equality with org-github seed (the source of truth)
# --------------------------------------------------------------------------- #


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class TestSyncWithOrgSeed:
    """Per the disk-to-disk-copy convention: this repo's per-project
    templates must be byte-equal to the org-github seed they were
    copied from. Drift is fixed via the cp recipe in the test
    failure message."""

    @pytest.mark.parametrize("relpath", [
        "ISSUE_TEMPLATE/bug_report.yml",
        "ISSUE_TEMPLATE/feature_request.yml",
        "ISSUE_TEMPLATE/config.yml",
        "PULL_REQUEST_TEMPLATE.md",
    ])
    def test_byte_equal(self, relpath: str) -> None:
        repo = _REPO_GH / relpath
        org = _ORG_GH / relpath
        assert org.is_file(), f"org-github seed missing {relpath}"
        repo_sha = _sha256(repo)
        org_sha = _sha256(org)
        assert repo_sha == org_sha, (
            f"{relpath} drifted between .github/ and org-github/.github/. "
            f"Re-sync: `cp org-github/.github/{relpath} .github/{relpath}` "
            f"(or the reverse if .github/ is the corrected version)."
        )


# --------------------------------------------------------------------------- #
# YAML parses (issue templates are GitHub-form YAML)
# --------------------------------------------------------------------------- #


@pytest.fixture
def yaml_module():
    try:
        import yaml
    except ImportError:
        pytest.skip("PyYAML not installed")
    return yaml


class TestYamlIntegrity:
    def test_bug_report_parses(self, yaml_module) -> None:
        text = (_REPO_GH / "ISSUE_TEMPLATE" / "bug_report.yml").read_text(
            encoding="utf-8"
        )
        parsed = yaml_module.safe_load(text)
        assert isinstance(parsed, dict)
        assert "name" in parsed
        assert "body" in parsed

    def test_feature_request_parses(self, yaml_module) -> None:
        text = (_REPO_GH / "ISSUE_TEMPLATE" / "feature_request.yml").read_text(
            encoding="utf-8"
        )
        parsed = yaml_module.safe_load(text)
        assert isinstance(parsed, dict)
        assert "name" in parsed
        assert "body" in parsed

    def test_config_parses(self, yaml_module) -> None:
        text = (_REPO_GH / "ISSUE_TEMPLATE" / "config.yml").read_text(
            encoding="utf-8"
        )
        parsed = yaml_module.safe_load(text)
        assert isinstance(parsed, dict)
        assert parsed["blank_issues_enabled"] is False


# --------------------------------------------------------------------------- #
# PR template content invariants
# --------------------------------------------------------------------------- #


class TestPRTemplate:
    def test_has_summary(self) -> None:
        text = (_REPO_GH / "PULL_REQUEST_TEMPLATE.md").read_text(encoding="utf-8")
        assert "## Summary" in text

    def test_has_breaking_changes_section(self) -> None:
        text = (_REPO_GH / "PULL_REQUEST_TEMPLATE.md").read_text(encoding="utf-8")
        assert "Breaking" in text

    def test_has_signoff_reference(self) -> None:
        text = (_REPO_GH / "PULL_REQUEST_TEMPLATE.md").read_text(encoding="utf-8")
        assert "Sign-off" in text or "git commit -s" in text
