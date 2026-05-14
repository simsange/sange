# Snapshot — Phase 0a (generators-scaffolded foundation) — 2026-05-15

**Created:** 2026-05-15T03:30Z
**Created by:** model:claude-opus-4-7@simtabihq
**Last git commit:** `37782d7` (HEAD = `main`), parent `06cbd9d Initial release`
**Reason for snapshot:** End of the Phase 0a "generators scaffold everything"
foundation. Phase 0b (business-logic build-out) is the next phase. This snapshot
is the cold-resume artifact a future session reads to pick up Phase 0b without
context-loss. Per ADR-031.

---

## State of the world

### What Phase 0a produced

**Source code (123 files in the Initial release commit):**

| Surface | Path | Notes |
|---|---|---|
| Python package | `src/sange/{__init__,_version,py.typed,exit_codes}.py` | 0.1.0.dev0; PEP 561 typed; canonical `ExitCode` `IntEnum` |
| Tests | `tests/{__init__,test_version,conftest}.py` + `tests/unit/test_*.py` (11 modules) | 229 tests, all passing |
| Tooling | `pyproject.toml`, `ruff.toml`, `mypy.ini`, `.pre-commit-config.yaml`, `.editorconfig`, `.gitignore`, `.gitattributes` | Apache 2.0 (ADR-007), hatchling backend, ADR-019 pinned deps |
| Generator helpers | `tools/generators/_lib/{output,fingerprint,markdown,manpage}.py` | Pure-stdlib (per ADR-029 bootstrap rule) |
| Generator orchestrator | `tools/generators/all.py` | 16-entry registry, topo-sorted via `graphlib` |
| Verifier | `tools/generators/verify_generated.py` | Body-sha256 round-trip check |
| Session-log verifier (T-G-016) | `tools/generators/verify_session_log.py` | The discipline gate (ADR-030 + ADR-031) |
| Fallback toolkit | `tools/scaffold/{emit_stub,fetch_canonical,README}.py` | Content-filter fallback per S-002-T-06 user directive |

**Implemented generators (11/16):**

| Task | File | Output | Notes |
|---|---|---|---|
| T-G-001 | `git_catalog.py` | `docs/reference/appendix-d-git-catalog.md` | 175 rows from live `git 2.51.0` + §9.0.1 Top-25 + §9.0.2 power commands |
| T-G-002 | `svn_catalog.py` | `docs/reference/appendix-e-svn-catalog.md` | 47 rows from live `svn 1.14.3` across svn/svnadmin/svnlook/svndumpfilter/svnsync |
| T-G-003 | `cross_vcs_map.py` | `docs/reference/appendix-f-cross-vcs.md` | 35 concepts × Git/SVN/Hg/Fossil/Pijul + Sange domain mapping |
| T-G-004 | `commit_templates.py` | `docs/reference/appendix-g-commit-templates.md` + `templates/commit-templates/default.toml` | 67 presets folding v1's 102-entry array (84 aliased + 18 filtered + 0 orphans) |
| T-G-005 | `kit_manifest.py` | `templates/MANIFEST.toml` + `docs/reference/kit-manifest.md` | Signed-manifest trust root (ADR-020); cosign-signs in CI |
| T-G-006 | `docs_index.py` | `docs/README.md` + `docs/tools/README.md` | Walks `docs/`, extracts H1 headings, groups by sub-dir |
| T-G-007 | `adr_scaffold.py` | `docs/adr/NNNN-<slug>.md` on demand | Used for ADR-032 + ADR-033 (real dogfooding) |
| T-G-008 | `exit_codes.py` | `docs/reference/exit-codes.md` | Canonical `ExitCode` `IntEnum` (10 values across Unix-conventions / cross-cutting / subsystem bands) |
| T-G-012 | `threat_model_table.py` | `docs/security/stride.md` | 26 STRIDE-classified threats; defense-in-depth invariant enforced for Critical-blast |
| T-G-015 | `profile_registry.py` | `docs/reference/profile-registry.md` + 36 `templates/gitignore-profiles/<category>/<name>.toml` | 35 patterns-owning profiles + `_core/license` safety net |
| T-G-016 | `verify_session_log.py` | (no file — discipline gate; CI-only) | Cross-ref resolver + grounding check + files-touched heuristic |

**Generated documentation (12 files under `docs/`):**

  * `docs/README.md` + `docs/tools/README.md` — canonical + tools indexes
  * `docs/reference/{appendix-d,appendix-e,appendix-f,appendix-g,exit-codes,kit-manifest,profile-registry}.md` — 7 reference docs
  * `docs/security/stride.md` — STRIDE threat model
  * `docs/adr/{0032,0033}-*.md` — 2 accepted ADRs

