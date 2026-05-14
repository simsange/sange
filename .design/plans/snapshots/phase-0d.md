# Snapshot — Phase 0d (v0.1.0 tag-gate) — 2026-05-16

**Created:** 2026-05-16T00:30Z
**Created by:** model:claude-opus-4-7@simtabihq
**Last git commit:** `018d5be` CI + release workflows + dependabot (Phase 0d 4/5)
**Parent of snapshot:** `f985ac6` Add Phase 0c end-of-phase snapshot
**Reason for snapshot:** End of Phase 0d 4-of-5. Every release-engineering
prerequisite is in place; only the final `git tag v0.1.0 && git push --tags`
step remains. That step requires explicit user authorization per
`~/.claude/CLAUDE.md` (the "never push without explicit instruction"
rule). This snapshot is the cold-resume artifact for the operator who
returns after the manual smoke test to authorize the tag. Per ADR-031.

---

## State of the world

### What Phase 0d produced

**Four commits past the Phase 0c snapshot (`f985ac6`):**

| SHA | Subject | Tests added |
|---|---|---|
| `29ee532` | 1/5 T-G-013 changelog-from-commits generator | 26 |
| `22a5ac3` | 2/5 Multi-arch Dockerfile + .dockerignore (ADR-033) | 33 |
| `876f3ad` | 3/5 scripts/smoke_v01.sh real-AI smoke | 18 |
| `018d5be` | 4/5 CI + release workflows + dependabot | 30 |

**Test growth:** 910 (Phase 0c boundary) → **1017 passing** (+107
across 4 new test modules: `test_changelog_from_commits.py`,
`test_docker_artifacts.py`, `test_smoke_script.py`,
`test_github_workflows.py`).

**File count:** 215 tracked files (Phase 0c was 202).

### The v0.1 release surface (now complete)

```
PROD / RELEASE
  ↓
GitHub tag push (v*.*.* matches release.yml trigger)
  ↓
.github/workflows/release.yml jobs:
  ↓
  build       — sdist + wheel + smoke-install
  ↓
  pypi        — pypa/gh-action-pypi-publish with OIDC trusted-publisher
                → PyPI: pip install sange
  ↓
  docker      — buildx with platforms: linux/amd64,linux/arm64
                + sigstore provenance + SBOM
                → ghcr.io/simtabi/sange:<tag> + :latest
  ↓
  release     — gh release create with notes from docs/CHANGELOG.md
                → GitHub Release page with attached sdist + wheel

DEV
  ↓
.github/workflows/ci.yml on every push + PR:
  ↓
  test (matrix: py3.10-3.13 × ubuntu-amd64 + ubuntu-arm64 + macos-14)
  lint (ruff)
  typecheck (mypy)
  generators (verify_session_log + verify_generated + all.py --check)
  build (sdist + wheel + smoke-install)
  docker (single-arch buildx sanity)
```

### Subsystems shipped in Phase 0d

| Surface | Path | Notes |
|---|---|---|
| Changelog generator | `tools/generators/changelog_from_commits.py` | Walks `.sange/commits/` filtered to PUSHED → Keep-a-Changelog 1.1.0 → `docs/CHANGELOG.md` |
| Container image | `Dockerfile` + `.dockerignore` + `docker-compose.yml` | Multi-stage, multi-arch upstream, non-root sange user, ENTRYPOINT sange |
| Real-AI smoke | `scripts/smoke_v01.sh` | Operator-driven; 8-step happy-path validation with `--dry-run` mock + `--provider {anthropic,openai,ollama}` |
| CI pipeline | `.github/workflows/ci.yml` | Matrix py3.10-3.13 × 3 OS, native ARM per ADR-033, ruff + mypy + generator verifiers |
| Release pipeline | `.github/workflows/release.yml` | Tag-driven, OIDC PyPI + multi-arch GHCR + GitHub Release |
| Dependabot | `.github/dependabot.yml` | Weekly Monday 06:00 America/New_York per global CLAUDE.md |

Phase 0d added **zero new runtime subsystems** — every commit was
release-engineering or operator tooling. The codebase shipped at the
end of Phase 0c is the codebase that goes to v0.1.0.

### Generators

**14/16 generators implemented.** T-G-013 (changelog-from-commits)
moved from "blocked" to "ok" this phase. The remaining 2 deferred:

  * T-G-010 jsonrpc-schema — blocked on §15 IPC schema (T-162)
  * T-G-014 hg/p4-catalogs — blocked on Mercurial / Perforce adapters

These are explicitly deferred to v2.0 / v3.0 per the §14 roadmap; they
do not block v0.1.

### ADRs

No new ADRs in Phase 0d. ADR-033 (multi-arch Docker) is the most
implementation-critical decision and lands in the Dockerfile + ci.yml +
release.yml pattern.

---

## What's CHANGED from Phase 0c

