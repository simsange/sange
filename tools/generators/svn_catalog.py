"""Generate `docs/reference/appendix-e-svn-catalog.md` from live SVN help.

T-G-002 — Appendix E, the SVN command catalog. Mirror of T-G-001 (Git) for
Subversion. Per §9.0.3 of `.design/sange-architecture-prompt.md` every row
on the §9.0.3 must-cover floor appears in the output.

The generator merges:

  1. **Live `svn help` + `svnadmin help`** — the canonical command lists
    (via `_lib.manpage.parse_svn_help` + a parser for `svnadmin`).
  2. **The §9.0.3 enrichment table** — Sange-specific columns (wrapper,
     AI augmentation, safety class, gate, Web UI parity, notes).

Commands present on the system but missing from enrichment fall back to a
default passthrough row with `safety_class=Reversible`,
`sange_wrapper="passthrough"`, and a `notes` flag inviting future work.

Determinism (ADR-023):

  * Input hash = sha256 of `(svn --version, svn help, svnadmin help,
    enrichment dict)`. Re-running under a different SVN version invalidates
    the hash automatically.
  * Output ordering: per-binary section, alphabetical by command name.
  * Tests pass `svn_help_text` + `svnadmin_help_text` + `svn_version_text`
    overrides so the generator is reproducible without `svn` installed.
"""

from __future__ import annotations

import datetime as _dt
import json
import re
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

# --- Path bootstrap ------------------------------------------------------- #
HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent.parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from _lib import manpage, markdown  # noqa: E402
from _lib.fingerprint import sha256_text  # noqa: E402
from _lib.output import (  # noqa: E402
    GeneratorMetadata,
    WriteMode,
    WriteOutcome,
    write_generated_file,
)

GENERATOR_VERSION = "1.0.0"
GENERATED_BY = "tools/generators/svn_catalog.py"
OUTPUT_PATH = REPO_ROOT / "docs" / "reference" / "appendix-e-svn-catalog.md"


# --------------------------------------------------------------------------- #
# Schema
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class SvnRow:
    name: str            # bare command name, e.g. "checkout"
    binary: str          # "svn" | "svnadmin" | "svnlook" | "svndumpfilter" | "svnsync"
    purpose: str
    sange_wrapper: str
    ai_augmentation: str
    safety_class: str    # Read-only / Reversible / Destructive / Catastrophic
    confirmation_gate: str
    web_ui_parity: str
    notes: str

    @property
    def full_name(self) -> str:
        return f"`{self.binary} {self.name}`"

    def to_table_row(self) -> list[str]:
        return [
            self.full_name,
            self.purpose,
            self.sange_wrapper,
            self.ai_augmentation,
            self.safety_class,
            self.confirmation_gate,
            self.web_ui_parity,
            self.notes,
        ]


BINARY_ORDER: tuple[str, ...] = ("svn", "svnadmin", "svnlook", "svndumpfilter", "svnsync")


# --------------------------------------------------------------------------- #
# Enrichment — the §9.0.3 must-cover floor
# --------------------------------------------------------------------------- #


def _sv(name: str, **kw) -> SvnRow:
    return SvnRow(name=name, binary="svn", **{
        "purpose": "",
        "sange_wrapper": "passthrough",
        "ai_augmentation": "none",
        "safety_class": "Reversible",
        "confirmation_gate": "None",
        "web_ui_parity": "No",
        "notes": "",
        **kw,
    })


def _sa(name: str, **kw) -> SvnRow:
    return SvnRow(name=name, binary="svnadmin", **{
        "purpose": "",
        "sange_wrapper": "passthrough",
        "ai_augmentation": "none",
        "safety_class": "Read-only",
        "confirmation_gate": "None",
        "web_ui_parity": "No",
        "notes": "",
        **kw,
    })


def _sl(name: str, **kw) -> SvnRow:
    return SvnRow(name=name, binary="svnlook", **{
        "purpose": "",
        "sange_wrapper": "passthrough",
        "ai_augmentation": "none",
        "safety_class": "Read-only",
        "confirmation_gate": "None",
        "web_ui_parity": "No",
        "notes": "",
        **kw,
    })


