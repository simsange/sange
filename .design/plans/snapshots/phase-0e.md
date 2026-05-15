# Snapshot — Phase 0e (ecosystem seeds + push-gated state) — 2026-05-16

**Created:** 2026-05-16T03:30Z
**Created by:** model:claude-opus-4-7@simtabihq
**Last git commit:** `8a215e7` Record `git remote add origin` in session log
**Parent of snapshot:** `64ad581` Add Phase 0d end-of-phase snapshot (v0.1.0 tag-gate)
**Reason for snapshot:** Phase 0e captures the post-Phase-0d ecosystem
work: the URL migration to the `sangedev` GitHub org, the v0.1.0 retag
at the corrected commit, the `documentation/` and `org-github/` seeds
for the future sangedev sister repos, the operator-facing
`docs/release.md`, and the local `origin` remote configuration. The
v0.1.0 tag is still local-only; `push` requires explicit user verb
per `~/.claude/CLAUDE.md`. This is the cold-resume artifact for the
operator returning to ship v0.1.0. Per ADR-031.

---

## State of the world

### What Phase 0e produced

**Eight commits past the Phase 0d snapshot (`64ad581`):**

| SHA | Subject | Notes |
|---|---|---|
| `48e99fb` | Record v0.1.0 tag creation in session log | Session-log row for the v0.1.0 tag-at-`64ad581` event (the tag was created the same session as the snapshot). |
| `c7090dc` | Migrate URLs: github.com/simtabi/sange → github.com/sangedev/sange | 16 files updated; cosign verification regex updated in `kit_manifest.py`; `MANIFEST.toml` regenerated. |
| `b947a2e` | Record URL migration in session log (S-003-T-42) | Audit row for the migration. |
| `ab89f2b` | Record v0.1.0 retag in session log (S-003-T-43) | The v0.1.0 tag was deleted + recreated at the URL-corrected commit (`b947a2e`); both ops local-only. |
| `553b063` | Scaffold sangedev/documentation seed | `documentation/` MkDocs Material site seeded; +32 tests. |
| `c65dbd4` | Scaffold sangedev/.github profile repo seed | `org-github/` community-health files; +41 tests. |
| `b95a9b2` | Write docs/release.md (operator-facing release recipe) | ~220-line OIDC + multi-arch + tag recipe; +33 tests. |
| `8a215e7` | Record `git remote add origin` in session log (S-003-T-47) | `origin` configured at `https://github.com/sangedev/sange.git`; no fetch, no push. |

**Test growth:** 1017 (Phase 0d boundary) → **1123 passing** (+106
across 4 new test modules: `test_documentation_scaffold.py`,
`test_org_github_scaffold.py`, `test_release_doc.py`, plus added
coverage in existing modules).

**File count:** 246 tracked files (Phase 0d was 215, +31 for the
two ecosystem seeds + release.md + new test modules).

### The `sangedev` GitHub-org plan

Per user direction on 2026-05-15: the Sange ecosystem lives at
`github.com/sangedev`, a dedicated GitHub org owned by Simtabi LLC.
Three repos planned at v0.1:

| Target repo | Status | Seed in this repo |
|---|---|---|
| `github.com/sangedev/sange` | **exists** (verified 200) | This repo. v0.1.0 tag local; push required to ship. |
| `github.com/sangedev/documentation` | **404** (planned) | `documentation/` directory in this repo. |
| `github.com/sangedev/.github` | **404** (planned) | `org-github/` directory in this repo. |

The two non-existent repos are seeded **in this repo**; the
operator creates them on GitHub then runs the bootstrap shell
recipe in each seed's `README.md` to push the seed content as the
initial commit of the new repo. After bootstrap, the operator can
delete the seed directory from this repo (optional — keeping it
as the source-of-truth + pushing via `git subtree push` is also valid).

### Subsystems shipped in Phase 0e

**Zero new runtime subsystems.** Every commit is either:

1. **URL/metadata maintenance** — the simtabi→sangedev migration.
2. **Ecosystem seeds** — `documentation/` + `org-github/` directories.
3. **Operator documentation** — `docs/release.md`.
4. **Local git config** — `origin` remote (no remote state changed).

The v0.1.0 codebase itself is unchanged from Phase 0d's `64ad581`
PLUS the URL fix in `c7090dc`. The v0.1.0 tag points at `b947a2e`
which captures the URL-corrected tree.

### Generators

**14/16 generators implemented** — unchanged from Phase 0d. The
URL migration regenerated `docs/reference/kit-manifest.md` +
`templates/MANIFEST.toml`; the new `docs/release.md` triggered a
T-G-006 regenerate of `docs/README.md` to index it.

