"""On-demand ADR scaffolder.

T-G-007 — produces `docs/adr/NNNN-<slug>.md` skeletons from the §2.2 ADR
template of `.design/sange-architecture-prompt.md`. Unlike the every-run
generators (T-G-008..T-G-015), this one fires on demand: a human typing
`python tools/generators/adr_scaffold.py "Switch to Pydantic v3"`.

Determinism + ADR-030 discipline:

  * The next ADR number is computed from the **canonical decision log**
    (`.design/plans/decisions-log.md`). The script also cross-checks
    `docs/adr/` for already-materialized files and picks `max(both) + 1`
    so a partially-mirrored state (a file landed without its row, or vice
    versa) doesn't silently collide.
  * The slug uses `_lib.markdown.slugify`, the same one Appendix D / E / F
    use — anchor links stay consistent across the doc set.
  * Frontmatter is emitted per §16.4.1 with `manual_edits_allowed: true`
    because the body is the human's to fill in. CI's
    `verify_generated.py` records the `input_sha256` for traceability and
    skips the body hash check.

The orchestrator entry-point (`run(mode, clock)`) is a no-op — this
generator does not have a recurring output. See `all.py` registry entry
T-G-007 with `output_paths=()` for the contract.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import re
import sys
from collections.abc import Sequence
from pathlib import Path

# --- Path bootstrap ------------------------------------------------------- #
HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent.parent
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


GENERATOR_VERSION = "1.0.0"
GENERATED_BY = "tools/generators/adr_scaffold.py"
DECISIONS_LOG = REPO_ROOT / ".design" / "plans" / "decisions-log.md"
ADR_DIR = REPO_ROOT / "docs" / "adr"

# `decisions-log.md` is a markdown table; canonical ADR rows look like
#   `| ADR-001 | Python core ...`
# Free-text mentions ("ADR-032 is the next available number") are *meta* and
# must NOT bump the next-free counter — otherwise the count drifts by one
# every time someone documents the next slot.
_ADR_ROW_RE = re.compile(r"^\|\s*ADR-(\d{3,4})\s*\|", re.MULTILINE)
_ADR_FILENAME_RE = re.compile(r"^(\d{3,4})-(?P<slug>[a-z0-9\-]+)\.md$")


def next_adr_number(
    *,
    decisions_log: Path = DECISIONS_LOG,
    adr_dir: Path = ADR_DIR,
) -> int:
    """Compute the next available ADR number from both sources of truth."""

    seen: set[int] = set()
    if decisions_log.exists():
        text = decisions_log.read_text(encoding="utf-8")
        seen.update(int(m.group(1)) for m in _ADR_ROW_RE.finditer(text))
    if adr_dir.exists():
        for path in adr_dir.glob("*.md"):
            m = _ADR_FILENAME_RE.match(path.name)
            if m:
                seen.add(int(m.group(1)))
    if not seen:
        return 1
    return max(seen) + 1


def adr_path(number: int, slug: str, *, adr_dir: Path = ADR_DIR) -> Path:
    return adr_dir / f"{number:04d}-{slug}.md"


def _render_body(
    *,
    number: int,
    title: str,
    today: _dt.date,
    summary: str = "",
    alternatives: Sequence[str] = (),
    consequences: Sequence[str] = (),
) -> str:
    alts = "\n".join(f"  - {a}" for a in alternatives) or "  - <alternative A> — rejected because …\n  - <alternative B> — rejected because …"
    conseqs = "\n".join(f"  - {c}" for c in consequences) or (
        "  - Positive: …\n"
        "  - Negative: …\n"
        "  - Neutral: …"
    )
    body = []
    body.append(markdown.heading(1, f"ADR-{number:04d}: {title}"))
    body.append("")
    body.append(f"**Status:** Proposed")
    body.append(f"**Date:** {today.isoformat()}")
    body.append("")
    body.append(f"**Context:** {summary or '<what is the situation? what forces are at play?>'}")
    body.append("")
    body.append("**Decision:** <what was decided, in one sentence, plus elaboration>.")
    body.append("")
    body.append("**Alternatives Rejected:**")
    body.append(alts)
    body.append("")
    body.append("**Consequences:**")
    body.append(conseqs)
    body.append("")
    body.append("**Lens Notes:**")
    body.append("  - Security: …")
    body.append("  - Performance: …")
    body.append("  - Maintainability: …")
    body.append("  - Developer Experience: …")
    body.append("  - Operability: …")
    body.append("  - Cost: …")
    body.append("")
    body.append("---")
    body.append("")
    body.append(
        "*Authored by the responding model + reviewer. After acceptance, add a "
        f"row to `.design/plans/decisions-log.md` (ADR-{number:04d}).*"
    )
    return "\n".join(body)


def scaffold(
    title: str,
    *,
    slug: str | None = None,
    number: int | None = None,
    clock: _dt.datetime | None = None,
    mode: WriteMode = WriteMode.WRITE,
    decisions_log: Path = DECISIONS_LOG,
    adr_dir: Path = ADR_DIR,
    overwrite: bool = False,
    summary: str = "",
) -> WriteOutcome:
    """Scaffold a single ADR file. Caller chooses WRITE vs CHECK."""

    if number is None:
        number = next_adr_number(decisions_log=decisions_log, adr_dir=adr_dir)
    final_slug = slug or markdown.slugify(title)
    if not final_slug:
        raise ValueError(f"could not derive a slug from {title!r}")
    target = adr_path(number, final_slug, adr_dir=adr_dir)

    if mode is WriteMode.WRITE and target.exists() and not overwrite:
        raise FileExistsError(
            f"refusing to overwrite {target}; pass overwrite=True or pick a fresh number"
        )

    clock = clock or _dt.datetime.now(tz=_dt.timezone.utc)
    body = _render_body(
        number=number,
        title=title,
        today=clock.date(),
        summary=summary,
    )

    # The input fingerprint is a deterministic function of (title, number)
    # so re-runs with the same title produce the same hash. Re-using the
    # body would be circular; we hash the *intent*.
    input_payload = f"adr-{number:04d}\ntitle:{title}\nslug:{final_slug}\n".encode("utf-8")
    input_sha = sha256_text(input_payload.decode("utf-8"))

    meta = GeneratorMetadata(
        generated_by=GENERATED_BY,
        generator_version=GENERATOR_VERSION,
        input_sha256=input_sha,
        manual_edits_allowed=True,  # humans fill in the ADR body
        generated_at=clock,
    )
    return write_generated_file(target, body, meta, mode=mode)


def run(*, mode: WriteMode, clock: _dt.datetime) -> list[WriteOutcome]:  # noqa: ARG001
    """Orchestrator entry-point — T-G-007 is on-demand, not part of `--write`."""

    return []


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="adr_scaffold",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("title", help="Short ADR title (e.g. \"Switch to Pydantic v3\").")
    p.add_argument(
        "--slug",
        help="Override the auto-generated slug. Defaults to slugified title.",
    )
    p.add_argument(
        "--number",
        type=int,
        help="Override the auto-detected next number. Use only when re-numbering.",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the target path without writing the file.",
    )
    p.add_argument(
        "--overwrite",
        action="store_true",
        help="Allow overwriting an existing ADR file (dangerous — confirm with the team).",
    )
    p.add_argument(
        "--summary",
        default="",
        help="Optional one-line context summary to seed the Context field.",
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    if args.dry_run:
        number = args.number or next_adr_number()
        slug = args.slug or markdown.slugify(args.title)
        path = adr_path(number, slug)
        print(f"would scaffold: {path.relative_to(REPO_ROOT)}")
        print(f"next free ADR number: {number:04d}")
        return 0

    outcome = scaffold(
        args.title,
        slug=args.slug,
        number=args.number,
        overwrite=args.overwrite,
        summary=args.summary,
    )
    print(f"scaffolded: {outcome.path.relative_to(REPO_ROOT)}  sha256={outcome.output_sha256}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
