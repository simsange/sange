# Snapshot — Phase 1 docs sprint complete — 2026-05-16

**Created:** 2026-05-16T02:30Z
**Created by:** model:claude-opus-4-7@simtabihq
**Last git commit:** `c0057aa` docs(changelog): record the 13-doc sprint under [Unreleased]
**Parent of snapshot:** `c64f563` Fix CI post-rename: -u flag in test fixture, skip version-bound generators (the `phase-0e-release-aftermath.md` snapshot reference commit)
**Reason for snapshot:** Phase 1 CLI surface closed end-to-end (T-040..T-045)
+ the 13-doc reader-facing sprint completed. State now: every `Planned`
README row that wasn't gated on a v0.5+/v1.0+ feature is closed. Cold-resume
artifact for the next session — whether that's the operator activating
PyPI for v0.1.0 publish, cutting v0.1.0.post1 from the queue, or
starting Phase 2 work. Per ADR-031.

---

## State of the world

### Eighteen commits past `phase-0e-release-aftermath.md`

| SHA | Subject | Notes |
|---|---|---|
| `c64f563` | Fix CI post-rename: -u flag + skip version-bound generators | The prior snapshot's reference commit. |
| `c582438` | Snapshot — Phase 0e release-aftermath | The snapshot file itself. |
| `a6b6204` | Fold v0.1.0 lessons into docs/release.md | Step 0 pre-flight checklist + "Failure modes seen in production" table. |
| `7625d8a` | feat(cli): add `sange commits new` (T-042) | Manual draft surface; 7 tests in `TestCommitsNew`. |
| `29a214b` | feat(cli): add submit / reject / commit lifecycle verbs (T-044) | 3 verbs + 14 tests. The remaining lifecycle surface. |
| `2840776` | feat(cli): add `sange commits ai` alias (T-043) | Typer-alias registration of `commit_command`; 5 tests in `TestCommitsAi`. |
| `a7e8b87` | docs(reference): regenerate cli-reference for Phase 1 verbs | T-G-009 picked up the 5 new verbs. |
| `26f5230` | docs(changelog): catch up root CHANGELOG.md through Phase 1 closure | Created the `[Unreleased]` + `[0.1.0]` structure. |
| `af44c12` | docs(readme): bring status line + doc table to current accuracy | Two-tier "Live now / Planned" refactor; 9-broken → 0-broken links. |
| `832bf13` | docs(tools): add commit lifecycle walkthrough + regen index | First per-tool walkthrough. |
| `8bb4a80` | docs: add quickstart.md + sync README table | 5-minute onramp. |
| `f1d4ab6` | docs(governance): add roadmap.md | Reader-friendly v0.1 → v4.0+ map. |
| `2b06906` | docs(governance): add adr-process.md | How Sange records decisions. |
| `be8eb19` | docs(security): add prompt-injection.md | T-030 redaction posture in one place. |
| `1f10c3c` | docs(security): add slsa-and-sbom.md | Supply-chain integrity claims. |
| `67ffc5d` | docs: add architecture.md | Reader's guide mapping the canonical 1500-line deliverable. |
| `e6fb894` | docs: close the v0.1-eligible "Planned" docs | installation + tools/vcs/git + tools/lang/python. |
| `ee2be66` | docs: second closing pass — svn / privacy / node + CONTRIBUTING fix | The "all undone tasks" closing batch. |
| `c0057aa` | docs(changelog): record the 13-doc sprint under [Unreleased] | The current HEAD. |

**Test count drift:** 1137 (phase-0e boundary) → **1163 passing** (+26 across `TestCommitsNew`, `TestCommitsSubmit`, `TestCommitsReject`, `TestCommitsCommit`, `TestCommitsAi`).

**Tracked file count:** 252 (phase-0e boundary) → **266** (+14 — 13 new docs + the snapshot file itself).

**Docs index count** (`docs/README.md`): 14 (phase-0e boundary) → **26** (+12 — the new docs minus governance/privacy.md which sits in governance/ alongside roadmap and adr-process; also +1 for snapshot itself, balanced).

### Phase 1 CLI surface — closed

Per [`.design/plans/checklist.md::Phase 1`](../checklist.md):

| Task | Status | Verbs |
|---|---|---|
| T-040 | ✓ done | typer skeleton, global flags |
| T-041 | ✓ done | `sange init` |
| T-042 | ✓ done | `sange commits new` |
| T-043 | ✓ done | `sange commits ai` (typer-alias of `sange commit`) |
| T-044 | ✓ done | `sange commits submit / reject / commit / push` |
| T-045 | ✓ done | `sange commit` happy-path alias |

