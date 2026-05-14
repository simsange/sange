"""Generate `docs/reference/appendix-d-git-catalog.md` from live `git help -a`.

T-G-001 — Appendix D, the comprehensive Git command catalog. Per §9 of
`.design/sange-architecture-prompt.md`, every Git command gets a row with the
columns the §9.1 schema declares: Tier, Purpose, Sange wrapper, AI augmentation,
Safety class, Confirmation gate, Web UI parity, Notes.

The generator merges two inputs:

  1. **Live `git help -a`** — the canonical list of commands the installed git
     binary exposes (via `_lib.manpage.parse_git_help_all`).
  2. **The §9.0.1 Top-25 + §9.0.2 power-commands enrichment table** below — the
     Sange-specific columns (wrapper, AI augmentation, safety class, gate,
     Web UI parity, notes) that the prompt commits to.

Commands present in git but missing from the enrichment table fall back to a
default row derived from git's own section header (Main Porcelain → Common;
Ancillary → Common; Low-level → Plumbing; External → Third-party) with
`sange_wrapper = "passthrough"` and a `notes` flag inviting future enrichment.

Determinism (ADR-023):

  * Input hash = sha256 of `(git --version, canonicalized git-help-output,
    canonicalized enrichment dict)`. Re-running under a different git version
    or after enrichment edits invalidates the hash and forces regeneration.
  * Output ordering is stable: per-tier section, alphabetical by command
    within each section.
  * Tests pass a fixture `git_help_text` so the generator is reproducible
    without git installed.
"""

from __future__ import annotations

import datetime as _dt
import json
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

# --- Path bootstrap ------------------------------------------------------- #
HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent.parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

# --- Imports -------------------------------------------------------------- #
from _lib import manpage, markdown  # noqa: E402
from _lib.fingerprint import sha256_text  # noqa: E402
from _lib.output import (  # noqa: E402
    GeneratorMetadata,
    WriteMode,
    WriteOutcome,
    write_generated_file,
)

GENERATOR_VERSION = "1.0.0"
GENERATED_BY = "tools/generators/git_catalog.py"
OUTPUT_PATH = REPO_ROOT / "docs" / "reference" / "appendix-d-git-catalog.md"


# --------------------------------------------------------------------------- #
# Schema
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class CatalogRow:
    name: str
    tier: str
    purpose: str
    sange_wrapper: str
    ai_augmentation: str
    safety_class: str
    confirmation_gate: str
    web_ui_parity: str
    notes: str

    def to_table_row(self) -> list[str]:
        return [
            f"`git {self.name}`",
            self.tier,
            self.purpose,
            self.sange_wrapper,
            self.ai_augmentation,
            self.safety_class,
            self.confirmation_gate,
            self.web_ui_parity,
            self.notes,
        ]


# Tier ordering used both for section headings and within-section grouping.
TIER_ORDER: tuple[str, ...] = ("Essential", "Common", "Power", "Plumbing", "Third-party")

# Default tier derived from git's own section header when no enrichment exists.
DEFAULT_TIER_BY_SECTION: dict[str, str] = {
    "Main Porcelain Commands": "Common",
    "Ancillary Commands / Manipulators": "Common",
    "Ancillary Commands / Interrogators": "Common",
    "Interacting with Others": "Common",
    "Low-level Commands / Manipulators": "Plumbing",
    "Low-level Commands / Interrogators": "Plumbing",
    "Low-level Commands / Syncing Repositories": "Plumbing",
    "Low-level Commands / Syncing Content": "Plumbing",
    "Low-level Commands / Internal Helpers": "Plumbing",
    "External commands": "Third-party",
    "Command aliases": "Third-party",
}


# --------------------------------------------------------------------------- #
# Enrichment table — the Sange-specific columns the prompt §9.0 commits to.
#
# This dict is the source of truth for the documented Sange wrappers, AI
# augmentations, safety classes, and confirmation gates. Adding a new row
# here is the right way to "claim" a wrapper for a Git command.
#
# Per §9.4: every wrapper must add at least one of the seven augmentations
# (AI / safety gate / lifecycle / audit / rich rendering / cross-VCS / config-
# aware). Pure passthrough rows must say so in `notes` ("passthrough —
# consider augmentation").
# --------------------------------------------------------------------------- #


