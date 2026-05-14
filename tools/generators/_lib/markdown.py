"""Deterministic Markdown helpers — tables, anchors, code blocks, escapes.

The generators that emit Appendix D / E / F / G + the docs index + the
reference docs lean on these. Determinism rules:

  * No `time` / `random` / sorting-by-dict-insertion-order — sort explicitly.
  * Table cells are pipe-escaped (`|` → `\\|`), backslash-escaped at the right
    moment, and never wrap (long content stays in the cell with `<br>` if
    the renderer needs a hint).
  * Headings have predictable slug anchors so `[text](#anchor)` cross-refs
    in one generator match those in another.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence


_SLUG_NON_ALNUM = re.compile(r"[^a-z0-9\s\-]+")
_SLUG_WHITESPACE = re.compile(r"[\s]+")


def slugify(text: str) -> str:
    """GitHub-flavoured anchor slugify.

    Lower-case, strip punctuation other than `-`, collapse whitespace to `-`.
    Stable for the same input forever.
    """

    s = text.strip().lower()
    s = _SLUG_NON_ALNUM.sub("", s)
    s = _SLUG_WHITESPACE.sub("-", s)
    s = s.strip("-")
    return s


def heading(level: int, text: str, *, anchor: str | None = None) -> str:
    """Render a Markdown heading with an HTML anchor when an explicit one is needed.

    `level` is 1..6. GitHub auto-generates anchors from the heading text via
    its own slugifier; pass `anchor=...` only when you need a different one.
    """

    if not 1 <= level <= 6:
        raise ValueError(f"heading level must be 1..6, got {level}")
    prefix = "#" * level
    if anchor is None:
        return f"{prefix} {text}\n"
    return f'<a id="{anchor}"></a>\n{prefix} {text}\n'


def escape_cell(value: object) -> str:
    """Render a table cell payload safely.

    Pipe characters in cells break the table — escape them. Render `None`
    as an empty cell rather than the literal "None".
    """

    if value is None:
        return ""
    text = str(value)
    text = text.replace("\\", "\\\\")
    text = text.replace("|", "\\|")
    # Newlines inside cells break Markdown tables on most renderers. Replace
    # with a `<br>` so the row remains a single line at the parser level.
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\n", "<br>")
    return text


def table(
    headers: Sequence[str],
    rows: Iterable[Sequence[object]],
    *,
    alignments: Sequence[str] | None = None,
) -> str:
    """Render a deterministic Markdown table.

    `alignments`: one of ``"left"``, ``"right"``, ``"center"`` per column;
    when omitted every column is left-aligned (the GitHub default).

    The output is line-terminated by `\\n` (no trailing blank line).
    """

    cols = len(headers)
    if alignments is None:
        alignments = ["left"] * cols
    if len(alignments) != cols:
        raise ValueError(
            f"alignments has {len(alignments)} entries; expected {cols} (one per column)"
        )

    align_markers = []
    for a in alignments:
        if a == "left":
            align_markers.append(":---")
        elif a == "right":
            align_markers.append("---:")
        elif a == "center":
            align_markers.append(":---:")
        else:
            raise ValueError(f"unknown alignment {a!r}")

    out_lines = ["| " + " | ".join(escape_cell(h) for h in headers) + " |"]
    out_lines.append("| " + " | ".join(align_markers) + " |")
    for row in rows:
        if len(row) != cols:
            raise ValueError(
                f"row has {len(row)} cells; expected {cols} (one per column)"
            )
        out_lines.append("| " + " | ".join(escape_cell(c) for c in row) + " |")
    return "\n".join(out_lines) + "\n"


def code_block(content: str, *, lang: str = "") -> str:
    """Fenced code block. `lang` may be empty for plain text."""

    fence = "```"
    # Bump the fence length if `content` contains a triple-backtick run that
    # would otherwise close our block prematurely.
    while fence in content:
        fence += "`"
    head = fence + lang
    return f"{head}\n{content}\n{fence}\n"


def horizontal_rule() -> str:
    return "---\n"


def link(text: str, url: str, *, title: str | None = None) -> str:
    if title is None:
        return f"[{text}]({url})"
    safe_title = title.replace('"', '\\"')
    return f'[{text}]({url} "{safe_title}")'


def bullet_list(items: Iterable[str], *, indent: int = 0) -> str:
    pad = " " * indent
    return "\n".join(f"{pad}- {item}" for item in items) + "\n"