`all.py --check` reports `ok=14 not_implemented=2 stale=0`.

### ADRs

No new ADRs in Phase 0e. ADR-015 ("URL scheme") was **updated** to
add the sangedev-org note + "Updated 2026-05-16" timestamp; per
`decisions-log.md` policy the ADR remains accepted (it's a clarification,
not a new decision).

---

## What's CHANGED from Phase 0d

1. **URLs migrated.** Every operational file (pyproject, README,
   Dockerfile, release.yml, etc.) references
   `github.com/sangedev/sange`. Audit-trail rows in `session-log.md`
   that record what was committed at write-time are intentionally
   NOT modified (ADR-031: history is append-only).

2. **v0.1.0 tag points at the corrected commit.** The original
   tag at `64ad581` (pre-URL-fix) was deleted; the new tag is at
   `b947a2e`. Both operations local-only.

3. **Two sister-repo seeds exist in this repo.** `documentation/`
   for the docs site, `org-github/` for org-wide community-health
   files. Each has its own `README.md` with the migration shell
   recipe.

4. **Operator-facing release recipe is written.** `docs/release.md`
   covers the full procedure end-to-end; the maintainer can run a
   release entirely from that doc without consulting other refs.

5. **`origin` remote is configured.** Local-only; sets up the
   runway so `git push origin main` / `git push origin v0.1.0`
   Just Work without `-u` flag plumbing.

6. **Test suite at 1123.** Every new artifact has structural
   tests; cross-file invariants enforced (URL discipline,
   canonical-source byte-equality, workflow-name consistency).

---

## What's NOT done yet (the v0.1.0 publish gate)

**Three remote-state-changing operations remain.** Each requires
an explicit user verb per `~/.claude/CLAUDE.md`:

| User verb | Action | Effect |
|---|---|---|
| `"push main"` | `git push origin main` | Publishes the codebase to `github.com/sangedev/sange`. **NO release triggered** (tags aren't pushed by default; `git push origin main` doesn't include refs/tags). |
| `"push v0.1.0"` or `"push tag v0.1.0"` | `git push origin v0.1.0` | Triggers `.github/workflows/release.yml` → PyPI (OIDC trusted-publisher) + GHCR multi-arch push + GitHub Release auto-generation. **IRREVERSIBLE** — the tag is immutable once accepted. |
| `"push main and v0.1.0"` | Both, sequentially | The full publish flow. |

The release pipeline takes ~7 minutes wall-clock on first run.

### Bootstrap for the sister repos

Independent of the main repo's push, two more bootstraps remain:

1. **Create `github.com/sangedev/documentation`** — manual step:
   visit https://github.com/organizations/sangedev/repositories/new,
   name the repo `documentation`. Then run the shell recipe from
   `documentation/README.md`.

2. **Create `github.com/sangedev/.github`** — manual step: name
   the repo exactly `.github` (the leading dot is intentional —
   it's how GitHub recognizes the org-level community-health
   repo). Then run the shell recipe from `org-github/README.md`.

These can be done in any order, including before or after the
main repo's `v0.1.0` ships. None are gated on the others.

### One non-repo follow-up

The Simtabi org-level `CLAUDE.md` at
`/Users/imanimanyara/Artisan/projects/opensource/CLAUDE.md`
lists Simtabi-owned GitHub orgs (`simtabi`, `ichava`, `laranail`,
`mukoracms`). `sangedev` should be added per the file's own
documented "Adding / removing an org" procedure. One-line table
edit. Outside this repo's scope; do explicitly via:

```
| `sangedev`   | `/Users/imanimanyara/Artisan/projects/opensource/sange/`     | active | Sange ecosystem — main project + documentation + .github seeds live under the main sange checkout until standalone repos are bootstrapped. |
```

The user can authorize this with a verb like `"register sangedev
org"` or do it manually.

---

## What the next session must do

If the user hasn't pushed yet:

1. **Read this snapshot first.** The push-gate options + operator
   checklist + sister-repo bootstraps are all documented above.

2. **Wait for an explicit verb.** Per CLAUDE.md:
   - `"push main"` → `git push origin main`
   - `"push v0.1.0"` → `git push origin v0.1.0`
   - `"push main and v0.1.0"` → both
   - `"register sangedev org"` → edit
     `/Users/imanimanyara/Artisan/projects/opensource/CLAUDE.md`
   - `"hold"` / `"not yet"` → log a row + no action