def _t25(
    name: str,
    purpose: str,
    sange_wrapper: str,
    ai_augmentation: str,
    safety: str,
    gate: str,
    web: str,
    notes: str = "",
) -> tuple[str, CatalogRow]:
    """Helper for the §9.0.1 Top-25 — all Essential by default."""

    return name, CatalogRow(
        name=name,
        tier="Essential",
        purpose=purpose,
        sange_wrapper=sange_wrapper,
        ai_augmentation=ai_augmentation,
        safety_class=safety,
        confirmation_gate=gate,
        web_ui_parity=web,
        notes=notes,
    )


def _power(
    name: str,
    purpose: str,
    sange_wrapper: str,
    ai_augmentation: str,
    safety: str,
    gate: str,
    web: str,
    notes: str = "",
) -> tuple[str, CatalogRow]:
    """Helper for the §9.0.2 under-used power commands."""

    return name, CatalogRow(
        name=name,
        tier="Power",
        purpose=purpose,
        sange_wrapper=sange_wrapper,
        ai_augmentation=ai_augmentation,
        safety_class=safety,
        confirmation_gate=gate,
        web_ui_parity=web,
        notes=notes,
    )


ENRICHMENT: dict[str, CatalogRow] = dict(
    [
        # ----- §9.0.1 Top 25 (Essentials / Common) ---------------------------
        _t25(
            "init",
            "Create an empty Git repository or reinitialize an existing one.",
            "`sange init`",
            "Scaffolds `.sange/` skeleton; AI-suggested gitignore profile selection (§6.5.1).",
            "Read-only",
            "None",
            "Yes (Project & Repo Management)",
            "First step in every new repo.",
        ),
        _t25(
            "clone",
            "Clone a repository into a new directory.",
            "`sange clone <url>`",
            "AI summary of repo on first clone (README + recent commits).",
            "Read-only",
            "None",
            "Yes (Project & Repo Management)",
            "",
        ),
        _t25(
            "status",
            "Show the working tree status.",
            "`sange status`",
            "Inline AI explanation of unusual states (detached HEAD, unmerged paths).",
            "Read-only",
            "None",
            "Yes (Project & Repo Management)",
            "Variant tuple rendered above the git status (§6.5.2.10).",
        ),
        _t25(
            "add",
            "Add file contents to the index.",
            "`sange add` (interactive checkboxes)",
            "AI-suggests staging groups by logical change.",
            "Reversible",
            "None",
            "Yes (Commit Management)",
            "",
        ),
        _t25(
            "commit",
            "Record changes to the repository.",
            "`sange commit` (happy path) + `sange commits <subcommand>` (granular lifecycle)",
            "Full §6.8 commit-message lifecycle JSON; AI generation with prompt enhancer; ≥50 normalized presets.",
            "Reversible",
            "Y/n (per-step approval)",
            "Yes (Commit Management)",
            "The headline §6.8 feature.",
        ),
        _t25(
            "log",
            "Show commit logs.",
            "`sange log` (rich pager)",
            "AI-summarized \"what happened on this branch since X\".",
            "Read-only",
            "None",
            "Yes (Commit Management timeline)",
            "",
        ),
        _t25(
            "diff",
            "Show changes between commits, commit and working tree, etc.",
            "`sange diff`",
            "Syntax-highlighted, AI-explained diff for review.",
            "Read-only",
            "None",
            "Yes (per-commit diff view)",
            "",
        ),
        _t25(
            "branch",
            "List, create, or delete branches.",
            "`sange branch`",
            "Naming-policy validation, age + ahead/behind, AI-named branches from intent.",
            "Reversible",
            "Y/n (on delete)",
            "Yes (Branch Management)",
            "",
        ),
        _t25(
            "checkout",
            "Switch branches or restore working tree files.",
            "`sange checkout`",
            "Warns when superseded by `switch`/`restore`; passthrough.",
            "Reversible",
            "None",
            "Read-only view",
            "Prefer `sange switch` for branches and `sange restore` for files.",
        ),
        _t25(
            "switch",
            "Switch branches.",
            "`sange switch`",
            "Preferred over `checkout` per current Git guidance.",
            "Reversible",
            "None",
            "Yes (Branch Management)",
            "",
        ),
        _t25(
            "merge",
            "Join two or more development histories together.",
            "`sange merge`",
            "AI-suggested conflict resolutions; AI-generated merge-commit message.",
            "Reversible",
            "Y/n on conflicts",
            "Yes (Push & Publish Approval)",
            "",
        ),
        # Note: `rebase` is "Common" not "Essential" per the §9.0.1 numbering;
        # we record it here so the table reads canonically Top-25 in order.
        (
            "rebase",
            CatalogRow(
                name="rebase",
                tier="Common",
                purpose="Reapply commits on top of another base tip.",
                sange_wrapper="`sange rebase` (interactive-aware)",
                ai_augmentation="AI-suggested commit grouping for `--interactive` rebases; rerere integration.",
                safety_class="Destructive",
                confirmation_gate="Type-to-confirm on `--force-with-lease`",
                web_ui_parity="No (CLI/TUI only)",
                notes="Rewrites history — prefer merge in shared branches.",
            ),
        ),
        _t25(
            "pull",
            "Fetch from and integrate with another repository or a local branch.",
            "`sange sync`",
            "Fetch + rebase/merge per config; AI-summarized incoming changes since last pull.",
            "Reversible",
            "None",
            "Yes (Push & Publish Approval)",
            "",
        ),
        _t25(
            "push",
            "Update remote refs along with associated objects.",
            "`sange push` (or via `sange commits push`) / `sange publish`",
            "Pre-flight: secret scan + large-file warner + policy violations; gitignore-swap on `publish` (§6.5); variant-aware (§6.5.2.6).",
            "Destructive",
            "Type-to-confirm on `--force` and `publish`",
            "Yes (Push & Publish Approval)",
            "Most-protected verb; multiple gates layer.",
        ),
        _t25(
            "fetch",
            "Download objects and refs from another repository.",
            "`sange fetch`",
            "none",
            "Read-only",
            "None",
            "No",
            "Passthrough; consider augmentation in v0.5.",
        ),
        _t25(
            "remote",
            "Manage set of tracked repositories.",
            "`sange remote`",
            "list / add / rename / set-url / prune subcommands.",
            "Reversible",
            "Y/n on remove",
            "Yes (settings)",
            "",
        ),
        (
            "stash",
            CatalogRow(
                name="stash",
                tier="Common",
                purpose="Stash the changes in a dirty working directory away.",
                sange_wrapper="`sange stash`",
                ai_augmentation="Semantic naming, AI-named entries.",
                safety_class="Reversible",
                confirmation_gate="None",
                web_ui_parity="Yes (Rollback & Recovery)",
                notes="Stashes survive across worktrees.",
            ),
        ),
        (
            "reset",
            CatalogRow(
                name="reset",
                tier="Common",
                purpose="Reset current HEAD to the specified state.",
                sange_wrapper="`sange reset`",
                ai_augmentation="Mode-aware (soft/mixed/hard); type-to-confirm on `--hard`.",
                safety_class="Destructive",
                confirmation_gate="Type-to-confirm on `--hard`",
                web_ui_parity="Yes (Rollback & Recovery)",
                notes="Prefer `sange undo` (reflog-based, safer) for everyday reversal.",
            ),
        ),
        (
            "revert",
            CatalogRow(
                name="revert",
                tier="Common",
                purpose="Revert some existing commits.",
                sange_wrapper="`sange revert`",
                ai_augmentation="Single/range/merge-commit aware; AI-generated revert commit message.",
                safety_class="Reversible",
                confirmation_gate="None",
                web_ui_parity="Yes (Rollback & Recovery)",
                notes="Adds a new commit — safer than `reset`.",
            ),
        ),
        (
            "tag",
            CatalogRow(
                name="tag",
                tier="Common",
                purpose="Create, list, delete or verify a tag object signed with GPG.",
                sange_wrapper="`sange tag`",
                ai_augmentation="Annotated + signed via configured key; AI-generated tag message; release-note linkage.",
                safety_class="Reversible",
                confirmation_gate="None on create; Type-to-confirm on `--delete` for shared tags",
                web_ui_parity="Yes (Release Management)",
                notes="Signed tags re-asserted post-purge (§6.11.5).",
            ),
        ),
        (
            "show",
            CatalogRow(
                name="show",
                tier="Common",
                purpose="Show various types of objects.",
                sange_wrapper="`sange show`",
                ai_augmentation="AI-explained commit (intent, risk, related issues).",
                safety_class="Read-only",
                confirmation_gate="None",
                web_ui_parity="Yes",
                notes="",
            ),
        ),
        (
            "rm",
            CatalogRow(
                name="rm",
                tier="Common",
                purpose="Remove files from the working tree and from the index.",
                sange_wrapper="`sange rm`",
                ai_augmentation="`--cached`-aware; warns about purge for sensitive removals → §6.11.",
                safety_class="Catastrophic",
                confirmation_gate="Multi-step (file list + confirm)",
                web_ui_parity="No",
                notes="`--force` + uncommitted changes can lose data; sange refuses without explicit waiver.",
            ),
        ),
        (
            "mv",
            CatalogRow(
                name="mv",
                tier="Common",
                purpose="Move or rename a file, a directory, or a symlink.",
                sange_wrapper="`sange mv`",
                ai_augmentation="none",
                safety_class="Reversible",
                confirmation_gate="None",
                web_ui_parity="No",
                notes="Passthrough; consider augmentation in v0.5.",
            ),
        ),
        _t25(
            "config",
            "Get and set repository or global options.",
            "`sange config`",
            "Reads/writes SangeConfig + git config; never plaintext secrets (§6.3).",
            "Reversible",
            "None",
            "Yes (settings)",
            "Secrets resolve via the variant's `secrets_resolver` (§6.5.2.8).",
        ),
        # ----- §9.0.2 Power commands (under-used but powerful) ----------------
        _power(
            "bisect",
            "Use binary search to find the commit that introduced a bug.",
            "`sange bisect`",
            "Run-based + AI-suggested narrowing.",
            "Read-only",
            "None",
            "No",
            "",
        ),
        _power(
            "worktree",
            "Manage multiple working trees.",
            "`sange worktree`",
            "Parallel branches without re-cloning; foundational for `sange purge` mirror discipline (§6.11.4).",
            "Reversible",
            "None",
            "No",
            "",
        ),
        _power(
            "rerere",
            "Reuse recorded resolution of conflicted merges.",
            "`sange rerere`",
            "Auto-enabled with audit on conflict-replay; pairs with §6.8 lifecycle.",
            "Reversible",
            "None",
            "No",
            "",
        ),
        _power(
            "maintenance",
            "Run tasks to optimize Git repository data.",
            "`sange maintenance`",
            "Manual + scheduled-job integration (§8.2.8).",
            "Reversible",
            "None",
            "Yes (Scheduler)",
            "",
        ),
        _power(
            "sparse-checkout",
            "Reduce your working tree to a subset of tracked files.",
            "`sange sparse-checkout`",
            "init/set/disable + AI-suggested path-set from monorepo heuristics.",
            "Reversible",
            "None",
            "No",
            "",
        ),
        _power(
            "replace",
            "Create, list, delete refs to replace objects.",
            "`sange replace`",
            "With `--no-graft` warning; refused for destructive intent (use §6.11 instead).",
            "Destructive",
            "Type-to-confirm",
            "No",
            "Niche but documented.",
        ),
        _power(
            "notes",
            "Add or inspect object notes.",
            "`sange notes`",
            "Lifecycle-integrated; carries AI-generated review notes; powers reviewer comments in §8.2.2.",
            "Reversible",
            "None",
            "Yes (Commit Management)",
            "",
        ),
        _power(
            "reflog",
            "Manage reflog information.",
            "`sange reflog` + `sange recover`",
            "Last safety net before `sange purge` expires it; `sange recover` reads on crash.",
            "Read-only",
            "None",
            "Yes (Rollback & Recovery)",
            "",
        ),
        (
            "restore",
            CatalogRow(
                name="restore",
                tier="Common",
                purpose="Restore working tree files.",
                sange_wrapper="`sange restore`",
                ai_augmentation="Preferred over `checkout` for files per current Git guidance.",
                safety_class="Reversible",
                confirmation_gate="None",
                web_ui_parity="Yes (Rollback & Recovery)",
                notes="Replaces the file-restore half of legacy `checkout`.",
            ),
        ),
        _power(
            "range-diff",
            "Compare two commit ranges (e.g. two versions of a branch).",
            "`sange range-diff`",
            "Used during rebase/cherry-pick reviews.",
            "Read-only",
            "None",
            "Yes (review diff viewer)",
            "",
        ),
        (
            "cherry-pick",
            CatalogRow(
                name="cherry-pick",
                tier="Common",
                purpose="Apply the changes introduced by some existing commits.",
                sange_wrapper="`sange cherry-pick`",
                ai_augmentation="Conflict-resolution helpers + AI message rewrite.",
                safety_class="Reversible",
                confirmation_gate="Y/n on conflict",
                web_ui_parity="Yes (Commit Management)",
                notes="Hot-fix backport without merge graph.",
            ),
        ),
        (
            "blame",
            CatalogRow(
                name="blame",
                tier="Common",
                purpose="Show what revision and author last modified each line.",
                sange_wrapper="`sange blame`",
                ai_augmentation="Rich-rendered; AI-summarized authorship per region.",
                safety_class="Read-only",
                confirmation_gate="None",
                web_ui_parity="Yes",
                notes="Inline ownership / why-this-line.",
            ),
        ),
        (
            "grep",
            CatalogRow(
                name="grep",
                tier="Common",
                purpose="Print lines matching a pattern.",
                sange_wrapper="`sange grep`",
                ai_augmentation="Rich-rendered; respects gitignore-swap state (§6.5).",
                safety_class="Read-only",
                confirmation_gate="None",
                web_ui_parity="No",
                notes="Code search across history.",
            ),
        ),
        _power(
            "submodule",
            "Initialize, update or inspect submodules.",
            "`sange submodule`",
            "add/update/sync/status/foreach subcommands.",
            "Reversible",
            "None",
            "Yes (read-only)",
            "Required for §6.11 submodule re-procedure note.",
        ),
        _power(
            "clean",
            "Remove untracked files from the working tree.",
            "`sange clean`",
            "Dry-run by default.",
            "Catastrophic",
            "Type-to-confirm",
            "Yes (Rollback & Recovery)",
            "Never run without confirmation.",
        ),
        _power(
            "describe",
            "Give an object a human readable name based on an available ref.",
            "`sange describe`",
            "Semver-aware; builds release strings from tags.",
            "Read-only",
            "None",
            "Yes (Release)",
            "",
        ),
        _power(
            "archive",
            "Create an archive of files from a named tree.",
            "`sange archive`",
            "Integrated with `sange bundle build` (§6.9.2).",
            "Read-only",
            "None",
            "Yes (Release Bundling)",
            "",
        ),
        _power(
            "gc",
            "Cleanup unnecessary files and optimize the local repository.",
            "`sange gc`",
            "With explicit `sange gc --aggressive` for purge cleanup; §7.",
            "Reversible",
            "Y/n on `--aggressive`",
            "Yes (Operations)",
            "",
        ),
        _power(
            "apply",
            "Apply a patch to files and/or to the index.",
            "`sange apply`",
            "Patch ingestion; needed for distributed review.",
            "Reversible",
            "None",
            "No",
            "",
        ),
        _power(
            "am",
            "Apply a series of patches from a mailbox.",
            "`sange am`",
            "Patch ingestion; needed for distributed review.",
            "Reversible",
            "None",
            "No",
            "",
        ),
        _power(
            "format-patch",
            "Prepare patches for e-mail submission.",
            "`sange format-patch`",
            "Patch generation; pairs with `am`.",
            "Read-only",
            "None",
            "No",
            "",
        ),
        _power(
            "shortlog",
            "Summarize 'git log' output.",
            "`sange shortlog`",
            "Release-note generation feedstock.",
            "Read-only",
            "None",
            "Yes (Release notes)",
            "",
        ),
        # ----- §9.0.6 Cross-cutting integration anchors (these are git-CLI-shaped) ---
        _power(
            "filter-repo",
            "Quickly rewrite git repository history.",
            "`sange purge` (§7.10 / §6.11)",
            "10-state lifecycle, 8 pre-flight gates, 8 post-rewrite verifications, hash-chained audit JSONL, typed-phrase gates.",
            "Catastrophic",
            "Multi-step (typed-phrase + audit waiver)",
            "Yes (§8.2.21 Purge & History Surgery — planning only; destructive transition is terminal-only per ADR-018)",
            "Third-party binary (`git-filter-repo`); §6.11 wraps it. Not in `git help -a` core; appears only if installed as a git extension.",
        ),
    ]
)