def _sdf(name: str, **kw) -> SvnRow:
    return SvnRow(name=name, binary="svndumpfilter", **{
        "purpose": "",
        "sange_wrapper": "passthrough",
        "ai_augmentation": "none",
        "safety_class": "Reversible",
        "confirmation_gate": "None",
        "web_ui_parity": "No",
        "notes": "",
        **kw,
    })


def _ss(name: str, **kw) -> SvnRow:
    return SvnRow(name=name, binary="svnsync", **{
        "purpose": "",
        "sange_wrapper": "passthrough",
        "ai_augmentation": "none",
        "safety_class": "Reversible",
        "confirmation_gate": "None",
        "web_ui_parity": "No",
        "notes": "",
        **kw,
    })


ENRICHMENT: tuple[SvnRow, ...] = (
    # ===== svn (working-copy operations) =====
    _sv(
        "checkout",
        purpose="Check out a working copy from a repository.",
        sange_wrapper="`sange clone <svn-url>`",
        ai_augmentation="AI summary of the repo on first checkout.",
        safety_class="Read-only",
        web_ui_parity="Yes (Project & Repo Management)",
        notes="Aliases: co.",
    ),
    _sv(
        "update",
        purpose="Bring changes from the repository into the working copy.",
        sange_wrapper="`sange sync`",
        ai_augmentation="AI-summarized incoming changes since last update.",
        safety_class="Reversible",
        web_ui_parity="Yes (Push & Publish Approval)",
        notes="Alias: up.",
    ),
    _sv(
        "commit",
        purpose="Send changes from your working copy to the repository.",
        sange_wrapper="`sange commit` / `sange commits push`",
        ai_augmentation="Full §6.8 commit-message lifecycle JSON; AI generation with prompt enhancer; ≥50 normalized presets.",
        safety_class="Destructive",
        confirmation_gate="Y/n (per-step approval)",
        web_ui_parity="Yes (Commit Management)",
        notes="Aliases: ci. Variant-aware (§6.5.2.6).",
    ),
    _sv(
        "add",
        purpose="Put files and directories under version control.",
        sange_wrapper="`sange add`",
        ai_augmentation="AI-suggested staging groups by logical change.",
        safety_class="Reversible",
        web_ui_parity="Yes (Commit Management)",
        notes="",
    ),
    _sv(
        "delete",
        purpose="Remove files and directories from version control.",
        sange_wrapper="`sange rm`",
        ai_augmentation="Warns about purge for sensitive removals → §6.11.",
        safety_class="Destructive",
        confirmation_gate="Y/n",
        web_ui_parity="No",
        notes="Aliases: del, remove, rm.",
    ),
    _sv(
        "copy",
        purpose="Duplicate something in working copy or repository, remembering history.",
        sange_wrapper="`sange copy`",
        ai_augmentation="none",
        safety_class="Reversible",
        web_ui_parity="No",
        notes="Alias: cp.",
    ),
    _sv(
        "move",
        purpose="Move (rename) an item in a working copy or repository.",
        sange_wrapper="`sange mv`",
        ai_augmentation="none",
        safety_class="Reversible",
        web_ui_parity="No",
        notes="Aliases: mv, rename, ren.",
    ),
    _sv(
        "revert",
        purpose="Restore pristine working copy state (undo local changes).",
        sange_wrapper="`sange revert`",
        ai_augmentation="AI-generated revert annotation.",
        safety_class="Destructive",
        confirmation_gate="Type-to-confirm",
        web_ui_parity="Yes (Rollback & Recovery)",
        notes="DESTRUCTIVE — destroys uncommitted local changes; no recovery.",
    ),
    _sv(
        "diff",
        purpose="This displays the differences between two paths.",
        sange_wrapper="`sange diff`",
        ai_augmentation="Syntax-highlighted, AI-explained diff.",
        safety_class="Read-only",
        web_ui_parity="Yes (per-commit diff view)",
        notes="Alias: di.",
    ),
    _sv(
        "status",
        purpose="Print the status of working copy files and directories.",
        sange_wrapper="`sange status`",
        ai_augmentation="Inline AI explanation of unusual states.",
        safety_class="Read-only",
        web_ui_parity="Yes (Project & Repo Management)",
        notes="Alias: stat, st. Variant tuple rendered above the status (§6.5.2.10).",
    ),
    _sv(
        "log",
        purpose="Show the log messages for a set of revision(s) and/or path(s).",
        sange_wrapper="`sange log`",
        ai_augmentation="AI-summarized 'what happened on this branch since X'.",
        safety_class="Read-only",
        web_ui_parity="Yes (Commit Management timeline)",
        notes="",
    ),
    _sv(
        "info",
        purpose="Display information about a local or remote item.",
        sange_wrapper="`sange info`",
        ai_augmentation="none",
        safety_class="Read-only",
        web_ui_parity="Yes (Project view)",
        notes="",
    ),
    _sv(
        "blame",
        purpose="Output the content of specified files or URLs with revision and author information.",
        sange_wrapper="`sange blame`",
        ai_augmentation="Rich-rendered; AI-summarized authorship per region.",
        safety_class="Read-only",
        web_ui_parity="Yes",
        notes="Aliases: praise, annotate, ann.",
    ),
    _sv(
        "cat",
        purpose="Output the content of specified files or URLs.",
        sange_wrapper="`sange cat`",
        ai_augmentation="none",
        safety_class="Read-only",
        web_ui_parity="No",
        notes="",
    ),
    _sv(
        "list",
        purpose="List directory entries in the repository.",
        sange_wrapper="`sange list`",
        ai_augmentation="none",
        safety_class="Read-only",
        web_ui_parity="No",
        notes="Alias: ls.",
    ),
    _sv(
        "merge",
        purpose="Apply the differences between two sources to a working copy path.",
        sange_wrapper="`sange merge`",
        ai_augmentation="AI-suggested conflict resolutions; AI-generated merge-commit message.",
        safety_class="Reversible",
        confirmation_gate="Y/n on conflicts",
        web_ui_parity="Yes (Push & Publish Approval)",
        notes="Most-protected SVN verb after `commit`.",
    ),
    _sv(
        "mergeinfo",
        purpose="Display merge-tracking information.",
        sange_wrapper="`sange mergeinfo`",
        ai_augmentation="none",
        safety_class="Read-only",
        web_ui_parity="No",
        notes="",
    ),
    _sv(
        "switch",
        purpose="Update the working copy to a different URL.",
        sange_wrapper="`sange switch`",
        ai_augmentation="none",
        safety_class="Reversible",
        web_ui_parity="Yes (Branch Management — SVN branches are URLs)",
        notes="Alias: sw.",
    ),
    _sv(
        "relocate",
        purpose="Relocate the working copy to point to a different repository root URL.",
        sange_wrapper="`sange relocate`",
        ai_augmentation="none",
        safety_class="Reversible",
        confirmation_gate="Y/n",
        web_ui_parity="No",
        notes="Used when the repository server moves.",
    ),
    _sv(
        "resolve",
        purpose="Resolve conflicts on working copy files or directories.",
        sange_wrapper="`sange resolve`",
        ai_augmentation="AI-suggested resolution strategies.",
        safety_class="Reversible",
        web_ui_parity="Yes (Push & Publish Approval — conflicts surface)",
        notes="Use `--accept theirs|mine|...` to specify the resolution.",
    ),
    _sv(
        "resolved",
        purpose="Remove conflicted state on working copy files or directories (DEPRECATED).",
        sange_wrapper="`sange resolve --status resolved`",
        ai_augmentation="none",
        safety_class="Reversible",
        web_ui_parity="No",
        notes="Deprecated by SVN — use `svn resolve --accept working` instead.",
    ),
    _sv(
        "cleanup",
        purpose="Recursively clean up the working copy, removing locks and resuming unfinished operations.",
        sange_wrapper="`sange cleanup`",
        ai_augmentation="none",
        safety_class="Reversible",
        web_ui_parity="Yes (Operations)",
        notes="Reads .sange/.recovery if a crash interrupted a previous SVN op.",
    ),
    _sv(
        "lock",
        purpose="Lock working copy paths or URLs in the repository, preventing others from committing changes.",
        sange_wrapper="`sange lock`",
        ai_augmentation="none",
        safety_class="Reversible",
        web_ui_parity="No",
        notes="SVN-specific (Git has no equivalent).",
    ),
    _sv(
        "unlock",
        purpose="Unlock working copy paths or URLs.",
        sange_wrapper="`sange unlock`",
        ai_augmentation="none",
        safety_class="Reversible",
        web_ui_parity="No",
        notes="",
    ),
    _sv(
        "propset",
        purpose="Set the value of a property on files, dirs, or revisions.",
        sange_wrapper="`sange propset`",
        ai_augmentation="none",
        safety_class="Reversible",
        web_ui_parity="No",
        notes="Alias: pset, ps.",
    ),
    _sv(
        "propget",
        purpose="Print the value of a property.",
        sange_wrapper="`sange propget`",
        ai_augmentation="none",
        safety_class="Read-only",
        web_ui_parity="No",
        notes="Alias: pget, pg.",
    ),
    _sv(
        "proplist",
        purpose="List all properties on files, dirs, or revisions.",
        sange_wrapper="`sange proplist`",
        ai_augmentation="none",
        safety_class="Read-only",
        web_ui_parity="No",
        notes="Alias: plist, pl.",
    ),
    _sv(
        "propedit",
        purpose="Edit a property with an external editor.",
        sange_wrapper="`sange propedit`",
        ai_augmentation="none",
        safety_class="Reversible",
        web_ui_parity="No",
        notes="Alias: pedit, pe.",
    ),
    _sv(
        "propdel",
        purpose="Remove a property from files, dirs, or revisions.",
        sange_wrapper="`sange propdel`",
        ai_augmentation="none",
        safety_class="Reversible",
        confirmation_gate="Y/n",
        web_ui_parity="No",
        notes="Alias: pdel, pd.",
    ),
    _sv(
        "import",
        purpose="Commit an unversioned file or tree into the repository.",
        sange_wrapper="`sange import`",
        ai_augmentation="Pre-flight: secret scan + large-file warner.",
        safety_class="Destructive",
        confirmation_gate="Y/n",
        web_ui_parity="No",
        notes="Creates intermediate directories. One-shot only.",
    ),
    _sv(
        "export",
        purpose="Create an unversioned copy of a tree.",
        sange_wrapper="`sange export`",
        ai_augmentation="none",
        safety_class="Read-only",
        web_ui_parity="No",
        notes="Useful for building bundles (§6.9.4) without VCS metadata.",
    ),
    _sv(
        "mkdir",
        purpose="Create a new directory under version control.",
        sange_wrapper="`sange mkdir`",
        ai_augmentation="none",
        safety_class="Reversible",
        web_ui_parity="No",
        notes="Creates the directory locally or remotely depending on argument.",
    ),
    _sv(
        "changelist",
        purpose="Associate (or dissociate) changelist CLNAME with the named files.",
        sange_wrapper="`sange changelist`",
        ai_augmentation="none",
        safety_class="Reversible",
        web_ui_parity="No",
        notes="Alias: cl. SVN-specific — groups working-copy files for partial commits.",
    ),
    _sv(
        "upgrade",
        purpose="Upgrade the metadata storage format for a working copy.",
        sange_wrapper="`sange upgrade`",
        ai_augmentation="none",
        safety_class="Reversible",
        confirmation_gate="Y/n",
        web_ui_parity="No",
        notes="One-time per WC after an SVN client upgrade.",
    ),
    _sv(
        "patch",
        purpose="Apply a patch to a working copy.",
        sange_wrapper="`sange apply`",
        ai_augmentation="AI-explained patch summary before apply.",
        safety_class="Reversible",
        web_ui_parity="No",
        notes="Cross-VCS — same wrapper as git apply (§9.0.2).",
    ),
    # ===== svnadmin (repository administration) =====
    _sa(
        "dump",
        purpose="Dump the contents of filesystem to stdout in a 'dumpfile' portable format.",
        sange_wrapper="`sange purge mirror` / `sange backup` (depending on intent)",
        ai_augmentation="Used by §6.11 SVN executor + §6.12 backup kit.",
        safety_class="Reversible",
        web_ui_parity="Yes (Operations — backup)",
        notes="Read-only on the repo; output goes to stdout/file.",
    ),
    _sa(
        "load",
        purpose="Read a 'dumpfile'-formatted stream from stdin, committing new revisions into the repository's filesystem.",
        sange_wrapper="`sange purge execute --vcs svn` (§6.11)",
        ai_augmentation="Used by the SVN purge executor in the rewrite-history pipeline.",
        safety_class="Catastrophic",
        confirmation_gate="Multi-step (typed-phrase + audit waiver)",
        web_ui_parity="Yes (§8.2.21 Purge & History Surgery — planning only)",
        notes="The destructive half of `dump→filter→load`; rewrites history.",
    ),
    _sa(
        "create",
        purpose="Create a new, empty repository.",
        sange_wrapper="`sange init --vcs svn`",
        ai_augmentation="Scaffolds .sange/ skeleton + auto-detects gitignore-equivalent.",
        safety_class="Read-only",
        web_ui_parity="No",
        notes="First step in any new SVN project.",
    ),
    _sa(
        "hotcopy",
        purpose="Make a hot copy of a repository (online backup).",
        sange_wrapper="`sange backup --hot`",
        ai_augmentation="none",
        safety_class="Reversible",
        confirmation_gate="Y/n",
        web_ui_parity="Yes (Operations — backup)",
        notes="The recommended SVN backup strategy; can run while repo is live.",
    ),
    _sa(
        "verify",
        purpose="Verify the data stored in the repository.",
        sange_wrapper="`sange doctor --vcs svn`",
        ai_augmentation="Integrated into `sange doctor` health probes.",
        safety_class="Read-only",
        web_ui_parity="Yes (Operations — health check)",
        notes="",
    ),
    # ===== svndumpfilter (history-rewrite filter) =====
    _sdf(
        "exclude",
        purpose="Exclude the listed paths from the dumpfile stream.",
        sange_wrapper="`sange purge execute --vcs svn` (§6.11)",
        ai_augmentation="Used by the SVN purge executor's `dump → filter → load → swap` pipeline.",
        safety_class="Catastrophic",
        confirmation_gate="Multi-step (typed-phrase + audit waiver)",
        web_ui_parity="Yes (§8.2.21 — planning only)",
        notes="The SVN equivalent of `git filter-repo`. Wrapped by §6.11.",
    ),
    _sdf(
        "include",
        purpose="Include only the listed paths in the dumpfile stream.",
        sange_wrapper="`sange purge execute --vcs svn --include` (§6.11)",
        ai_augmentation="Less-common inverse of `exclude`; same wrapper.",
        safety_class="Catastrophic",
        confirmation_gate="Multi-step",
        web_ui_parity="Yes (§8.2.21 — planning only)",
        notes="",
    ),
    # ===== svnsync (mirror / replicate) =====
    _ss(
        "init",
        purpose="Initialize a destination repository for synchronization from another repository.",
        sange_wrapper="`sange mirror init`",
        ai_augmentation="none",
        safety_class="Reversible",
        web_ui_parity="No",
        notes="Initial setup for a one-way SVN mirror.",
    ),
    _ss(
        "sync",
        purpose="Transfer all pending revisions from the source repository to the destination.",
        sange_wrapper="`sange mirror sync`",
        ai_augmentation="none",
        safety_class="Reversible",
        web_ui_parity="No",
        notes="Idempotent; safe to run repeatedly.",
    ),
    # ===== svnlook (read-only repo inspection) =====
    _sl(
        "tree",
        purpose="Print the tree of a directory in the repository (with options to show revision info).",
        sange_wrapper="`sange tree`",
        ai_augmentation="Rich-rendered tree view per §7.0.3.",
        safety_class="Read-only",
        web_ui_parity="No",
        notes="Used by `svnadmin verify` and the §6.11 purge analyzer.",
    ),
    _sl(
        "log",
        purpose="Print the log message for a transaction or revision.",
        sange_wrapper="`sange log --raw`",
        ai_augmentation="Pre-commit hook reads via svnlook log.",
        safety_class="Read-only",
        web_ui_parity="No",
        notes="Used by SVN hooks (pre-commit / post-commit) for log-message inspection.",
    ),
)