**Kit content (38 files under `templates/`):**

  * `templates/gitignore-profiles/<category>/<name>.toml` — 36 profile TOMLs
  * `templates/commit-templates/default.toml` — 67-preset library
  * `templates/MANIFEST.toml` — signed trust root

### Tests passing

**229 tests** across 11 unit-test modules. Full suite under 1 second on the
dev machine. Single warning (pytest-asyncio's `asyncio_mode` config option
unknown — the lib isn't installed; lands with `pip install -e ".[dev]"`).

### ADRs (33 total)

The decisions-log carries `ADR-001..ADR-033`. New this session (Phase 0a):

  * **ADR-032** — Multi-dimensional variant matrix for gitignore-swap
    (Android-Studio-inspired). Replaces the binary `dev | prod` axis with a
    Cartesian product over user-declared dimensions; ships
    `templates/variants/` skeletons in v1.0.
  * **ADR-033** — Multi-arch Docker + Linux (`linux/amd64` + `linux/arm64`
    from v1.0; `linux/arm/v7` from v2.0). Every Sange-shipped image and
    every Linux package layer installed by Sange runs natively on Apple
    Silicon + Hetzner Ampere ARM + AWS Graviton + Raspberry Pi 4/5.

Pre-existing ADR-001..ADR-031 from the design phase (see `phase-design.md`
snapshot) are all still accepted; none superseded.

**Next available ADR slot: ADR-034.**

### Risks

  * **Closed (1):** R-001 (codebase target path) — fully closed at v4.2.
  * **Open (17):** R-002 through R-018 in `risk-register.md`.
  * **De-facto closed (1) — not yet flipped to `Closed`:** R-017 (`sange-v1/`
    + `sange-v2/` held until v0.1.0 beta). The audit findings are fully
    ingested into `.design/sange-architecture.md` §5, the prompt's §4.0
    verified-facts block, and `tools/generators/commit_templates.py::V1_LEGACY_MESSAGES`
    (the 102-entry tuple captured byte-exactly from disk). v1+v2 directories
    are now gitignored in the new repo's `.gitignore`; they remain on disk
    until the user signals to delete. **Suggest:** the next session may flip
    R-017 to `Closed` once `docs/audit/v1.md` + `docs/audit/v2.md` get
    emitted (currently they live only in the deliverable's §5).

### Git history

```
37782d7 Record initial-release commit in session log
06cbd9d Initial release
```

The **`06cbd9d Initial release`** commit contains 123 files. The
**`37782d7`** follow-up adds the session-log row that records the prior
commit's SHA — the audit chain spans the git-init boundary cleanly.

### Session-log

`.design/plans/session-log.md` has **58 rows** total:

  * S-001 — Initial design phase (T-01..T-22, historical reconstruction)
  * S-002 — Build phase (T-01..T-35, real-time entries from this session;
    every row from S-001-T-20 onward has the `grounding` column populated
    per ADR-030)

The session-log verifier (`tools/generators/verify_session_log.py`) runs
clean against the canonical file:
**54 rows parsed by the verifier (the row counts differ because the
verifier's parser ignores headers / empty rows / fixtures), 0 cross-ref
failures, 0 grounding failures, 0 files-touched failures.** Exit 0.

### Verifier state

  * `verify_generated.py` — **12 generator-emitted files inspected, 0
    failures** (the 11 implemented generators' canonical outputs + the
    on-demand ADR scaffolds).
  * `verify_session_log.py` — clean (see above).
  * `all.py --check --clock <ts>` — `ok=11 not_implemented=5 stale=0
    crashed=0 of 16 registered`. The 5 not_implemented generators are
    blocked on Phase 0b business logic (see below).

### Files materially changed in this snapshot's window

Everything in the Initial release commit. Diff vs. the `phase-design.md`
snapshot:

  * 123 new files (source + generators + tests + docs + templates +
    community markdown + license + tooling configs).
  * `.design/plans/{session-log, decisions-log, risk-register, …}.md`
    extended with Phase 0a entries.
  * `.design/sange-architecture-prompt.md` v4.4 → **v4.6** (changelogs
    for v4.5 variant-matrix + v4.6 multi-arch).
  * `.design/sange-architecture.md` extended with §15.6 (variant matrix
    mirror).

---

## What the next session must do

A fresh session given only `.design/` + the git history should be able to
read this section and know exactly what to do next.

1. **Next phase:** Phase 0b — business-logic build-out, on top of the
   Phase 0a generator-scaffolded foundation. Per ADR-029 the generators
   came first by design; the human-built lifecycle / adapters / CLI / TUI
   comes second.

2. **First task — choose one:**
   - **T-002** — `SangeConfig` Pydantic v2 model with TOML + JSON merge
     per §6.3. The keystone that unblocks T-G-011 (config_schema
     generator) and feeds every subsystem. **Recommended start.**
   - **T-003** — `VCSDriver` Protocol per §6.2 (abstract base for the
     `adapters/vcs/` layer). Smaller; sets up the SOLID structure
     before any concrete adapter lands.
   - **T-G-013** — `changelog_from_commits.py` (writes `docs/CHANGELOG.md`
     from `.sange/commits/*.json`). Empty output today (no commits yet),
     but lands the generator pattern for `.sange/commits/` consumers.
   - **Multi-arch Dockerfile + `.github/workflows/ci.yml`** — hands-on
     ADR-033 implementation. Operational artifacts, not generators.

3. **Where to start reading:**
   - This snapshot (`.design/plans/snapshots/phase-0a.md`).
   - `.design/plans/{decisions-log, risk-register, checklist, session-log}.md` —
     latest state.
   - `.design/sange-architecture-prompt.md` §6.3 (config hierarchy) +
     §6.5.2 (variant matrix that the config drives) for T-002.
   - `.design/sange-architecture.md` for the narrative context.

4. **Current branch:** `main`. Last commit: `37782d7`. **Working tree
   clean.**

5. **Active in-flight operations:** None.
   - No `.sange/.recovery` (no gitignore-swap mid-flight).
   - No `.sange/purge/<latest>/plan.json` (no purge mid-flight).
   - No half-emitted generator outputs.

6. **Open `🧪` clarifying questions for the user:** None at the Phase 0a
   boundary. The build-kickoff prompt anticipated likely Phase 0b
   questions; future questions land via `AskUserQuestion`.

7. **Critical sequencing reminders:**
   - **Phase 0b builds on the Phase 0a generator foundation.** The 5
     remaining T-G-NNN generators (T-G-009/010/011/013/014) come back
     into scope as their input shapes (SangeConfig, JSON-RPC schema,
     typer app, `.sange/commits/`, Mercurial+Perforce adapters) land
     through Phase 0b–Phase 4 business logic.
   - **Append a session-log row after every completed task** per
     ADR-028. New rows must populate the `grounding` column per ADR-030.
   - **Never push without explicit instruction** per `~/.claude/CLAUDE.md`.
   - **Ask one question at a time** per ADR-024.
   - **Read before reference; cite source; no invented IDs** per ADR-030.
   - **Multi-arch from day one** per ADR-033 — every Dockerfile, every
     CI workflow, every Linux package install path.

---

## Resumability test

  * [x] **A fresh session given only this snapshot + the build-kickoff
        prompt can correctly identify the next task.** The snapshot's
        "What the next session must do" section names T-002 (recommended)
        + three alternatives, points to the four read-first files, and
        reminds the next session of the six critical sequencing rules.
  * [x] **The fresh session does not need to ask for additional context
        that should have been in this snapshot.** Every Phase 0a deliverable
        is listed by name + path; every ADR added is named; every test
        count + verifier state is recorded; every risk is up-to-date.

Both boxes checked. Snapshot complete.

---

## Audit-chain link

This snapshot is the second cold-resume artifact in the project's history
(the first was `phase-design.md` at the end of the design phase). The
git-history chain is now real:

```
HEAD (37782d7) → 06cbd9d Initial release → (git init)
              ↑                          ↑
           snapshot                phase-design.md snapshot
           dated 2026-05-15        dated 2026-05-13
```

The hash-chained runtime audit log (`.sange/audit/*.jsonl`) doesn't exist
yet — it lands with the v0.1.0 sanged daemon (Phase 3 / T-108). Until then,
the session-log (`.design/plans/session-log.md`) + git commit history are
the audit trail; `tools/generators/verify_session_log.py` enforces
cross-reference integrity per ADR-030 + ADR-031.

The integrity of this snapshot rests on:

  * The 11 implemented generators + 12 emitted reference docs + 38 kit
    fragments listed above being present on disk and readable.
  * Cross-reference resolution: every ADR-NNN / T-NNN / T-G-NNN / R-NNN /
    S-NNN-T-MM cited above resolves to a real entry in the canonical
    file (verified at snapshot-write time via `verify_session_log.py`
    + spot-checks).
  * The `229 passed` test-suite output reproducible by running
    `python3 -m pytest tests/` from the repo root.
  * The `verify_generated.py: 12 files inspected; 0 failures` output
    reproducible by running it from the repo root.
  * The `verify_session_log.py: 54 rows parsed; 0 failures` output
    reproducible by running it from the repo root.
  * Git commit `06cbd9d` containing the expected 123 files (verifiable
    via `git show --stat 06cbd9d | tail -1`).

If any of the above is no longer true when this snapshot is read, the
snapshot is stale. The reader appends a `S-NNN-T-MM` row to the session
log noting the discrepancy before proceeding.

---

*Maintained alongside the design workbook. Phase 0a → Phase 0b boundary.
The next snapshot (`phase-0b.md`) lands when Phase 0b reaches its own
exit gate.*