# Sange-native verbs that have no direct `git` equivalent — these don't appear
# in `git help -a` but must be documented as part of the catalog's coverage.
SANGE_NATIVE_ROWS: tuple[CatalogRow, ...] = (
    CatalogRow(
        name="undo",
        tier="Power",
        purpose="(Sange-native) Safe reversal of the last destructive operation using reflog + audit chain.",
        sange_wrapper="`sange undo`",
        ai_augmentation="Lifecycle-aware; replays from the §7.0.7 hash-chained audit log.",
        safety_class="Reversible",
        confirmation_gate="Type-to-confirm",
        web_ui_parity="Yes (Rollback & Recovery)",
        notes="Sange-native — no direct git equivalent. Built on reflog + audit + lifecycle JSON.",
    ),
    CatalogRow(
        name="review",
        tier="Power",
        purpose="(Sange-native) Local PR-style review of staged changes.",
        sange_wrapper="`sange review`",
        ai_augmentation="AI-explained diff with risk highlighting and suggested test additions.",
        safety_class="Read-only",
        confirmation_gate="None",
        web_ui_parity="Yes (Commit Management)",
        notes="Sange-native — no direct git equivalent.",
    ),
    CatalogRow(
        name="recover",
        tier="Power",
        purpose="(Sange-native) Restore from a crash mid-publish or mid-purge.",
        sange_wrapper="`sange recover`",
        ai_augmentation="Reads `.sange/.recovery`, `.sange/purge/<latest>/plan.json`, in-flight bundle state.",
        safety_class="Reversible",
        confirmation_gate="Type-to-confirm",
        web_ui_parity="Yes (Operations)",
        notes="Sange-native (§6.5 SIGKILL-safety, §6.11 purge rollback).",
    ),
    CatalogRow(
        name="variant",
        tier="Power",
        purpose="(Sange-native) Multi-dimensional variant matrix manager (ADR-032).",
        sange_wrapper="`sange variant` (list/show/use/unset/resolve/detect/diff/verify/filters/scaffold/materialize)",
        ai_augmentation="Branch-map auto-detection; heuristic resolution from CI env + Docker tags + `.env.*`.",
        safety_class="Reversible",
        confirmation_gate="None on `show`/`list`; stage-locked on `use`",
        web_ui_parity="Yes (variant chip in header)",
        notes="Sange-native — see §6.5.2 + ADR-032 + §7.6.1.",
    ),
    CatalogRow(
        name="scaffold",
        tier="Power",
        purpose="(Sange-native) Premade Operations Kit materialization (§6.12, §7.11).",
        sange_wrapper="`sange scaffold` (list/show/add/diff/update/remove/verify)",
        ai_augmentation="Three-way merge on update; provenance.json tracking; signed-manifest verification.",
        safety_class="Reversible",
        confirmation_gate="`--force` required to overwrite",
        web_ui_parity="Yes (settings)",
        notes="Sange-native — `templates/MANIFEST.toml.sig` is the trust root (ADR-020).",
    ),
    CatalogRow(
        name="doctor",
        tier="Power",
        purpose="(Sange-native) Health probe — local + container + variant + audit.",
        sange_wrapper="`sange doctor`",
        ai_augmentation="Variant pollution check (§6.5.2.9); audit-chain integrity check.",
        safety_class="Read-only",
        confirmation_gate="None",
        web_ui_parity="Yes (Operations)",
        notes="Sange-native; modes: `--container`, `--variant`, `--audit`, `--all`.",
    ),
)


