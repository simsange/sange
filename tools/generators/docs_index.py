"""Generate docs/README.md + docs/tools/README.md from the docs/ tree.

T-G-006 — walks `docs/`, extracts each file's first `# Heading` (skipping any
§16.4.1 YAML frontmatter), groups by top-level sub-directory, and emits two
indexes:

  * `docs/README.md` — the canonical index for the manual. Root `README.md`
    links into this; every other docs/ section is reachable from here.
  * `docs/tools/README.md` — the tools-section index (per-tool walkthroughs
    once the T-G-NNN generators populate that sub-tree).

Determinism (ADR-023):

  * Walk is alphabetically sorted by relative path.
  * Heading extraction is regex-based, deterministic, and tolerant of
    frontmatter + leading whitespace.
  * Re-runs produce byte-identical output when content is byte-identical.

Per ADR-017 + §16.3, the docs/ tree is the manual; the root README is the
1-page entry-point that routes the reader here.
"""

from __future__ import annotations

import datetime as _dt
import json
import re
import sys
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

# --- Path bootstrap ------------------------------------------------------- #
HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent.parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from _lib import markdown  # noqa: E402
from _lib.fingerprint import extract_body, sha256_text  # noqa: E402
from _lib.output import (  # noqa: E402
    GeneratorMetadata,
    WriteMode,
    WriteOutcome,
    write_generated_file,
)

GENERATOR_VERSION = "1.0.0"
GENERATED_BY = "tools/generators/docs_index.py"

DOCS_DIR = REPO_ROOT / "docs"
DOCS_INDEX_PATH = DOCS_DIR / "README.md"
TOOLS_INDEX_PATH = DOCS_DIR / "tools" / "README.md"


# Files that don't appear in the index (the indexes themselves, plus any
# README inside a section that's just an aggregator).
SKIP_NAMES = {"README.md"}


# Section ordering for the canonical index. Subdirectories not in this list
# are appended alphabetically after these.
SECTION_ORDER = (
    "architecture",   # the narrative — first link readers want
    "tools",          # per-tool walkthroughs
    "reference",      # catalogs + schemas
    "security",       # threat model + disclosure
    "adr",            # accepted decisions
    "audit",          # v1/v2 audit findings
    "governance",     # contributing, ADR process, roadmap
    "operations",     # runbooks
    "diagrams",       # rendered SVGs
)


# Friendly title per section — beats "Reference" alone for top-level
# navigation. New subdirs fall through to a Title-Case default.
SECTION_TITLE = {
    "architecture": "Architecture (narrative)",
    "tools": "Per-tool walkthroughs",
    "reference": "Reference (catalogs + schemas)",
    "security": "Security",
    "adr": "Architecture Decision Records",
    "audit": "Audit findings (v1, v2)",
    "governance": "Governance + roadmap",
    "operations": "Operations runbooks",
    "diagrams": "Diagrams",
}


# --------------------------------------------------------------------------- #
# File enumeration + heading extraction
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class DocFile:
    relative_path: str   # always POSIX, relative to DOCS_DIR
    section: str         # top-level subdir; or "_root" for direct children of docs/
    heading: str         # first H1 heading after frontmatter; defaults to filename


_H1 = re.compile(r"^\s*#\s+(?P<text>.+?)\s*$")


def _extract_heading(text: str) -> str | None:
    """Pull the first H1 heading from a markdown body, skipping frontmatter."""

    _front, body = extract_body(text)
    for line in body.splitlines():
        m = _H1.match(line)
        if m:
            return m.group("text").strip()
    return None


def walk_docs(docs_dir: Path) -> list[DocFile]:
    files: list[DocFile] = []
    if not docs_dir.exists():
        return files

    for path in sorted(docs_dir.rglob("*.md")):
        if not path.is_file():
            continue
        if path.name in SKIP_NAMES:
            continue
        if path.name.startswith("."):
            continue
        rel = path.relative_to(docs_dir).as_posix()
        parts = rel.split("/", 1)
        section = parts[0] if len(parts) > 1 else "_root"

        # Heading extraction; tolerate read errors gracefully.
        heading: str | None = None
        try:
            heading = _extract_heading(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError):
            pass
        if not heading:
            # Fallback: use the filename's stem in title-case.
            heading = path.stem.replace("-", " ").replace("_", " ").title()

        files.append(
            DocFile(relative_path=rel, section=section, heading=heading)
        )
    return files


# --------------------------------------------------------------------------- #
# Index rendering
# --------------------------------------------------------------------------- #


def _grouped(files: Iterable[DocFile]) -> dict[str, list[DocFile]]:
    grouped: dict[str, list[DocFile]] = defaultdict(list)
    for f in files:
        grouped[f.section].append(f)
    for section in grouped:
        grouped[section].sort(key=lambda x: x.relative_path)
    return grouped


def _ordered_sections(present: Iterable[str]) -> list[str]:
    present_set = set(present)
    out: list[str] = []
    for s in SECTION_ORDER:
        if s in present_set:
            out.append(s)
            present_set.discard(s)
    out.extend(sorted(present_set))
    return out


def _section_title(section: str) -> str:
    if section == "_root":
        return "Top-level"
    return SECTION_TITLE.get(section, section.replace("-", " ").title())


