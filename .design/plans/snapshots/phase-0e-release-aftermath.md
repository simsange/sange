# Snapshot — Phase 0e (release-aftermath re-snapshot) — 2026-05-15

**Created:** 2026-05-15T15:30Z
**Created by:** model:claude-opus-4-7@simtabihq
**Last git commit:** `c64f563` Fix CI post-rename: -u flag in test fixture, skip version-bound generators
**Parent of snapshot:** `8a215e7` Record `git remote add origin` in session log (the prior `phase-0e.md` snapshot)
**Reason for snapshot:** The v0.1.0 release was attempted, the `sangedev`
GitHub org was renamed in-place to `simsange`, GitHub Actions were
bumped to node24-using majors, and two CI failures were fix-forwarded
on `main`. Three of those four events materially change the resume
conditions vs `phase-0e.md`. The v0.1.0 release pipeline is **partially
complete** (build + docker + GHCR push shipped; PyPI publish blocked
on a one-time trusted-publisher configuration the maintainer must do
manually). This snapshot captures the state at CI-green / partial-release
so a cold-resume session knows exactly which gates are passed and
which remain operator-blocked. Per ADR-031.

---

## State of the world

### What this re-snapshot captures (vs `phase-0e.md`)

**Twelve commits past the prior phase-0e snapshot (`8a215e7`):**

