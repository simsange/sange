"""Manpage and help-output parsers for `git`, `svn`, `hg`, `p4`.

The catalog generators (T-G-001 git, T-G-002 svn, T-G-014 hg/p4) consume these
to produce Appendix D / E / F rows. Two concerns are intentionally separated:

  * `run_*` — subprocess wrappers (I/O; tested via fixture replay only).
  * `parse_*` — pure functions over text (deterministic; trivially fuzz-able).

That split is what keeps the generators reproducible inside CI even when the
exact installed binary differs from the developer's machine: CI runs the
parsers against checked-in fixture output rather than re-shelling out.

Anti-hallucination (ADR-030): the parsers tolerate the loose, free-text shape
of help output by being conservative. Lines we don't recognise are returned
as `UnclassifiedLine` rather than silently dropped, so a fixture-replay CI
diff surfaces format drift the next time `git help -a` changes its layout.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

# --------------------------------------------------------------------------- #
# Data shapes
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class CommandEntry:
    """A command name + its one-line description (as printed by `<vcs> help`).

    `section` is the section header the command appeared under (e.g. "Main
    Porcelain Commands" for git, "Available subcommands" for svn). Empty
    when the help output has no sections.
    """

    name: str
    short_description: str
    section: str = ""

    def __lt__(self, other: object) -> bool:  # deterministic sort fallback
        if not isinstance(other, CommandEntry):
            return NotImplemented
        return (self.section, self.name) < (other.section, other.name)


@dataclass(frozen=True)
class UnclassifiedLine:
    """A line the parser didn't recognise — kept so format drift is visible."""

    text: str
    line_number: int


@dataclass(frozen=True)
class ParseResult:
    commands: tuple[CommandEntry, ...]
    unclassified: tuple[UnclassifiedLine, ...] = field(default=())

    def names(self) -> tuple[str, ...]:
        return tuple(sorted({c.name for c in self.commands}))


# --------------------------------------------------------------------------- #
# Subprocess wrappers (I/O)
# --------------------------------------------------------------------------- #


class CommandNotFound(RuntimeError):
    """The wrapped binary (`git`, `svn`, etc.) is not on PATH."""


def _run(binary: str, args: Sequence[str], cwd: Path | None = None) -> str:
    """Run `<binary> <args>`. Return stdout as text.

    Raises `CommandNotFound` if the binary isn't on PATH; raises
    `subprocess.CalledProcessError` on non-zero exit. Environment is
    cleaned of locale variables so output is reproducible across machines,
    but PATH is preserved so non-`/usr/bin` binaries (Homebrew, ServBay,
    asdf, mise, etc.) still resolve in the child process.
    """

    import os

    if shutil.which(binary) is None:
        raise CommandNotFound(
            f"{binary!r} not found on PATH — install it or supply fixture text"
        )

    env = {
        # PATH must be preserved — subprocess.run inherits None env, then
        # filtered; without PATH the child can't find binaries that
        # shutil.which (which uses the parent's PATH) just resolved.
        "PATH": os.environ.get("PATH", ""),
        # HOME is needed by many tools for config-file discovery (e.g. git
        # consults ~/.gitconfig; without HOME it'd fail with "git config:
        # unable to read config file").
        "HOME": os.environ.get("HOME", ""),
        # Force C locale so help output is en_US.UTF-8 with no per-system
        # message catalogue substitutions.
        "LC_ALL": "C",
        "LANG": "C",
        # Strip pager so output streams plainly.
        "PAGER": "cat",
        "GIT_PAGER": "cat",
        # No interactive prompts.
        "GIT_TERMINAL_PROMPT": "0",
    }
    result = subprocess.run(
        [binary, *list(args)],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        check=True,
        encoding="utf-8",
    )
    return result.stdout


def run_git(args: Sequence[str], cwd: Path | None = None) -> str:
    return _run("git", args, cwd=cwd)


def run_svn(args: Sequence[str]) -> str:
    return _run("svn", args)


def run_hg(args: Sequence[str]) -> str:
    return _run("hg", args)


def run_p4(args: Sequence[str]) -> str:
    return _run("p4", args)


# --------------------------------------------------------------------------- #
# Parsers (pure)
# --------------------------------------------------------------------------- #


# `git help -a` lines look like:
#   "Main Porcelain Commands"
#   ""
#   "   add                Add file contents to the index"
#   "   am                 Apply a series of patches from a mailbox"
# Section headers are unindented and non-blank; command rows start with two
# or more spaces, then the command name (no spaces), then ≥2 spaces, then
# the description.
_GIT_COMMAND_LINE = re.compile(
    r"^(?P<indent>\s+)(?P<name>[\w\-+.]+)\s{2,}(?P<desc>.+?)\s*$"
)
# Section headers in `git help -a`: an uppercase-leading line containing
# letters, spaces, slashes, hyphens, digits. Examples observed in real git
# output: "Main Porcelain Commands", "Ancillary Commands / Manipulators",
# "Low-level Commands / Internal Helpers", "External commands".
_GIT_SECTION_HEADER = re.compile(r"^[A-Z][\w /\-]+$")


def parse_git_help_all(text: str) -> ParseResult:
    """Parse `git help -a --no-verbose --no-aliases` output.

    Sections are tracked. Commands are returned in the order they appear so
    callers can preserve canonical ordering. The parser is tolerant of
    blank lines, the leading "See 'git help ...'" preamble, and the
    "External commands" section (which we keep).
    """

    commands: list[CommandEntry] = []
    unclassified: list[UnclassifiedLine] = []
    section = ""

    for line_no, raw in enumerate(text.splitlines(), start=1):
        line = raw.rstrip()
        if not line.strip():
            continue
        # Section header — unindented, no leading whitespace, no `--` etc.
        if line == line.lstrip() and _GIT_SECTION_HEADER.match(line.rstrip(":")):
            section = line.rstrip(":")
            continue
        m = _GIT_COMMAND_LINE.match(line)
        if m:
            commands.append(
                CommandEntry(
                    name=m.group("name"),
                    short_description=m.group("desc"),
                    section=section,
                )
            )
            continue
        if line.lower().startswith("see 'git help"):
            continue
        unclassified.append(UnclassifiedLine(text=line, line_number=line_no))

    return ParseResult(
        commands=tuple(commands),
        unclassified=tuple(unclassified),
    )


# `svn help` lists subcommands as:
#    add                  Put new files and directories under version control.
#    blame (praise, ...)  Show when each line of a file was last (or first) modified.
# Each entry indented by ≥3 spaces; the name section may include parenthesized
# aliases.
_SVN_COMMAND_LINE = re.compile(
    r"^\s{3,}(?P<name>[\w\-]+)"
    r"(?:\s*\((?P<aliases>[^)]+)\))?"
    r"\s{2,}(?P<desc>.+?)\s*$"
)


def parse_svn_help(text: str) -> ParseResult:
    """Parse `svn help` (no subcommand) output.

    Returns one CommandEntry per primary name. Aliases become additional
    entries with the same description, so Appendix E can render them as
    cross-references.
    """

    commands: list[CommandEntry] = []
    unclassified: list[UnclassifiedLine] = []

    capture = False
    for line_no, raw in enumerate(text.splitlines(), start=1):
        line = raw.rstrip()
        stripped = line.strip()
        if "Available subcommands" in stripped:
            capture = True
            continue
        if not capture:
            continue
        if not stripped:
            continue
        m = _SVN_COMMAND_LINE.match(line)
        if m:
            commands.append(
                CommandEntry(
                    name=m.group("name"),
                    short_description=m.group("desc"),
                    section="Available subcommands",
                )
            )
            aliases = m.group("aliases")
            if aliases:
                for alias in (a.strip() for a in aliases.split(",")):
                    if alias:
                        commands.append(
                            CommandEntry(
                                name=alias,
                                short_description=m.group("desc")
                                + f" (alias of `svn {m.group('name')}`)",
                                section="Available subcommands",
                            )
                        )
            continue
        unclassified.append(UnclassifiedLine(text=line, line_number=line_no))

    return ParseResult(
        commands=tuple(commands),
        unclassified=tuple(unclassified),
    )


# `hg help` lines look like:
#    add           add the specified files on the next commit
# Indented by ≥1 space; name; ≥2 spaces; description.
_HG_COMMAND_LINE = re.compile(
    r"^\s+(?P<name>[\w\-]+)\s{2,}(?P<desc>.+?)\s*$"
)


def parse_hg_help(text: str) -> ParseResult:
    """Parse `hg help` output."""

    commands: list[CommandEntry] = []
    unclassified: list[UnclassifiedLine] = []
    section = ""
    capture = False

    for line_no, raw in enumerate(text.splitlines(), start=1):
        line = raw.rstrip()
        stripped = line.strip()
        if stripped.endswith(":") and not stripped.startswith(" "):
            section = stripped.rstrip(":")
            capture = True
            continue
        if not capture or not stripped:
            continue
        m = _HG_COMMAND_LINE.match(line)
        if m:
            commands.append(
                CommandEntry(
                    name=m.group("name"),
                    short_description=m.group("desc"),
                    section=section,
                )
            )
            continue
        unclassified.append(UnclassifiedLine(text=line, line_number=line_no))

    return ParseResult(
        commands=tuple(commands),
        unclassified=tuple(unclassified),
    )


# --------------------------------------------------------------------------- #
# Synopsis extraction (for the per-command `git help <cmd>` man pages)
# --------------------------------------------------------------------------- #


_SYNOPSIS_HEADERS = ("SYNOPSIS", "synopsis", "Synopsis")


def extract_synopsis(manpage_text: str) -> str:
    """Pull the SYNOPSIS section from a man-page-shaped text.

    Returns the contiguous block starting at the line after a `SYNOPSIS`
    header until the next ALL-CAPS section header. Returns an empty string
    if no synopsis section is found.
    """

    lines = manpage_text.splitlines()
    inside = False
    out: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not inside:
            if stripped in _SYNOPSIS_HEADERS:
                inside = True
            continue
        # End of synopsis when we hit the next section header (ALL CAPS, 3+ chars,
        # at column 0 or with minimal indentation).
        if stripped and stripped == stripped.upper() and 3 <= len(stripped) <= 32 \
                and stripped.isascii() and " " not in stripped.rstrip() \
                and not stripped.startswith("-"):
            break
        out.append(line)
    return "\n".join(out).strip()
