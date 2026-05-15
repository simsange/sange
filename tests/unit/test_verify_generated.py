"""End-to-end smoke tests for `tools/generators/verify_generated.py`.

We import the verifier module directly (sys.path bootstrap below) and drive it
against tmp_path so the tests don't depend on any real generated file in the
repo. Three guarantees:

  * A fresh file written by `write_generated_file` passes verification.
  * Tampering with the body causes a MISMATCH.
  * Files without the §16.4.1 frontmatter are silently ignored (the verifier
    is for *generator output*, not arbitrary text).
"""

from __future__ import annotations

import datetime as _dt
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
GENERATORS_DIR = REPO_ROOT / "tools" / "generators"
if str(GENERATORS_DIR) not in sys.path:
    sys.path.insert(0, str(GENERATORS_DIR))

import verify_generated  # noqa: E402  (after path bootstrap)
from _lib.output import GeneratorMetadata, WriteMode, write_generated_file  # noqa: E402


def _meta() -> GeneratorMetadata:
    return GeneratorMetadata(
        generated_by="tools/generators/test_fixture.py",
        generator_version="0.0.1",
        input_sha256="0" * 64,
        manual_edits_allowed=False,
        generated_at=_dt.datetime(2026, 1, 1, 0, 0, 0, tzinfo=_dt.UTC),
    )


def test_fresh_file_passes(tmp_path: Path) -> None:
    target = tmp_path / "docs" / "reference" / "fixture.md"
    write_generated_file(target, "Hello body!\n", _meta(), mode=WriteMode.WRITE)
    result = verify_generated.check_file(target)
    assert result is not None
    assert result.ok is True


def test_tampered_body_fails(tmp_path: Path) -> None:
    target = tmp_path / "doc.md"
    write_generated_file(target, "Hello body!\n", _meta(), mode=WriteMode.WRITE)
    raw = target.read_text(encoding="utf-8")
    target.write_text(raw.replace("Hello body!", "MUTATED"), encoding="utf-8")
    result = verify_generated.check_file(target)
    assert result is not None
    assert result.ok is False
    assert "mismatch" in result.reason.lower()


def test_file_without_frontmatter_is_skipped(tmp_path: Path) -> None:
    target = tmp_path / "plain.md"
    target.write_text("# Just a heading\n\nNo frontmatter.\n", encoding="utf-8")
    assert verify_generated.check_file(target) is None


def test_manual_edits_allowed_skips_body_hash(tmp_path: Path) -> None:
    target = tmp_path / "manual.md"
    meta = GeneratorMetadata(
        generated_by="x",
        generator_version="1",
        input_sha256="abc",
        manual_edits_allowed=True,
        generated_at=_dt.datetime(2026, 1, 1, tzinfo=_dt.UTC),
    )
    write_generated_file(target, "Original body.\n", meta, mode=WriteMode.WRITE)
    # Now mutate the body — manual edits are explicitly allowed, so verification
    # should pass.
    raw = target.read_text(encoding="utf-8")
    target.write_text(raw.replace("Original body.", "Hand-edited!"), encoding="utf-8")
    result = verify_generated.check_file(target)
    assert result is not None
    assert result.ok is True
    assert "manual_edits_allowed" in result.reason


def test_iter_candidate_files_skips_binaries(tmp_path: Path) -> None:
    (tmp_path / "doc.md").write_text("hi\n", encoding="utf-8")
    (tmp_path / "image.png").write_bytes(b"\x89PNG\r\n")
    (tmp_path / "ignored.sig").write_bytes(b"sig")
    seen = list(verify_generated.iter_candidate_files([tmp_path]))
    names = {p.name for p in seen}
    assert "doc.md" in names
    assert "image.png" not in names
    assert "ignored.sig" not in names
