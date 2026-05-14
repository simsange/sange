"""Tests for T-G-005 — `tools/generators/kit_manifest.py`.

Asserts:
  * Walk enumerates every file under templates/ (no missing, no duplicates).
  * MANIFEST.toml is never self-referenced in its own walk.
  * *.sig files are skipped (signatures cover content, are not content themselves).
  * Per-file sha256 in the manifest matches a freshly-computed sha256 of the file.
  * Manifest TOML parses cleanly.
  * Reference doc carries §16.4.1 frontmatter.
  * Byte-identical re-run with the same clock + same file content.
  * Hidden files (.DS_Store, dotfiles) and editor backups (~) are skipped.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import sys
from pathlib import Path

import pytest

try:
    import tomllib  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover
    import tomli as tomllib  # type: ignore[import-not-found]

REPO_ROOT = Path(__file__).resolve().parents[2]
GENERATORS_DIR = REPO_ROOT / "tools" / "generators"
if str(GENERATORS_DIR) not in sys.path:
    sys.path.insert(0, str(GENERATORS_DIR))

import kit_manifest  # noqa: E402

from _lib.output import WriteMode  # noqa: E402


FIXED_CLOCK = _dt.datetime(2026, 5, 14, 20, 0, 0, tzinfo=_dt.timezone.utc)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@pytest.fixture
def staged_kit(tmp_path: Path) -> tuple[Path, Path, Path]:
    """Build a tiny templates/ tree under tmp_path; return (templates_dir, manifest_path, doc_path)."""

    templates = tmp_path / "templates"
    (templates / "gitignore-profiles" / "lang").mkdir(parents=True)
    (templates / "commit-templates").mkdir()
    (templates / "scripts").mkdir()

    (templates / "gitignore-profiles" / "lang" / "python.toml").write_text(
        "[profile]\nname = \"lang/python\"\n", encoding="utf-8",
    )
    (templates / "commit-templates" / "default.toml").write_text(
        "[meta]\npreset_count = 67\n", encoding="utf-8",
    )
    (templates / "scripts" / "doctor.sh").write_text("#!/bin/bash\necho hi\n", encoding="utf-8")

    # Files that must be skipped:
    (templates / "MANIFEST.toml.sig").write_text("fake signature bytes", encoding="utf-8")
    (templates / ".DS_Store").write_bytes(b"\x00" * 12)
    (templates / "scripts" / "doctor.sh~").write_text("editor backup", encoding="utf-8")
    (templates / "scripts" / ".hidden").write_text("hidden file", encoding="utf-8")

    return templates, templates / "MANIFEST.toml", tmp_path / "kit-manifest.md"


# --------------------------------------------------------------------------- #
# Walk semantics
# --------------------------------------------------------------------------- #


class TestWalk:
    def test_skips_self_reference(self, staged_kit: tuple[Path, Path, Path]) -> None:
        templates, manifest, _ = staged_kit
        # Pretend a MANIFEST.toml exists from a previous run.
        manifest.write_text("(stub)", encoding="utf-8")
        files = kit_manifest.walk_templates(templates)
        names = {f.relative_path for f in files}
        assert "MANIFEST.toml" not in names
        assert "MANIFEST.toml.sig" not in names

    def test_skips_signature_files(self, staged_kit: tuple[Path, Path, Path]) -> None:
        templates, _, _ = staged_kit
        files = kit_manifest.walk_templates(templates)
        names = {f.relative_path for f in files}
        assert all(not n.endswith(".sig") for n in names), names

    def test_skips_dotfiles_and_backups(self, staged_kit: tuple[Path, Path, Path]) -> None:
        templates, _, _ = staged_kit
        files = kit_manifest.walk_templates(templates)
        names = {f.relative_path for f in files}
        assert ".DS_Store" not in names
        assert "scripts/.hidden" not in names
        assert "scripts/doctor.sh~" not in names

    def test_enumerates_every_real_file(self, staged_kit: tuple[Path, Path, Path]) -> None:
        templates, _, _ = staged_kit
        files = kit_manifest.walk_templates(templates)
        names = {f.relative_path for f in files}
        assert names == {
            "gitignore-profiles/lang/python.toml",
            "commit-templates/default.toml",
            "scripts/doctor.sh",
        }

    def test_category_is_top_level_dir(self, staged_kit: tuple[Path, Path, Path]) -> None:
        templates, _, _ = staged_kit
        files = kit_manifest.walk_templates(templates)
        by_path = {f.relative_path: f for f in files}
        assert by_path["gitignore-profiles/lang/python.toml"].category == "gitignore-profiles"
        assert by_path["commit-templates/default.toml"].category == "commit-templates"
        assert by_path["scripts/doctor.sh"].category == "scripts"

    def test_file_type_classification(self, staged_kit: tuple[Path, Path, Path]) -> None:
        templates, _, _ = staged_kit
        files = kit_manifest.walk_templates(templates)
        by_path = {f.relative_path: f for f in files}
        assert by_path["gitignore-profiles/lang/python.toml"].file_type == "toml"
        assert by_path["commit-templates/default.toml"].file_type == "toml"
        assert by_path["scripts/doctor.sh"].file_type == "sh"

    def test_walk_is_alphabetically_sorted(self, staged_kit: tuple[Path, Path, Path]) -> None:
        templates, _, _ = staged_kit
        files = kit_manifest.walk_templates(templates)
        paths = [f.relative_path for f in files]
        assert paths == sorted(paths)


# --------------------------------------------------------------------------- #
# Generator end-to-end
# --------------------------------------------------------------------------- #


class TestGeneratorEndToEnd:
    def test_emits_manifest_and_reference(self, staged_kit: tuple[Path, Path, Path]) -> None:
        templates, manifest, doc = staged_kit
        kit_manifest.run(
            mode=WriteMode.WRITE, clock=FIXED_CLOCK,
            templates_dir=templates, manifest_path=manifest, reference_doc_path=doc,
        )
        assert manifest.exists()
        assert doc.exists()

    def test_manifest_parses_as_toml(self, staged_kit: tuple[Path, Path, Path]) -> None:
        templates, manifest, doc = staged_kit
        kit_manifest.run(
            mode=WriteMode.WRITE, clock=FIXED_CLOCK,
            templates_dir=templates, manifest_path=manifest, reference_doc_path=doc,
        )
        with manifest.open("rb") as fh:
            data = tomllib.load(fh)
        assert "meta" in data
        assert "file" in data
        assert data["meta"]["file_count"] == 3
        assert data["meta"]["signature_required"] is True
        assert data["meta"]["hash_algorithm"] == "sha256"

    def test_manifest_includes_every_walked_file(self, staged_kit: tuple[Path, Path, Path]) -> None:
        templates, manifest, doc = staged_kit
        kit_manifest.run(
            mode=WriteMode.WRITE, clock=FIXED_CLOCK,
            templates_dir=templates, manifest_path=manifest, reference_doc_path=doc,
        )
        with manifest.open("rb") as fh:
            data = tomllib.load(fh)
        paths = {entry["path"] for entry in data["file"]}
        assert paths == {
            "gitignore-profiles/lang/python.toml",
            "commit-templates/default.toml",
            "scripts/doctor.sh",
        }

    def test_per_file_sha256_matches_actual_file(self, staged_kit: tuple[Path, Path, Path]) -> None:
        templates, manifest, doc = staged_kit
        kit_manifest.run(
            mode=WriteMode.WRITE, clock=FIXED_CLOCK,
            templates_dir=templates, manifest_path=manifest, reference_doc_path=doc,
        )
        with manifest.open("rb") as fh:
            data = tomllib.load(fh)
        for entry in data["file"]:
            actual_bytes = (templates / entry["path"]).read_bytes()
            assert entry["sha256"] == _sha256(actual_bytes), entry["path"]

    def test_reference_doc_has_frontmatter(self, staged_kit: tuple[Path, Path, Path]) -> None:
        templates, manifest, doc = staged_kit
        kit_manifest.run(
            mode=WriteMode.WRITE, clock=FIXED_CLOCK,
            templates_dir=templates, manifest_path=manifest, reference_doc_path=doc,
        )
        body = doc.read_text(encoding="utf-8")
        assert body.startswith("---\n")
        assert "generated_by: tools/generators/kit_manifest.py" in body

    def test_byte_identical_rerun(self, staged_kit: tuple[Path, Path, Path]) -> None:
        templates, manifest, doc = staged_kit
        kit_manifest.run(
            mode=WriteMode.WRITE, clock=FIXED_CLOCK,
            templates_dir=templates, manifest_path=manifest, reference_doc_path=doc,
        )
        first_manifest = manifest.read_bytes()
        first_doc = doc.read_bytes()
        kit_manifest.run(
            mode=WriteMode.WRITE, clock=FIXED_CLOCK,
            templates_dir=templates, manifest_path=manifest, reference_doc_path=doc,
        )
        assert manifest.read_bytes() == first_manifest
        assert doc.read_bytes() == first_doc

    def test_check_mode_match(self, staged_kit: tuple[Path, Path, Path]) -> None:
        templates, manifest, doc = staged_kit
        kit_manifest.run(
            mode=WriteMode.WRITE, clock=FIXED_CLOCK,
            templates_dir=templates, manifest_path=manifest, reference_doc_path=doc,
        )
        outcomes = kit_manifest.run(
            mode=WriteMode.CHECK, clock=FIXED_CLOCK,
            templates_dir=templates, manifest_path=manifest, reference_doc_path=doc,
        )
        assert outcomes[0].result is not None
        assert outcomes[0].result.value == "match"

    def test_new_file_changes_manifest(self, staged_kit: tuple[Path, Path, Path]) -> None:
        templates, manifest, doc = staged_kit
        kit_manifest.run(
            mode=WriteMode.WRITE, clock=FIXED_CLOCK,
            templates_dir=templates, manifest_path=manifest, reference_doc_path=doc,
        )
        first_doc = doc.read_bytes()

        # Drop a new file and re-run.
        (templates / "scripts" / "new-helper.sh").write_text("#!/bin/bash\n", encoding="utf-8")
        kit_manifest.run(
            mode=WriteMode.WRITE, clock=FIXED_CLOCK,
            templates_dir=templates, manifest_path=manifest, reference_doc_path=doc,
        )
        assert doc.read_bytes() != first_doc

        with manifest.open("rb") as fh:
            data = tomllib.load(fh)
        paths = {entry["path"] for entry in data["file"]}
        assert "scripts/new-helper.sh" in paths
