"""Tests for the `documentation/` MkDocs scaffold.

Static-analysis tests asserting structural invariants. No `mkdocs
build` invocation — that's a CI / docs-site-deploy concern.
"""

from __future__ import annotations

from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_DOC = _REPO_ROOT / "documentation"
_MKDOCS = _DOC / "mkdocs.yml"
_REQ = _DOC / "requirements.txt"
_README = _DOC / "README.md"
_DOCS = _DOC / "docs"


# --------------------------------------------------------------------------- #
# File existence
# --------------------------------------------------------------------------- #


class TestStructure:
    def test_documentation_dir_exists(self) -> None:
        assert _DOC.is_dir()

    def test_mkdocs_yml(self) -> None:
        assert _MKDOCS.is_file()

    def test_requirements_txt(self) -> None:
        assert _REQ.is_file()

    def test_readme(self) -> None:
        assert _README.is_file()

    def test_docs_dir(self) -> None:
        assert _DOCS.is_dir()


# --------------------------------------------------------------------------- #
# mkdocs.yml
# --------------------------------------------------------------------------- #


@pytest.fixture
def mkdocs_yaml() -> dict:
    try:
        import yaml
    except ImportError:
        pytest.skip("PyYAML not installed")
    return yaml.safe_load(_MKDOCS.read_text(encoding="utf-8"))


class TestMkdocsConfig:
    def test_parses(self, mkdocs_yaml: dict) -> None:
        assert isinstance(mkdocs_yaml, dict)

    def test_site_name(self, mkdocs_yaml: dict) -> None:
        assert mkdocs_yaml["site_name"] == "Sange"

    def test_repo_url_points_at_sangedev(self, mkdocs_yaml: dict) -> None:
        # Per the URL migration from S-003-T-42, repo URL must point
        # at the sangedev org, not simtabi.
        assert "sangedev/sange" in mkdocs_yaml["repo_url"]
        assert "simtabi/sange" not in mkdocs_yaml["repo_url"]

    def test_canonical_site_url(self, mkdocs_yaml: dict) -> None:
        # The published site goes to the OSS portal subdomain.
        assert mkdocs_yaml["site_url"] == "https://opensource.simtabi.com/documentation/sange"

    def test_material_theme(self, mkdocs_yaml: dict) -> None:
        assert mkdocs_yaml["theme"]["name"] == "material"

    def test_nav_has_homepage(self, mkdocs_yaml: dict) -> None:
        nav = mkdocs_yaml["nav"]
        # First entry should be Home → index.md.
        assert any(
            isinstance(item, dict) and item.get("Home") == "index.md"
            for item in nav
        )

    def test_nav_has_getting_started(self, mkdocs_yaml: dict) -> None:
        nav = mkdocs_yaml["nav"]
        assert any(
            isinstance(item, dict)
            and "Getting started" in item
            for item in nav
        )

    def test_nav_includes_cli_section(self, mkdocs_yaml: dict) -> None:
        nav = mkdocs_yaml["nav"]
        cli_section = next(
            (item for item in nav if isinstance(item, dict) and "CLI" in item),
            None,
        )
        assert cli_section is not None


# --------------------------------------------------------------------------- #
# requirements.txt
# --------------------------------------------------------------------------- #


class TestRequirements:
    def test_mkdocs_pinned(self) -> None:
        text = _REQ.read_text(encoding="utf-8")
        assert "mkdocs>=" in text or "mkdocs ==" in text

    def test_material_theme_pinned(self) -> None:
        text = _REQ.read_text(encoding="utf-8")
        assert "mkdocs-material" in text


# --------------------------------------------------------------------------- #
# Content pages
# --------------------------------------------------------------------------- #


class TestContent:
    def test_index_exists(self) -> None:
        assert (_DOCS / "index.md").is_file()

    def test_getting_started_exists(self) -> None:
        assert (_DOCS / "getting-started.md").is_file()

    @pytest.mark.parametrize("page", [
        "cli/index.md",
        "cli/commit.md",
        "cli/commits.md",
        "cli/doctor.md",
        "cli/init.md",
        "cli/ai.md",
        "architecture/index.md",
        "architecture/audit-chain.md",
        "architecture/redaction.md",
    ])
    def test_referenced_page_exists(self, page: str) -> None:
        """Every nav entry that points at a local .md must resolve."""

        assert (_DOCS / page).is_file(), f"missing {page}"

    def test_index_mentions_sangedev_repo(self) -> None:
        index = (_DOCS / "index.md").read_text(encoding="utf-8")
        assert "github.com/sangedev/sange" in index

    def test_no_simtabi_sange_url_in_content(self) -> None:
        """Belt-and-suspenders: confirm the URL migration covered the
        docs site too."""

        for md in _DOCS.rglob("*.md"):
            text = md.read_text(encoding="utf-8")
            assert "github.com/simtabi/sange" not in text, (
                f"{md.relative_to(_DOC)} still references the old org URL"
            )


# --------------------------------------------------------------------------- #
# Cross-reference invariants
# --------------------------------------------------------------------------- #


class TestNavReferences:
    def test_every_local_md_in_nav_exists(self, mkdocs_yaml: dict) -> None:
        """Walk the nav recursively; every leaf that ends in .md must
        resolve to a file under docs/. (External http(s) leaves are
        not checked.)"""

        def _walk(node, found: list[str]):
            if isinstance(node, str):
                if node.endswith(".md") and not node.startswith("http"):
                    found.append(node)
            elif isinstance(node, list):
                for x in node:
                    _walk(x, found)
            elif isinstance(node, dict):
                for v in node.values():
                    _walk(v, found)

        leaves: list[str] = []
        _walk(mkdocs_yaml["nav"], leaves)
        for leaf in leaves:
            assert (_DOCS / leaf).is_file(), f"nav references missing {leaf}"


# --------------------------------------------------------------------------- #
# README — migration plan
# --------------------------------------------------------------------------- #


class TestReadme:
    def test_readme_explains_migration(self) -> None:
        text = _README.read_text(encoding="utf-8")
        assert "sangedev/documentation" in text
        assert "Migration" in text or "migration" in text

    def test_readme_has_local_preview(self) -> None:
        text = _README.read_text(encoding="utf-8")
        assert "mkdocs serve" in text


# --------------------------------------------------------------------------- #
# .gitignore — site/ output is excluded
# --------------------------------------------------------------------------- #


class TestGitignore:
    def test_documentation_site_dir_ignored(self) -> None:
        gi = (_REPO_ROOT / ".gitignore").read_text(encoding="utf-8")
        assert "documentation/site" in gi
