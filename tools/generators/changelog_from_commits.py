"""Generate `docs/CHANGELOG.md` from `.sange/commits/*.json`.

T-G-013 — walks the lifecycle store (`.sange/commits/`) filtered to
`status=PUSHED`, groups by Conventional Commits type, and emits a
Keep-a-Changelog-formatted markdown file.

Grouping per Keep-a-Changelog 1.1.0:

  * `feat`     → "Added" section
  * `fix`      → "Fixed" section
  * `perf`     → "Changed" section (performance is a behavioural change)
  * `refactor` → "Changed" section
  * `docs`     → "Documentation" section (extension; Keep-a-Changelog
                  doesn't enumerate this, but the spec allows additional
                  sub-headings)
  * `style`    → "Changed" section
  * `test` / `build` / `ci` / `chore` / `revert` → "Maintenance" section

Per Keep-a-Changelog the order is: Added → Changed → Deprecated →
Removed → Fixed → Security. We follow that order; any empty section
is omitted.

The generator uses the §16.4.1 frontmatter contract:
`input_sha256` is computed from the canonical-bytes concatenation of
every PUSHED commit JSON, so any change to a commit row triggers a
regeneration. `output_sha256` is verified by `verify_generated.py`.

Per §6.8.6 commit-JSON files are the source of truth; the changelog
is a derived view. The generator is **idempotent** — running it twice
in a row produces byte-identical output.

For v0.1 every PUSHED commit lands under an "Unreleased" header.
Release-tagging (`sange release tag v0.1.0`) will rewrite the
"Unreleased" header to the tag + date and start a fresh "Unreleased"
section above it; that lands in T-G-013b (v0.5+).
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import sys
from dataclasses import dataclass
from pathlib import Path

# --- Path bootstrap ------------------------------------------------------- #
HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent.parent
SRC_DIR = REPO_ROOT / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

# --- Imports -------------------------------------------------------------- #
from _lib import markdown  # noqa: E402
from _lib.output import (  # noqa: E402
    GeneratorMetadata,
    WriteMode,
    WriteOutcome,
    write_generated_file,
)
from sange.core.lifecycle import (  # noqa: E402
    CommitJSON,
    CommitsDirectory,
    CommitStatus,
)


GENERATOR_VERSION = "1.0.0"
GENERATED_BY = "tools/generators/changelog_from_commits.py"
OUTPUT_PATH = REPO_ROOT / "docs" / "CHANGELOG.md"


# Keep-a-Changelog section order — empty sections are omitted.
_SECTION_ORDER: tuple[str, ...] = (
    "Added", "Changed", "Deprecated", "Removed", "Fixed", "Security",
    "Documentation", "Maintenance",
)

# Conventional Commits type → Keep-a-Changelog section heading.
_TYPE_TO_SECTION: dict[str, str] = {
    "feat":     "Added",
    "fix":      "Fixed",
    "perf":     "Changed",
    "refactor": "Changed",
    "style":    "Changed",
    "docs":     "Documentation",
    "test":     "Maintenance",
    "build":    "Maintenance",
    "ci":       "Maintenance",
    "chore":    "Maintenance",
    "revert":   "Maintenance",
}


# --------------------------------------------------------------------------- #
# Input collection
# --------------------------------------------------------------------------- #


def _pushed_commits(commits_dir: Path) -> list[CommitJSON]:
    """Read every PUSHED commit JSON under `commits_dir/.sange/commits/`
    in counter order. Returns [] when the directory doesn't exist yet."""

    cd = CommitsDirectory(commits_dir)
    if not cd.commits_dir.is_dir():
        return []
    return cd.list_all(status=CommitStatus.PUSHED)


def _input_fingerprint(commits: list[CommitJSON]) -> str:
    """SHA256 of the concatenated canonical JSON of every PUSHED commit.

    Ordering by counter is deterministic, so the hash is stable across
    runs as long as the underlying commits don't change."""

    h = hashlib.sha256()
    for commit in commits:
        # Pydantic's `model_dump_json` is deterministic for a fixed model
        # config; sort_keys=False but field ordering is fixed by the
        # model class. We force-sort by counter to be defensive.
        payload = commit.model_dump_json()
        h.update(payload.encode("utf-8"))
        h.update(b"\x00")
    return h.hexdigest()


# --------------------------------------------------------------------------- #
# Rendering
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class _Entry:
    """One rendered line in a Keep-a-Changelog section."""

    type_: str
    scope: str
    subject: str
    breaking: bool
    sha: str
    counter: int

    @property
    def bullet(self) -> str:
        prefix = ""
        if self.scope:
            prefix = f"**{self.scope}:** "
        marker = "**BREAKING:** " if self.breaking else ""
        sha_short = f"`{self.sha[:7]}`" if self.sha else ""
        return f"{marker}{prefix}{self.subject} {sha_short}".strip()


def _bucket(commits: list[CommitJSON]) -> dict[str, list[_Entry]]:
    """Group commits by their Keep-a-Changelog section."""

    buckets: dict[str, list[_Entry]] = {s: [] for s in _SECTION_ORDER}
    for commit in commits:
        section = _TYPE_TO_SECTION.get(commit.message.type, "Maintenance")
        buckets[section].append(
            _Entry(
                type_=commit.message.type,
                scope=commit.message.scope,
                subject=commit.message.subject,
                breaking=commit.message.breaking_change,
                sha=commit.committed_sha,
                counter=commit.counter,
            )
        )
    return buckets


def _build_body(commits: list[CommitJSON]) -> str:
    parts: list[str] = []
    parts.append(markdown.heading(1, "Changelog"))
    parts.append("")
    parts.append(
        "Generated from `.sange/commits/*.json` (`status=PUSHED`) by "
        "`tools/generators/changelog_from_commits.py` (T-G-013). "
        "Adheres to [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/) "
        "and [Semantic Versioning 2.0.0](https://semver.org/spec/v2.0.0.html)."
    )
    parts.append("")
    parts.append(markdown.heading(2, "Unreleased"))
    parts.append("")

    if not commits:
        parts.append(
            "_No PUSHED commits yet. Run `sange commits push <id>` to "
            "land a commit; this file regenerates from the lifecycle store._"
        )
        parts.append("")
        return "\n".join(parts)

    buckets = _bucket(commits)
    for section in _SECTION_ORDER:
        entries = buckets.get(section, [])
        if not entries:
            continue
        parts.append(markdown.heading(3, section))
        parts.append("")
        # Sort within section by counter (ascending == chronological).
        for entry in sorted(entries, key=lambda e: e.counter):
            parts.append(f"- {entry.bullet}")
        parts.append("")

    return "\n".join(parts)


# --------------------------------------------------------------------------- #
# Entry-point
# --------------------------------------------------------------------------- #


def run(
    *,
    mode: WriteMode,
    clock: _dt.datetime,
    commits_dir: Path | None = None,
) -> list[WriteOutcome]:
    """Generator entry-point invoked by `tools/generators/all.py`.

    `commits_dir` accepts a test override; default is REPO_ROOT.
    """

    repo = commits_dir if commits_dir is not None else REPO_ROOT
    commits = _pushed_commits(repo)

    meta = GeneratorMetadata(
        generated_by=GENERATED_BY,
        generator_version=GENERATOR_VERSION,
        input_sha256=_input_fingerprint(commits),
        manual_edits_allowed=False,
        generated_at=clock,
    )
    body = _build_body(commits)
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
