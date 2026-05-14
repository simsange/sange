# Snapshot — Phase 0c (v0.1 exit-criteria met) — 2026-05-15

**Created:** 2026-05-15T22:00Z
**Created by:** model:claude-opus-4-7@simtabihq
**Last git commit:** `a20caee` Add interactive approval (Phase 0c 7/7)
**Parent of snapshot:** `35e2cbb` Add Phase 0b end-of-phase snapshot
**Reason for snapshot:** End of Phase 0c. All 7 wiring tasks done. The
§14.1 v0.1 exit-criteria flow works end-to-end against a real git
working tree. Phase 0d (v0.1 release engineering — multi-arch Docker
build, CI pipeline finalization, real-AI-provider smoke tests, package
publishing) is the natural next phase. Per ADR-031.

---

## State of the world

### What Phase 0c produced

**Seven commits past the Phase 0b snapshot (`35e2cbb`):**

| SHA | Subject | Tests added |
|---|---|---|
| `7d18ef4` | 1/7 Wire LifecycleEngine into `sange commit` | 4 (+ 5 hardened) |
| `e5c0841` | 2/7 Add `sange commits list` | 14 |
| `8e18adb` | 3/7 Add `sange commits approve` | 8 |
| `b995cdf` | 4/7 Add `sange commits push` (v0.1 keystone) | 12 |
| `e6bf8e6` | 5/7 T-013 doctor Makefile-tracked detection | 11 |
| `0f00c66` | 6/7 Add `sange init` | 17 |
| `a20caee` | 7/7 Add interactive approval via questionary | 5 |

**Test growth:** 846 (Phase 0b boundary) → **910 passing** (+64 across
3 new test modules: `test_cli_commits.py`, `test_doctor_makefile.py`,
`test_cli_init.py`).

**File count:** 202 tracked files (Phase 0b was 196).

### The closed §14.1 v0.1 happy path

```
sange init
  ↓ creates .sange/{commits,telemetry}/ + Makefile + .gitignore
git diff --staged | sange commit
  ↓ T-030 redaction → AI provider → CommitMessageResult
  ↓ allocate counter → save .sange/commits/0001-<type>-<scope>-<slug>.json (status=DRAFT)
  ↓ record AiCallEvent to .sange/telemetry/events-YYYY-Www.ndjson
sange commits approve 1 [-i]
  ↓ (interactive: questionary prompt approve / reject / skip)
  ↓ LifecycleEngine.submit() → PENDING_REVIEW (transparently)
  ↓ LifecycleEngine.approve(actor=$USER, via=cli) → APPROVED
sange commits push 1
  ↓ GitDriver.detect(repo) → real Repo
  ↓ _render_message → Conventional Commits text
  ↓ GitDriver.commit(repo, message=...) → real `git commit` → SHA
  ↓ LifecycleEngine.mark_committed(sha) → COMMITTED
  ↓ GitDriver.push(repo, remote=origin) → push to remote
  ↓ LifecycleEngine.mark_pushed(remote) → PUSHED
sange doctor
  ↓ python ≥ 3.10, git available, config valid, AI providers status,
  ↓ §10.3 Makefile-tracked check
sange commits list [--status <state>] [--include-archived] [--json]
  ↓ walks .sange/commits/ → renders table or JSON
```

Every step persists to disk; every AI call's provenance lands in the
NDJSON telemetry feed; T-030 redaction fires before any payload
leaves the machine; §10.3 contract is enforced.

### Subsystems shipped in Phase 0c

| Surface | Path | Notes |
|---|---|---|
| `sange commit` save | `src/sange/cli/commit.py` `_save_draft()` | DRAFT JSON to .sange/commits/ |
| `sange commits` sub-app | `src/sange/cli/commits.py` | list / approve / push commands + _render_message + _resolve_target |
| Doctor Makefile check | `src/sange/cli/doctor.py::_check_makefile_tracked` | §10.3 contract enforcement |
| `sange init` | `src/sange/cli/init.py` | .sange/ skeleton + Makefile + .gitignore |
| Interactive approval | `src/sange/cli/commits.py::_interactive_decision` + `_interactive_reject_reason` | questionary 2.1.1 |

All five surfaces consume engines that were already shipped + tested
in Phase 0b (CommitsDirectory, LifecycleEngine, GitDriver,
TelemetryCollector, PromptEnhancer). **Phase 0c added zero new
subsystems — every commit was wiring.**

### Generators

**13/16 generators implemented** — unchanged from Phase 0b. Every
Phase 0c commit auto-regenerated `docs/reference/cli-reference.md`
(typer introspection picks up new flags + sub-commands without
manual sync).

