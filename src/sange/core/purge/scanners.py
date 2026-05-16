"""§6.11.4 gate 8 — gitleaks + trufflehog pre-run against the mirror.

> "Scanner pre-run. A `gitleaks` + `trufflehog` scan runs against the
> *current* repo and the *post-rewrite* mirror; the rewrite is
> rejected if the post-rewrite scan finds *more* findings of the same
> kind than the pre-rewrite scan (regression detection)." — §6.11.4

This module ships the pre-rewrite scan only (v0.5 read-only scope).
The "post-rewrite scan + regression rejection" is a v1.0 concern
that consumes this module's `ScannerResult` as a baseline.

Approach: shell out via `run_streamed` (one audit chain entry +
0600 transcript per tool). Each scanner returns a `ScannerResult`
with the parsed findings count plus enough metadata for the audit
payload + plan.scanner_results merge.

Tool detection: `shutil.which()` finds the binary on PATH. Tests
inject `tool_path` directly so they don't depend on host tooling.
When a tool is absent, the result has `available=False` /
`returncode=-1` and no chain event is appended — the v0.5 scope
calls these "soft" preconditions, not hard fails.
"""

from __future__ import annotations

import json as _json
import shutil
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from sange.core.audit import AuditChain, EventKind
from sange.core.purge.plan import PurgePlan
from sange.core.streaming import run_streamed

# Internal type aliases for the scanner-runner shape.
_ArgvBuilder = Callable[[Path], list[str]]
_FindingsParser = Callable[[Path], int]


class ScannerError(Exception):
    """Raised when a scanner invocation can't proceed."""


# Sentinel for "tool not found on PATH" results. Real transcripts
# always live under `.sange/audit/transcripts/`, never under `/dev`.
_NO_TRANSCRIPT: Final[Path] = Path("/dev/null")


@dataclass(frozen=True)
class ScannerResult:
    """Outcome of one scanner invocation.

    Fields:
      * `name`             — `"gitleaks"` or `"trufflehog"`.
      * `available`        — True iff the binary was found on PATH.
      * `returncode`       — child's exit code; `-1` if not available.
      * `findings_count`   — parsed from tool's JSON output. `0` when
                             not available or when the tool found
                             nothing.
      * `event_id`         — audit chain event id. `""` when not
                             available (no subprocess fired).
      * `transcript_path`  — absolute path to the transcript log.
                             `/dev/null` when not available.
    """

    name: str
    available: bool
    returncode: int
    findings_count: int
    event_id: str
    transcript_path: Path

    @property
    def succeeded(self) -> bool:
        """True iff the scanner ran AND exited cleanly.

        Some scanners (gitleaks) exit non-zero ON FINDING leaks — that's
        a "successfully found things" outcome, not a failure. Callers
        that want "tool ran cleanly OR found stuff" should check
        `available and returncode in (0, 1)`.
        """

        return self.available and self.returncode == 0


def run_gitleaks(
    plan: PurgePlan,
    mirror_path: Path,
    *,
    audit_chain: AuditChain,
    actor: str,
    tool_path: Path | None = None,
    timeout: float = 300.0,
) -> ScannerResult:
    """Scan the mirror with `gitleaks git`.

    gitleaks exits 1 when it finds secrets and 0 when it finds none
    — both are "successful runs". A returncode of 2+ indicates a
    crash / config error / unsupported flag.
    """

    return _run_scanner(
        name="gitleaks",
        plan=plan,
        mirror_path=mirror_path,
        audit_chain=audit_chain,
        actor=actor,
        tool_path=tool_path,
        timeout=timeout,
        build_argv=lambda binary: [
            str(binary),
            "git",
            str(mirror_path),
            "--no-banner",
            "--report-format=json",
            "--report-path=-",
        ],
        parse_findings=_parse_gitleaks_findings,
    )


def run_trufflehog(
    plan: PurgePlan,
    mirror_path: Path,
    *,
    audit_chain: AuditChain,
    actor: str,
    tool_path: Path | None = None,
    timeout: float = 300.0,
) -> ScannerResult:
    """Scan the mirror with `trufflehog git`.

    trufflehog's `--json` flag emits NDJSON (one finding per line). The
    findings count is the number of well-formed JSON objects on stdout.
    """

    return _run_scanner(
        name="trufflehog",
        plan=plan,
        mirror_path=mirror_path,
        audit_chain=audit_chain,
        actor=actor,
        tool_path=tool_path,
        timeout=timeout,
        build_argv=lambda binary: [
            str(binary),
            "git",
            f"file://{mirror_path}",
            "--json",
            "--no-update",
        ],
        parse_findings=_parse_trufflehog_findings,
    )


