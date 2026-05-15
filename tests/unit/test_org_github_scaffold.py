"""Tests for the `org-github/` scaffold — seed of `sangedev/.github`.

Static-analysis tests asserting structural invariants. The scaffold
provides org-wide community-health-file defaults for every repo in
the `sangedev` GitHub org.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest


_REPO_ROOT = Path(__file__).resolve().parents[2]
_ORG = _REPO_ROOT / "org-github"


# --------------------------------------------------------------------------- #
# File existence
# --------------------------------------------------------------------------- #


class TestStructure:
    def test_dir_exists(self) -> None:
        assert _ORG.is_dir()

    @pytest.mark.parametrize("path", [
        "README.md",
        "LICENSE",
        "CODE_OF_CONDUCT.md",
        "SECURITY.md",
        "CONTRIBUTING.md",
        "SUPPORT.md",
        "profile/README.md",
        ".github/ISSUE_TEMPLATE/bug_report.yml",
        ".github/ISSUE_TEMPLATE/feature_request.yml",
        ".github/ISSUE_TEMPLATE/config.yml",
        ".github/PULL_REQUEST_TEMPLATE.md",
    ])
    def test_required_file(self, path: str) -> None:
        assert (_ORG / path).is_file(), f"missing {path}"


# --------------------------------------------------------------------------- #
# Canonical-source files — byte-equal to the main repo (disk-to-disk copy)
# --------------------------------------------------------------------------- #


class TestCanonicalSources:
    """Per CLAUDE.md "canonical / upstream files: disk-to-disk only" —
    CODE_OF_CONDUCT.md / SECURITY.md / LICENSE should be byte-equal
    to the main repo's versions. They are NOT paraphrased."""

    def _sha256(self, path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def test_code_of_conduct_byte_equal(self) -> None:
        org = self._sha256(_ORG / "CODE_OF_CONDUCT.md")
        main = self._sha256(_REPO_ROOT / "CODE_OF_CONDUCT.md")
        assert org == main, (
            "org-github/CODE_OF_CONDUCT.md drifted from the main repo's. "
            "Re-cp: `cp CODE_OF_CONDUCT.md org-github/CODE_OF_CONDUCT.md`."
        )

    def test_security_policy_byte_equal(self) -> None:
        org = self._sha256(_ORG / "SECURITY.md")
        main = self._sha256(_REPO_ROOT / "SECURITY.md")
        assert org == main

    def test_license_byte_equal(self) -> None:
        org = self._sha256(_ORG / "LICENSE")
        main = self._sha256(_REPO_ROOT / "LICENSE")
        assert org == main


# --------------------------------------------------------------------------- #
# Profile README — the org's GitHub landing card
# --------------------------------------------------------------------------- #


class TestProfileReadme:
    def test_lists_known_repos(self) -> None:
        text = (_ORG / "profile" / "README.md").read_text(encoding="utf-8")
        # Each repo in the table must be linked.
        assert "github.com/sangedev/sange" in text
        assert "github.com/sangedev/documentation" in text
        assert "github.com/sangedev/.github" in text

    def test_includes_quick_start_command(self) -> None:
        text = (_ORG / "profile" / "README.md").read_text(encoding="utf-8")
        # Quick-start shows the v0.1 happy path.
        assert "pip install sange" in text
        assert "sange commit" in text

    def test_mentions_apache_license(self) -> None:
        text = (_ORG / "profile" / "README.md").read_text(encoding="utf-8")
        assert "Apache" in text

    def test_no_simtabi_sange_url(self) -> None:
        # URL migration discipline — same as documentation/.
        text = (_ORG / "profile" / "README.md").read_text(encoding="utf-8")
        assert "github.com/simtabi/sange" not in text


# --------------------------------------------------------------------------- #
# CONTRIBUTING.md — org-wide vs per-repo
# --------------------------------------------------------------------------- #


class TestContributing:
    def test_references_dco(self) -> None:
        text = (_ORG / "CONTRIBUTING.md").read_text(encoding="utf-8")
        # Sign-off via DCO is the canonical contributor-attestation
        # for Apache-2.0 OSS projects.
        assert "Developer Certificate of Origin" in text or "DCO" in text

    def test_mentions_conventional_commits(self) -> None:
        text = (_ORG / "CONTRIBUTING.md").read_text(encoding="utf-8")
        assert "Conventional Commits" in text

    def test_links_to_security(self) -> None:
        text = (_ORG / "CONTRIBUTING.md").read_text(encoding="utf-8")
        assert "SECURITY.md" in text

    def test_links_to_coc(self) -> None:
        text = (_ORG / "CONTRIBUTING.md").read_text(encoding="utf-8")
        assert "CODE_OF_CONDUCT.md" in text


# --------------------------------------------------------------------------- #
# SUPPORT.md — routing table
# --------------------------------------------------------------------------- #


class TestSupport:
    def test_routes_security_separately(self) -> None:
        text = (_ORG / "SUPPORT.md").read_text(encoding="utf-8")
        # Security MUST NOT be a public issue.
        assert "SECURITY.md" in text
        assert "NOT a public issue" in text

    def test_directs_questions_to_discussions(self) -> None:
        text = (_ORG / "SUPPORT.md").read_text(encoding="utf-8")
        assert "Discussions" in text


# --------------------------------------------------------------------------- #
# Issue templates — bug + feature + config
# --------------------------------------------------------------------------- #


@pytest.fixture
def bug_yaml() -> dict:
    try:
        import yaml
    except ImportError:
        pytest.skip("PyYAML not installed")
    return yaml.safe_load(
        (_ORG / ".github" / "ISSUE_TEMPLATE" / "bug_report.yml").read_text(
            encoding="utf-8"
        )
    )


@pytest.fixture
def feat_yaml() -> dict:
    try:
        import yaml
    except ImportError:
        pytest.skip("PyYAML not installed")
    return yaml.safe_load(
        (_ORG / ".github" / "ISSUE_TEMPLATE" / "feature_request.yml").read_text(
            encoding="utf-8"
        )
    )


@pytest.fixture
def config_yaml() -> dict:
    try:
        import yaml
    except ImportError:
        pytest.skip("PyYAML not installed")
    return yaml.safe_load(
        (_ORG / ".github" / "ISSUE_TEMPLATE" / "config.yml").read_text(
            encoding="utf-8"
        )
    )


class TestBugReportTemplate:
    def test_parses(self, bug_yaml: dict) -> None:
        assert isinstance(bug_yaml, dict)

    def test_has_bug_label(self, bug_yaml: dict) -> None:
        assert "bug" in bug_yaml.get("labels", [])

    def test_requires_version(self, bug_yaml: dict) -> None:
        # Field id "version" must be present + required.
        version_field = next(
            (f for f in bug_yaml["body"] if f.get("id") == "version"), None
        )
        assert version_field is not None
        assert version_field["validations"]["required"] is True

    def test_warns_off_security(self, bug_yaml: dict) -> None:
        # The intro markdown points security reports elsewhere.
        intro = next(
            (f for f in bug_yaml["body"] if f["type"] == "markdown"), None
        )
        assert intro is not None
        assert "SECURITY.md" in intro["attributes"]["value"]


class TestFeatureRequestTemplate:
    def test_parses(self, feat_yaml: dict) -> None:
        assert isinstance(feat_yaml, dict)

    def test_has_enhancement_label(self, feat_yaml: dict) -> None:
        assert "enhancement" in feat_yaml.get("labels", [])

    def test_directs_to_discussions_first(self, feat_yaml: dict) -> None:
        intro = next(
            (f for f in feat_yaml["body"] if f["type"] == "markdown"), None
        )
        assert intro is not None
        assert "Discussions" in intro["attributes"]["value"]


class TestIssueConfig:
    def test_blank_issues_disabled(self, config_yaml: dict) -> None:
        # Force users through a template — keeps triage manageable.
        assert config_yaml["blank_issues_enabled"] is False

    def test_contact_link_to_security(self, config_yaml: dict) -> None:
        links = config_yaml["contact_links"]
        urls = [l["url"] for l in links]
        assert any("SECURITY.md" in u for u in urls)

    def test_contact_link_to_discussions(self, config_yaml: dict) -> None:
        links = config_yaml["contact_links"]
        urls = [l["url"] for l in links]
        assert any("discussions" in u.lower() for u in urls)


# --------------------------------------------------------------------------- #
# PR template
# --------------------------------------------------------------------------- #


class TestPRTemplate:
    def test_has_summary_section(self) -> None:
        text = (_ORG / ".github" / "PULL_REQUEST_TEMPLATE.md").read_text(
            encoding="utf-8"
        )
        assert "## Summary" in text

    def test_has_breaking_changes_section(self) -> None:
        text = (_ORG / ".github" / "PULL_REQUEST_TEMPLATE.md").read_text(
            encoding="utf-8"
        )
        assert "Breaking" in text

    def test_mentions_signoff(self) -> None:
        text = (_ORG / ".github" / "PULL_REQUEST_TEMPLATE.md").read_text(
            encoding="utf-8"
        )
        assert "Sign-off" in text or "git commit -s" in text


# --------------------------------------------------------------------------- #
# README — migration plan
# --------------------------------------------------------------------------- #


class TestRootReadme:
    def test_explains_migration(self) -> None:
        text = (_ORG / "README.md").read_text(encoding="utf-8")
        assert "sangedev/.github" in text
        assert "Migration" in text or "migration" in text

    def test_lists_files_in_tree(self) -> None:
        text = (_ORG / "README.md").read_text(encoding="utf-8")
        # The tree listing in the README must match the actual layout.
        for f in (
            "CODE_OF_CONDUCT.md", "SECURITY.md", "CONTRIBUTING.md",
            "SUPPORT.md", "profile/", "ISSUE_TEMPLATE/",
            "PULL_REQUEST_TEMPLATE.md",
        ):
            assert f in text


# --------------------------------------------------------------------------- #
# No simtabi/sange URLs anywhere
# --------------------------------------------------------------------------- #


class TestUrlDiscipline:
    def test_no_old_org_url(self) -> None:
        """Regression test pinning the URL migration for the org-github/
        seed too."""

        for f in _ORG.rglob("*"):
            if f.is_file() and f.suffix in (".md", ".yml", ".yaml"):
                text = f.read_text(encoding="utf-8")
                assert "github.com/simtabi/sange" not in text, (
                    f"{f.relative_to(_ORG)} still references the old org URL"
                )
