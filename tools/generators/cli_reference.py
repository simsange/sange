"""Generate `docs/reference/cli-reference.md` from the live typer app.

T-G-009 — introspects `sange.cli:app` and emits a deterministic
command reference. The on-disk artifact carries §16.4.1 frontmatter
with `output_sha256` so `verify_generated.py` detects manual edits.

Determinism guarantees:

  * Commands are walked in alphabetical order at every depth.
  * Option lists are sorted by their primary long-form flag.
  * The `input_sha256` covers the live click-command tree — any change
    to `src/sange/cli/*.py` mutates the rendered help text and so
    mutates the hash. CI re-runs after every cli edit.

Per ADR-029 the generator runs on a fresh clone; per ADR-023 it
re-uses the `_lib/{output,markdown,fingerprint}` primitives so the
output shape matches every other generator's frontmatter contract.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# --- Path bootstrap ------------------------------------------------------- #
HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent.parent
SRC_DIR = REPO_ROOT / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

# --- Imports (after path bootstrap) --------------------------------------- #
import click  # noqa: E402
import typer  # noqa: E402
from _lib import markdown  # noqa: E402
from _lib.output import (  # noqa: E402
    GeneratorMetadata,
    WriteMode,
    WriteOutcome,
    write_generated_file,
)

from sange.cli import app as _cli_app  # noqa: E402

GENERATOR_VERSION = "1.0.0"
GENERATED_BY = "tools/generators/cli_reference.py"
OUTPUT_PATH = REPO_ROOT / "docs" / "reference" / "cli-reference.md"


# --------------------------------------------------------------------------- #
# Walk the click-command tree (typer apps compose to click groups).
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class _Option:
    flags: tuple[str, ...]
    help: str
    is_flag: bool
    default: Any
    required: bool


@dataclass(frozen=True)
class _Argument:
    name: str
    required: bool


@dataclass(frozen=True)
class _CommandNode:
    invocation: str           # `sange`, `sange ai preview`, …
    help: str
    is_group: bool
    options: tuple[_Option, ...]
    arguments: tuple[_Argument, ...]
    children: tuple[_CommandNode, ...]


def _root_command() -> click.Command:
    """The live click-command tree for the typer app."""

    return typer.main.get_command(_cli_app)


def _format_flags(param: click.Option) -> tuple[str, ...]:
    """Sorted tuple of the option's flag strings."""

    # click stores opts as a list; preserve order for help-text fidelity but
    # canonical the rendering by sorting short-form last.
    flags = tuple(param.opts) + tuple(param.secondary_opts)
    return tuple(sorted(flags, key=lambda s: (not s.startswith("--"), s)))


def _walk(node: click.Command, invocation: str) -> _CommandNode:
    options: list[_Option] = []
    arguments: list[_Argument] = []
    for p in node.params:
        if isinstance(p, click.Option):
            options.append(
                _Option(
                    flags=_format_flags(p),
                    help=p.help or "",
                    is_flag=bool(p.is_flag),
                    default=p.default if not callable(p.default) else None,
                    required=bool(p.required),
                )
            )
        elif isinstance(p, click.Argument):
            arguments.append(
                _Argument(name=p.name or "", required=bool(p.required))
            )

    options.sort(key=lambda o: o.flags[0] if o.flags else "")
    arguments.sort(key=lambda a: a.name)

    children: list[_CommandNode] = []
    if isinstance(node, click.Group):
        for sub_name in sorted(node.commands.keys()):
            sub = node.commands[sub_name]
            children.append(_walk(sub, f"{invocation} {sub_name}"))

    return _CommandNode(
        invocation=invocation,
        help=(node.help or "").strip(),
        is_group=isinstance(node, click.Group),
        options=tuple(options),
        arguments=tuple(arguments),
        children=tuple(children),
    )


# --------------------------------------------------------------------------- #
# Input fingerprint — captures every command's invocation + help + options.
# --------------------------------------------------------------------------- #


def _fingerprint(node: _CommandNode) -> str:
    """Stable sha256 of the entire tree's shape + content."""

    h = hashlib.sha256()

    def _hash_node(n: _CommandNode) -> None:
        h.update(n.invocation.encode("utf-8"))
        h.update(b"\x00")
        h.update(n.help.encode("utf-8"))
        h.update(b"\x00")
        for o in n.options:
            h.update("|".join(o.flags).encode("utf-8"))
            h.update(b"\x01")
            h.update(o.help.encode("utf-8"))
            h.update(b"\x01")
            h.update(repr(o.default).encode("utf-8"))
            h.update(b"\x02")
        for a in n.arguments:
            h.update(a.name.encode("utf-8"))
            h.update(b":req" if a.required else b":opt")
            h.update(b"\x02")
        for c in n.children:
            _hash_node(c)

    _hash_node(node)
    return h.hexdigest()