The §6.8.4 "granular lifecycle commands" design intent is realized.
Every transition in the §6.8.2 state machine has a CLI verb.

### Docs sprint scoreboard

**13 of 16 "Planned" README docs landed.** The remaining 3 are
correctly NOT written; they describe features that don't ship yet.

| File | Status | Gate |
|---|---|---|
| `docs/installation.md` | ✓ done | (was) PyPI publish — wrote honestly with source-install path + future-pip-install framing |
| `docs/quickstart.md` | ✓ done | 5-min onramp |
| `docs/architecture.md` | ✓ done | Reader's guide |
| `docs/tools/workflow/commit-lifecycle.md` | ✓ done | First per-tool walkthrough |
| `docs/tools/vcs/git.md` | ✓ done | Git adapter |
| `docs/tools/vcs/svn.md` | ✓ done | SVN-plan honest about v0.5 adapter gating; points at Appendix E (ships) |
| `docs/tools/lang/python.md` | ✓ done | Python projects |
| `docs/tools/lang/node.md` | ✓ done | Node.js projects |
| `docs/governance/roadmap.md` | ✓ done | v0.1 → v4.0+ map |
| `docs/governance/adr-process.md` | ✓ done | How decisions are recorded |
| `docs/governance/privacy.md` | ✓ done | Privacy + telemetry |
| `docs/security/prompt-injection.md` | ✓ done | T-030 redaction |
| `docs/security/slsa-and-sbom.md` | ✓ done | Supply chain |
| `docs/tools/release/bundle.md` | **NOT written** | v0.5+ release engine doesn't ship |
| `docs/tools/security/purge.md` | **NOT written** | v1.0 purge subsystem doesn't ship |
| `docs/tools/ui/remote-access.md` | **NOT written** | v1.0 Web UI doesn't ship |
| `docs/tools/ui/vps-setup.md` | **NOT written** | v1.0 kit-surface doesn't ship |
| `docs/reference/json-rpc-schema.md` | **NOT written** | T-162 v1.0 daemon doesn't ship |
| `docs/operations/` | **NOT written** | v0.5+ operator-facing surface doesn't ship |

The "not written" entries are documented in the README's "Planned"
table with explicit gate-conditions.

### Generators state

**Unchanged from `phase-0e-release-aftermath.md` in capability
terms** — 14/16 implemented, T-G-010 (jsonrpc_schema) deferred per
T-162, T-G-014 (hg/p4 catalogs) deferred per Phase 4/5 adapter
work.

**Generated docs that auto-updated** during the sprint:

- `docs/reference/cli-reference.md` (T-G-009) — picked up the 5 new
  `sange commits` verbs.
- `docs/README.md` + `docs/tools/README.md` (T-G-006) — picked up
  the 13 new docs (regenerated 13 times across the sprint).

`all.py --check --skip T-G-001 T-G-002` at HEAD:
`ok=12 not_implemented=2 stale=0 crashed=0`.

### Audit trail

`.design/plans/session-log.md` grew from 110 rows (phase-0e
boundary) to **120 rows** at HEAD: +10 audit rows
(`S-003-T-{59..68,73..74}` plus the snapshot S-003-T-57 itself
already present). Every doc landing has an audit row; every code
landing has an audit row. `verify_session_log.py` clean.

### ADRs

No new ADRs accepted during this sprint. **33 ADRs total**
(ADR-001 through ADR-033). Two ADR detail files exist
(`docs/adr/0032-variant-matrix-android-studio-inspired.md` +
`docs/adr/0033-multi-arch-docker.md`); the other 31 live only in
the decisions log. Documented honestly in
`docs/governance/adr-process.md::Two surfaces, one decision`.

### Quality gates (all green at HEAD)

```
ruff check .                                    → 0 errors
mypy src                                        → 0 issues
pytest -q                                       → 1163 passed, 1 skipped
python tools/generators/verify_session_log.py   → 120 row(s) parsed, 0 failures
python tools/generators/all.py --check --skip T-G-001 T-G-002
                                                → ok=12 not_implemented=2 stale=0 crashed=0
```

The 1 skipped test is `tests/unit/test_documentation_scaffold.py:235`
which requires `mkdocs` on PATH (env-skipped without prejudice).