# --------------------------------------------------------------------------- #
# Live-help parsing
# --------------------------------------------------------------------------- #


_SVNADMIN_COMMAND_LINE = re.compile(
    r"^\s{3,}(?P<name>[\w\-]+)\s{2,}(?P<desc>.+?)\s*$"
)


def parse_svnadmin_help(text: str) -> list[manpage.CommandEntry]:
    """Parse `svnadmin help` (no subcommand) output."""

    out: list[manpage.CommandEntry] = []
    capture = False
    for line in text.splitlines():
        stripped = line.strip()
        if "Available subcommands" in stripped or stripped == "subcommands":
            capture = True
            continue
        if not capture or not stripped:
            continue
        m = _SVNADMIN_COMMAND_LINE.match(line)
        if m:
            out.append(
                manpage.CommandEntry(
                    name=m.group("name"),
                    short_description=m.group("desc"),
                    section="svnadmin subcommands",
                )
            )
    return out


# --------------------------------------------------------------------------- #
# Row gathering
# --------------------------------------------------------------------------- #


def _svn_version(*, override: str | None = None) -> str:
    if override is not None:
        return override
    try:
        return manpage.run_svn(["--version", "--quiet"]).strip()
    except manpage.CommandNotFound:
        return "svn-not-installed"


def _gather_rows(
    *,
    svn_help_text: str | None = None,
    svnadmin_help_text: str | None = None,
    svn_version_text: str | None = None,
) -> tuple[list[SvnRow], str]:
    """Build the row list + return the canonical input hash payload."""

    svn_version = _svn_version(override=svn_version_text)

    if svn_help_text is None:
        try:
            svn_help_text = manpage.run_svn(["help"])
        except manpage.CommandNotFound:
            svn_help_text = ""

    if svnadmin_help_text is None:
        try:
            svnadmin_help_text = manpage._run("svnadmin", ["help"])
        except manpage.CommandNotFound:
            svnadmin_help_text = ""

    svn_parsed = manpage.parse_svn_help(svn_help_text)
    svnadmin_parsed = parse_svnadmin_help(svnadmin_help_text)

    rows: dict[tuple[str, str], SvnRow] = {}

    # Seed every live command with a passthrough row.
    for command in svn_parsed.commands:
        key = ("svn", command.name)
        rows[key] = SvnRow(
            name=command.name,
            binary="svn",
            purpose=command.short_description,
            sange_wrapper="passthrough",
            ai_augmentation="none",
            safety_class="Reversible",
            confirmation_gate="None",
            web_ui_parity="No",
            notes="passthrough — consider augmentation (§9.4)",
        )
    for command in svnadmin_parsed:
        key = ("svnadmin", command.name)
        rows[key] = SvnRow(
            name=command.name,
            binary="svnadmin",
            purpose=command.short_description,
            sange_wrapper="passthrough",
            ai_augmentation="none",
            safety_class="Read-only",
            confirmation_gate="None",
            web_ui_parity="No",
            notes="passthrough — consider augmentation (§9.4)",
        )

    # Overlay enrichment.
    for enriched in ENRICHMENT:
        rows[(enriched.binary, enriched.name)] = enriched

    binary_index = {b: i for i, b in enumerate(BINARY_ORDER)}
    sorted_rows = sorted(
        rows.values(),
        key=lambda r: (binary_index.get(r.binary, len(BINARY_ORDER)), r.name),
    )

    payload = json.dumps(
        {
            "svn_version": svn_version,
            "svn_help_sha256": sha256_text(svn_help_text),
            "svnadmin_help_sha256": sha256_text(svnadmin_help_text),
            "enrichment_rows": sorted(
                f"{e.binary}/{e.name}" for e in ENRICHMENT
            ),
        },
        sort_keys=True,
    )
    return sorted_rows, payload


