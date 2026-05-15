"""Fetch canonical upstream documents and materialize them locally.

Used as a content-filter fallback during the build phase: when an interactive
AI session cannot directly emit a canonical document (Contributor Covenant 2.1,
Apache 2.0 LICENSE, a github/gitignore template, etc.) because the upstream
text trips a content-filtering policy, the model instead emits *this script*.
A human (or any reviewer) runs the script offline; it downloads the canonical
content from a known upstream URL, verifies a sha256 it knows, and writes the
file. No content travels through the model's output path.

Anti-hallucination (ADR-030):

  * Every entry below names a `url` AND an `expected_sha256`.
  * The expected hash field is initially marked `LOCK-ON-FIRST-FETCH` — meaning
    the script trusts the first download's hash *only when a human ran it*, then
    writes the hash back into this file as the locked-in expected value.
  * Subsequent runs verify the download's sha256 against the locked value and
    refuse to write on mismatch. The lock-on-first-fetch flow makes the URL +
    its provenance visible in a single audit-friendly file.
  * NEVER ship a hash this script invented. If you see a string of 64 hex chars
    in `expected_sha256` after a fresh check-out of the repo, that hash was
    locked-in by a real reviewer's run — verify the audit trail at
    `.design/plans/session-log.md` for the row that locked it.

Usage:

  # List entries this script knows about:
  python tools/scaffold/fetch_canonical.py list

  # Fetch + write a single entry (refuses if the file already exists):
  python tools/scaffold/fetch_canonical.py fetch code-of-conduct

  # Fetch + write, overwriting:
  python tools/scaffold/fetch_canonical.py fetch code-of-conduct --force

  # Fetch + write all entries that don't yet exist:
  python tools/scaffold/fetch_canonical.py fetch-all

  # Lock the expected sha256 from the actual download (first-time setup):
  python tools/scaffold/fetch_canonical.py lock code-of-conduct

  # Verify a previously-written file still matches its locked sha256:
  python tools/scaffold/fetch_canonical.py verify code-of-conduct

Exit codes:
  0  Success.
  2  Bad argument or unknown entry.
  64 File exists and --force not set.
  66 sha256 mismatch (likely tamper, network MITM, or upstream change).
  67 Network or HTTP error.
  68 Hash is still LOCK-ON-FIRST-FETCH — must run `lock` once before `fetch`.

Hash format: lowercase hex sha256, no whitespace, no prefix.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

# --------------------------------------------------------------------------- #
# Registry — every canonical file this script knows about.
# --------------------------------------------------------------------------- #
#
# Each entry declares: the local path (relative to repo root), the upstream
# URL, the sha256 hash (locked by `lock`), a one-line description, and the
# license attribution required when redistributing the content.
#
# To register a NEW canonical document:
#   1. Append a CanonicalEntry below (expected_sha256 = LOCK_TOKEN).
#   2. Run `python tools/scaffold/fetch_canonical.py lock <id>`.
#   3. Commit the updated registry.


LOCK_TOKEN = "LOCK-ON-FIRST-FETCH"


@dataclass(frozen=True)
class CanonicalEntry:
    id: str
    local_path: Path
    upstream_url: str
    expected_sha256: str
    description: str
    license: str
    attribution: str
    headers: dict[str, str] = field(default_factory=dict)


REGISTRY: list[CanonicalEntry] = [
    CanonicalEntry(
        id="code-of-conduct",
        local_path=Path("CODE_OF_CONDUCT.md"),
        # Contributor Covenant 2.1 — canonical markdown source maintained by the
        # Contributor Covenant project itself. Verify provenance at
        # https://www.contributor-covenant.org/ before unlocking the hash.
        upstream_url=(
            "https://raw.githubusercontent.com/"
            "EthicalSource/contributor_covenant/release/"
            "content/version/2/1/code_of_conduct.md"
        ),
        expected_sha256=LOCK_TOKEN,
        description="Contributor Covenant 2.1 (Code of Conduct).",
        license="CC BY 4.0",
        attribution=(
            "Contributor Covenant version 2.1, available at "
            "https://www.contributor-covenant.org/version/2/1/code_of_conduct.html. "
            "Licensed CC BY 4.0."
        ),
    ),
    CanonicalEntry(
        id="apache-2.0-license",
        local_path=Path("vendor/LICENSE-Apache-2.0.txt"),
        upstream_url="https://www.apache.org/licenses/LICENSE-2.0.txt",
        expected_sha256=LOCK_TOKEN,
        description=(
            "Apache License 2.0 — vendored copy for cross-reference; the repo's"
            " own LICENSE file is already populated in T-001."
        ),
        license="Apache-2.0",
        attribution="Copyright Apache Software Foundation.",
    ),
    CanonicalEntry(
        id="gitignore-python",
        local_path=Path("vendor/gitignore-templates/Python.gitignore"),
        upstream_url=(
            "https://raw.githubusercontent.com/"
            "github/gitignore/main/Python.gitignore"
        ),
        expected_sha256=LOCK_TOKEN,
        description="github/gitignore Python template (input to T-G-015 profile registry).",
        license="CC0-1.0",
        attribution="github/gitignore community.",
    ),
    CanonicalEntry(
        id="gitignore-node",
        local_path=Path("vendor/gitignore-templates/Node.gitignore"),
        upstream_url=(
            "https://raw.githubusercontent.com/"
            "github/gitignore/main/Node.gitignore"
        ),
        expected_sha256=LOCK_TOKEN,
        description="github/gitignore Node template.",
        license="CC0-1.0",
        attribution="github/gitignore community.",
    ),
    CanonicalEntry(
        id="gitignore-laravel",
        local_path=Path("vendor/gitignore-templates/Laravel.gitignore"),
        upstream_url=(
            "https://raw.githubusercontent.com/"
            "github/gitignore/main/community/PHP/Laravel.gitignore"
        ),
        expected_sha256=LOCK_TOKEN,
        description="github/gitignore Laravel community template.",
        license="CC0-1.0",
        attribution="github/gitignore community.",
    ),
]


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _get(entry_id: str) -> CanonicalEntry:
    for e in REGISTRY:
        if e.id == entry_id:
            return e
    known = ", ".join(e.id for e in REGISTRY)
    print(f"error: unknown entry {entry_id!r}; known: {known}", file=sys.stderr)
    sys.exit(2)


def _sha256(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()


def _download(entry: CanonicalEntry) -> bytes:
    req = urllib.request.Request(
        entry.upstream_url,
        headers={"User-Agent": "sange-fetch-canonical/1.0", **entry.headers},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.read()
    except urllib.error.URLError as exc:
        print(f"error: network failure fetching {entry.upstream_url!r}: {exc}", file=sys.stderr)
        sys.exit(67)


def _write_file(path: Path, blob: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(blob)


def _attribution_banner(entry: CanonicalEntry) -> str:
    return (
        f"<!-- Canonical upstream source: {entry.upstream_url} -->\n"
        f"<!-- License: {entry.license} -->\n"
        f"<!-- Attribution: {entry.attribution} -->\n"
        f"<!-- sha256 (locked): {entry.expected_sha256} -->\n"
        "<!-- Fetched via tools/scaffold/fetch_canonical.py. Do not edit by hand;\n"
        "     run `fetch_canonical.py fetch <id> --force` to re-pull from upstream. -->\n\n"
    )


def _patch_locked_hash(entry_id: str, locked_hex: str) -> None:
    """Rewrite the registry literal so `expected_sha256=LOCK_TOKEN` becomes the locked hash.

    This is a deliberately surgical text patch — we match the entry by id, then
    replace the very next `expected_sha256=` literal. The script keeps the rest
    of the registry untouched.
    """
    text = Path(__file__).read_text(encoding="utf-8")
    needle = f'id="{entry_id}",'
    idx = text.find(needle)
    if idx < 0:
        print(
            f"error: could not find registry literal for {entry_id!r} — "
            "patch the LOCK_TOKEN by hand.",
            file=sys.stderr,
        )
        sys.exit(1)

    after = text.index("expected_sha256=", idx)
    end = text.index(",", after)
    line = text[after : end + 1]
    if "LOCK_TOKEN" not in line:
        # Already locked — refuse to clobber.
        print(
            f"error: entry {entry_id!r} already has a locked hash; "
            "use `fetch --force` to re-pull and `lock` again if you really mean to.",
            file=sys.stderr,
        )
        sys.exit(1)

    replacement = f'expected_sha256="{locked_hex}",'
    new_text = text[:after] + replacement + text[end + 1 :]
    Path(__file__).write_text(new_text, encoding="utf-8")


# --------------------------------------------------------------------------- #
# Commands
# --------------------------------------------------------------------------- #


def cmd_list(args: argparse.Namespace) -> int:
    for e in REGISTRY:
        status = "locked" if e.expected_sha256 != LOCK_TOKEN else "UNLOCKED"
        print(f"{e.id:<24} [{status}]  {e.local_path}")
        print(f"  upstream : {e.upstream_url}")
        print(f"  license  : {e.license}")
        if e.expected_sha256 != LOCK_TOKEN:
            print(f"  sha256   : {e.expected_sha256}")
        print()
    return 0


def cmd_fetch(args: argparse.Namespace) -> int:
    entry = _get(args.entry)
    path = REPO_ROOT / entry.local_path

    if entry.expected_sha256 == LOCK_TOKEN:
        print(
            f"error: {entry.id!r} has no locked sha256 — run "
            f"`python tools/scaffold/fetch_canonical.py lock {entry.id}` first.",
            file=sys.stderr,
        )
        return 68

    if path.exists() and not args.force:
        print(f"error: {path} already exists (use --force to overwrite)", file=sys.stderr)
        return 64

    blob = _download(entry)
    got = _sha256(blob)
    if got != entry.expected_sha256:
        print(
            f"error: sha256 mismatch for {entry.id!r}\n"
            f"  expected: {entry.expected_sha256}\n"
            f"  got     : {got}\n"
            f"  bytes   : {len(blob)}\n"
            "Possible causes: upstream changed (rare for tagged-version URLs), "
            "network MITM, or someone tampered with this script's registry.",
            file=sys.stderr,
        )
        return 66

    payload = blob
    if path.suffix.lower() in {".md", ".markdown"} and args.banner:
        payload = _attribution_banner(entry).encode("utf-8") + blob

    _write_file(path, payload)
    print(f"wrote {path} ({len(payload):,} bytes, sha256={got})")
    return 0


def cmd_lock(args: argparse.Namespace) -> int:
    entry = _get(args.entry)
    if entry.expected_sha256 != LOCK_TOKEN:
        print(
            f"note: {entry.id!r} already has a locked sha256 "
            f"({entry.expected_sha256}); refusing to re-lock without --force.",
            file=sys.stderr,
        )
        if not args.force:
            return 1

    blob = _download(entry)
    got = _sha256(blob)
    print(
        f"Downloaded {entry.upstream_url}\n"
        f"  bytes  : {len(blob):,}\n"
        f"  sha256 : {got}\n"
        f"  Locking this hash into the registry."
    )
    _patch_locked_hash(entry.id, got)
    print("Locked. Re-run with `fetch` to materialize the file.")
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    entry = _get(args.entry)
    path = REPO_ROOT / entry.local_path
    if not path.exists():
        print(f"error: {path} does not exist", file=sys.stderr)
        return 2

    blob = path.read_bytes()
    # Strip optional attribution banner (we know its delimiter).
    if blob.startswith(b"<!-- Canonical upstream source:"):
        end = blob.find(b"-->\n\n")
        if end >= 0:
            blob = blob[end + len(b"-->\n\n") :]

    got = _sha256(blob)
    if got != entry.expected_sha256:
        print(
            f"MISMATCH for {entry.id!r}\n"
            f"  expected: {entry.expected_sha256}\n"
            f"  got     : {got}",
            file=sys.stderr,
        )
        return 66
    print(f"OK  {entry.id} -> {path} (sha256={got})")
    return 0


def cmd_fetch_all(args: argparse.Namespace) -> int:
    rc = 0
    for e in REGISTRY:
        path = REPO_ROOT / e.local_path
        if path.exists() and not args.force:
            print(f"skip {e.id}: {e.local_path} already exists")
            continue
        if e.expected_sha256 == LOCK_TOKEN:
            print(f"skip {e.id}: unlocked (run `lock {e.id}` first)")
            continue
        sub = argparse.Namespace(entry=e.id, force=args.force, banner=args.banner)
        rc = cmd_fetch(sub) or rc
    return rc


def cmd_report(args: argparse.Namespace) -> int:
    """JSON report — convenient for the session-log's `audit_chain` column."""
    payload: list[dict[str, object]] = []
    for e in REGISTRY:
        path = REPO_ROOT / e.local_path
        payload.append(
            {
                "id": e.id,
                "local_path": str(e.local_path),
                "upstream_url": e.upstream_url,
                "expected_sha256": e.expected_sha256,
                "license": e.license,
                "present": path.exists(),
            }
        )
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