# --------------------------------------------------------------------------- #
# Generator
# --------------------------------------------------------------------------- #


def _git_version(*, override: str | None = None) -> str:
    if override is not None:
        return override
    try:
        return manpage.run_git(["--version"]).strip()
    except manpage.CommandNotFound:
        return "git-not-installed"


def _gather_rows(
    *,
    git_help_text: str | None = None,
    git_version_text: str | None = None,
) -> tuple[list[CatalogRow], str]:
    """Build the full row set + return the canonical input hash payload.

    Test hook: pass `git_help_text` to bypass the live subprocess call.
    """

    git_version = _git_version(override=git_version_text)
    if git_help_text is None:
        try:
            git_help_text = manpage.run_git(["help", "-a"])
        except manpage.CommandNotFound:
            git_help_text = ""

    parsed = manpage.parse_git_help_all(git_help_text)
    seen_names = {c.name for c in parsed.commands}

    rows: dict[str, CatalogRow] = {}

    # 1. Seed every git-reported command with a default row (so even commands
    #    we haven't enriched yet still appear in the catalog).
    for command in parsed.commands:
        default_tier = DEFAULT_TIER_BY_SECTION.get(command.section, "Plumbing")
        rows[command.name] = CatalogRow(
            name=command.name,
            tier=default_tier,
            purpose=command.short_description,
            sange_wrapper="passthrough",
            ai_augmentation="none",
            safety_class="Read-only" if default_tier == "Plumbing" else "Reversible",
            confirmation_gate="None",
            web_ui_parity="No",
            notes="passthrough — consider augmentation (§9.4)",
        )

    # 2. Overlay the enrichment table — wins over the seeded default. Also
    #    includes enrichment-only commands (e.g. `filter-repo`) that don't
    #    appear in `git help -a` on every system.
    for name, row in ENRICHMENT.items():
        rows[name] = row

    # 3. Append Sange-native verbs (last; they don't exist as git commands).
    sange_native_names: set[str] = set()
    for native in SANGE_NATIVE_ROWS:
        rows[native.name] = native
        sange_native_names.add(native.name)

    # Sort: tier first (by TIER_ORDER), then alphabetical within tier.
    tier_index = {t: i for i, t in enumerate(TIER_ORDER)}
    sorted_rows = sorted(
        rows.values(),
        key=lambda r: (tier_index.get(r.tier, len(TIER_ORDER)), r.name),
    )

    # Canonical input payload — sha256-able, deterministic across runs.
    payload = json.dumps(
        {
            "git_version": git_version,
            "git_help_sha256": sha256_text(git_help_text),
            "git_command_count": len(seen_names),
            "enrichment_rows": sorted(ENRICHMENT.keys()),
            "sange_native_rows": sorted(sange_native_names),
        },
        sort_keys=True,
        indent=None,
        separators=(",", ":"),
    )

    return sorted_rows, payload