3. **After main pushes:** verify the GitHub repo received the
   commit history. The `sangedev/sange` repo on GitHub should
   show the README + Phase 0e content + the v0.1.0 tag in the
   tags list (if the tag is pushed too).

4. **After the tag pushes:** monitor `release.yml` at
   `https://github.com/sangedev/sange/actions`. ~7 minutes
   wall-clock on first run. If anything fails, the recovery
   procedure is in `docs/release.md`.

5. **For the sister repos:** the user creates each repo on
   GitHub then runs the documented shell recipe. The shell
   recipes don't need any verb authorization from the model —
   they're operator-driven.

6. **Current branch:** `main`. Last commit: `8a215e7`. **Working
   tree note:** `docs/tools/README.md` carries a benign
   frontmatter-timestamp modification (`output_sha256` unchanged;
   only `generated_at` differs). Not committed; can be cleaned
   up in a follow-up regen if desired. Not load-bearing.

7. **Active in-flight operations:** None.
   - No `.sange/` in repo root.
   - No half-emitted generator outputs.
   - No uncommitted edits beyond the noted timestamp drift.

8. **Open `🧪` clarifying questions for the user:** Two —
   **the v0.1.0 push verbs** and **whether to register
   sangedev in the Simtabi org-level CLAUDE.md**. Both wait
   for the user.

9. **Critical sequencing reminders:**
   - **Never push without explicit instruction** per
     `~/.claude/CLAUDE.md` — applies to both `main` and tags.
   - **Never force-push a pushed tag** — releases are immutable;
     fix forward with `v0.1.0.post1` or `v0.1.1`.
   - **Append a session-log row after every completed task** per
     ADR-028.
   - **Read before reference** per ADR-030 — verify the remote
     state after each push lands before claiming success.
   - **Multi-arch from day one** per ADR-033 — release.yml's
     docker job builds `linux/amd64` + `linux/arm64`.

---

## Resumability test

  * [x] **A fresh session given only this snapshot can correctly
        identify the next action.** "What the next session must
        do" section 1+2 names the four valid user verbs (push
        main / push v0.1.0 / push both / register sangedev), the
        operator follow-ups for the two sister repos, and the
        release.yml pipeline monitoring path.
  * [x] **The fresh session does not need to ask for additional
        context that should have been in this snapshot.** Every
        Phase 0e commit is named with its SHA + scope; the
        ecosystem plan (three target repos + their status + their
        seeds) is documented; the push-gate options are explicit;
        the post-tag failure-recovery path is in `docs/release.md`
        (referenced).

Both boxes checked. Snapshot complete.

---

## Audit-chain link

This snapshot is the **sixth** cold-resume artifact in the project's
history. The git-history chain past `64ad581` (phase-0d):

```
HEAD (8a215e7) → b95a9b2 → c65dbd4 → 553b063 → ab89f2b
              → b947a2e → c7090dc → 48e99fb → 64ad581 (phase-0d)
              → 018d5be → 876f3ad → 22a5ac3 → 29ee532
              → f985ac6 (phase-0c) → … (back through phase-0b/a/design)
```

The integrity of this snapshot rests on:

  * The 14 implemented generators + 15 generator-emitted files
    (unchanged from Phase 0d boundary; URL migration regenerated
    affected outputs but ok=14/16 net-state unchanged).
  * Cross-reference resolution via
    `tools/generators/verify_session_log.py: 99 rows parsed; 0 failures`.
  * The `1123 passed` test-suite output reproducible by running
    `PYTHONPATH=src python3 -m pytest -q` from the repo root.
  * The `all.py --check ok=14 not_implemented=2 stale=0` output
    reproducible by running it from the repo root.
  * Git commit `8a215e7` being reachable from `main` and containing
    the expected 246 tracked files.
  * The v0.1.0 tag at `b947a2e` being annotated + carrying
    `Source: https://github.com/sangedev/sange` in its message
    body — verifiable via `git show v0.1.0 --no-patch`.
  * The `origin` git remote being configured at
    `https://github.com/sangedev/sange.git` — verifiable via
    `git remote -v`.
  * Both sister-repo seeds (`documentation/` + `org-github/`)
    being present with their respective `README.md` migration
    recipes and full test coverage.

If any of the above is no longer true when this snapshot is read,
the snapshot is stale. The reader appends a `S-NNN-T-MM` row to
the session log noting the discrepancy before proceeding.

---

*Maintained alongside the design workbook. Phase 0e → v0.1.0
public release boundary. The next snapshot (`v0.1.md`) lands
when the v0.1.0 tag is pushed AND the release pipeline completes
— both required for the snapshot to mark the release as
"shipped".*