**Remaining 3 deferred** still blocked on real features:
  * T-G-010 jsonrpc-schema (needs §15 IPC schema / T-162)
  * T-G-013 changelog-from-commits (now PARTIALLY unblocked — the
    `.sange/commits/` write path exists, just needs the generator
    walk + Keep-a-Changelog rendering)
  * T-G-014 hg/p4-catalogs (needs Mercurial / Perforce adapters)

### ADRs

No new ADRs in Phase 0c. All 33 from Phase 0a + 0b remain accepted.
Phase 0c was pure implementation against existing decisions.

---

## What's CHANGED from Phase 0b

1. **The headline `sange commit` now PERSISTS state.** Phase 0b's
   `sange commit` printed a message and discarded it. Phase 0c writes
   a DRAFT row to `.sange/commits/` and threads it through the rest
   of the lifecycle.
2. **The `sange commits` sub-app exists.** Three commands (list /
   approve / push) cover every state transition needed for v0.1.
3. **The v0.1 happy path is operational.** A developer can install,
   init, generate, approve, commit, push — all via Sange. Real git is
   actually invoked; the bare-remote smoke-test confirmed the remote
   receives the Conventional Commits message.
4. **`sange init` makes the bootstrap explicit.** Before Phase 0c the
   user had to know about `.sange/commits/` + `.sange/telemetry/`
   conventions; now `sange init` materializes them + the Makefile +
   .gitignore in one command.
5. **§10.3 Makefile-tracked contract is now enforced.** Doctor
   refuses to pass when it finds a tracked Makefile + emits the
   recovery recipe inline.
6. **Interactive flow added.** `sange commits approve -i` opens a
   questionary prompt (approve / reject / skip). Reject path captures
   a reason and writes it to the audit record.

---

## What's NOT done yet (v0.1 release-engineering gap)

The §14.1 v0.1 *functional* exit criteria are met. The remaining
v0.1 work is **release engineering** — making the package shippable,
not adding features:

1. **Real-AI-provider smoke test.** The pipeline works against
   MockProvider; verify against a real Anthropic / OpenAI / Ollama
   provider end-to-end. Probably a separate `scripts/smoke_v01.sh`.

2. **Multi-arch Dockerfile** per ADR-033 — `linux/amd64` +
   `linux/arm64` from v1.0. Even though v0.1 is CLI-only, the §6.10
   container-secret model needs to land alongside the image build.

3. **CI pipeline finalization.** `.github/workflows/ci.yml` exists
   from Phase 0a but needs the full matrix: pytest across Python
   3.10 / 3.11 / 3.12 / 3.13 on `ubuntu-24.04` + `ubuntu-24.04-arm`
   + `macos-14`, plus the generator-verify gate.

4. **`release.yml` workflow** — tag-driven PyPI publish via OIDC
   trusted publisher (already documented in `docs/release.md`).

5. **T-G-013 changelog generator** — now unblocked. Walks
   `.sange/commits/` (PUSHED status), groups by Conventional Commits
   type, emits `docs/CHANGELOG.md` in Keep-a-Changelog format.
   ~150 lines + ~15 tests.

6. **`pip install -e ".[dev]"` smoke test.** The package builds
   today (`python -m build`); verify the dev install actually exposes
   `sange` on PATH and the entry-point works post-install.

7. **v0.1.0 tag + release.** Once items 1-6 are green, `git tag v0.1.0`
   + push + CI release pipeline does the rest.

These are all **release-engineering tasks** — no new subsystems
required, just operational polish.

### Optional v0.5+ work not in scope here

`sange commits reject <id>` (non-interactive), `sange commits discard
<id>`, `sange commits review <id>` (richer review surface), the §13
web UI, the §15 MCP endpoint, the v2.0 Mercurial adapter, the v3.0
Perforce adapter. All deferred per the §14 roadmap.

---

## What the next session must do

1. **Read this snapshot first.** Recommended next-task ordering for
   the v0.1 release-engineering gap:

   | Order | Task | Scope | Why first |
   |---|---|---|---|
   | 1 | T-G-013 changelog generator | ~150 lines + ~15 tests | Closes pipeline 14/16 + gives `v0.1.0` release a real changelog source |
   | 2 | Multi-arch Dockerfile + CI matrix | ~300 lines / 2 YAMLs | ADR-033 contract; needed for any container artifact |
   | 3 | Real-AI smoke script | ~50 lines + manual run | Validates the headline UX against a real provider |
   | 4 | release.yml workflow | ~150 lines YAML | Closes OIDC trusted-publisher path |
   | 5 | v0.1.0 tag + release | git tag + push | Ships v0.1 |

   After (5), v0.1 is released.