| SHA | Subject | Notes |
|---|---|---|
| `31e14c5` | Add Phase 0e end-of-phase snapshot (publish gate) | The prior snapshot itself (committed after it was authored). |
| `c35d825` | Add per-repo .github/ ISSUE_TEMPLATE + PR template | Repo-level community-health (mirrors the org-level seeds in `org-github/`). |
| `7abfe0d` | chore(docs): refresh docs/tools/README.md timestamp | T-G-006 regenerate after the .github/ scaffold. |
| `804fad5` | Lint sweep: 375 ruff errors → 0 clean | First-time-ruff pass on the entire repo. Config-level ignores + targeted fixes (B904 raise-from, RUF005, etc.). |
| `43181b4` | Type-check sweep: 25 mypy errors → 0 clean | `ignore_missing_imports` for the 5 optional AI extras + `tomli`; `cast(AIProvider, ...)` for 3 lazy-loaded providers; one real bug fixed (`_gather_repo_context` returned `BranchInfo` where `str` was declared). |
| `e247d86` | Pre-release validation + docs-site regex-table bug fix | `mkdocs --strict` crash fixed (`A-Za-z0-9` in a markdown table cell tripped Python's HTML parser into a `<![CDATA[...]]>` marked-section state); fenced-code-block replacement. |
| `68d1c8e` | Validate docker build + container run (S-003-T-53) | Single-arch buildx + smoke runs locally; mirrors the CI `docker` job. |
| `6f51071` | Record v0.1.0 push event (S-003-T-54) | Audit row for the `git push origin main` + `git push origin v0.1.0` events. |
| `09e5bee` | Migrate URLs: github.com/sangedev/sange → github.com/simsange/sange | 36 files updated via batch sed; `kit_manifest.py` regex pattern updated to the simsange-flavored cosign verification URL; `templates/MANIFEST.toml` + `docs/reference/kit-manifest.md` regenerated. |
| `3aa1569` | Bump GitHub Actions + mkdocs deps to current versions | Action versions: checkout v4→v6, setup-python v5→v6, upload-artifact v4→v7, download-artifact v4→v8, docker/login v3→v4, docker/buildx v3→v4, docker/qemu v3→v4, docker/build-push v6→v7 — each verified via `api.github.com/repos/<action>/releases/latest` before pinning. mkdocs floors lifted to Dependabot's proposed values. |
| `c504a53` | Record org rename + audit push + action bumps (S-003-T-55) | Audit row for the rename + push + bump cluster. |
| `c64f563` | Fix CI post-rename: -u flag in test fixture, skip version-bound generators | The current HEAD. Two CI failures fix-forwarded — one real test bug (newer git requires `-u` for upstream tracking), one CI-environment skip (T-G-001 + T-G-002 embed the installed git/svn version, which always differs between CI and local). |

**Test growth:** 1123 (phase-0e boundary) → **1138 tests collected**
(+15; the increase tracks `tests/unit/test_repo_github_templates.py`
+ minor coverage additions). 1137 pass, 1 environment-skipped (mkdocs
not on PATH — expected without `documentation/requirements.txt`
installed in the test venv).

**File count:** 252 tracked files (phase-0e was 246; +6 are the new
test module + the v0.1.0 tag's audit footprint + the
release-aftermath ancillary edits).

### The GitHub-org rename: `sangedev` → `simsange`

The user renamed the org **in-place** on 2026-05-15 between commits
`c504a53` and the release-aftermath fixes. GitHub's in-place org
rename preserves: repo contents, tags, branches, Dependabot PRs, CI
history, and (most importantly) HTTP redirects from the old org
name. What it does **not** preserve: tag-annotation bodies that hard-
coded the old org URL.

| Surface | Before | After | Notes |
|---|---|---|---|
| Org GitHub | `github.com/sangedev` | `github.com/simsange` | In-place rename; old URL HTTP-redirects to new for repo paths. |
| Repo | `sangedev/sange` | `simsange/sange` | Codebase + history + tags + dependabot PRs preserved. |
| `git remote` | `git@github.com:sangedev/sange.git` | `git@github.com:simsange/sange.git` | Local-only switch via `git remote set-url`. |
| `v0.1.0` tag | annotated, body says `Source: https://github.com/sangedev/sange` | **unchanged** | Per CLAUDE.md "release-as-immutable" — tag is **not** deleted/recreated. The sangedev URL is now a historical artifact baked into the tag object (verifiable via `git show v0.1.0 --no-patch`). |
| GHCR image | `ghcr.io/sangedev/sange:v0.1.0` + `:latest` | `ghcr.io/simsange/sange:v0.1.0` + `:latest` | The release.yml docker job that ran at tag-push time produced the original `sangedev` tags; the post-rename release.yml (commit `3aa1569`) targets `simsange`. The next release pushes simsange tags. The original sangedev-tagged image is reachable via redirect from `ghcr.io/simsange/...` per GitHub's container-registry rename policy. |
| `pyproject.toml::project.urls.Homepage` | `opensource.simtabi.com/products/sangedev/sange` | `opensource.simtabi.com/products/simsange/sange` | URL slug change. |

The `simsange` row was registered in `/Users/imanimanyara/Artisan/
projects/opensource/CLAUDE.md` per its own "Adding an org" procedure
(out-of-repo edit, explicitly authorized by the user verb "register
sangedev org" — interpreted as `simsange` given the rename).

### v0.1.0 release pipeline state

The v0.1.0 tag was pushed to `sangedev/sange` (pre-rename) which
auto-triggered `.github/workflows/release.yml`:

| Job | Result | Artifact |
|---|---|---|
| `build sdist + wheel` | ✓ success (25s) | wheel + sdist in workflow artifact store (still accessible at GH Actions run `25916854851`) |
| `publish to PyPI (OIDC)` | ✗ failure (10s) | `invalid-publisher: valid token, but no corresponding publisher` |
| `docker build + push (multi-arch)` | ✓ success (5m35s) | `ghcr.io/sangedev/sange:v0.1.0` + `:latest` published with sigstore provenance + SBOM |
| `create GitHub Release` | — skipped | Depends on `pypi` job |

The PyPI failure is **not** a code defect — it's the one-time
trusted-publisher record that the maintainer must configure manually
at `pypi.org/manage/account/publishing/`. Once configured (`project=sange`,
`owner=simsange`, `repository=sange`, `workflow=release.yml`,
`environment=pypi`), the maintainer can re-run only the failed
`pypi` job (and the auto-triggered `release` job) from the GH
Actions UI — the wheel artifact is already on the workflow run's
`dist` artifact store. No re-tag required.

### CI on `main` post-rename + post-fix

All 10 CI jobs green at HEAD (`c64f563`) per workflow run
`25921530595`:

```
✓ mypy
✓ ruff
✓ pytest (py3.12 / ubuntu-24.04)
✓ pytest (py3.12 / ubuntu-24.04-arm)
✓ pytest (py3.12 / macos-14)
✓ pytest (py3.13 / ubuntu-24.04)
✓ pytest (py3.13 / ubuntu-24.04-arm)
✓ generators (verify + all.py --check)
✓ package builds (sdist + wheel)
✓ docker build (single-arch sanity)
```

### Generators state

**Unchanged from `phase-0e.md` in capability terms** — 14/16
implemented, T-G-010 (jsonrpc_schema) deferred per T-162 (Phase 3
JSON-RPC core), T-G-014 (hg/p4 catalogs) deferred per Phase 4/5
adapter work.

**Operational change**: `.github/workflows/ci.yml::generators` job
now runs `all.py --check --skip T-G-001 T-G-002`. The two skipped
generators introspect the installed `git --version` / `svn --version`
and embed those in the catalog frontmatter + body, so CI's git
2.43 / svn 1.14.x ubuntu-24.04 runner never byte-matches a
contributor's local toolchain. Local `--write` invocation
regenerates against the contributor's actual toolchain when they
consciously want to refresh; the committed catalog is the source
of truth for what CI verifies on every other generator.

Local `all.py --check --skip T-G-001 T-G-002` at HEAD:
`ok=12 not_implemented=2 stale=0 crashed=0`.

### ADRs

No new ADRs accepted in this re-snapshot interval. ADR count
remains **33** (ADR-001 through ADR-033 in the decisions log; ADR
files exist on disk for `0032-variant-matrix-android-studio-inspired.md`
and `0033-multi-arch-docker.md`, the rest live in
`decisions-log.md`). No ADRs were revised.

### Risks

No new risks opened or closed via the formal `risk-register.md`
process during this interval. Three operational footguns surfaced
in-flight that are worth flagging here as future ADR/risk candidates:

| Pseudo-risk | Surface | Mitigation already applied |
|---|---|---|
| Generators that embed toolchain versions can't pass `--check` across heterogeneous CI ↔ local environments | `git_catalog.py` + `svn_catalog.py` | Skip those two in CI `--check`; document the rationale inline in `ci.yml`. |
| Newer `git` versions refuse bare `git push origin` without `-u` upstream tracking | `tests/unit/test_cli_commits.py::_setup_git_repo` (now fixed) and any future test fixture | The fixture comment now documents the requirement; future test fixtures should follow the same pattern. **No production-code change needed** because `GitDriver.push()` correctly emits the bare `git push origin` matching the §6.13 contract. |
| GitHub org renames preserve repo content but bake the old org URL into annotated tags | `v0.1.0` tag (sangedev URL) | None possible — tag is immutable. Documented in this snapshot + S-003-T-55 session-log row. |

### Files materially changed (vs prior snapshot `phase-0e.md`)

URL migration is mechanical (sangedev → simsange across 36 files);
the materially-changed-content list below excludes those.

| File | What changed |
|---|---|
| `.design/plans/session-log.md` | +6 audit rows (S-003-T-50, T-51, T-52, T-53, T-54, T-55, T-56). Append-only. |
| `.design/plans/snapshots/phase-0e-release-aftermath.md` | This snapshot. |
| `.github/workflows/ci.yml` | Matrix bumped to py3.12/3.13 only (3.10/3.11 removed — pin contradicted them); action versions bumped to node24 majors; `generators` step now `--skip T-G-001 T-G-002`. |
| `.github/workflows/release.yml` | Action versions bumped; GHCR tags updated to `ghcr.io/simsange/sange:*`. |
| `.github/ISSUE_TEMPLATE/*`, `.github/PULL_REQUEST_TEMPLATE.md` | Created per-repo templates mirroring the org-level seeds in `org-github/`. |
| `mypy.ini` | `ignore_missing_imports` stanzas for the 5 optional AI extras + `tomli`. |
| `ruff.toml` | Project-wide rule ignore list (SIM105, UP042, B008, B017, N818, RUF001, RUF012, SIM102/103/108) + per-file E501 ignores for `tools/generators/**`, `verify_session_log.py`, test fixture files, `commit_message.py`. |
| `src/sange/adapters/ai/_protocol.py` | `cast(AIProvider, ...)` on 3 lazy-loaded provider constructions (mypy-fix). |
| `src/sange/cli/commit.py` | Fixed `_gather_repo_context` return-type bug (was returning `BranchInfo`, was declared `str`); `TYPE_CHECKING`-guarded `CommitMessageResult` import; B904 raise-from. |
| `src/sange/cli/commits.py` | B904 raise-from across 7 sites; `str(answer)` cast in `_interactive_decision`; `push_result_payload: dict[str, object] | None`. |
| `src/sange/cli/init.py` | `_Action = dict[str, Any]` type alias replacing bare `list[dict]`. |
| `src/sange/cli/doctor.py` | `details: dict[str, Any]` + `_check_makefile_tracked` helper (§10.3 enforcement). |
| `src/sange/core/config/loader.py` | Removed legacy `tomli as tomllib` fallback (project floor is 3.12); narrow `parsed: dict[str, Any] = json.loads(text)`. |
| `tests/unit/test_cli_commits.py` | `_setup_git_repo` push call now includes `-u` flag. |
| `tests/unit/test_documentation_scaffold.py` | `test_repo_url_points_at_simsange` rename + url-discipline test. |
| `tests/unit/test_github_workflows.py` | Matrix-coverage assertion updated to `len(versions) >= 2`. |
| `tests/unit/test_repo_github_templates.py` | NEW — byte-equality tests pinning repo-level `.github/` templates to the canonical org seeds in `org-github/`. |
| `tools/generators/kit_manifest.py` | cosign regex pattern updated to `simsange/sange`. |

### Pinned external URLs (verify before re-pinning)

URLs the v0.1 release pipeline depends on. Verified at snapshot time:

| URL | Expected | Used by |
|---|---|---|
| `https://pypi.org/p/sange` | 404 until first publish | release.yml::pypi environment URL |
| `https://github.com/simsange/sange` | 200 | every metadata file |
| `https://ghcr.io/simsange/sange:v0.1.0` | (private until package made public) | docker pull at runtime |
| `https://opensource.simtabi.com/products/simsange/sange` | landing page (per org URL convention) | pyproject.toml Homepage |
| `https://opensource.simtabi.com/documentation/simsange/sange` | docs landing (per org URL convention) | pyproject.toml Documentation |

---

## What's CHANGED from `phase-0e.md`

Eight material deltas:

1. **Org renamed `sangedev` → `simsange`.** Every operational file
   targets `github.com/simsange/sange` + `ghcr.io/simsange/sange`.
   Audit-trail rows + the v0.1.0 tag annotation retain the historical
   `sangedev` strings per the append-only rules.

2. **GitHub Actions bumped to node24-using majors.** Eight actions
   updated; each version verified via `api.github.com/repos/<action>/
   releases/latest` before pinning per CLAUDE.md "Verification
   before pinning".

3. **v0.1.0 codebase is on the remote.** `refs/heads/main` at
   `c64f563` and `refs/tags/v0.1.0` (annotated tag at
   `b947a2e9`) are public at `github.com/simsange/sange`.

4. **Multi-arch Docker image published to GHCR.** `ghcr.io/simsange/sange:v0.1.0`
   + `:latest` with sigstore provenance + SBOM. (Originally
   published as `ghcr.io/sangedev/sange:*` at tag-push time;
   reachable via GHCR's rename redirect.)

5. **CI is green on `main` post-rename + post-fix.** 10/10 jobs
   pass at HEAD; previously two had failed (test-fixture missing
   `-u`, generator version-drift).

6. **ruff + mypy clean.** First-time-clean sweeps: 375 → 0 ruff
   errors and 25 → 0 mypy errors. The ruff config + mypy.ini
   pinpoint exactly which suppressions are intentional.

7. **`mkdocs --strict` builds the docs site clean.** One regex-in-
   table-cell parser footgun fixed (now a fenced code block).

8. **Per-repo `.github/` community-health templates exist.** Mirrors
   the org-level seeds in `org-github/`; byte-equality tested.

## What's STILL the same as `phase-0e.md`

- **Subsystem code surface**: zero new runtime subsystems. Every
  change since `phase-0e.md` is metadata, infrastructure, lint/type
  hygiene, or audit. The v0.1 functional flow (`sange init` →
  `git diff | sange commit` → `commits approve` → `commits push`)
  is the same code path.
- **Generator count**: 14/16 implemented; T-G-010 + T-G-014 deferred.
- **ADR count**: 33; no new ADRs accepted in this interval.
- **Sister-repo seeds**: `documentation/` + `org-github/` directories
  still present, still pinned by byte-equality tests, still gated
  on the operator manually creating `simsange/documentation` +
  `simsange/.github` repos before running each seed's
  `README.md` bootstrap recipe.

---

## What the next session must do

A fresh session with only `.design/` access should be able to read
this section and know exactly what to do next.

1. **First task (operator-blocked):** Configure PyPI trusted publisher
   at `pypi.org/manage/account/publishing/` with `project=sange`,
   `owner=simsange`, `repository=sange`, `workflow=release.yml`,
   `environment=pypi`. Then create the `pypi` GitHub Environment
   at `github.com/simsange/sange/settings/environments`. Then
   re-run the failed `publish to PyPI (OIDC)` job in workflow
   run `25916854851` from the GH Actions UI. The dependent
   `create GitHub Release` job will auto-trigger.

2. **First task (code-side, candidate work):** Phase 1 CLI surface
   completion. `sange commits` currently exposes only `list`,
   `approve`, `push` (T-040, T-041, T-045 plus partial T-044
   landed). The §18 checklist task list calls for `commits new`
   (T-042 manual draft), `commits ai` (T-043 AI-driven draft),
   and the missing T-044 verbs (`submit`, `reject`, `commit`).
   None blocks v0.1.0 from shipping (the `sange commit` happy-path
   alias covers the documented v0.1 flow) but the gaps are real
   and will block a clean v0.5.

3. **Where to start reading (for the CLI gap):**
   - `src/sange/cli/commits.py:33` — `list` command (the simplest of
     the three existing verbs; use as template for `new` + `submit`
     + `reject` + `commit`).
   - `src/sange/cli/commit.py` — the existing `sange commit` happy-
     path alias; some of its logic likely splits cleanly into
     `commits ai` (the draft phase) + `commits commit` (the land
     phase).
   - `src/sange/core/lifecycle/schema.py` — the 8-state `CommitStatus`
     enum; `submit` is DRAFT→SUBMITTED, `reject` is SUBMITTED→REJECTED,
     `approve` is SUBMITTED→APPROVED (already implemented).

4. **Current branch:** `main` (no feature branches in flight).

5. **Active in-flight operations** (purges, bundles, gitignore-swap
   recovery files): **none**.

6. **Open `🧪` clarifying questions for the user:**
   - Should v0.1.0 be re-attempted as `v0.1.0.post1` if the PyPI
     trusted-publisher configuration takes long enough that
     `simsange/sange` accumulates other fix-forward commits in
     the meantime? CLAUDE.md says "release-as-immutable" so the
     tag itself shouldn't move; `.post1` is the PEP 440 pattern
     for ship-fixes-without-bumping-version.
   - Should the v0.1.0 GHCR image at `ghcr.io/simsange/sange:*`
     be flipped to public visibility now, or wait until the PyPI
     publish + GitHub Release fully land?

## Resumability test result

- [x] A fresh session given only the build-kickoff prompt + this
      snapshot correctly identifies the next task. (The
      operator-blocked PyPI step is clearly named with its exact
      configuration values; the code-side gap is named with file
      paths to start reading.)
- [x] The fresh session does not need to ask for additional
      context that should have been in this snapshot. (All four
      surfaces — release-pipeline state, CI state, generator
      state, code-coverage state — are captured with verifiable
      facts.)

## Audit-chain link

This snapshot is the **seventh** cold-resume artifact in the
project's history (the sixth being `phase-0e.md` itself). The
git-history chain past `8a215e7` (phase-0e):

```
HEAD (c64f563) → c504a53 → 3aa1569 → 09e5bee → 6f51071
              → 68d1c8e → e247d86 → 43181b4 → 804fad5
              → 7abfe0d → c35d825 → 31e14c5 → 8a215e7 (phase-0e)
              → b95a9b2 → c65dbd4 → 553b063 → ab89f2b
              → b947a2e → c7090dc → 48e99fb → 64ad581 (phase-0d)
              → … (back through phase-0c/0b/0a/design)
```

The integrity of this snapshot rests on:

  * The 14 implemented generators + unchanged file outputs versus
    `phase-0e.md` (the URL migration regenerated `kit-manifest.md`
    + `MANIFEST.toml` only; T-G-006 regenerated `docs/tools/README.md`
    for the `.github/` scaffold; T-G-001 + T-G-002 are CI-skipped).
  * Cross-reference resolution via
    `tools/generators/verify_session_log.py: 108 row(s) parsed; 0 failures`.
  * The `1137 passed, 1 skipped` test-suite output reproducible by
    running `python3.13 -m pytest -q` from the repo root.
  * The `all.py --check --skip T-G-001 T-G-002` output reproducible
    by running it from the repo root: `ok=12 not_implemented=2 stale=0 crashed=0`.
  * Git commit `c64f563` being reachable from `origin/main` and
    containing the expected 252 tracked files.
  * The v0.1.0 tag at `b947a2e9` being annotated + carrying
    `Source: https://github.com/sangedev/sange` in its message
    body — verifiable via `git show v0.1.0 --no-patch`.
  * The `origin` git remote being configured at
    `git@github.com:simsange/sange.git` — verifiable via
    `git remote -v`.
  * The GitHub workflow run `25921530595` (CI on `c64f563`) being
    `conclusion=success` for all 10 jobs.
  * The GitHub workflow run `25916854851` (release on `v0.1.0`)
    being `failure` overall, with `build` + `docker` succeeded
    and `pypi` failed + `release` skipped.

If any of the above is no longer true when this snapshot is read,
the snapshot is stale. The reader appends a `S-NNN-T-MM` row to
the session log noting the discrepancy before proceeding.

---

*Maintained alongside the design workbook. Re-snapshot mid-Phase-0e
per `snapshots/README.md` naming convention. The next snapshot
(`v0.1.md`) lands when the v0.1.0 release pipeline fully completes
— pending the operator's PyPI trusted-publisher configuration.*
