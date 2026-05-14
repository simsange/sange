"""Fallback stub-file generator.

Used when an interactive session hits an "Output blocked by content filtering
policy" error and cannot emit a long-form text file directly. This script
produces a placeholder file with the right frontmatter, the right filename,
and a `TODO: HUMAN REVIEW` marker the user can fill in by hand later.

Usage:
    python tools/scaffold/emit_stub.py \\
        --path CONTRIBUTING.md \\
        --kind markdown \\
        --topic "Contribution guide" \\
        --refers-to ".design/sange-architecture-prompt.md §16.2, ADR-007"

The output is intentionally minimal — just enough that the file is present, the
package can build, and the test/lint pipeline doesn't trip on a missing path.
Phase 0a's generator pipeline (T-G-001 .. T-G-016) eventually replaces these
stubs with the real, schema-validated content.

This script is part of the Sange anti-hallucination discipline (ADR-030):
when uncertain, emit a marker rather than guess at the content.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import sys
from pathlib import Path
from textwrap import dedent

STUB_KINDS = {"markdown", "python", "toml", "yaml", "ini", "text", "json"}


def _now_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _frontmatter(
    kind: str,
    topic: str,
    refers_to: str,
    body: str,
) -> str:
    """Render kind-appropriate frontmatter + the stub body."""

    output_sha = hashlib.sha256(body.encode("utf-8")).hexdigest()

    if kind in {"markdown"}:
        return dedent(
            f"""\
            ---
            generated_by: tools/scaffold/emit_stub.py
            generated_at: {_now_iso()}
            kind: {kind}
            topic: {topic!r}
            refers_to: {refers_to!r}
            output_sha256: {output_sha}
            stub: true
            review_required: true
            ---

            <!-- TODO: HUMAN REVIEW — this file was emitted as a content-filter fallback. -->
            <!-- Replace this body with the real content; keep the frontmatter so CI's     -->
            <!-- tools/generators/verify_generated.py can detect when the stub is gone.     -->

            # {topic}

            > **Stub.** This file is a placeholder. See `{refers_to}` for the source-of-truth
            > spec, then replace this body with the canonical text. Once replaced, the
            > frontmatter's `stub: true` flips to `stub: false` (or the frontmatter is
            > removed entirely if no other generator owns this file).

            {body}
            """
        )
    elif kind == "python":
        return dedent(
            f"""\
            # generated_by: tools/scaffold/emit_stub.py
            # generated_at: {_now_iso()}
            # kind: {kind}
            # topic: {topic!r}
            # refers_to: {refers_to!r}
            # output_sha256: {output_sha}
            # stub: true
            # review_required: true
            \"\"\"{topic} — stub. See {refers_to}. TODO: human review.\"\"\"

            {body}
            """
        )
    elif kind in {"toml", "ini"}:
        return dedent(
            f"""\
            # generated_by = "tools/scaffold/emit_stub.py"
            # generated_at = "{_now_iso()}"
            # kind = "{kind}"
            # topic = "{topic}"
            # refers_to = "{refers_to}"
            # output_sha256 = "{output_sha}"
            # stub = true
            # review_required = true
            # TODO: human review.

            {body}
            """
        )
    elif kind == "yaml":
        return dedent(
            f"""\
            # generated_by: tools/scaffold/emit_stub.py
            # generated_at: {_now_iso()}
            # kind: {kind}
            # topic: {topic!r}
            # refers_to: {refers_to!r}
            # output_sha256: {output_sha}
            # stub: true
            # review_required: true
            # TODO: human review.

            {body}
            """
        )
    elif kind == "json":
        # JSON can't carry frontmatter comments; embed metadata as a top-level key.
        # Body must already be a JSON object/array. We don't validate here.
        return body
    else:
        # plain text
        return dedent(
            f"""\
            # generated_by: tools/scaffold/emit_stub.py
            # generated_at: {_now_iso()}
            # kind: {kind}
            # topic: {topic!r}
            # refers_to: {refers_to!r}
            # output_sha256: {output_sha}
            # stub: true
            # review_required: true
            # TODO: human review.

            {body}
            """
        )


def emit(
    path: Path,
    kind: str,
    topic: str,
    refers_to: str,
    body: str = "",
    force: bool = False,
) -> int:
    if kind not in STUB_KINDS:
        print(f"error: unknown kind {kind!r}; allowed: {sorted(STUB_KINDS)}", file=sys.stderr)
        return 2

    if path.exists() and not force:
        print(f"error: {path} already exists (use --force to overwrite)", file=sys.stderr)
        return 64

    rendered = _frontmatter(kind, topic, refers_to, body)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(rendered, encoding="utf-8")
    print(f"wrote {path} ({len(rendered):,} bytes, kind={kind}, stub=true)")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--path", required=True, type=Path, help="Output file path.")
    parser.add_argument(
        "--kind",
        required=True,
        choices=sorted(STUB_KINDS),
        help="File kind for frontmatter style.",
    )
    parser.add_argument(
        "--topic",
        required=True,
        help="Short label of what this file is meant to contain.",
    )
    parser.add_argument(
        "--refers-to",
        required=True,
        help="Source-of-truth reference (§-anchor in the prompt, ADR-NNN, etc.).",
    )
    parser.add_argument(
        "--body",
        default="",
        help="Optional body text to place under the frontmatter.",
    )
    parser.add_argument(
        "--body-file",
        type=Path,
        help="Read body from a file rather than --body.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite an existing file.",
    )
    args = parser.parse_args(argv)

    body = args.body
    if args.body_file is not None:
        body = args.body_file.read_text(encoding="utf-8")

    return emit(
        path=args.path,
        kind=args.kind,
        topic=args.topic,
        refers_to=args.refers_to,
        body=body,
        force=args.force,
    )


if __name__ == "__main__":
    raise SystemExit(main())