2. **Where to start reading:**
   - This snapshot (`.design/plans/snapshots/phase-0c.md`).
   - `.design/sange-architecture-prompt.md` §14.1 (v0.1 scope) +
     §16.4 (release / OIDC) + ADR-033 (multi-arch).
   - `tools/generators/exit_codes.py` (the template for T-G-013).
   - `docs/release.md` (the OIDC + tag-driven publish recipe).
   - `src/sange/core/lifecycle/store.py::CommitsDirectory.list_all`
     (T-G-013's input source — filter by `status=PUSHED`).

3. **Current branch:** `main`. Last commit: `a20caee`. **Working tree
   clean.**

4. **Active in-flight operations:** None.
   - No `.sange/.recovery` (no gitignore-swap mid-flight).
   - No `.sange/purge/<latest>/plan.json` (no purge mid-flight).
   - No half-emitted generator outputs.
   - No half-written test files.
   - No `.sange/commits/` in the repo root (cleared at Phase 0c task 1).

5. **Open `🧪` clarifying questions for the user:** None at the Phase 0c
   boundary.

6. **Critical sequencing reminders:**
   - **Append a session-log row after every completed task** per
     ADR-028. New rows must populate the `grounding` column per
     ADR-030.
   - **Never push without explicit instruction** per
     `~/.claude/CLAUDE.md`.
   - **Ask one question at a time** per ADR-024.
   - **Read before reference; cite source; no invented IDs** per ADR-030.
   - **Multi-arch from day one** per ADR-033 — when the Dockerfile
     lands, both `linux/amd64` AND `linux/arm64` from v1.0.
   - **Telemetry is fire-and-forget** — never let a collector failure
     surface to the caller.
   - **Redaction is non-negotiable** — T-030 redaction must run
     before any provider call.
   - **No CLI test pollutes cwd** — the convention (Phase 0c task 1)
     is `--no-save --no-telemetry` for tests that don't exercise
     save / telemetry behavior.

---

## Resumability test

  * [x] **A fresh session given only this snapshot can correctly
        identify the next task.** The "What the next session must do"
        section names T-G-013 (1) + ordered alternatives (2-5),
        points to the five read-first files, and reminds of the
        eight critical sequencing rules.
  * [x] **The fresh session does not need to ask for additional
        context that should have been in this snapshot.** Every
        Phase 0c commit is named with its SHA + scope + test count;
        every new surface is listed with its path; the closed v0.1
        happy path is documented as an ASCII flow; the release-engineering
        gap is enumerated.

Both boxes checked. Snapshot complete.

---

## Audit-chain link

This snapshot is the fourth cold-resume artifact in the project's
history. The git-history chain:

```
HEAD (a20caee) → 0f00c66 → e6bf8e6 → b995cdf → 8e18adb
              → e5c0841 → 7d18ef4 → 35e2cbb (phase-0b snapshot)
              → 790b9a3 → ab885f2 → 396eed1 → fb12b0e
              → 0fb9800 → 6de5f68 → 92e3969 → 2677826
              → c6b37d9 → 003734b → e9e2a3b → 4cf12a0
              → d68110a → 99b9434 → 2c4a04d (phase-0a snapshot)
              → 37782d7 → 06cbd9d (Initial release)
              ↑                          ↑
        phase-0c.md             phase-design.md
        (this snapshot)         (design phase end)
```

The integrity of this snapshot rests on:

  * The 13 implemented generators + 14 generator-emitted files
    listed in `phase-0b.md` plus the regenerated `cli-reference.md`
    (each Phase 0c CLI change re-emitted it cleanly).
  * Cross-reference resolution via
    `tools/generators/verify_session_log.py: 86 rows parsed; 0 failures`.
  * The `910 passed` test-suite output reproducible by running
    `PYTHONPATH=src python3 -m pytest -q` from the repo root.
  * The `all.py --check ok=13 not_implemented=3 stale=0` output
    reproducible by running it from the repo root.
  * Git commit `a20caee` being reachable from `main` and containing
    the expected 202 tracked files.
  * The v0.1 happy path being executable: a fresh repo running the
    five-step flow at the top of this snapshot lands a Conventional
    Commits message on a real git remote.

If any of the above is no longer true when this snapshot is read,
the snapshot is stale. The reader appends a `S-NNN-T-MM` row to the
session log noting the discrepancy before proceeding.

---

*Maintained alongside the design workbook. Phase 0c → v0.1 release-engineering
boundary. The next snapshot (`v0.1.md`) lands when the v0.1.0 tag is
pushed and the release pipeline completes.*
