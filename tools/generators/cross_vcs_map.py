"""Generate Appendix F — cross-VCS concept map.

T-G-003 — emits `docs/reference/appendix-f-cross-vcs.md`. Side-by-side table
showing how core VCS concepts map across Git / SVN / Mercurial (v1.0 mandatory)
and Fossil / Pijul (v2 planning). Foundation for the §6.2 VCS-agnostic Domain
layer.

Determinism (ADR-023):

  * Input is a hand-curated `CONCEPTS` tuple — no external data.
  * Per-concept rows have stable IDs (`C-NNN`) so future renames don't
    silently break tooling that links to them.
  * Re-runs are byte-identical for the same clock.
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

from _lib import markdown  # noqa: E402
from _lib.fingerprint import sha256_text  # noqa: E402
from _lib.output import (  # noqa: E402
    GeneratorMetadata,
    WriteMode,
    WriteOutcome,
    write_generated_file,
)

GENERATOR_VERSION = "1.0.0"
GENERATED_BY = "tools/generators/cross_vcs_map.py"
OUTPUT_PATH = REPO_ROOT / "docs" / "reference" / "appendix-f-cross-vcs.md"


# --------------------------------------------------------------------------- #
# Schema
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Concept:
    id: str               # stable ID, e.g. "C-001"
    concept: str          # short noun-phrase
    description: str
    git: str              # mandatory v1
    svn: str              # mandatory v1
    hg: str               # mandatory v1
    fossil: str = "—"     # v2 planning
    pijul: str = "—"      # v2 planning
    sange_domain: str = ""  # Sange domain entity (Repo, Commit, Branch, …)
    notes: str = ""


def _c(
    id_: str,
    concept: str,
    description: str,
    *,
    git: str,
    svn: str,
    hg: str,
    fossil: str = "—",
    pijul: str = "—",
    sange_domain: str = "",
    notes: str = "",
) -> Concept:
    return Concept(
        id=id_, concept=concept, description=description,
        git=git, svn=svn, hg=hg, fossil=fossil, pijul=pijul,
        sange_domain=sange_domain, notes=notes,
    )


# --------------------------------------------------------------------------- #
# The concept catalog
# --------------------------------------------------------------------------- #


CONCEPTS: tuple[Concept, ...] = (
    # ====== Repository topology ======
    _c(
        "C-001", "Repository", "The whole versioned project.",
        git=".git/ directory + working tree",
        svn="trunk/, branches/, tags/ in a central server",
        hg=".hg/ directory + working directory",
        fossil="Single .fossil SQLite file",
        pijul=".pijul/ directory",
        sange_domain="Repo",
    ),
    _c(
        "C-002", "Working copy", "Files in the user's local checkout.",
        git="Working tree (tracked + untracked files)",
        svn="Working copy (svn co)",
        hg="Working directory",
        fossil="Local checkout (open repository)",
        pijul="Working copy",
        sange_domain="Repo.path",
    ),
    _c(
        "C-003", "Staging area / Index", "Pre-commit holding pen.",
        git="Index (`git add` stages here)",
        svn="(none — `svn commit` commits the working copy directly)",
        hg="(none by default; `hg add` marks files; commit takes whole WC)",
        fossil="(none — `fossil commit` takes whole WC)",
        pijul="(none — uses patches as primary unit)",
        sange_domain="Commit.diff (lifecycle JSON wraps the staging concept)",
        notes="Git is the outlier; §6.8 commit lifecycle adds a uniform staging surface across all VCSes.",
    ),
    # ====== Commits + history ======
    _c(
        "C-010", "Commit / Revision", "Atomic snapshot of the project state.",
        git="Commit object (sha1/sha256 hash)",
        svn="Revision (monotonic integer, repo-wide)",
        hg="Changeset (sha1 hash, also has rev-number alias)",
        fossil="Check-in (sha1/sha256)",
        pijul="Patch (set of patches applied)",
        sange_domain="Commit",
    ),
    _c(
        "C-011", "Author / Committer", "Who made the change vs. who recorded it.",
        git="`author` and `committer` headers (can differ)",
        svn="Single `author` field per revision",
        hg="`user` field per changeset",
        fossil="`user` field per check-in",
        pijul="Patch author",
        sange_domain="Commit.author, Commit.committer",
    ),
    _c(
        "C-012", "Commit message", "Why the change was made.",
        git="Commit message (subject + body convention)",
        svn="Log message (set at commit time via `-m`)",
        hg="Commit message",
        fossil="Comment field",
        pijul="Patch description",
        sange_domain="CommitMessage (§6.8.3 JSON schema)",
    ),
    _c(
        "C-013", "Diff / Patch", "Set of file changes between two states.",
        git="`git diff`, `git format-patch` (unified diff)",
        svn="`svn diff` (unified diff)",
        hg="`hg diff` (unified diff)",
        fossil="`fossil diff`",
        pijul="Patch (first-class object, not derived from diff)",
        sange_domain="CommitDiff",
        notes="Pijul treats patches as the primary unit — distinct from diff-derived models.",
    ),
    _c(
        "C-014", "Log / History", "Time-ordered sequence of commits.",
        git="`git log` (DAG-walk)",
        svn="`svn log` (linear by revision number)",
        hg="`hg log` (DAG-walk)",
        fossil="`fossil timeline`",
        pijul="`pijul log`",
        sange_domain="Commit list",
    ),
    _c(
        "C-015", "Blame / Annotate", "Per-line authorship.",
        git="`git blame`",
        svn="`svn blame` (alias: praise, annotate, ann)",
        hg="`hg annotate`",
        fossil="`fossil blame`",
        pijul="`pijul credit`",
        sange_domain="(Sange wraps via `sange blame`)",
    ),
    # ====== Branching ======
    _c(
        "C-020", "Branch", "Independent line of development.",
        git="Branch ref (`refs/heads/<name>`)",
        svn="Branch = URL path under `branches/` (convention)",
        hg="Named branch (permanent) or bookmark (movable, like Git)",
        fossil="Branch (tag-based)",
        pijul="Channel",
        sange_domain="Branch",
        notes="SVN branches are URL paths, not refs — `sange branch` translates between the two models.",
    ),
    _c(
        "C-021", "Tag (lightweight)", "Named pointer to a commit.",
        git="Lightweight tag (`refs/tags/<name>`)",
        svn="Tag = URL path under `tags/` (convention)",
        hg="Tag (recorded in `.hgtags`)",
        fossil="Tag",
        pijul="Tag",
        sange_domain="Release.tag",
    ),
    _c(
        "C-022", "Tag (signed/annotated)", "Tag with metadata + GPG signature.",
        git="Annotated tag (`git tag -s <name>`)",
        svn="(no native equivalent — sign the tag-creating commit instead)",
        hg="Signed tag (via `extensions.gpg`)",
        fossil="Tag with signature (via cryptosign)",
        pijul="(no native equivalent)",
        sange_domain="Release (signed)",
        notes="Sigstore + cosign cover the gap for VCSes lacking native signed tags.",
    ),
    _c(
        "C-023", "HEAD / Current revision", "Where the working copy is positioned.",
        git="HEAD ref (file or symbolic ref)",
        svn="BASE revision (working copy's parent)",
        hg="Working-directory parent (`hg parents`)",
        fossil="Checkout revision",
        pijul="Current state of the channel",
        sange_domain="Repo.head",
    ),
    # ====== Remote operations ======
    _c(
        "C-030", "Remote / Origin", "Where the repo is hosted.",
        git="Remote (`origin`, plus arbitrary additional remotes)",
        svn="Repository URL (single source of truth)",
        hg="Path (`default` is conventional origin)",
        fossil="Sync URL",
        pijul="Remote (channel + URL)",
        sange_domain="Repo.remote",
    ),
    _c(
        "C-031", "Clone / Checkout", "First-time fetch into a local directory.",
        git="`git clone <url>`",
        svn="`svn checkout <url>`",
        hg="`hg clone <url>`",
        fossil="`fossil clone <url> + fossil open`",
        pijul="`pijul clone <url>`",
        sange_domain="(Sange wraps via `sange clone`)",
    ),
    _c(
        "C-032", "Fetch", "Pull remote commits without merging into working copy.",
        git="`git fetch`",
        svn="(implicit — `svn update` does both)",
        hg="`hg pull` (without `-u`)",
        fossil="`fossil pull`",
        pijul="`pijul pull`",
        sange_domain="(Sange wraps via `sange fetch`)",
    ),
    _c(
        "C-033", "Update / Sync", "Apply remote commits to working copy.",
        git="`git pull` (= fetch + merge or fetch + rebase)",
        svn="`svn update` (fetch + merge into WC)",
        hg="`hg pull -u`",
        fossil="`fossil update`",
        pijul="`pijul pull` (idempotent)",
        sange_domain="(Sange wraps via `sange sync`)",
    ),
    _c(
        "C-034", "Push / Commit-to-remote", "Send local commits to a remote.",
        git="`git push <remote> <branch>`",
        svn="`svn commit` (commits directly to the central server)",
        hg="`hg push`",
        fossil="`fossil push`",
        pijul="`pijul push`",
        sange_domain="(Sange wraps via `sange push` / `sange publish`)",
        notes="SVN's `commit` does the role of both Git's `commit` and `push`; the §6.8 lifecycle separates them on the Sange side.",
    ),
    # ====== Merge / rebase ======
    _c(
        "C-040", "Merge", "Integrate two histories.",
        git="`git merge` (creates merge commit OR fast-forward)",
        svn="`svn merge` (merge-tracking via `svn:mergeinfo` properties)",
        hg="`hg merge`",
        fossil="`fossil merge`",
        pijul="(patches commute; merge is implicit)",
        sange_domain="(Sange wraps via `sange merge`)",
        notes="Pijul's patch-commutation model fundamentally differs from DAG-based VCSes; merges that are conflict-free require zero merge commits.",
    ),
    _c(
        "C-041", "Rebase / History rewrite (local)", "Replay commits on a different base.",
        git="`git rebase`",
        svn="(no equivalent — history is immutable on the server)",
        hg="`hg rebase` (extension)",
        fossil="(no rebase — history is immutable; use checkout + commit instead)",
        pijul="(patches reorder naturally via commutation)",
        sange_domain="(Sange wraps via `sange rebase`)",
        notes="SVN + Fossil are intentionally rebase-free; the §6.11 purge subsystem is the only way to rewrite history in those VCSes.",
    ),
    _c(
        "C-042", "Cherry-pick", "Apply a single commit from elsewhere.",
        git="`git cherry-pick <sha>`",
        svn="`svn merge -c <rev>`",
        hg="`hg graft <rev>`",
        fossil="`fossil merge --cherrypick`",
        pijul="(apply individual patch directly)",
        sange_domain="(Sange wraps via `sange cherry-pick`)",
    ),
    _c(
        "C-043", "Conflict resolution", "Reconcile divergent changes.",
        git="`git mergetool`, edit + `git add` + `git commit`",
        svn="`svn resolve --accept theirs|mine|...`",
        hg="`hg resolve`",
        fossil="(manual edit + `fossil commit`)",
        pijul="(patches commute when possible; explicit resolution otherwise)",
        sange_domain="(Sange wraps via `sange resolve` with AI-suggested strategies)",
    ),
    # ====== Undo / recovery ======
    _c(
        "C-050", "Revert (add inverse)", "Create a new commit that undoes an earlier one.",
        git="`git revert <sha>`",
        svn="`svn merge -r REV:PREV` then commit",
        hg="`hg backout <rev>`",
        fossil="(manual: checkout PREV, commit a reverting change)",
        pijul="`pijul unrecord` (remove patch from channel)",
        sange_domain="(Sange wraps via `sange revert`)",
    ),
    _c(
        "C-051", "Reset / Rewind", "Move HEAD to a different commit.",
        git="`git reset --soft|--mixed|--hard <sha>`",
        svn="(no equivalent — central history is immutable; revert local WC instead)",
        hg="`hg update <rev>` + `hg purge` for hard equivalent",
        fossil="`fossil checkout <prev>` + `fossil commit` to record",
        pijul="`pijul unrecord` walks the channel back",
        sange_domain="(Sange wraps via `sange reset` with type-to-confirm on `--hard`)",
    ),
    _c(
        "C-052", "Stash / Shelve", "Temporarily set aside uncommitted changes.",
        git="`git stash` / `git stash pop`",
        svn="`svn diff > patch && svn revert -R .` then `svn patch <patch>`",
        hg="`hg shelve` / `hg unshelve`",
        fossil="`fossil stash save` / `fossil stash pop`",
        pijul="`pijul unrecord` + selectively re-record later",
        sange_domain="(Sange wraps via `sange stash`)",
    ),
    _c(
        "C-053", "Reflog / Recovery log", "Local audit trail of HEAD movements.",
        git="`git reflog`",
        svn="(no equivalent on the server; svn dump files preserve history)",
        hg="`hg journal` (extension)",
        fossil="(implicit — every check-in is in `fossil timeline`)",
        pijul="(implicit — patches are first-class)",
        sange_domain="(Sange wraps via `sange reflog` + `sange recover`)",
        notes="The §7.0.7 hash-chained audit log is Sange's cross-VCS unification of reflog-like recovery.",
    ),
    _c(
        "C-054", "Bisect", "Binary search to find a regression-introducing commit.",
        git="`git bisect`",
        svn="(no native — script + `svn update -r <rev>` loop)",
        hg="`hg bisect`",
        fossil="`fossil bisect`",
        pijul="(no native)",
        sange_domain="(Sange wraps via `sange bisect`)",
    ),
    # ====== Hooks + policy ======
    _c(
        "C-060", "Hooks", "Scripts that run at VCS event boundaries.",
        git=".git/hooks/{pre-commit,pre-push,commit-msg,...}",
        svn="repo/hooks/{pre-commit,post-commit,pre-revprop-change,...}",
        hg=".hg/hgrc [hooks] section",
        fossil="(via `fossil settings ticket-newticket-script` etc.)",
        pijul=".pijul/hooks/",
        sange_domain="HookSpec (§7.4)",
    ),
    _c(
        "C-061", "Ignore patterns", "Files VCS should not track.",
        git=".gitignore (per-directory)",
        svn="svn:ignore property",
        hg=".hgignore",
        fossil="`fossil settings ignore-glob`",
        pijul=".ignore",
        sange_domain="GitignoreProfile (§6.5.1) + variant matrix (§6.5.2)",
    ),
    _c(
        "C-062", "Submodules / Externals", "Nested repositories.",
        git="`git submodule`",
        svn="svn:externals property",
        hg="`hg subrepository` (extension)",
        fossil="(no first-class — use `fossil settings allow-fossil-cmd` patterns)",
        pijul="(no first-class)",
        sange_domain="(passthrough via `sange submodule`)",
    ),
    # ====== Large files + LFS ======
    _c(
        "C-070", "Large file storage", "Binary blobs stored out-of-band.",
        git="Git LFS (separate pointer protocol)",
        svn="(native — SVN stores blobs in repo directly; no LFS)",
        hg="largefiles or LFS extension",
        fossil="(native — Fossil stores binaries in repo SQLite)",
        pijul="(native — patches carry their content)",
        sange_domain="(Sange wraps Git LFS via `sange lfs`; other VCSes are natively binary-friendly)",
    ),
    # ====== Bundle / transport ======
    _c(
        "C-080", "Bundle / Patch series", "Self-contained transferable history slice.",
        git="`git bundle create` / `git bundle unbundle`",
        svn="`svnadmin dump` / `svnadmin load`",
        hg="`hg bundle` / `hg unbundle`",
        fossil="`fossil bundle`",
        pijul="Patch files (`pijul record` produces a patch)",
        sange_domain="ReleaseBundle (§6.9)",
        notes="The §6.9 Release Bundling subsystem wraps each VCS's native bundle format with sigstore + SBOM + provenance attestation.",
    ),
    # ====== History rewrite (purge) ======
    _c(
        "C-090", "History rewrite (purge sensitive content)", "Removing data from history.",
        git="`git filter-repo` (or BFG)",
        svn="`svnadmin dump | svndumpfilter exclude | svnadmin load`",
        hg="`hg convert --filemap` / `hg strip`",
        fossil="(very limited — `fossil shun` marks artifacts; some content stays)",
        pijul="`pijul unrecord` (removes patches cleanly by design)",
        sange_domain="PurgePlan (§6.11)",
        notes="The §6.11 VCS History Purge subsystem wraps every VCS's destructive rewrite path with the same 8-gate / 8-verify safety contract.",
    ),
    # ====== Sange-native concepts (no VCS equivalent) ======
    _c(
        "C-100", "Variant (stage × flavor)", "Multi-axis source-set composition.",
        git="(no equivalent)",
        svn="(no equivalent)",
        hg="(no equivalent)",
        fossil="(no equivalent)",
        pijul="(channels are the closest — but Pijul channels are independent histories, not orthogonal axes)",
        sange_domain="VariantMatrix (§6.5.2 + ADR-032)",
        notes="Sange-native — derived from Android Studio's build variants.",
    ),
    _c(
        "C-101", "Commit lifecycle JSON", "Reviewable AI-augmented commit-message lifecycle.",
        git="(no equivalent)",
        svn="(no equivalent)",
        hg="(no equivalent)",
        fossil="(no equivalent)",
        pijul="(no equivalent)",
        sange_domain="Commit (§6.8.3 JSON schema with 8-state machine)",
        notes="Sange-native — §6.8 commit lifecycle.",
    ),
)


# --------------------------------------------------------------------------- #
# Rendering
# --------------------------------------------------------------------------- #


def _build_body() -> str:
    parts: list[str] = []
    parts.append(markdown.heading(1, "Appendix F — Cross-VCS concept map"))
    parts.append(
        "> Generated by `tools/generators/cross_vcs_map.py` (T-G-003). "
        "Side-by-side mapping of core VCS concepts across Git, SVN, "
        "Mercurial (v1.0 mandatory) and Fossil + Pijul (v2 planning). "
        "Foundation for the §6.2 VCS-agnostic Domain layer.\n"
    )
    parts.append(
        f"**Total concepts:** {len(CONCEPTS)}. "
        "Concept IDs (`C-NNN`) are stable per release; renaming an ID is a "
        "SemVer-major change.\n"
    )

    parts.append(markdown.heading(2, "How to read this table"))
    parts.append(
        markdown.bullet_list(
            [
                "**Concept** — the abstract VCS operation or entity.",
                "**Git / SVN / Hg** — v1.0 mandatory columns. Sange's Domain layer (§6.2) abstracts over these three.",
                "**Fossil / Pijul** — v2 planning. Listed where a clean equivalent exists; `—` where the model differs fundamentally.",
                "**Sange domain entity** — the §6.2 Domain class the concept maps to (Repo, Commit, Branch, Release, PurgePlan, …).",
                "**Notes** — caveats, modelling tradeoffs, the reason a concept is Sange-native, etc.",
            ]
        )
    )
    parts.append("")

    parts.append(markdown.heading(2, "Concept catalog"))
    headers = [
        "ID",
        "Concept",
        "Description",
        "Git",
        "SVN",
        "Mercurial",
        "Fossil",
        "Pijul",
        "Sange domain",
        "Notes",
    ]
    rows = [
        [
            c.id,
            c.concept,
            c.description,
            c.git,
            c.svn,
            c.hg,
            c.fossil,
            c.pijul,
            c.sange_domain or "—",
            c.notes or "—",
        ]
        for c in CONCEPTS
    ]
    parts.append(markdown.table(headers, rows))
    parts.append("")

    parts.append(markdown.heading(2, "Coverage summary"))
    rows = [
        ["Total concepts", str(len(CONCEPTS))],
        ["With v1 mandatory columns (Git+SVN+Hg)", str(len(CONCEPTS))],
        [
            "With Fossil column populated (v2 planning)",
            str(sum(1 for c in CONCEPTS if c.fossil != "—")),
        ],
        [
            "With Pijul column populated (v2 planning)",
            str(sum(1 for c in CONCEPTS if c.pijul != "—")),
        ],
        [
            "Sange-native concepts (no direct VCS equivalent)",
            str(sum(1 for c in CONCEPTS if "Sange-native" in c.notes)),
        ],
    ]
    parts.append(
        markdown.table(["Metric", "Count"], rows, alignments=["left", "right"])
    )
    parts.append("")

    parts.append(markdown.heading(2, "Architectural significance"))
    parts.append(
        "Per §6.2 the Sange Domain layer is **VCS-agnostic** — a `Commit` "
        "doesn't know whether it came from Git or SVN. This table is the "
        "mapping the Adapter layer (`adapters/vcs/git.py`, `adapters/vcs/svn.py`, "
        "`adapters/vcs/hg.py`) uses to translate VCS-specific terminology into "
        "the abstract Domain. New VCS support = a new Adapter that fills out "
        "the rows in this table for that VCS; **zero changes** to Application "
        "or Domain layers."
    )
    parts.append("")
    parts.append(markdown.heading(2, "How to extend the table"))
    parts.append(
        markdown.bullet_list(
            [
                "Add a new concept → append a `_c(...)` literal to `CONCEPTS` in `tools/generators/cross_vcs_map.py`. Use the next free `C-NNN` ID.",
                "Add a new VCS column → introduce a new field on the `Concept` dataclass + update the renderer. New VCS columns are SemVer-minor additions; renaming is SemVer-major.",
                "Promote v2 columns to v1 mandatory → update the relevant Tier when the VCS adapter ships (e.g. Mercurial in v2.0, Fossil in v3.0).",
                "Regenerate → `python tools/generators/all.py --only T-G-003 --write`.",
                "Verify integrity → `python tools/generators/verify_generated.py`.",
            ]
        )
    )
    return "\n".join(parts)


# --------------------------------------------------------------------------- #
# Generator entry-point
# --------------------------------------------------------------------------- #


def _input_sha256() -> str:
    payload = {
        "generator_version": GENERATOR_VERSION,
        "concepts": [
            {
                "id": c.id,
                "concept": c.concept,
                "description": c.description,
                "git": c.git,
                "svn": c.svn,
                "hg": c.hg,
                "fossil": c.fossil,
                "pijul": c.pijul,
                "sange_domain": c.sange_domain,
                "notes": c.notes,
            }
            for c in CONCEPTS
        ],
    }
    return sha256_text(json.dumps(payload, sort_keys=True))


def run(
    *,
    mode: WriteMode,
    clock: _dt.datetime,
    output_path: Path | None = None,
) -> list[WriteOutcome]:
    target = output_path or OUTPUT_PATH
    meta = GeneratorMetadata(
        generated_by=GENERATED_BY,
        generator_version=GENERATOR_VERSION,
        input_sha256=_input_sha256(),
        manual_edits_allowed=False,
        generated_at=clock,
    )
    return [write_generated_file(target, _build_body(), meta, mode=mode)]


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
        print(f"[{mode.value}] {r.path}  sha256={r.output_sha256}"
              + (f"  ({r.result.value})" if r.result else ""))
    raise SystemExit(rc)
