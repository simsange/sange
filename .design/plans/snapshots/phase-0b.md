# Snapshot — Phase 0b (foundation business-logic) — 2026-05-15

**Created:** 2026-05-15T17:00Z
**Created by:** model:claude-opus-4-7@simtabihq
**Last git commit:** `790b9a3` T-012 Modular Makefile generator
**Parent of snapshot:** `2c4a04d` Add Phase 0a end-of-phase snapshot
**Reason for snapshot:** End of the Phase 0b "foundation business logic"
push. The §6.7.1 → §6.8 → §7 → §12 audit chain is closed end-to-end:
`sange commit` works against a real diff, emits a Conventional Commits
message, and records the call's provenance to `.sange/telemetry/*.ndjson`.
Phase 0c (lifecycle integration: DRAFT → APPROVED → COMMITTED → PUSHED
via `.sange/commits/`) is the natural next phase. Per ADR-031.

---

## State of the world

### What Phase 0b produced

**Twelve commits past the Phase 0a snapshot (`2c4a04d`):**

| SHA | Subject | Tests added |
|---|---|---|
| `99b9434` | T-002 SangeConfig + T-G-011 schema generator | 65 |
| `d68110a` | T-003 VCSDriver Protocol + Domain models | 52 |
| `4cf12a0` | T-004 GitDriver read operations | 61 |
| `e9e2a3b` | T-005 GitDriver write operations | 26 |
| `003734b` | T-006 Commit JSON schema + storage layer | 60 |
| `c6b37d9` | T-007 Commit lifecycle state machine | 48 |
| `2677826` | T-009 AI provider abstraction | 70 |
| `92e3969` | T-010 Prompt Enhancer core | 96 |
| `6de5f68` | T-011 Commit-message enhancement template | 25 |
| `0fb9800` | T-040 Typer CLI skeleton | 23 |
| `fb12b0e` | T-G-009 CLI reference generator | 18 |
| `396eed1` | T-014 Local telemetry collector | 28 |
| `ab885f2` | Wire TelemetryCollector into PromptEnhancer + CLI | 10 |
| `790b9a3` | T-012 Modular Makefile generator | 31 |

**Test growth:** 229 (Phase 0a) → **842 passing** (+613 across 28 new
test modules).

**File count:** 196 tracked files (Phase 0a was 123).

### Subsystems shipped

| Subsystem | Path | Public surface |
|---|---|---|
| Config | `src/sange/core/config/` | `SangeConfig` (13 Pydantic v2 sub-models), `load()` with precedence chain + ENV merge |
| Domain models | `src/sange/core/models/` | `Repo`, `CommitRef`, `BranchInfo`, `WorkingCopyStatus`, `FileEntry`, etc. (frozen dataclasses) |
| VCS Adapter Protocol | `src/sange/adapters/vcs/_protocol.py` | `VCSDriver` Protocol + 4 capability sub-Protocols + `DriverError` + `PushResult` + `TagInfo` |
| Git adapter | `src/sange/adapters/vcs/git/` | `GitDriver` (21 methods); env-disciplined `run_git()` + 7 pure parsers |
| Lifecycle | `src/sange/core/lifecycle/` | `CommitJSON` (8-state), `CommitStore`, `CommitsDirectory`, `LifecycleEngine` |
| AI adapters | `src/sange/adapters/ai/` | `AIProvider` Protocol + `MockProvider` + `get_provider()` factory |
| Prompt enhancer | `src/sange/core/enhancer/` | `PromptEnhancer`, `Redactor` (T-030 mitigation), `TemplateRegistry`, formatting strategies, `AuditRecord` |
| Commit-message template | `src/sange/core/enhancer/tasks/commit_message.py` | `build_commit_message_template()` + `generate_commit_message()` |
| Telemetry | `src/sange/core/telemetry/` | `TelemetryCollector` (NDJSON, weekly rotation), `AiCallEvent`, `CommandEvent`, `ErrorEvent` |
| CLI | `src/sange/cli/` | typer app: `sange --version`, `sange doctor`, `sange ai {providers,preview}`, `sange commit` |

### End-to-end pipeline (closed audit chain)

```
diff (stdin or --diff)
  → sange.cli.commit_command
  → CommitMessageRequest
  → generate_commit_message()
  → PromptEnhancer.enhance()
    → Redactor.scrub()                  # T-030 mitigation
    → TemplateRegistry.render()
    → for_provider(name).format()       # XML / JSON / Markdown
    → AIProvider.complete()              # provider call w/ schema enforcement + 1 retry
    → _validate_against_schema()
  → CommitMessageResult                  # type, scope, subject, body, breaking_change
  → AuditRecord
  → TelemetryCollector.from_audit()
  → AiCallEvent
  → NDJSON in .sange/telemetry/events-YYYY-Www.ndjson
  → Conventional Commits output (stdout)
  → "recorded to <path>" notice (stderr)
```

Telemetry is **off-by-default at the external-send layer** (per ADR-008)
but **on-by-default for local NDJSON** (per §12.1). The CLI flag
`--no-telemetry` opts out per-invocation; `--telemetry-dir <path>`
redirects the file location.