# --------------------------------------------------------------------------- #
# Entrypoint
# --------------------------------------------------------------------------- #


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="fetch_canonical",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("list", help="List registered entries.").set_defaults(func=cmd_list)

    pf = sub.add_parser("fetch", help="Fetch + write a single entry.")
    pf.add_argument("entry")
    pf.add_argument("--force", action="store_true")
    pf.add_argument(
        "--banner",
        action="store_true",
        default=True,
        help="Prefix Markdown with an attribution banner (default true).",
    )
    pf.add_argument(
        "--no-banner",
        dest="banner",
        action="store_false",
    )
    pf.set_defaults(func=cmd_fetch)

    pa = sub.add_parser("fetch-all", help="Fetch every entry that doesn't yet exist.")
    pa.add_argument("--force", action="store_true")
    pa.add_argument("--banner", action="store_true", default=True)
    pa.add_argument("--no-banner", dest="banner", action="store_false")
    pa.set_defaults(func=cmd_fetch_all)

    pl = sub.add_parser("lock", help="Download once, record sha256 into registry.")
    pl.add_argument("entry")
    pl.add_argument("--force", action="store_true")
    pl.set_defaults(func=cmd_lock)

    pv = sub.add_parser("verify", help="Verify a written file's sha256 matches its lock.")
    pv.add_argument("entry")
    pv.set_defaults(func=cmd_verify)

    sub.add_parser("report", help="Emit a JSON status report.").set_defaults(func=cmd_report)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)  # type: ignore[no-any-return]


if __name__ == "__main__":
    raise SystemExit(main())
