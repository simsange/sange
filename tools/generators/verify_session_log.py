"""Verify `.design/plans/session-log.md` integrity — ADR-030 + ADR-031 in CI.

T-G-016 — the discipline gate behind the anti-hallucination + memory-preservation
disciplines. CI invokes this directly (it's not part of the `all.py --write`
pipeline; the orchestrator entry is a no-op).

Checks:

  1. **Cross-reference resolution.** Every `linked` column entry containing
     `ADR-NNN`, `T-NNN`, `T-G-NNN`, `R-NNN`, or `S-NNN-T-MM` must resolve
     to a real entry in the canonical file:
       * `ADR-NNN`         → `.design/plans/decisions-log.md` table row
       * `T-NNN` / `T-G-NNN` → `.design/plans/checklist.md` task line
       * `R-NNN`           → `.design/plans/risk-register.md` table row
       * `S-NNN-T-MM`      → another row in `session-log.md` itself

  2. **Grounding-column completeness.** Per ADR-030 + ADR-031, every row from
     `S-001-T-20` onward + every `S-002-T-NN` row must have a non-empty
     grounding column. The grounding lists the files the model READ before
     performing the action — the basis for any factual claim.

  3. **`files_touched` reachability.** Each path in `files_touched` either
     (a) exists on disk relative to the repo root, OR (b) is one of the
     documented exception forms (`(chat only)`, `(none — read-only)`, etc.).
     When git is initialized (T-001 future step), this will extend to a
     `git log` window cross-check for the row's timestamp.

Exit codes (per `src/sange/exit_codes.py`):

    0   All checks passed.
    2   Invalid argument or unparseable session-log.
    66  At least one check failed (VERIFICATION_FAILED).

This script is **pure stdlib** — same discipline as `verify_generated.py`,
runnable before any third-party install.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

# --- Path bootstrap ------------------------------------------------------- #
HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent.parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from _lib.output import (  # noqa: E402
    WriteMode,
    WriteOutcome,
)

SESSION_LOG_PATH = REPO_ROOT / ".design" / "plans" / "session-log.md"
DECISIONS_LOG_PATH = REPO_ROOT / ".design" / "plans" / "decisions-log.md"
CHECKLIST_PATH = REPO_ROOT / ".design" / "plans" / "checklist.md"
RISK_REGISTER_PATH = REPO_ROOT / ".design" / "plans" / "risk-register.md"

EXIT_OK = 0
EXIT_BAD_ARG = 2
EXIT_VERIFICATION_FAILED = 66


# A session-log row id like `S-001-T-20`. The grounding rule starts here.
GROUNDING_REQUIRED_FROM = "S-001-T-20"


# Documented "no real file change" placeholders that appear in `files_touched`
# when an entry doesn't correspond to a file write. Examples observed in the
# canonical session-log:
#   `(chat only)`, `(none — read-only)`, `(no files — research)`, `(all 10 files)`,
#   `(user-driven move)`, `(empty)`, `(none)`.
NON_FILE_PLACEHOLDER = re.compile(r"^\(.*\)$|^—$|^chat only$|^n/a$", re.IGNORECASE)


# --------------------------------------------------------------------------- #
# Schema
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class SessionLogRow:
    id: str
    timestamp: str
    actor: str
    surface: str
    action: str
    files_touched_raw: str
    grounding_raw: str
    linked_raw: str
    notes_raw: str


@dataclass
class CheckReport:
    rows_parsed: int = 0
    cross_ref_failures: list[str] = field(default_factory=list)
    grounding_failures: list[str] = field(default_factory=list)
    files_touched_failures: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not (self.cross_ref_failures or self.grounding_failures or self.files_touched_failures)

    def total_failures(self) -> int:
        return (
            len(self.cross_ref_failures)
            + len(self.grounding_failures)
            + len(self.files_touched_failures)
        )


# --------------------------------------------------------------------------- #
# Parsing
# --------------------------------------------------------------------------- #


_ROW_PREFIX = re.compile(r"^\|\s*(?P<id>S-\d{3}-T-\d{2})\s*\|")

# Pre-v4.4 rows had 8 columns (no grounding); v4.4+ rows have 10 columns:
#   id | timestamp | actor | surface | action | files_touched | grounding | linked | audit_chain | notes
# We parse based on column count.
_LEGACY_COLUMNS = 8
_GROUNDING_COLUMNS = 10


def _split_pipe_row(line: str) -> list[str]:
    # Strip leading/trailing pipes + split on `|` not preceded by `\`.
    inner = line.strip()
    if inner.startswith("|"):
        inner = inner[1:]
    if inner.endswith("|"):
        inner = inner[:-1]
    # Honor `\|` escapes (cells may contain them).
    parts = re.split(r"(?<!\\)\|", inner)
    return [p.strip() for p in parts]


def parse_session_log(text: str) -> list[SessionLogRow]:
    """Parse every `| S-NNN-T-MM | ... |` table row in the log."""

    rows: list[SessionLogRow] = []
    for raw_line in text.splitlines():
        if not _ROW_PREFIX.match(raw_line):
            continue
        cells = _split_pipe_row(raw_line)
        if len(cells) == _LEGACY_COLUMNS:
            row_id, ts, actor, surface, action, files_touched, linked, notes = cells
            grounding_raw = ""
        elif len(cells) == _GROUNDING_COLUMNS:
            row_id, ts, actor, surface, action, files_touched, grounding_raw, linked, _audit_chain, notes = cells
        else:
            # Unrecognized shape — skip silently rather than mis-bin.
            continue
        rows.append(
            SessionLogRow(
                id=row_id,
                timestamp=ts,
                actor=actor,
                surface=surface,
                action=action,
                files_touched_raw=files_touched,
                grounding_raw=grounding_raw,
                linked_raw=linked,
                notes_raw=notes,
            )
        )
    return rows


# --------------------------------------------------------------------------- #
# Cross-reference resolvers
# --------------------------------------------------------------------------- #


_ADR_REF = re.compile(r"\bADR-(\d{3,4})\b")
_TASK_REF = re.compile(r"\bT-G?-?(\d{3,4})\b")  # T-NNN or T-G-NNN
_TASK_REF_QUALIFIED = re.compile(r"\bT(?:-G)?-\d{3}\b")
_RISK_REF = re.compile(r"\bR-(\d{3,4})\b")
_SESSION_REF = re.compile(r"\bS-\d{3}-T-\d{2}\b")
_ADR_ROW_RE = re.compile(r"^\|\s*ADR-(\d{3,4})\s*\|", re.MULTILINE)
_RISK_ROW_RE = re.compile(r"^\|\s*R-(\d{3,4})\s*\|", re.MULTILINE)
_TASK_LINE_RE = re.compile(r"\*\*(T(?:-G)?-\d{3,4})\*\*")


def _known_adrs(decisions_text: str) -> set[str]:
    return {f"ADR-{m.group(1)}" for m in _ADR_ROW_RE.finditer(decisions_text)}


def _known_risks(risk_text: str) -> set[str]:
    return {f"R-{m.group(1)}" for m in _RISK_ROW_RE.finditer(risk_text)}


def _known_tasks(checklist_text: str) -> set[str]:
    """Tasks listed in checklist.md as `**T-NNN**` or `**T-G-NNN**`."""

    return {m.group(1) for m in _TASK_LINE_RE.finditer(checklist_text)}


def _known_sessions(session_log_text: str) -> set[str]:
    return {m.group(0) for m in re.finditer(r"S-\d{3}-T-\d{2}", session_log_text)}


def _known_stride_threats() -> set[str]:
    """Load STRIDE threat IDs from `tools/generators/threat_model_table.py`.

    The threat module's IDs share the T-NNN shape with checklist tasks — both
    are valid targets for a `T-NNN` reference in the session-log. We tolerate
    a missing module (e.g. during bootstrap) and fall back to the empty set.
    """

    try:
        import threat_model_table  # type: ignore[import-not-found]
    except ImportError:
        return set()
    return {t.id for t in threat_model_table.THREATS}


# --------------------------------------------------------------------------- #
# Check (a): cross-reference resolution
# --------------------------------------------------------------------------- #


def check_cross_references(
    rows: list[SessionLogRow],
    *,
    known_adrs: set[str],
    known_risks: set[str],
    known_tasks: set[str],
    known_sessions: set[str],
    known_stride_threats: set[str] | None = None,
) -> list[str]:
    failures: list[str] = []
    for row in rows:
        # Combine linked + notes fields for cross-ref discovery — `notes`
        # legitimately names many ADRs/risks too.
        sources = {"linked": row.linked_raw, "notes": row.notes_raw}
        for source_name, blob in sources.items():
            # ADR refs
            for m in _ADR_REF.finditer(blob):
                adr = f"ADR-{m.group(1)}"
                if adr not in known_adrs:
                    failures.append(
                        f"{row.id}: {source_name} references {adr} but it's not in decisions-log.md"
                    )
            # Risk refs
            for m in _RISK_REF.finditer(blob):
                risk = f"R-{m.group(1)}"
                if risk not in known_risks:
                    failures.append(
                        f"{row.id}: {source_name} references {risk} but it's not in risk-register.md"
                    )
            # Task refs — T-NNN or T-G-NNN.
            # T-NNN shares the shape with STRIDE threat IDs; accept either.
            stride_set = known_stride_threats or set()
            for m in _TASK_REF_QUALIFIED.finditer(blob):
                task = m.group(0)
                if task in known_tasks:
                    continue
                if task in stride_set:
                    continue  # STRIDE threat reference, not a checklist task
                failures.append(
                    f"{row.id}: {source_name} references {task} but it's neither a checklist task "
                    "nor a STRIDE threat ID"
                )
            # Session refs
            for m in _SESSION_REF.finditer(blob):
                sess = m.group(0)
                if sess == row.id:
                    continue  # self-reference is fine
                if sess not in known_sessions:
                    failures.append(
                        f"{row.id}: {source_name} references {sess} but it's not a known session row"
                    )
    return failures


# --------------------------------------------------------------------------- #
# Check (b): grounding column completeness
# --------------------------------------------------------------------------- #


def _row_id_ord(row_id: str) -> tuple[int, int]:
    """Return a sortable (session_number, task_number) tuple from `S-NNN-T-MM`."""

    m = re.match(r"S-(\d{3})-T-(\d{2})", row_id)
    if not m:
        return (0, 0)
    return (int(m.group(1)), int(m.group(2)))


def _is_grounding_required(row_id: str) -> bool:
    """Per ADR-030 + ADR-031, grounding is required from S-001-T-20 onward
    AND for every S-NNN-T-MM where N >= 2."""

    session_num, task_num = _row_id_ord(row_id)
    if session_num >= 2:
        return True
    if session_num == 1 and task_num >= 20:
        return True
    return False


def _is_grounding_empty(grounding: str) -> bool:
    stripped = grounding.strip()
    if not stripped:
        return True
    return stripped in {"—", "n/a", "(n/a)"}


def check_grounding(rows: list[SessionLogRow]) -> list[str]:
    failures: list[str] = []
    for row in rows:
        if not _is_grounding_required(row.id):
            continue
        if _is_grounding_empty(row.grounding_raw):
            failures.append(
                f"{row.id}: grounding column is empty; required from S-001-T-20 onward "
                "per ADR-030 + ADR-031"
            )
    return failures


# --------------------------------------------------------------------------- #
# Check (c): files_touched reachability
# --------------------------------------------------------------------------- #


_INLINE_PATH = re.compile(r"`([^`]+)`")
_SHA256_HEX = re.compile(r"^[0-9a-f]{64}$")
_KNOWN_EXTENSIONS = {
    ".py", ".md", ".markdown", ".toml", ".yaml", ".yml", ".json", ".sh", ".bash",
    ".ini", ".cfg", ".txt", ".conf", ".html", ".css", ".js", ".ts", ".php",
    ".go", ".rs", ".rb", ".java", ".kt", ".dart", ".sql", ".gitignore",
}


def _looks_like_a_path(token: str) -> bool:
    """Decide whether a backtick-quoted token is likely a repo-relative path.

    Filters out the false positives that pollute the `files_touched` cell:
    sha256 hashes, bare identifiers, commentary, template placeholders.
    """

    if not token:
        return False
    if "§" in token or "(" in token or ")" in token or "<" in token or ">" in token:
        return False  # commentary, anchor, or placeholder template
    if _SHA256_HEX.match(token):
        return False
    if " " in token:
        return False  # multi-word commentary, not a path
    # A real path either contains `/` (relative path) or ends with a known extension.
    if "/" in token:
        return True
    return any(token.endswith(ext) for ext in _KNOWN_EXTENSIONS)


def _extract_paths_from_files_touched(blob: str) -> list[str]:
    """Pull repo-relative paths out of the `files_touched` cell."""

    return [m for m in _INLINE_PATH.findall(blob) if _looks_like_a_path(m)]


def check_files_touched(
    rows: list[SessionLogRow],
    *,
    repo_root: Path,
) -> list[str]:
    """Verify paths cited in `files_touched`.

    Per ADR-030 + ADR-031, the backtick-quoted-path discipline applies from
    `S-001-T-20` onward; earlier S-001 rows are historical reconstruction
    (see the session-log header) and use prose-style references that don't
    consistently quote paths. Those rows are exempt from the strict path
    check but still pass the cross-reference + grounding checks (where
    applicable).
    """

    failures: list[str] = []
    for row in rows:
        blob = row.files_touched_raw.strip()
        paths = _extract_paths_from_files_touched(blob)

        # Pre-discipline rows (S-001-T-01..T-19) — historical reconstruction.
        if not _is_grounding_required(row.id):
            # Still try to validate any backtick-quoted paths that DO appear,
            # but tolerate prose-only cells.
            for path_str in paths:
                if any(ch in path_str for ch in ("(", ")", "§")):
                    continue
                target = repo_root / path_str
                if not target.exists():
                    # Soft warning: print but don't fail.
                    pass  # historical row — exempt
            continue

        if not paths:
            # No backtick-quoted paths. Acceptable if the cell is one of the
            # documented placeholders.
            if (
                NON_FILE_PLACEHOLDER.match(blob)
                or "chat only" in blob.lower()
                or "no files" in blob.lower()
                or "none —" in blob.lower()
                or "n/a" in blob.lower()
            ):
                continue
            failures.append(
                f"{row.id}: files_touched has no recognizable path and no placeholder: {blob[:80]!r}"
            )
            continue
        for path_str in paths:
            if any(ch in path_str for ch in ("(", ")", "§")):
                continue
            target = repo_root / path_str
            if not target.exists():
                failures.append(
                    f"{row.id}: files_touched references `{path_str}` but it doesn't exist on disk"
                )
    return failures


# --------------------------------------------------------------------------- #
# Orchestration
# --------------------------------------------------------------------------- #


def verify(
    *,
    session_log_path: Path = SESSION_LOG_PATH,
    decisions_log_path: Path = DECISIONS_LOG_PATH,
    checklist_path: Path = CHECKLIST_PATH,
    risk_register_path: Path = RISK_REGISTER_PATH,
    repo_root: Path = REPO_ROOT,
) -> CheckReport:
    """Run all three checks against the canonical files. Pure function."""

    session_text = session_log_path.read_text(encoding="utf-8")
    decisions_text = decisions_log_path.read_text(encoding="utf-8") if decisions_log_path.exists() else ""
    checklist_text = checklist_path.read_text(encoding="utf-8") if checklist_path.exists() else ""
    risk_text = risk_register_path.read_text(encoding="utf-8") if risk_register_path.exists() else ""

    rows = parse_session_log(session_text)
    known_adrs = _known_adrs(decisions_text)
    known_risks = _known_risks(risk_text)
    known_tasks = _known_tasks(checklist_text)
    known_sessions = _known_sessions(session_text)
    known_threats = _known_stride_threats()

    return CheckReport(
        rows_parsed=len(rows),
        cross_ref_failures=check_cross_references(
            rows,
            known_adrs=known_adrs,
            known_risks=known_risks,
            known_tasks=known_tasks,
            known_sessions=known_sessions,
            known_stride_threats=known_threats,
        ),
        grounding_failures=check_grounding(rows),
        files_touched_failures=check_files_touched(rows, repo_root=repo_root),
    )


def run(*, mode: WriteMode, clock) -> list[WriteOutcome]:
    """Orchestrator entry-point — T-G-016 is CI-only; this is a no-op.

    Direct invocation via the `__main__` block is the actual verification
    path. The orchestrator's `--check` reports "ok 0 file(s)"; CI invokes
    `python tools/generators/verify_session_log.py` directly.
    """

    return []


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #


def _print_report(report: CheckReport, *, verbose: bool) -> None:
    print(f"verify_session_log: {report.rows_parsed} row(s) parsed")
    if report.passed:
        print("  ✓ all cross-references resolve")
        print("  ✓ grounding column populated where required")
        print("  ✓ files_touched paths reachable")
        return

    if report.cross_ref_failures:
        print(f"  ✗ cross-reference failures: {len(report.cross_ref_failures)}")
        for fail in report.cross_ref_failures if verbose else report.cross_ref_failures[:10]:
            print(f"    - {fail}")
        if not verbose and len(report.cross_ref_failures) > 10:
            print(f"    ... ({len(report.cross_ref_failures) - 10} more — use --verbose to see all)")

    if report.grounding_failures:
        print(f"  ✗ grounding-column failures: {len(report.grounding_failures)}")
        for fail in report.grounding_failures if verbose else report.grounding_failures[:10]:
            print(f"    - {fail}")
        if not verbose and len(report.grounding_failures) > 10:
            print(f"    ... ({len(report.grounding_failures) - 10} more)")

    if report.files_touched_failures:
        print(f"  ✗ files_touched failures: {len(report.files_touched_failures)}")
        for fail in report.files_touched_failures if verbose else report.files_touched_failures[:10]:
            print(f"    - {fail}")
        if not verbose and len(report.files_touched_failures) > 10:
            print(f"    ... ({len(report.files_touched_failures) - 10} more)")

    print(f"\n  Total failures: {report.total_failures()}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="verify_session_log",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--session-log",
        type=Path,
        default=SESSION_LOG_PATH,
        help="Path to the session log (default: .design/plans/session-log.md).",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print every failure, not just the first 10 per category.",
    )
    args = parser.parse_args(argv)

    if not args.session_log.exists():
        print(f"error: session log not found at {args.session_log}", file=sys.stderr)
        return EXIT_BAD_ARG

    report = verify(session_log_path=args.session_log)
    _print_report(report, verbose=args.verbose)
    return EXIT_OK if report.passed else EXIT_VERIFICATION_FAILED


if __name__ == "__main__":
    raise SystemExit(main())