1. **The package is publishable.** `python -m build` produces a sdist
   + wheel; the release workflow OIDC-publishes them to PyPI without
   any API token in repo secrets.

2. **The container image is buildable + signable.** `docker buildx
   --platform linux/amd64,linux/arm64` produces a multi-arch OCI
   manifest; the release pipeline signs it via sigstore and attaches
   an SBOM.

3. **The changelog auto-generates.** `tools/generators/changelog_from
   _commits.py` walks the PUSHED queue and produces a Keep-a-Changelog-
   formatted `docs/CHANGELOG.md`. The release workflow extracts the
   "Unreleased" section as the v0.1.0 release notes.

4. **CI matrix tests every supported environment.** Python 3.10 / 3.11
   / 3.12 / 3.13 × Ubuntu amd64 + native ARM + macOS. Generator-verify
   + lint + type-check + build + Docker-sanity all gated.

5. **Dependency hygiene is automated.** Weekly Monday 06:00
   America/New_York Dependabot PRs across pip + GitHub Actions +
   Docker base images.

6. **The operator has a smoke checklist.** `scripts/smoke_v01.sh`
   drives the full §14.1 happy path against any of the four providers
   (anthropic / openai / ollama / mock); `--dry-run` validates
   plumbing without real tokens.

---

## What's NOT done yet (the v0.1.0 tag-and-push gate)