def _build_body(
    *,
    rows: list[CatalogRow],
    git_version: str,
) -> str:
    parts: list[str] = []
    parts.append(markdown.heading(1, "Appendix D — Git command catalog"))
    parts.append(
        "> Generated by `tools/generators/git_catalog.py` (T-G-001). Combines live "
        "`git help -a` output with the §9.0.1 Top-25 + §9.0.2 power-commands "
        "enrichment from `.design/sange-architecture-prompt.md`.\n"
    )
    parts.append(
        f"**Git version used to build this catalog:** `{git_version}`. Re-run "
        "the generator after a `git` upgrade; the §16.4.1 frontmatter's "
        "`input_sha256` invalidates automatically when either `git --version` "
        "or `git help -a` output changes.\n"
    )
    parts.append(
        "**Column shape (per §9.1):** Command • Tier • Purpose • Sange wrapper • "
        "AI augmentation • Safety class • Confirmation gate • Web UI parity • Notes.\n"
    )
    parts.append(
        "**Coverage discipline (per §9.4):** every Sange wrapper documented here "
        "must do at least one of the seven §9.4 augmentations (AI / safety gate / "
        "lifecycle / audit / rich rendering / cross-VCS / config-aware). Pure "
        "passthrough rows are flagged in the Notes column.\n"
    )

    grouped: dict[str, list[CatalogRow]] = {tier: [] for tier in TIER_ORDER}
    for row in rows:
        grouped.setdefault(row.tier, []).append(row)

    summary_data = [
        [tier, str(len(grouped.get(tier, [])))]
        for tier in TIER_ORDER
    ]
    summary_data.append(["**Total**", str(len(rows))])
    parts.append(markdown.heading(2, "Summary"))
    parts.append(
        markdown.table(
            ["Tier", "Rows"],
            summary_data,
            alignments=["left", "right"],
        )
    )
    parts.append("")

    headers = [
        "Command",
        "Tier",
        "Purpose",
        "Sange wrapper",
        "AI augmentation",
        "Safety class",
        "Confirmation gate",
        "Web UI parity",
        "Notes",
    ]

    for tier in TIER_ORDER:
        tier_rows = grouped.get(tier, [])
        if not tier_rows:
            continue
        parts.append(markdown.heading(2, f"{tier} tier ({len(tier_rows)})"))
        parts.append(
            markdown.table(
                headers,
                [r.to_table_row() for r in tier_rows],
            )
        )
        parts.append("")

    parts.append(markdown.heading(2, "Sange-native verbs (no direct git equivalent)"))
    parts.append(
        "These commands are documented inline above (Power tier). They have no "
        "underlying `git` command — Sange invents them on top of the VCS surface."
    )
    parts.append("")
    parts.append(
        markdown.bullet_list(
            f"`sange {row.name}` — {row.purpose.removeprefix('(Sange-native) ')}"
            for row in SANGE_NATIVE_ROWS
        )
    )
    parts.append("")

    parts.append(markdown.heading(2, "How to update this appendix"))
    parts.append(
        markdown.bullet_list(
            [
                "Add a new Sange wrapper for a Git command → append a row to the "
                "`ENRICHMENT` dict in `tools/generators/git_catalog.py`.",
                "Reclassify a tier → edit the row's `tier` field there.",
                "Upgrade Git → the next run picks up new commands automatically; "
                "review the diff and enrich the newly-appearing rows.",
                "Verify integrity → `python tools/generators/verify_generated.py`.",
                "Regenerate → `python tools/generators/all.py --only T-G-001 --write`.",
            ]
        )
    )
    return "\n".join(parts)


def run(
    *,
    mode: WriteMode,
    clock: _dt.datetime,
    git_help_text: str | None = None,
    git_version_text: str | None = None,
    output_path: Path | None = None,
) -> list[WriteOutcome]:
    """Generator entry-point.

    Test parameters (`git_help_text`, `git_version_text`, `output_path`) make
    the generator reproducible without a live `git` binary and without
    touching the canonical output location.
    """

    rows, payload = _gather_rows(
        git_help_text=git_help_text,
        git_version_text=git_version_text,
    )
    git_version = _git_version(override=git_version_text)
    body = _build_body(rows=rows, git_version=git_version)

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

    results = run(
        mode=mode,
        clock=_dt.datetime.now(tz=_dt.timezone.utc),
    )
    rc = 0
    for r in results:
        if r.result is not None and r.result.value != "match":
            rc = 66
        line = f"[{mode.value}] {r.path}  sha256={r.output_sha256}"
        if r.result is not None:
            line += f"  ({r.result.value})"
        print(line)
    raise SystemExit(rc)
