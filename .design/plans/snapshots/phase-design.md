# Snapshot — Phase Design (end-of-design) — 2026-05-13

**Created:** 2026-05-13T18:00Z
**Created by:** model:claude-opus-4-7@simtabihq
**Last git commit:** *(repo not yet `git init`-ed; design artifacts unversioned in git as of this snapshot — will be initialized in T-001)*
**Reason for snapshot:** End of the design phase. Phase 0a (generators-scaffold-everything) is the next thing to do. This snapshot is the cold-resume artifact for the next session.

---

## State of the world

### What design produced

| Artifact | Path | Lines | Purpose |
|---|---|---|---|
| Architecture prompt | `.design/sange-architecture-prompt.md` | 3,543 | The workbook (spec + methodology); v4.4 |
| Architecture deliverable | `.design/sange-architecture.md` | 1,501 | Items §1-§44 substantively present; §45-§50 stubbed; v4.4 |
| Build-kickoff prompt | `.design/plans/build-kickoff-prompt.md` | 153 | The exact prompt to paste into a fresh agentic-IDE session |
| README index | `.design/plans/README.md` | 59 | How the design folder works |
| Positioning | `.design/plans/positioning.md` | 61 | Audience scope + engineering bar |
| Implementation plan | `.design/plans/implementation-plan.md` | 141 | Phased plan; Phase 0a is next |
| Checklist | `.design/plans/checklist.md` | 129 | T-001..T-G-016 enumerated |
| Decisions log | `.design/plans/decisions-log.md` | 64 | ADR-001..ADR-031 |
| Content audit | `.design/plans/content-audit.md` | 217 | Every chat-history requirement → captured section |
| Traceability matrix | `.design/plans/traceability-matrix.md` | 108 | Capability → ADR → checklist → quality gate |
| Quality gates | `.design/plans/quality-gates.md` | 112 | §19 mirror; v1.0 readiness review |
| Risk register | `.design/plans/risk-register.md` | 32 | R-001 closed; R-002..R-018 open |
| Session log | `.design/plans/session-log.md` | 107 | S-001-T-01..S-001-T-21; first 22 rows are historical reconstruction; T-20 onward use the new `grounding` column |
| Snapshot README | `.design/plans/snapshots/README.md` | 108 | Cold-resume template + crash-recovery protocol |
| **This snapshot** | `.design/plans/snapshots/phase-design.md` | (this file) | The end-of-design snapshot |

**Total design-phase output:** 14 files / 6,335+ lines / ~280 KB.

### Tasks completed across the design phase

The session-log captures S-001-T-01 through S-001-T-21 (21 design-phase task completions). No checklist task IDs (T-NNN) are completed yet — those are all reserved for the build phase.

### ADRs accepted (31)

ADR-001 through ADR-031, summarized in `.design/plans/decisions-log.md`. Highlights:

- **ADR-001** Python core + Laravel UI separated by JSON-RPC
- **ADR-002** Laravel 13 + Livewire 4 + first-party `laravel/passkeys` (separate package, released 2026-05-12)
- **ADR-003** No Laravel AI SDK — all AI in Python core
- **ADR-007** Apache 2.0, © Simtabi LLC
- **ADR-018** History purge is synchronous CLI-only (never async/scheduled)
- **ADR-019** CLI/TUI library stack locked
- **ADR-020** Premade Operations Kit signed/versioned/curated
- **ADR-021** Subgrouped Category convention canonical for every fragment tree
- **ADR-022** Sange does not replace VCS tools; 7 personas; SOLID/DRY/KISS engineering bar
- **ADR-023** Generate-first / fine-tune-second
- **ADR-024** One question at a time
- **ADR-025** Godmode workbook framing + fluent OOP
- **ADR-026** Profile Registry policy (35 v1.0 profiles)
- **ADR-027** `.design/` workbook layout + codebase path locked in-place
- **ADR-028** Session-log + audit-after-every-task method
- **ADR-029** Generators scaffold *everything* (not just catalogs)
- **ADR-030** Anti-hallucination (read before reference, cite source, no invented IDs)
- **ADR-031** Memory preservation + crash-recovery + resumability

Next available ADR slot: **ADR-032**.

### Risks closed

- **R-001** Codebase target path ambiguity → closed by ADR-027 (in-place at `/Users/imanimanyara/Artisan/projects/opensource/sange/`)

### Risks opened (17)

R-002 through R-018, in `.design/plans/risk-register.md`. Notable open risks:

- **R-002** `laravel/passkeys` is new (released 2026-05-12); ecosystem stability unproven
- **R-005** Premade kit fragments age faster than the Sange release cadence
- **R-006** Purge `--batch` flag socially normalized
- **R-016** `sange.sh` registered (user-confirmed); needs ownership validation + DNS/TLS config
- **R-017** `sange-v1/` and `sange-v2/` HELD until v0.1.0 beta (do NOT delete)
- **R-018** Generator drift across the v0.5→v1.0 development window

### Generators state

**No generators have run yet.** All T-G-001 through T-G-016 are unimplemented. Phase 0a's first job is to write them and run them. Expected outputs (from `implementation-plan.md` Phase 0a step 5):

