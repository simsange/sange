"""Invariants for src/sange/exit_codes.py + the T-G-008 generator output.

These tests guard the SemVer contract that exit codes carry: they must be
unique, have descriptions, follow the §7.0.8 numbering bands, and round-trip
through the generator without drift.
"""

from __future__ import annotations

import datetime as _dt
import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
GENERATORS_DIR = REPO_ROOT / "tools" / "generators"
if str(GENERATORS_DIR) not in sys.path:
    sys.path.insert(0, str(GENERATORS_DIR))

import exit_codes as exit_codes_generator  # noqa: E402
from _lib.fingerprint import body_sha256  # noqa: E402
from _lib.output import WriteMode  # noqa: E402

from sange.exit_codes import DESCRIPTIONS, ExitCode, describe  # noqa: E402

# --------------------------------------------------------------------------- #
# Enum invariants
# --------------------------------------------------------------------------- #


class TestExitCodeInvariants:
    def test_every_code_is_unique(self) -> None:
        values = [c.value for c in ExitCode]
        assert len(values) == len(set(values)), values

    def test_every_code_has_a_description(self) -> None:
        missing = [c for c in ExitCode if c not in DESCRIPTIONS]
        assert not missing, f"missing descriptions for {missing}"

    def test_no_extra_descriptions(self) -> None:
        extra = [k for k in DESCRIPTIONS if k not in list(ExitCode)]
        assert not extra, f"descriptions for codes not in the enum: {extra}"

    def test_descriptions_are_non_empty_sentences(self) -> None:
        for code, desc in DESCRIPTIONS.items():
            stripped = desc.strip()
            assert stripped, f"empty description for {code}"
            # End in a period; mirrors the docstring style across the module.
            assert stripped.endswith("."), f"description for {code} should end with a period"

    def test_numbering_bands(self) -> None:
        # 0..2 reserved for Unix conventions; 64..69 cross-cutting; 70+ subsystem.
        for code in ExitCode:
            value = code.value
            assert value in {0, 1, 2} or value >= 64, (
                f"{code} has value {value} which falls outside Unix-conventions / "
                "cross-cutting / subsystem bands documented in §7.0.8"
            )

    def test_describe_returns_text(self) -> None:
        assert describe(ExitCode.OK).startswith("Success")
        assert describe(ExitCode.USER_ABORTED).startswith("User cancelled")


class TestKnownValues:
    """Spot-check the values the §7.0.8 reference table commits to.

    These are the codes the published docs promise. If you find yourself
    changing one, that's a SemVer-major change — and the test exists to slow
    you down enough to notice.
    """

    @pytest.mark.parametrize(
        ("name", "expected"),
        [
            ("OK", 0),
            ("GENERIC_FAILURE", 1),
            ("INVALID_ARGUMENT", 2),
            ("PRECONDITION_FAILED", 64),
            ("USER_ABORTED", 65),
            ("VERIFICATION_FAILED", 66),
            ("ROLLBACK_FAILED", 67),
            ("AUDIT_WRITE_REFUSED", 68),
            ("SIGNATURE_VERIFICATION_FAILED", 69),
            ("KIT_VERSION_DRIFT", 70),
        ],
    )
    def test_canonical_value(self, name: str, expected: int) -> None:
        assert ExitCode[name].value == expected


# --------------------------------------------------------------------------- #
# Generator round-trip
# --------------------------------------------------------------------------- #


CLOCK_FIXTURE = _dt.datetime(2026, 1, 2, 3, 4, 5, tzinfo=_dt.UTC)


class TestExitCodesGenerator:
    def test_check_mode_passes_on_freshly_written_file(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        target = tmp_path / "exit-codes.md"
        monkeypatch.setattr(exit_codes_generator, "OUTPUT_PATH", target)

        # First write
        write_results = exit_codes_generator.run(mode=WriteMode.WRITE, clock=CLOCK_FIXTURE)
        assert len(write_results) == 1
        assert target.exists()

        # Verify
        check_results = exit_codes_generator.run(mode=WriteMode.CHECK, clock=CLOCK_FIXTURE)
        assert len(check_results) == 1
        assert check_results[0].result is not None
        assert check_results[0].result.value == "match"

    def test_check_detects_drift(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        target = tmp_path / "exit-codes.md"
        monkeypatch.setattr(exit_codes_generator, "OUTPUT_PATH", target)

        exit_codes_generator.run(mode=WriteMode.WRITE, clock=CLOCK_FIXTURE)
        text = target.read_text(encoding="utf-8")
        target.write_text(text.replace("Sange exit codes", "TAMPERED"), encoding="utf-8")

        check_results = exit_codes_generator.run(mode=WriteMode.CHECK, clock=CLOCK_FIXTURE)
        assert check_results[0].result is not None
        assert check_results[0].result.value == "mismatch"

    def test_body_contains_every_code(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        target = tmp_path / "exit-codes.md"
        monkeypatch.setattr(exit_codes_generator, "OUTPUT_PATH", target)
        exit_codes_generator.run(mode=WriteMode.WRITE, clock=CLOCK_FIXTURE)
        body = target.read_text(encoding="utf-8")
        for code in ExitCode:
            assert code.name in body, f"generator output missing {code.name}"

    def test_body_includes_metadata_block(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        target = tmp_path / "exit-codes.md"
        monkeypatch.setattr(exit_codes_generator, "OUTPUT_PATH", target)
        exit_codes_generator.run(mode=WriteMode.WRITE, clock=CLOCK_FIXTURE)
        text = target.read_text(encoding="utf-8")
        assert "generated_by: tools/generators/exit_codes.py" in text
        assert re.search(r"output_sha256: [0-9a-f]{64}", text)
        assert re.search(r"input_sha256: [0-9a-f]{64}", text)

    def test_body_sha256_round_trip(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        target = tmp_path / "exit-codes.md"
        monkeypatch.setattr(exit_codes_generator, "OUTPUT_PATH", target)
        exit_codes_generator.run(mode=WriteMode.WRITE, clock=CLOCK_FIXTURE)
        text = target.read_text(encoding="utf-8")
        # The declared output_sha256 must equal the body's actual sha256.
        m = re.search(r"output_sha256: ([0-9a-f]{64})", text)
        assert m is not None
        declared = m.group(1)
        actual = body_sha256(text)
        assert declared == actual

    def test_two_runs_with_same_clock_are_byte_identical(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        target = tmp_path / "exit-codes.md"
        monkeypatch.setattr(exit_codes_generator, "OUTPUT_PATH", target)
        exit_codes_generator.run(mode=WriteMode.WRITE, clock=CLOCK_FIXTURE)
        first = target.read_bytes()
        exit_codes_generator.run(mode=WriteMode.WRITE, clock=CLOCK_FIXTURE)
        second = target.read_bytes()
        assert first == second