# --------------------------------------------------------------------------- #
# Body rendering
# --------------------------------------------------------------------------- #


def _build_body(*, rows: list[SvnRow], svn_version: str) -> str:
    parts: list[str] = []
    parts.append(markdown.heading(1, "Appendix E — SVN command catalog"))
    parts.append(
        "> Generated by `tools/generators/svn_catalog.py` (T-G-002). Combines "
        "live `svn help` + `svnadmin help` with the §9.0.3 must-cover floor "
        "enrichment from `.design/sange-architecture-prompt.md`.\n"
    )
    parts.append(
        f"**SVN version used to build this catalog:** `{svn_version}`. "
        "Re-run the generator after a `svn` upgrade.\n"
    )
    parts.append(
        "**Column shape (per §9.1):** Command • Purpose • Sange wrapper • "
        "AI augmentation • Safety class • Confirmation gate • Web UI parity • "
        "Notes.\n"
    )
    parts.append(
        "**Coverage discipline (per §9.4):** every Sange wrapper documented "
        "here must do at least one of the seven §9.4 augmentations. Pure "
        "passthrough rows are flagged in the Notes column.\n"
    )

    grouped: dict[str, list[SvnRow]] = {b: [] for b in BINARY_ORDER}
    for row in rows:
        grouped.setdefault(row.binary, []).append(row)

    parts.append(markdown.heading(2, "Summary"))
    summary = []
    for binary in BINARY_ORDER:
        summary.append([f"`{binary}`", str(len(grouped.get(binary, [])))])
    summary.append(["**Total**", str(len(rows))])
    parts.append(
        markdown.table(
            ["Binary", "Commands"],
            summary,
            alignments=["left", "right"],
        )
    )
    parts.append("")

    headers = [
        "Command",
        "Purpose",
        "Sange wrapper",
        "AI augmentation",
        "Safety class",
        "Confirmation gate",
        "Web UI parity",
        "Notes",
    ]

    for binary in BINARY_ORDER:
        binary_rows = grouped.get(binary, [])
        if not binary_rows:
            continue
        parts.append(markdown.heading(2, f"`{binary}` ({len(binary_rows)})"))
        parts.append(
            markdown.table(
                headers,
                [r.to_table_row() for r in binary_rows],
            )
        )
        parts.append("")

    parts.append(markdown.heading(2, "Cross-VCS notes"))
    parts.append(
        markdown.bullet_list(
            [
                "`svn merge` differs from `git merge` — SVN's merge-tracking lives in `svn:mergeinfo` properties; `sange merge --vcs svn` consults `svn mergeinfo`.",
                "`svndumpfilter exclude` is SVN's equivalent of `git filter-repo`; wrapped by §6.11 (`sange purge execute --vcs svn`).",
                "SVN has no Git-equivalent staging area — `svn commit` commits the working copy directly. The §6.8 commit-message lifecycle JSON wraps that with a review gate.",
                "SVN branches and tags are URL paths under `branches/` and `tags/` by convention; `sange branch` translates between SVN URL paths and the abstract Branch domain model (§7.6).",
                "SVN's `cleanup` recovers from a crashed operation similarly to Sange's gitignore-swap recovery (§6.5) — both leave a marker on disk and resume on the next command.",
            ]
        )
    )
    parts.append("")
    parts.append(markdown.heading(2, "How to update this appendix"))
    parts.append(
        markdown.bullet_list(
            [
                "Add a new Sange wrapper for an SVN command → append a row to the `ENRICHMENT` tuple in `tools/generators/svn_catalog.py`.",
                "Upgrade SVN → the next run picks up new commands automatically; review the diff and enrich the newly-appearing rows.",
                "Verify integrity → `python tools/generators/verify_generated.py`.",
                "Regenerate → `python tools/generators/all.py --only T-G-002 --write`.",
            ]
        )
    )
    return "\n".join(parts)


# --------------------------------------------------------------------------- #
# Generator entry-point
# --------------------------------------------------------------------------- #


def run(
    *,
    mode: WriteMode,
    clock: _dt.datetime,
    svn_help_text: str | None = None,
    svnadmin_help_text: str | None = None,
    svn_version_text: str | None = None,
    output_path: Path | None = None,
) -> list[WriteOutcome]:
    rows, payload = _gather_rows(
        svn_help_text=svn_help_text,
        svnadmin_help_text=svnadmin_help_text,
        svn_version_text=svn_version_text,
    )
    svn_version = _svn_version(override=svn_version_text)
    body = _build_body(rows=rows, svn_version=svn_version)
    meta = GeneratorMetadata(
        generated_by=GENERATED_BY,
        generator_version=GENERATOR_VERSION,
        input_sha256=sha256_text(payload),
        manual_edits_allowed=False,
        generated_at=clock,
    )
    target = output_path or OUTPUT_PATH
    return [write_generated_file(target, body, meta, mode=mode)]


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--check", action="store_true")
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