### Generators

**13/16 generators implemented** (Phase 0a finished at 11/16; Phase 0b
added T-G-009 + T-G-011; T-012 is a kit-emitter, not a doc-generator,
so doesn't count toward the 16).

| Task | File | Output |
|---|---|---|
| T-G-001 → T-G-008 | (Phase 0a) | unchanged |
| T-G-011 | `tools/generators/config_schema.py` | `docs/reference/config-schema.md` |
| T-G-009 | `tools/generators/cli_reference.py` | `docs/reference/cli-reference.md` |
| T-G-012, T-G-015, T-G-016 | (Phase 0a) | unchanged |
| T-012 (not numbered T-G-NNN) | `tools/generators/makefile_kit.py` | `templates/Makefile.template` + 5 fragments |

**Remaining 3 deferred** (blocked on real features, not pipeline):

| Task | Blocker |
|---|---|
| T-G-010 jsonrpc-schema | Needs §15 IPC schema (T-162) |
| T-G-013 changelog-from-commits | Needs `.sange/commits/` lifecycle writes (Phase 0c) |
| T-G-014 hg/p4-catalogs | Needs Mercurial + Perforce adapters (v2.0 / v3.0) |

### Kit content

`templates/MANIFEST.toml` carries 43 entries (was 38 after Phase 0a, +5
makefile fragments).

| Path | Source generator | Notes |
|---|---|---|
| `templates/gitignore-profiles/<cat>/<name>.toml` (36) | T-G-015 | unchanged |
| `templates/commit-templates/default.toml` | T-G-004 | unchanged |
| `templates/Makefile.template` | T-012 | new — top-level shim |
| `templates/makefiles/_core/{help,env,colors}.mk` | T-012 | new — auto-help + env + colors |
| `templates/makefiles/vcs/git.mk` | T-012 | new — sange-delegating targets |
| `templates/makefiles/lang/python.mk` | T-012 | new — test/lint/format/install |
| `templates/MANIFEST.toml` | T-G-005 | regenerated to pick up new files |

### Tests passing

**842 tests** across 39 unit-test modules. Single warning (pytest-asyncio
config; harmless). Suite runs in ~15-17 s — git-driver integration tests
(real `git init` against `tmp_path`) account for most of the time.

### ADRs

No new ADRs in Phase 0b. All 33 from Phase 0a remain accepted; none
superseded. The §6.7.1 redaction layer + §12.1 telemetry collector
implemented the ADR-008 + threat-T-030 contracts that were already
documented; no decisions changed.

---

## What's CHANGED from Phase 0a

1. **Audit chain closed.** Phase 0a had the design + generators. Phase
   0b shipped the business logic that consumes them.
2. **`sange commit` works.** The §14.1 v0.1 headline command exists and
   produces real output against a canned mock or a real AI provider
   (once installed).
3. **Telemetry IS active.** Every AI call's provenance lands in
   `.sange/telemetry/events-YYYY-Www.ndjson` by default. Operators can
   opt out per-invocation.
4. **CLI surface exists.** `sange --help`, `sange doctor`, `sange ai
   providers`, `sange ai preview`, `sange commit` all callable.
5. **§10 Modular Makefile kit is shipped.** Five fragments + the
   top-level shim; `make help` works against the kit in a fresh dir.
6. **§16.4 generator pipeline scaled cleanly.** 13/16 generators
   running; the 3 remaining are blocked on real features (not the
   pipeline). Adding T-G-009 + T-012 happened smoothly with the same
   `_lib/output.py` scaffolding.

---

## What's NOT done yet (the v0.1 exit-criteria gap)

The §14.1 v0.1 exit criteria says:

> A developer can install, init a repo, generate a commit message,
> take it through draft → approved → committed → pushed.

What's missing for the **draft → approved → committed → pushed** flow:

1. **`.sange/commits/` write path** in `sange commit`. Today the CLI
   prints the message but doesn't allocate a counter or save a JSON
   DRAFT row. The pieces exist (`CommitsDirectory`, `LifecycleEngine`)
   but aren't wired into the CLI.

2. **`sange commits approve <id>`** sub-command. Calls
   `LifecycleEngine.approve()` on a DRAFT, transitions to APPROVED.

3. **`sange commits push <id>`** sub-command. Calls `GitDriver.push()`
   then `LifecycleEngine.mark_pushed()`.

4. **`sange commits list`** sub-command. Walks `.sange/commits/`,
   shows pending DRAFTs + APPROVED commits.

5. **`sange init`** sub-command. Materializes `.sange/` skeleton:
   `commits/`, `telemetry/`, `Makefile` (via T-012 kit), `.gitignore`
   entries.

6. **T-013 `sange doctor` Makefile-tracked check.** The §10.3
   contract that doctor fails loudly when the generated Makefile is
   tracked in git.

7. **Interactive approval gate** (questionary). For the §6.8.4 menu:
   draft → review → approve or reject.

These are all **wiring tasks** — no new subsystems. The engines (driver,
lifecycle, enhancer, collector) already exist and are tested.

---

## What the next session must do

1. **Read this snapshot first.** The recommended next-task ordering:

   | Order | Task | Scope | Why first |
   |---|---|---|---|
   | 1 | Lifecycle wiring into `sange commit` | ~150 lines + ~25 tests | Closes the DRAFT-row write path |
   | 2 | `sange commits list` | ~80 lines + ~10 tests | Lets users see what's in their queue |
   | 3 | `sange commits approve <id>` | ~80 lines + ~10 tests | The first state transition the user does interactively |
   | 4 | `sange commits push <id>` | ~120 lines + ~15 tests | Closes draft → approved → committed → pushed |
   | 5 | T-013 doctor Makefile-tracked | ~50 lines + ~10 tests | Closes §10.3 contract |
   | 6 | `sange init` | ~150 lines + ~20 tests | Bootstrap UX |
   | 7 | Interactive approval (questionary) | ~100 lines + ~15 tests | Final UX polish before v0.1 |

   After (7), the v0.1 exit criteria is met.

2. **Where to start reading:**
   - This snapshot (`.design/plans/snapshots/phase-0b.md`).
   - `.design/sange-architecture-prompt.md` §6.8.4 (commits sub-command
     menu) + §7.2 (VCS workflow CLI surface) + §14.1 (v0.1 scope).
   - `src/sange/cli/commit.py` (the current `sange commit` — the
     extension point for lifecycle writes).
   - `src/sange/core/lifecycle/state_machine.py::LifecycleEngine` (the
     transitions to call from each new CLI command).
   - `src/sange/core/lifecycle/store.py::CommitsDirectory` (the FS
     layer to write through).

3. **Current branch:** `main`. Last commit: `790b9a3`. **Working tree
   clean.**

4. **Active in-flight operations:** None.
   - No `.sange/.recovery` (no gitignore-swap mid-flight).
   - No `.sange/purge/<latest>/plan.json` (no purge mid-flight).
   - No half-emitted generator outputs.
   - No half-written test files.

5. **Open `🧪` clarifying questions for the user:** None at the Phase 0b
   boundary.

6. **Critical sequencing reminders:**
   - **Phase 0c builds on Phase 0b's engines.** The 4 remaining lifecycle
     commits are all wiring tasks; no new subsystems required.
   - **Append a session-log row after every completed task** per
     ADR-028. New rows must populate the `grounding` column per ADR-030.
   - **Never push without explicit instruction** per `~/.claude/CLAUDE.md`.
   - **Ask one question at a time** per ADR-024.
   - **Read before reference; cite source; no invented IDs** per ADR-030.
   - **Multi-arch from day one** per ADR-033 — every Dockerfile, every
     CI workflow, every Linux package install path.
   - **Telemetry is fire-and-forget** — never let a collector failure
     surface to the caller (test isolation pattern already in place).
   - **Redaction is non-negotiable** — T-030 is Critical-blast; the
     enhancer's `Redactor` runs before any provider call.

---

## Resumability test

  * [x] **A fresh session given only this snapshot can correctly
        identify the next task.** The "What the next session must do"
        section names lifecycle-wiring (1) + ordered alternatives (2-7),
        points to the five read-first files, and reminds of the seven
        critical sequencing rules.
  * [x] **The fresh session does not need to ask for additional context
        that should have been in this snapshot.** Every Phase 0b
        commit is named with its SHA + test count; every subsystem
        is listed with its path + public surface; every pipeline
        state is recorded; every exit-criteria gap is enumerated.

Both boxes checked. Snapshot complete.

---

## Audit-chain link

This snapshot is the third cold-resume artifact in the project's
history. The git-history chain:

```
HEAD (790b9a3) → ab885f2 → 396eed1 → fb12b0e → 0fb9800
              → 6de5f68 → 92e3969 → 2677826 → c6b37d9
              → 003734b → e9e2a3b → 4cf12a0 → d68110a
              → 99b9434 → 2c4a04d (phase-0a snapshot)
              → 37782d7 → 06cbd9d (Initial release)
              ↑                          ↑
        phase-0b.md             phase-design.md
        (this snapshot)         (design phase end)
```

The integrity of this snapshot rests on:

  * The 13 implemented generators + 14 generator-emitted files
    listed above being present on disk and verified by
    `tools/generators/verify_generated.py: 14 files inspected; 0 failures`.
  * Cross-reference resolution via
    `tools/generators/verify_session_log.py: 80 rows parsed; 0 failures`.
  * The `842 passed` test-suite output reproducible by running
    `PYTHONPATH=src python3 -m pytest -q` from the repo root.
  * The `all.py --check ok=13 not_implemented=3 stale=0` output
    reproducible by running it from the repo root.
  * Git commit `790b9a3` being reachable from `main` and containing
    the expected 196 tracked files.

If any of the above is no longer true when this snapshot is read, the
snapshot is stale. The reader appends a `S-NNN-T-MM` row to the session
log noting the discrepancy before proceeding.

---

*Maintained alongside the design workbook. Phase 0b → Phase 0c boundary.
The next snapshot (`phase-0c.md`) lands when the v0.1 exit criteria are
met (draft → approved → committed → pushed working end-to-end).*
