"""Generate docs/reference/exit-codes.md from src/sange/exit_codes.py.

T-G-008 — the smallest end-to-end generator. It validates the whole
deterministic pipeline (parse Python module → emit markdown with §16.4.1
frontmatter → verify hash round-trips) on minimal input before the heavier
catalog generators (T-G-001, T-G-002, T-G-004, T-G-015) follow the same
pattern.

Determinism:

  * The Enum members are iterated in their numeric order; the order in the
    source file does not matter.
  * The `input_sha256` is the canonical-bytes sha256 of `exit_codes.py`,
    so any source edit changes the hash and CI re-runs.
  * Body rendering uses `_lib.markdown.table()` for stable pipe-escaping +
    alignment.

Per ADR-029 the generator runs even on a fresh clone with no business logic
— `exit_codes.py` is already on disk after T-G-008a.
"""

from __future__ import annotations

import datetime as _dt
import sys
from pathlib import Path

# --- Path bootstrap ------------------------------------------------------- #
HERE = Path(__file__).resolve().parent              # tools/generators
REPO_ROOT = HERE.parent.parent                       # repo root
SRC_DIR = REPO_ROOT / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

# --- Imports (after path bootstrap) --------------------------------------- #
from _lib import markdown  # noqa: E402
from _lib.fingerprint import sha256_text  # noqa: E402
from _lib.output import (  # noqa: E402
    GeneratorMetadata,
    WriteMode,
    WriteOutcome,
    write_generated_file,
)
from sange.exit_codes import DESCRIPTIONS, ExitCode  # noqa: E402


GENERATOR_VERSION = "1.0.0"
GENERATED_BY = "tools/generators/exit_codes.py"
OUTPUT_PATH = REPO_ROOT / "docs" / "reference" / "exit-codes.md"
SOURCE_PATH = SRC_DIR / "sange" / "exit_codes.py"


def _input_sha256() -> str:
    """Canonical sha256 of the source module — the generator's input fingerprint."""

    return sha256_text(SOURCE_PATH.read_text(encoding="utf-8"))


def _category_for(code: ExitCode) -> str:
    if code.value <= 2:
        return "Unix"
    if 64 <= code.value <= 69:
        return "Cross-cutting"
    return "Subsystem"


def _build_body() -> str:
    rows: list[list[str]] = []
    for code in sorted(ExitCode, key=lambda c: c.value):
        description = DESCRIPTIONS.get(code, "")
        rows.append(
            [
                str(code.value),
                f"`{code.name}`",
                _category_for(code),
                description,
            ]
        )

    parts: list[str] = []
    parts.append(markdown.heading(1, "Sange exit codes"))
    parts.append(
        "> Generated from `src/sange/exit_codes.py` by "
        "`tools/generators/exit_codes.py` (T-G-008). Source-of-truth: §7.0.8 "
        "of `.design/sange-architecture-prompt.md`.\n"
    )
    parts.append(
        "Every Sange CLI / TUI / daemon process exits with one of the values "
        "in the table below. Adding a new value is a SemVer-minor change; "
        "removing or repurposing one is a SemVer-major change.\n"
    )
    parts.append(markdown.heading(2, "Reference"))
    parts.append(
        markdown.table(
            ["Code", "Constant", "Category", "Meaning"],
            rows,
            alignments=["right", "left", "left", "left"],
        )
    )
    parts.append("")
    parts.append(markdown.heading(2, "Programmatic access"))
    parts.append(
        "```python\n"
        "from sange.exit_codes import ExitCode, describe\n\n"
        "raise SystemExit(ExitCode.USER_ABORTED)\n\n"
        "# Or look up the description:\n"
        "describe(ExitCode.VERIFICATION_FAILED)\n"
        "```\n"
    )
    parts.append(markdown.heading(2, "Cross-references"))
    parts.append(
        markdown.bullet_list(
            [
                "Typed-phrase confirmation gate: `.design/sange-architecture-prompt.md` §7.0.5.",
                "Hash-chained audit JSONL: `.design/sange-architecture-prompt.md` §7.0.7.",
                "Purge subsystem pre-flight gates: `.design/sange-architecture-prompt.md` §6.11.4.",
                "Purge subsystem verification: `.design/sange-architecture-prompt.md` §6.11.5.",
                "Premade Operations Kit policy: `.design/sange-architecture-prompt.md` §6.12 (ADR-020).",
                "Generator integrity discipline: ADR-023 + ADR-029; verifier `tools/generators/verify_generated.py`.",
            ]
        )
    )
    return "\n".join(parts)


def run(*, mode: WriteMode, clock: _dt.datetime) -> list[WriteOutcome]:
    """Generator entry-point invoked by `tools/generators/all.py`."""

    meta = GeneratorMetadata(
        generated_by=GENERATED_BY,
        generator_version=GENERATOR_VERSION,
        input_sha256=_input_sha256(),
        manual_edits_allowed=False,
        generated_at=clock,
    )
    body = _build_body()
    outcome = write_generated_file(OUTPUT_PATH, body, meta, mode=mode)
    return [outcome]


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="Write the file.")
    parser.add_argument("--check", action="store_true", help="Verify on-disk content.")
    args = parser.parse_args()

    if not (args.write or args.check):
        args.write = True
    mode = WriteMode.WRITE if args.write else WriteMode.CHECK

    results = run(mode=mode, clock=_dt.datetime.now(tz=_dt.timezone.utc))
    rc = 0
    for r in results:
        if r.result is not None and r.result.value != "match":
            rc = 66
        line = f"[{mode.value}] {r.path}  sha256={r.output_sha256}"
        if r.result is not None:
            line += f"  ({r.result.value})"
        print(line)
    raise SystemExit(rc)