- T-G-001 → `docs/reference/appendix-d-git-catalog.md`
- T-G-002 → `docs/reference/appendix-e-svn-catalog.md`
- T-G-003 → `docs/reference/appendix-f-cross-vcs.md`
- T-G-004 → `docs/reference/appendix-g-commit-templates.md`
- T-G-005 → `templates/MANIFEST.toml`
- T-G-006 → `docs/README.md` + `docs/tools/README.md`
- T-G-007 → on-demand ADR file scaffolding
- T-G-008 → `docs/reference/exit-codes.md`
- T-G-009 → `docs/reference/cli-reference.md`
- T-G-010 → `docs/reference/json-rpc-schema.md`
- T-G-011 → `docs/reference/config-schema.md`
- T-G-012 → `docs/security/stride.md`
- T-G-013 → `docs/CHANGELOG.md`
- T-G-015 → 35 `templates/gitignore-profiles/<category>/<name>.toml` + `docs/reference/profile-registry.md`
- T-G-016 → CI check at `tools/generators/verify_session_log.py`

### Files materially changed in this snapshot's window

The entire `.design/` folder is the design-phase output. `sange-v1/` and `sange-v2/` directories are unchanged (held until v0.1.0 beta per R-017). No source code, no kit fragments, no `tools/generators/` exist yet.

---

## What the next session must do

A fresh session given only `.design/` access should be able to read this section and know exactly what to do next.

1. **First task:** **T-001 — Repo scaffolding.** Create `pyproject.toml` (hatchling backend, Python 3.12+ floor, deps pinned per ADR-019), `ruff.toml`, `mypy.ini` (`--strict`), `.pre-commit-config.yaml`, empty `src/sange/__init__.py` + `py.typed` + `_version.py`, `tests/__init__.py`, `LICENSE` (Apache 2.0 per ADR-007), `NOTICE`, `.editorconfig`, `.gitignore`, `.gitattributes`, `CHANGELOG.md`, `CONTRIBUTING.md`, `SECURITY.md` (disclosure → `opensource@simtabi.com`), `CODE_OF_CONDUCT.md` (Contributor Covenant 2.1), `AUTHORS.md`, root `README.md` per ADR-017 (≤300 lines, index-only).

2. **Where to start reading:**
   - `.design/plans/build-kickoff-prompt.md` — the exact rules to operate under
   - `.design/plans/implementation-plan.md` Phase 0a — the order
   - `.design/plans/checklist.md` T-001 through T-017 + T-G-001 through T-G-016
   - `.design/sange-architecture-prompt.md` §6.1 (stack picks) + §16.2 (layout) + §22 (execution order)

3. **Current branch:** *(no git repo initialized yet — `git init` is implied by T-001)*

4. **Active in-flight operations:** None. (No purges, no bundles, no gitignore-swap recovery files.)

5. **Open `🧪` clarifying questions for the user:** None at the design-phase boundary. The build-kickoff prompt anticipates likely Phase 0a questions and pre-answers them in its "Likely questions + pre-answers" table.

6. **Critical sequencing reminders:**
   - Phase 0a runs **before** Phase 0b per ADR-029 (generators scaffold everything; humans finesse later).
   - Append a session-log row after every completed task per ADR-028. Use the new template with the `grounding` column per ADR-030.
   - Codebase path is locked in-place at `/Users/imanimanyara/Artisan/projects/opensource/sange/` per ADR-027. Do NOT move files.
   - `sange-v1/` and `sange-v2/` are HELD until v0.1.0 beta per R-017. Do NOT delete or import from them.
   - Ask **one** clarifying question at a time per ADR-024.
   - **Read before reference; cite source; no invented IDs** per ADR-030.

---

## Resumability test result

- [x] **A fresh session given only the build-kickoff prompt + this snapshot can correctly identify the next task.** The snapshot's "What the next session must do" section names T-001 explicitly, points to the four read-first files, and reminds the next session of the four critical sequencing rules.
- [x] **The fresh session does not need to ask for additional context that should have been in this snapshot.** The build-kickoff prompt's "Likely questions + pre-answers" table covers the expected questions (Python version, build backend, linter, test runner, etc.); the snapshot's "Critical sequencing reminders" cover the discipline rules.

Both boxes checked. Snapshot complete.

---

## Audit-chain link

*(No runtime audit chain exists yet — this is the design phase. The first runtime audit-chain entry will be appended by T-001's `git init` + the first commit; from that point forward, `tools/generators/session_log.py` (deferred from T-G-016 conceptually; could be a separate task) will cross-reference design-time session-log rows to runtime audit-chain entries.)*

The integrity of this snapshot rests on:

- The 14 design-phase artifacts listed above being on disk and readable
- Cross-reference resolution: every ADR-NNN, R-NNN, T-NNN, S-NNN cited above resolves to a real entry in the canonical files (verified at snapshot-write time)
- The session-log's S-001-T-01 through S-001-T-21 sequence being intact (no gaps in the monotonic counter)

If any of the above is no longer true when this snapshot is read, the snapshot is stale and the reader should append a `S-NNN-T-MM` row noting the discrepancy before proceeding.