### Release pipeline state

**v0.1.0 tag** at `b947a2e9` (annotated, signed body `Source:
https://github.com/sangedev/sange` — historical artifact of the
pre-rename URL). Tag is immutable.

**Workflow run `25916854851`** (v0.1.0 release):

| Job | Result |
|---|---|
| `build sdist + wheel` | ✓ success |
| `publish to PyPI (OIDC)` | ✗ failure (`invalid-publisher`) |
| `docker build + push (multi-arch)` | ✓ success (`ghcr.io/sangedev/sange:v0.1.0` — pre-rename) |
| `create GitHub Release` | — skipped (depended on `pypi`) |

The PyPI failure remains operator-blocked on the one-time
trusted-publisher configuration at
[pypi.org/manage/account/publishing/](https://pypi.org/manage/account/publishing/)
(per `docs/release.md::Step 0`). Until that resolves,
`pip install sange` doesn't work; `docker pull
ghcr.io/simsange/sange:v0.1.0` does (via GHCR's rename redirect)
but requires the operator to flip the package visibility to Public.

### CI on `main` post-sprint

All 10 CI jobs green at workflow run `25928536468` (the most recent
push, `2b06906`). Subsequent push will produce a new run — its
status when the operator pushes the 6 queued commits will indicate
whether the docs sprint introduces any new issue. Local gates are
all green, so no surprises expected.

---

## What's CHANGED from `phase-0e-release-aftermath.md`

Six material deltas:

1. **Phase 1 CLI surface is now complete.** Three commits closing
   T-042/T-043/T-044; +26 tests; the `sange commits` sub-app now
   exposes the full lifecycle surface (list, new, ai, submit,
   approve, reject, commit, push).

2. **Thirteen reader-facing docs landed under `docs/`.** Six
   commits across the sprint; ~2400 lines of new documentation.
   The docs index grew 14 → 26. README's "Planned" table is now
   honest about what's gated on v0.5+/v1.0+ features.

3. **CHANGELOG.md catch-up.** Root CHANGELOG.md went from "Phase
   0a in progress, T-001 only" stale to "[0.1.0] tagged
   2026-05-14 + [Unreleased] enumerating every queued commit
   including the 13-doc sprint". Operator can cut v0.1.0.post1
   from a clean slate.

4. **README.md two-tier restructure.** "Live now" table (every
   path verified to exist on disk) vs "Planned" table (each row
   tagged with its explicit gate-condition). Zero 404-prone
   links.

5. **CONTRIBUTING.md stale-ref fixed.** Pointed at a
   never-emitted `docs/governance/contributing.md` with a
   misleading "(T-G-006)" annotation; replaced with a 4-item link
   list into actually-existing governance docs.

6. **The cli-reference generator (T-G-009) regenerated
   once** — picked up the 5 new verbs. T-G-006 (docs index)
   regenerated 13 times across the sprint — once per doc landing.

## What's STILL the same as `phase-0e-release-aftermath.md`

- **No new runtime subsystems.** The 1500-line canonical
  architecture deliverable hasn't moved. Phase 1 CLI is the
  shipped delta on the runtime side; everything else this sprint
  is metadata + docs.
- **Generator count.** 14/16 implemented; T-G-010 + T-G-014
  deferred per the original plan.
- **ADR count.** 33 accepted. No new ADRs.
- **Sister-repo seeds.** `documentation/` + `org-github/` still
  present pending operator bootstrap to
  `simsange/documentation` + `simsange/.github`.
- **v0.1.0 tag.** Immutable at `b947a2e9` with the historical
  `sangedev` URL baked in.

---

## What the next session must do

A fresh session with only `.design/` access should be able to read
this section and know exactly what to do next.

1. **First task (operator-blocked):** Configure PyPI trusted
   publisher at
   [pypi.org/manage/account/publishing/](https://pypi.org/manage/account/publishing/)
   with `project=sange`, `owner=simsange`, `repository=sange`,
   `workflow=release.yml`, `environment=pypi`. Create the `pypi`
   GitHub Environment at
   `github.com/simsange/sange/settings/environments` if it doesn't
   exist. Re-run the failed `publish to PyPI (OIDC)` job in
   workflow run `25916854851` from the GH Actions UI. The
   dependent `create GitHub Release` job will auto-trigger.

2. **First task (push-pending):** Six commits are queued on local
   main (`7625d8a..c0057aa` minus the already-pushed `2b06906`).
   Pushing them ships the entire Phase 1 CLI surface + the 13-doc
   sprint to `simsange/sange@main`. Push requires an explicit verb
   from the user per CLAUDE.md.

3. **Where to start reading (for code work):**
   - `src/sange/cli/commits.py` — the complete lifecycle CLI surface.
   - `src/sange/core/lifecycle/state_machine.py` — the engine the
     CLI wraps.
   - `docs/tools/workflow/commit-lifecycle.md` — the reader's
     walkthrough of what landed.

4. **First task (genuine code surface, candidate work):** Phase 2
   beta features per
   [`docs/governance/roadmap.md::v0.5-beta`](../../../docs/governance/roadmap.md#v05--beta-phase-1).
   The earliest unblocked task is **T-100** (SVN adapter — read
   operations) since the Git adapter pattern is established and
   the `VCSDriver` Protocol is stable. Next-earliest is **T-101**
   (gitignore-swap engine with SIGKILL recovery).

5. **Current branch:** `main`. Six unpushed commits.

6. **Active in-flight operations:** **none**.

7. **Open `🧪` clarifying questions for the user:**
   - Should the operator cut **`v0.1.0.post1`** once PyPI publish
     activates and the 6 unpushed commits land? The post-1 would
     ship the full Phase 1 CLI surface + the docs sprint. The
     CHANGELOG's `[Unreleased]` section is ready to become the
     post-1 release-notes verbatim.
   - Should the **`ghcr.io/simsange/sange:v0.1.0`** GHCR package be
     flipped to Public visibility, or wait until PyPI + GitHub
     Release fully land?
   - For Phase 2: should T-100 (SVN adapter) or T-101 (gitignore-
     swap) come first? Both are unblocked; the design says either
     order works.

## Resumability test result

- [x] A fresh session given only the build-kickoff prompt + this
      snapshot correctly identifies the next task. (Three first-task
      options surfaced with explicit values + file paths.)
- [x] The fresh session does not need to ask for additional
      context that should have been in this snapshot. (Test count,
      generator state, ADR count, CI status, release-pipeline state
      all captured with verifiable facts.)

## Audit-chain link

This snapshot is the **eighth** cold-resume artifact in the
project's history. The git-history chain past `c64f563`
(phase-0e-release-aftermath):

```
HEAD (c0057aa) → ee2be66 → e6fb894 → 67ffc5d → 1f10c3c → be8eb19
              → 2b06906 → f1d4ab6 → 8bb4a80 → 832bf13 → af44c12
              → 26f5230 → a7e8b87 → 2840776 → 29a214b → 7625d8a
              → a6b6204 → c582438 → c64f563 (phase-0e-release-aftermath)
              → … (back through phase-0e/0d/0c/0b/0a/design)
```

The integrity of this snapshot rests on:

  * The 14 implemented generators + unchanged generator outputs
    versus `phase-0e-release-aftermath.md` in capability terms.
  * Cross-reference resolution via
    `tools/generators/verify_session_log.py: 120 row(s) parsed; 0 failures`.
  * The `1163 passed, 1 skipped` test-suite output reproducible
    by running `python3.13 -m pytest -q` from the repo root.
  * The `all.py --check --skip T-G-001 T-G-002` output
    reproducible: `ok=12 not_implemented=2 stale=0 crashed=0`.
  * Git commit `c0057aa` being reachable from `main` and
    containing the expected **266 tracked files**.
  * The v0.1.0 tag at `b947a2e9` still pointing at the
    URL-corrected commit with the historical `sangedev`
    annotation — verifiable via `git show v0.1.0 --no-patch`.
  * The `origin` git remote being configured at
    `git@github.com:simsange/sange.git`.
  * `docs/README.md` listing **26 files** across the categories
    (top-level + `reference/` + `security/` + `governance/` +
    `tools/workflow/` + `tools/vcs/` + `tools/lang/` + `adr/`).

If any of the above is no longer true when this snapshot is read,
the snapshot is stale. The reader appends a `S-NNN-T-MM` row to
the session log noting the discrepancy before proceeding.

---

*The next snapshot (`v0.1.0.post1.md` or `phase-2.md`) lands when
either: (a) the operator activates PyPI + cuts v0.1.0.post1, or
(b) Phase 2 work begins on a real subsystem (T-100 SVN adapter,
T-101 gitignore-swap, etc.). Either event materially changes the
"what the next session must do" frame.*