**The only remaining step is the v0.1.0 release tag.** This step is
intentionally gated:

  * Per `~/.claude/CLAUDE.md` ("Never push without explicit
    instruction"): `git push --tags` is a remote-state-changing
    operation that requires an explicit user verb (`"push tags"`,
    `"tag and push v0.1.0"`, or similar).
  * Per `~/.claude/CLAUDE.md` ("Verification before pinning"): the
    operator must confirm the package builds + smoke passes against a
    real AI provider before the tag is created. The smoke script
    (`scripts/smoke_v01.sh --provider anthropic`) is the documented
    verification step.

### Operator checklist before authorizing the tag

```bash
# 1. Install editable
python3 -m venv .venv-smoke
source .venv-smoke/bin/activate
pip install -e ".[dev]"
sange --version    # expect: sange 0.1.0.dev0

# 2. Dry-run smoke (plumbing only, no tokens)
./scripts/smoke_v01.sh --dry-run

# 3. Real-AI smoke (~$0.005 in Claude calls)
export ANTHROPIC_API_KEY=sk-ant-...
./scripts/smoke_v01.sh --provider anthropic

# 4. Optional — Docker sanity
docker build -t sange:smoke .
docker run --rm sange:smoke --version

# 5. Authorize the tag with one of these verbs:
#    "tag v0.1.0"           — local tag only, separate push authorization
#    "tag and push v0.1.0"  — local tag + push (triggers release.yml)
```

### After the tag pushes

The release.yml workflow takes over:

  * Build sdist + wheel + smoke-install (~2 min).
  * Publish to PyPI via OIDC (~30 s).
  * Build multi-arch Docker image (~5 min via QEMU; ~2 min when
    native ARM runners land in v0.5+).
  * Create GitHub Release with sdist + wheel attached.

Total wall-time from `git push --tags` to "PyPI install works":
**~7 minutes** on first run.

---

## What the next session must do

If the tag has not yet been authorized, the next session continues
from this snapshot:

1. **Read this snapshot first.** The operator checklist above is the
   work to do before tagging. If the smoke has already run, the
   operator's reply will name the result.

2. **Tag/push decision:** the operator's verb dictates action.
   * `"tag v0.1.0"` → `git tag v0.1.0 -m "Initial release"`
     (annotated tag, local only; do not push without a separate
     "push tags" verb).
   * `"tag and push v0.1.0"` → tag + `git push origin v0.1.0`.
   * `"do not tag"` / `"hold"` → leave Phase 0d at 4/5; the user has
     reasons not to ship today. Add a session-log row noting the
     hold.

3. **If tagged but not pushed:** the user may want to inspect the
   tag locally first. `git show v0.1.0` displays the annotation; the
   tag can be deleted with `git tag -d v0.1.0` (local-only operation,
   safe without verb). Pushing is the gated step.

4. **If pushed:** monitor the release.yml workflow run. If it fails
   (most likely failure: trusted-publisher misconfigured, or GHCR
   permissions), the tag exists in the remote but the artifacts
   don't ship. Fix the workflow + push a `v0.1.0.post1` re-release;
   never force-push a pushed tag (per CLAUDE.md "no force-push to
   main" + the published-tag-as-immutable convention).

5. **Where to start reading after tag success:**
   - This snapshot.
   - `.github/workflows/release.yml` (the actual pipeline).
   - `docs/release.md` (the human-facing OIDC + GHCR setup recipe).
   - `docs/CHANGELOG.md` (auto-regenerated for v0.1.0; if no PUSHED
     commits exist yet, only the "No PUSHED commits yet" placeholder
     shows — the operator may want to dogfood `sange commit` against
     this repo's own changes to populate it).

6. **Current branch:** `main`. Last commit: `018d5be`. **Working
   tree clean.**

7. **Active in-flight operations:** None.
   - No `.sange/` in repo root.
   - No half-emitted generator outputs.
   - No half-written test files.
   - No uncommitted edits.

8. **Open `🧪` clarifying questions for the user:** One — **the
   v0.1.0 tag-and-push authorization**. The user must explicitly
   say `"tag"` or `"tag and push"` before the model performs either.

9. **Critical sequencing reminders:**
   - **Never push without explicit instruction** per
     `~/.claude/CLAUDE.md` — applies to tags too.
   - **Never force-push a pushed tag** — releases are immutable;
     fix forward with `v0.1.0.post1` or `v0.1.1`.
   - **Append a session-log row after every completed task** per
     ADR-028. The tag-creation event itself is a row.
   - **Read before reference** per ADR-030 — verify the tag content
     after `git tag` lands before reporting success.

---

## What's next AFTER v0.1.0

The §14 v0.5 milestone scope (per `.design/sange-architecture-prompt.md`
§14.2):

  * SVN adapter (T-100 onwards).
  * Gitignore-swap mechanism (§6.5).
  * Hooks engine (§6.9).
  * Secret scanning integration (§11).
  * Docker packaging with container-secret management (§6.10 full).
  * Expanded commit template library (≥50 presets — already shipped
    in T-G-004 at 67).
  * **VCS History Purge** read-only (§6.11): `sange purge plan /
    mirror / scan / analyze / preview / notify` functional;
    destructive subcommands stubbed.
  * CLI/TUI presentation conventions (§7.0.2): TerminalProfile
    detection + glyph-swapping + NO_COLOR / FORCE_COLOR (deferred
    from Phase 0c task 7 by design).

None of these are in scope for the v0.1.0 → v0.1.x bug-fix track;
they belong to v0.5.

---

## Resumability test

  * [x] **A fresh session given only this snapshot can correctly
        identify the next action.** "What the next session must do"
        section 1+2 names the operator checklist, the three valid
        user verbs, and the immutable-tag rule.
  * [x] **The fresh session does not need to ask for additional
        context that should have been in this snapshot.** Every
        Phase 0d commit is named with its SHA + test count; every
        new artifact is listed with its path; the v0.1.0
        tag-and-push gate is documented with exact commands; the
        post-tag failure-recovery path is documented; the v0.5
        roadmap is mentioned to avoid scope-creep questions.

Both boxes checked. Snapshot complete.

---

## Audit-chain link

This snapshot is the fifth cold-resume artifact in the project's
history. The git-history chain:

```
HEAD (018d5be) → 876f3ad → 22a5ac3 → 29ee532 → f985ac6 (phase-0c snapshot)
              → a20caee → 0f00c66 → e6bf8e6 → b995cdf → 8e18adb
              → e5c0841 → 7d18ef4 → 35e2cbb (phase-0b snapshot)
              → 790b9a3 → ab885f2 → 396eed1 → fb12b0e → 0fb9800
              → 6de5f68 → 92e3969 → 2677826 → c6b37d9 → 003734b
              → e9e2a3b → 4cf12a0 → d68110a → 99b9434
              → 2c4a04d (phase-0a snapshot)
              → 37782d7 → 06cbd9d (Initial release)
              ↑                          ↑
        phase-0d.md             phase-design.md
        (this snapshot)         (design phase end)
```

The integrity of this snapshot rests on:

  * The 14 implemented generators + 15 generator-emitted files
    (CHANGELOG.md joined T-G-009's cli-reference.md).
  * Cross-reference resolution via
    `tools/generators/verify_session_log.py: 91 rows parsed; 0 failures`.
  * The `1017 passed` test-suite output reproducible by running
    `PYTHONPATH=src python3 -m pytest -q` from the repo root.
  * The `all.py --check ok=14 not_implemented=2 stale=0` output
    reproducible by running it from the repo root.
  * Git commit `018d5be` being reachable from `main` and containing
    the expected 215 tracked files (verifiable via `git ls-files | wc -l`).
  * The v0.1 happy path being executable end-to-end via the
    documented operator-smoke command sequence.

If any of the above is no longer true when this snapshot is read,
the snapshot is stale. The reader appends a `S-NNN-T-MM` row to the
session log noting the discrepancy before proceeding.

---

*Maintained alongside the design workbook. Phase 0d → v0.1.0 release
boundary. The next snapshot (`v0.1.md`) lands when the v0.1.0 tag is
pushed AND the release pipeline completes — both the tag and the
pipeline-success are required for the snapshot to mark the release
as "shipped".*