def run_scanners(
    plan: PurgePlan,
    mirror_path: Path,
    *,
    audit_chain: AuditChain,
    actor: str,
    timeout: float = 300.0,
) -> tuple[ScannerResult, ScannerResult]:
    """Convenience — run both scanners + return (gitleaks_result, trufflehog_result).

    Sequential, not concurrent: scanning is the wall-clock bottleneck
    of the purge preflight, but running two scanners in parallel
    doubles disk I/O against the mirror's pack file with no clear
    win. Sequential keeps the audit chain entries in a predictable
    order.
    """

    return (
        run_gitleaks(
            plan, mirror_path, audit_chain=audit_chain, actor=actor,
            timeout=timeout,
        ),
        run_trufflehog(
            plan, mirror_path, audit_chain=audit_chain, actor=actor,
            timeout=timeout,
        ),
    )


# --------------------------------------------------------------------------- #
# Internals
# --------------------------------------------------------------------------- #


def _run_scanner(
    *,
    name: str,
    plan: PurgePlan,
    mirror_path: Path,
    audit_chain: AuditChain,
    actor: str,
    tool_path: Path | None,
    timeout: float,
    build_argv: _ArgvBuilder,
    parse_findings: _FindingsParser,
) -> ScannerResult:
    if not mirror_path.is_dir():
        raise ScannerError(f"mirror not found: {mirror_path}")

    binary = tool_path or _which_optional(name)
    if binary is None:
        return ScannerResult(
            name=name,
            available=False,
            returncode=-1,
            findings_count=0,
            event_id="",
            transcript_path=_NO_TRANSCRIPT,
        )

    argv = build_argv(binary)
    result = run_streamed(
        argv,
        audit_chain=audit_chain,
        actor=actor,
        event_kind=EventKind.GENERIC,
        payload={
            "phase": f"scan-{name}",
            "plan_id": plan.plan_id,
            "mirror_path": str(mirror_path),
        },
        timeout=timeout,
    )

    findings_count = parse_findings(result.transcript_path)
    return ScannerResult(
        name=name,
        available=True,
        returncode=result.returncode,
        findings_count=findings_count,
        event_id=result.event_id,
        transcript_path=result.transcript_path,
    )


def _which_optional(name: str) -> Path | None:
    found = shutil.which(name)
    return Path(found) if found else None


def _stdout_text(transcript_path: Path) -> str:
    """Extract only `[stdout] ` lines from a streaming-helper transcript.

    Same pattern as `mirror._capture_refs` + `analyzer._stdout_lines`.
    """

    text = transcript_path.read_text(encoding="utf-8")
    out: list[str] = []
    for raw in text.splitlines():
        if raw.startswith("[stdout] "):
            out.append(raw[len("[stdout] "):])
    return "\n".join(out)


def _parse_gitleaks_findings(transcript_path: Path) -> int:
    """gitleaks JSON output is a JSON ARRAY when `--report-path=-` is used.

    Length of the array = finding count. Empty array (`[]`) on a clean
    repo. Malformed output (truncated, etc.) is treated as zero —
    the audit chain has the transcript for forensics; we don't
    pretend to parse what isn't there.
    """

    raw = _stdout_text(transcript_path).strip()
    if not raw:
        return 0
    try:
        parsed = _json.loads(raw)
    except _json.JSONDecodeError:
        return 0
    if isinstance(parsed, list):
        return len(parsed)
    return 0


def _parse_trufflehog_findings(transcript_path: Path) -> int:
    """trufflehog's `--json` emits NDJSON. Count well-formed lines.

    Each line is one finding (or one diagnostic). We count only the
    lines that parse as JSON objects with at least one key — that
    filters out empty `{}` heartbeats and the occasional bare `null`.
    """

    text = _stdout_text(transcript_path)
    count = 0
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        try:
            parsed = _json.loads(stripped)
        except _json.JSONDecodeError:
            continue
        if isinstance(parsed, dict) and parsed:
            count += 1
    return count


__all__ = [
    "ScannerError",
    "ScannerResult",
    "run_gitleaks",
    "run_scanners",
    "run_trufflehog",
]
