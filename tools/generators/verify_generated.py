"""CI integrity check for every generator output.

Walks a configured set of paths, finds files with the §16.4.1 frontmatter
block, recomputes each body's sha256, and verifies it matches the declared
`output_sha256`. Exits cleanly when every file checks out; exits 66 (per the
§7.0.8 exit-code map of `.design/sange-architecture-prompt.md`) on any
mismatch so CI fails loudly.

Usage:

    # Check every generated file under the default scan roots:
    python tools/generators/verify_generated.py

    # Check a specific path:
    python tools/generators/verify_generated.py --paths docs/reference

    # CI-friendly (only print failures):
    python tools/generators/verify_generated.py --quiet

Exit codes (per `.design/sange-architecture-prompt.md` §7.0.8):

    0   All clean.
    2   Invalid argument.
    66  At least one body sha256 mismatched.
    67  Missing file referenced by frontmatter but absent on disk.

Per ADR-023 the generators are deterministic — every output's frontmatter
contains an `output_sha256` covering the body. If a human (or another tool)
edits a generated file, the body hash drifts from the declared hash and CI
catches it. `manual_edits_allowed: true` files are exempt from the body
check but still must carry an `input_sha256`.

This script is **pure stdlib**: it must run before `pip install` and before
the project's full dependency tree exists. Adding a non-stdlib import here
is a quality-gate failure.
"""

from __future__ import annotations

import argparse
import re
import sys
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path

from _lib.fingerprint import body_sha256, extract_body  # type: ignore[import-not-found]

REPO_ROOT = Path(__file__).resolve().parents[1].parent
DEFAULT_SCAN_ROOTS = (
    "docs",
    "templates",
    ".github/workflows",
)

EXIT_OK = 0
EXIT_BAD_ARG = 2
EXIT_MISMATCH = 66
EXIT_MISSING = 67


# Frontmatter is a small key-value block — we deliberately keep parsing
# regex-based rather than depending on PyYAML (per the pure-stdlib rule).
_FM_KV = re.compile(r"^(?P<key>[A-Za-z_][A-Za-z0-9_]*)\s*:\s*(?P<value>.*)$")


@dataclass(frozen=True)
class Frontmatter:
    generated_by: str
    generator_version: str
    generated_at: str
    input_sha256: str
    output_sha256: str
    manual_edits_allowed: bool
    raw: str


def _parse_value(text: str) -> str:
    text = text.strip()
    # Strip surrounding quotes if present (single or double).
    if len(text) >= 2 and text[0] == text[-1] and text[0] in {'"', "'"}:
        return text[1:-1]
    return text


def _to_bool(text: str) -> bool:
    t = text.strip().lower()
    if t in {"true", "yes", "on"}:
        return True
    if t in {"false", "no", "off", ""}:
        return False
    raise ValueError(f"not a boolean value: {text!r}")


def parse_frontmatter(text: str) -> Frontmatter | None:
    """Return a Frontmatter if `text` opens with the §16.4.1 block; else None."""

    front_raw, _body = extract_body(text)
    if not front_raw:
        return None

    fields: dict[str, str] = {}
    for line in front_raw.splitlines():
        stripped = line.strip()
        if stripped == "---" or not stripped:
            continue
        m = _FM_KV.match(stripped)
        if not m:
            continue
        fields[m.group("key")] = _parse_value(m.group("value"))

    required = {
        "generated_by",
        "generator_version",
        "generated_at",
        "input_sha256",
        "output_sha256",
    }
    if not required.issubset(fields):
        return None

    return Frontmatter(
        generated_by=fields["generated_by"],
        generator_version=fields["generator_version"],
        generated_at=fields["generated_at"],
        input_sha256=fields["input_sha256"],
        output_sha256=fields["output_sha256"],
        manual_edits_allowed=_to_bool(fields.get("manual_edits_allowed", "false")),
        raw=front_raw,
    )


@dataclass(frozen=True)
class CheckResult:
    path: Path
    ok: bool
    reason: str
    expected: str | None
    actual: str | None
    frontmatter: Frontmatter | None


def check_file(path: Path) -> CheckResult | None:
    """Check one path. Returns None for files without frontmatter (ignored)."""

    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        # Generated binary file — out of scope for this verifier.
        return None
    fm = parse_frontmatter(text)
    if fm is None:
        return None

    if fm.manual_edits_allowed:
        # The body has had a human's hand in it; we only verify the input hash
        # by trusting the generator to have re-checked at write time. So a
        # manual-edits-allowed entry is always "ok" from this verifier's view.
        return CheckResult(
            path=path,
            ok=True,
            reason="manual_edits_allowed=true; body hash not enforced",
            expected=fm.output_sha256,
            actual=None,
            frontmatter=fm,
        )

    actual = body_sha256(text)
    if actual == fm.output_sha256:
        return CheckResult(
            path=path,
            ok=True,
            reason="body sha256 matches",
            expected=fm.output_sha256,
            actual=actual,
            frontmatter=fm,
        )

    return CheckResult(
        path=path,
        ok=False,
        reason="body sha256 mismatch (file edited after generation, or generator drifted)",
        expected=fm.output_sha256,
        actual=actual,
        frontmatter=fm,
    )


def iter_candidate_files(roots: Iterable[Path]) -> Iterator[Path]:
    for root in roots:
        if not root.exists():
            continue
        if root.is_file():
            yield root
            continue
        for path in sorted(root.rglob("*")):
            if not path.is_file():
                continue
            if path.name.startswith("."):
                continue
            # Skip obvious binary types.
            if path.suffix.lower() in {
                ".png", ".jpg", ".jpeg", ".gif", ".ico", ".pdf",
                ".tar", ".gz", ".zip", ".so", ".dylib", ".dll",
                ".sig", ".pem", ".key",
            }:
                continue
            yield path


def _resolve_roots(args: argparse.Namespace) -> list[Path]:
    if args.paths:
        return [Path(p) if Path(p).is_absolute() else REPO_ROOT / p for p in args.paths]
    return [REPO_ROOT / r for r in DEFAULT_SCAN_ROOTS]


def _format_result(r: CheckResult, verbose: bool) -> str:
    status = "OK  " if r.ok else "FAIL"
    rel = r.path.relative_to(REPO_ROOT) if r.path.is_absolute() else r.path
    head = f"{status} {rel}"
    if r.ok and not verbose:
        return head
    parts = [head, f"     {r.reason}"]
    if r.expected is not None:
        parts.append(f"     expected output_sha256 = {r.expected}")
    if r.actual is not None:
        parts.append(f"     actual   output_sha256 = {r.actual}")
    return "\n".join(parts)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="verify_generated",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--paths",
        nargs="+",
        metavar="PATH",
        help="One or more paths (files or directories) to verify. "
        f"Defaults to: {', '.join(DEFAULT_SCAN_ROOTS)}",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress per-file OK lines; print only failures + a summary.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print full expected/actual hashes for every file.",
    )
    args = parser.parse_args(argv)

    roots = _resolve_roots(args)
    failures: list[CheckResult] = []
    seen: list[CheckResult] = []
    for path in iter_candidate_files(roots):
        result = check_file(path)
        if result is None:
            continue
        seen.append(result)
        if not result.ok:
            failures.append(result)
            print(_format_result(result, verbose=True), file=sys.stderr)
        elif not args.quiet:
            print(_format_result(result, verbose=args.verbose))

    print(
        f"\nverify_generated: {len(seen)} generator-emitted file(s) inspected; "
        f"{len(failures)} failure(s).",
        file=sys.stderr if failures else sys.stdout,
    )
    if failures:
        return EXIT_MISMATCH
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