# --------------------------------------------------------------------------- #
# Render
# --------------------------------------------------------------------------- #


def _flatten(node: _CommandNode) -> list[_CommandNode]:
    """Depth-first flattening, deterministic order (alphabetical)."""

    out = [node]
    for c in node.children:
        out.extend(_flatten(c))
    return out


def _format_default(default: Any) -> str:
    if default is None:
        return ""
    if isinstance(default, bool):
        return str(default).lower()
    if isinstance(default, (list, tuple)):
        if not default:
            return ""
        return ", ".join(str(x) for x in default)
    if default == "":
        return ""
    return f"`{default}`"


def _render_section(node: _CommandNode) -> str:
    parts: list[str] = []
    parts.append(markdown.heading(3, f"`{node.invocation}`"))
    parts.append("")
    if node.help:
        parts.append(node.help)
        parts.append("")

    if node.arguments:
        parts.append("**Arguments:**\n")
        rows = [
            [f"`{a.name}`", "required" if a.required else "optional"]
            for a in node.arguments
        ]
        parts.append(markdown.table(["Name", "Status"], rows))
        parts.append("")

    if node.options:
        parts.append("**Options:**\n")
        rows = []
        for o in node.options:
            flag_str = ", ".join(f"`{f}`" for f in o.flags)
            kind = "flag" if o.is_flag else "value"
            rows.append(
                [
                    flag_str,
                    kind,
                    _format_default(o.default),
                    o.help or "",
                ]
            )
        parts.append(
            markdown.table(
                ["Flag", "Kind", "Default", "Description"],
                rows,
            )
        )
        parts.append("")

    if node.is_group and node.children:
        parts.append("**Sub-commands:**\n")
        sub_rows = [
            [f"`{c.invocation}`", c.help or ""] for c in node.children
        ]
        parts.append(markdown.table(["Sub-command", "Description"], sub_rows))
        parts.append("")

    return "\n".join(parts)


def _build_body(tree: _CommandNode) -> str:
    parts: list[str] = []
    parts.append(markdown.heading(1, "Sange CLI reference"))
    parts.append("")
    parts.append(
        "> Generated from the live `sange.cli:app` (typer) by "
        "`tools/generators/cli_reference.py` (T-G-009). Source-of-truth "
        "for command behaviour: the Python decorators on each command "
        "function in `src/sange/cli/`. Update the code; this file "
        "regenerates from CI."
    )
    parts.append("")
    parts.append(
        "Every entry below is auto-introspected from the live click "
        "command tree, so flag ordering, help text, and defaults stay "
        "in lock-step with the implementation. Manual edits to this "
        "file are rejected by `verify_generated.py`."
    )
    parts.append("")

    parts.append(markdown.heading(2, "Command index"))
    parts.append("")
    flat = _flatten(tree)
    index_rows = [
        [f"`{n.invocation}`", n.help.split("\n", 1)[0] if n.help else ""]
        for n in flat
    ]
    parts.append(markdown.table(["Command", "Summary"], index_rows))
    parts.append("")

    parts.append(markdown.heading(2, "Commands"))
    parts.append("")
    for node in flat:
        parts.append(_render_section(node))

    parts.append(markdown.heading(2, "Exit codes"))
    parts.append("")
    parts.append(
        "See [`docs/reference/exit-codes.md`](exit-codes.md) for the "
        "canonical mapping. CLI commands return the codes documented "
        "there; `sange doctor` returns non-zero when any check fails."
    )
    parts.append("")

    return "\n".join(parts)


# --------------------------------------------------------------------------- #
# Entry-point
# --------------------------------------------------------------------------- #


def _build_tree() -> _CommandNode:
    root = _root_command()
    return _walk(root, invocation="sange")


def run(
    *,
    mode: WriteMode,
    clock: _dt.datetime,
    tree: _CommandNode | None = None,
) -> list[WriteOutcome]:
    """Generator entry-point invoked by `tools/generators/all.py`.

    `tree` accepts an override for tests that want to render a curated
    sub-tree instead of the live app.
    """

    if tree is None:
        tree = _build_tree()

    meta = GeneratorMetadata(
        generated_by=GENERATED_BY,
        generator_version=GENERATOR_VERSION,
        input_sha256=_fingerprint(tree),
        manual_edits_allowed=False,
        generated_at=clock,
    )
    body = _build_body(tree)
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