def _render_main_index(files: list[DocFile]) -> str:
    grouped = _grouped(files)
    parts: list[str] = []
    parts.append(markdown.heading(1, "Sange documentation"))
    parts.append(
        "> Generated by `tools/generators/docs_index.py` (T-G-006). The canonical "
        "index for the manual; root `README.md` links here. Per ADR-017 the root "
        "README is a 1-page entry-point that routes readers into this tree.\n"
    )

    parts.append(markdown.heading(2, "Summary"))
    summary_rows = []
    for section in _ordered_sections(grouped):
        summary_rows.append(
            [
                f"`{section}/`" if section != "_root" else "_top-level_",
                _section_title(section),
                str(len(grouped[section])),
            ]
        )
    summary_rows.append(["**Total**", "", str(len(files))])
    parts.append(
        markdown.table(
            ["Section", "Title", "Files"],
            summary_rows,
            alignments=["left", "left", "right"],
        )
    )
    parts.append("")

    for section in _ordered_sections(grouped):
        docs_in_section = grouped[section]
        section_label = "Top-level docs" if section == "_root" else f"`{section}/` — {_section_title(section)}"
        parts.append(markdown.heading(2, section_label))
        for doc in docs_in_section:
            link = markdown.link(doc.heading, doc.relative_path)
            parts.append(f"- {link} — [`{doc.relative_path}`](./{doc.relative_path})")
        parts.append("")

    parts.append(markdown.heading(2, "Generated content"))
    parts.append(
        "Many files in this tree are generated by `tools/generators/*` scripts "
        "and carry §16.4.1 frontmatter declaring `generated_by` + `output_sha256`. "
        "CI's `python tools/generators/verify_generated.py` enforces integrity "
        "(per ADR-023). To regenerate after a source change:\n"
    )
    parts.append(
        markdown.code_block(
            "python tools/generators/all.py --write    # regenerate every output\n"
            "python tools/generators/verify_generated.py   # verify no drift",
            lang="bash",
        )
    )
    return "\n".join(parts)


def _render_tools_index(files: list[DocFile]) -> str:
    parts: list[str] = []
    parts.append(markdown.heading(1, "Per-tool documentation"))
    parts.append(
        "> Generated by `tools/generators/docs_index.py` (T-G-006). Each Sange "
        "tool / feature gets one walkthrough in this directory; this index is "
        "regenerated as new walkthroughs land.\n"
    )

    tools_files = [f for f in files if f.section == "tools"]
    if not tools_files:
        parts.append(
            "_No per-tool walkthroughs have landed yet. Walkthroughs follow the "
            "§10.4 Category convention — `docs/tools/<category>/<topic>.md` — "
            "and land alongside their corresponding generator output (T-G-008 "
            "exit-codes, T-G-015 profile-registry, etc.). See "
            "[`../README.md`](../README.md) for the full documentation index._\n"
        )
        parts.append("")
        return "\n".join(parts)

    by_category: dict[str, list[DocFile]] = defaultdict(list)
    for f in tools_files:
        # tools/<category>/<topic>.md  →  category = <category>
        sub_path = f.relative_path[len("tools/") :]
        category = sub_path.split("/", 1)[0] if "/" in sub_path else "_root"
        by_category[category].append(f)
    for category in sorted(by_category):
        parts.append(markdown.heading(2, f"`{category}/`"))
        for f in sorted(by_category[category], key=lambda x: x.relative_path):
            parts.append(
                f"- [{f.heading}](../{f.relative_path}) — `{f.relative_path}`"
            )
        parts.append("")
    return "\n".join(parts)


# --------------------------------------------------------------------------- #
# Generator entry-point
# --------------------------------------------------------------------------- #


def _input_sha256(files: list[DocFile]) -> str:
    payload = {
        "generator_version": GENERATOR_VERSION,
        "files": [
            {"path": f.relative_path, "section": f.section, "heading": f.heading}
            for f in files
        ],
    }
    return sha256_text(json.dumps(payload, sort_keys=True))


def run(
    *,
    mode: WriteMode,
    clock: _dt.datetime,
    docs_dir: Path | None = None,
    main_index_path: Path | None = None,
    tools_index_path: Path | None = None,
) -> list[WriteOutcome]:
    """Generator entry-point — emits both index files."""

    root = docs_dir or DOCS_DIR
    main_target = main_index_path or DOCS_INDEX_PATH
    tools_target = tools_index_path or TOOLS_INDEX_PATH

    files = walk_docs(root)

    meta = GeneratorMetadata(
        generated_by=GENERATED_BY,
        generator_version=GENERATOR_VERSION,
        input_sha256=_input_sha256(files),
        manual_edits_allowed=False,
        generated_at=clock,
    )

    main_body = _render_main_index(files)
    tools_body = _render_tools_index(files)

    return [
        write_generated_file(main_target, main_body, meta, mode=mode),
        write_generated_file(tools_target, tools_body, meta, mode=mode),
    ]


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if not (args.write or args.check):
        args.write = True
    mode = WriteMode.WRITE if args.write else WriteMode.CHECK

    results = run(mode=mode, clock=_dt.datetime.now(tz=_dt.UTC))
    rc = 0
    for r in results:
        if r.result is not None and r.result.value != "match":
            rc = 66
        line = f"[{mode.value}] {r.path}  sha256={r.output_sha256}"
        if r.result is not None:
            line += f"  ({r.result.value})"
        print(line)
    raise SystemExit(rc)
