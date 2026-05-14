# Build-kickoff prompt

> The exact prompt to paste into a fresh Claude Code / Cursor / agentic-IDE session to start the **build phase** of Sange v3. The design phase is complete (v4.3 of the architecture prompt + the deliverable). Use this when you're ready to write code.

## When to use this

| Situation | File to use |
|---|---|
| **Starting the build** (Phase 0a / Phase 0b) | This file ← |
| **Continuing the design** (rare — design is done) | `../sange-architecture-prompt.md` raw |
| **Forking the workbook for a NEW non-Sange agency project** | `../sange-architecture-prompt.md` with §0 fork-procedure followed; replace every `🟦 SANGE` cell |
| **Quick reference during work** | `../sange-architecture.md` §1 + `positioning.md` (10-min skim) |
| **When a generator drifts or you find a bug mid-build** | `session-log.md` + targeted edit + `python tools/generators/verify_generated.py --check` |

## How to use this

1. Open a fresh Claude Code (or Cursor / Cline / any agentic IDE with filesystem access) session **inside the repo root**: `/Users/imanimanyara/Artisan/projects/opensource/sange/`. The model needs to read every file under `.design/` directly from the filesystem.
2. Copy the prompt block below verbatim into the first user message.
3. The model reads the nine listed files, then either asks one clarifying question (per ADR-024) or starts T-001. Either way, the next thing on disk that changes should be a new file under the repo root.
4. As each task in `checklist.md` completes, the model appends a row to `session-log.md` per ADR-028.

If you're using a smaller model with no filesystem access, paste this prompt **plus** the contents of `../sange-architecture.md` (~78 KB) **plus** `implementation-plan.md` (~7 KB) inline. The model can ask for any other file by name and you paste it on demand.

---

## The prompt (copy from here ↓)

```
You are picking up Sange v3 mid-stream. The DESIGN PHASE IS COMPLETE.
Read these in order before doing anything else:

1.  .design/plans/README.md                  — how the design folder works
2.  .design/plans/positioning.md             — what we're building and for whom
3.  .design/plans/decisions-log.md           — 29 accepted ADRs you must honor
4.  .design/plans/implementation-plan.md     — phased plan; Phase 0a is next
5.  .design/plans/checklist.md               — T-001..T-G-015 are next
6.  .design/plans/risk-register.md           — open risks to watch
7.  .design/plans/session-log.md             — append a row after EVERY completed task
8.  .design/sange-architecture-prompt.md     — the spec workbook (v4.3)
9.  .design/sange-architecture.md            — the architecture deliverable (v4.3)

START at Phase 0a per implementation-plan.md (ADR-029: generators scaffold
everything). Do T-001 through T-017 in order, then T-G-001 through T-G-015.

Hard rules:
- ADR-024 — ask me ONE question at a time when you need confirmation. Never batch.
- ADR-029 — generators scaffold the source tree; do not hand-create files
  that the generators are supposed to emit.
- ADR-028 — append a session-log row to .design/plans/session-log.md after
  every completed task. Use the new template with the `grounding` column
  (list of files you READ before doing the action).
- ADR-019 — CLI/TUI library stack is locked (typer + rich + questionary +
  textual TUI-only + structlog + wcwidth + shellingham + python-magic +
  stdlib asyncio/subprocess). Disallowed: tqdm, colorama, inquirer, loguru,
  plumbum, sh, click. Deviation requires a new ADR.
- ADR-030 — ANTI-HALLUCINATION. Read before reference. Cite source
  (file:line, URL+date, ADR-NNN, quoted command output). NO invented
  IDs (ADR-NNN, T-NNN, R-NNN), file paths, library versions, or API shapes.
  "Cannot verify" is allowed; guessing is not. Use markers `🟡 UNVERIFIED`,
  `✅ Verified at <ts>`, `❌ Refuted`. Generator output is authoritative; do
  not paraphrase the catalog from memory when the file is on disk.
- ADR-031 — MEMORY PRESERVATION. `.design/` is the memory; the chat is
  ephemeral. Write phase-boundary snapshots to .design/plans/snapshots/
  phase-<N.M>.md (template at .design/plans/snapshots/README.md). On any
  crash / resume: read session-log → git status → .sange/.recovery →
  .sange/purge/<latest>/plan.json → latest snapshot → append a new
  session-log row with `previous_session_resume` in notes → continue.
- §22 step 11.5 — Continuity Check before any "Deliver" step. Validate
  every session-log row has `grounding`, the latest snapshot is newer than
  the last git commit, every `🟡 UNVERIFIED` is resolved or escalated.
- Honor every red-team pass in the prompt. They are working defenses, not
  decoration — match each one with a test in tests/security/ or tests/unit/.
- Codebase path is LOCKED in-place at /Users/imanimanyara/Artisan/projects/opensource/sange/
  (ADR-027). Do NOT move files into or out of this directory.
- sange-v1/ and sange-v2/ are HELD until v0.1.0 beta (R-017). Do not delete
  them. Do not import from them. Use docs/audit/ for any reference you need.

Phase 0a output expectations (the first batch of work the model produces):
- Repo scaffolding (T-001): pyproject.toml, ruff.toml, mypy.ini,
  .pre-commit-config.yaml, src/sange/__init__.py + py.typed + _version.py,
  tests/__init__.py, LICENSE (Apache 2.0), NOTICE, .editorconfig, .gitignore,
  .gitattributes, CHANGELOG.md, CONTRIBUTING.md, SECURITY.md (→
  opensource@simtabi.com), CODE_OF_CONDUCT.md (Contributor Covenant 2.1),
  AUTHORS.md, root README.md.
- Generator foundation (T-015..T-017): tools/generators/_lib/{output,
  manpage,markdown,fingerprint}.py, tools/generators/verify_generated.py,
  tools/generators/all.py.
- Individual generators (T-G-001..T-G-015): emit
  docs/reference/appendix-{d,e,f,g}.md, docs/reference/{exit-codes,
  cli-reference,json-rpc-schema,config-schema,profile-registry}.md,
  docs/security/stride.md, docs/CHANGELOG.md, docs/README.md,
  docs/tools/README.md, templates/MANIFEST.toml, and the 35 profile-registry
  TOMLs under templates/gitignore-profiles/<category>/<name>.toml.
- Generators also emit kit fragments: templates/workflows/<provider>/,
  templates/bundlers/<tool>/, templates/push-to-prod/<strategy>/,
  templates/vps-setup/<topology>/, .github/workflows/*.yml, Dockerfile,
  docker-compose.yml, and the .sange/ template skeleton.

Every generator-emitted file carries §16.4.1 frontmatter (generator_by,
generator_version, generated_at, input_sha256, output_sha256). CI's
verify_generated.py rejects any drift.

Begin with T-001 (repo scaffolding). Confirm with me before any destructive
operation, before any force-push, and before any external network call that
costs money (AI providers — even for testing).

If you find yourself reaching for a fact you can't verify (a library version,
a CLI flag, the contents of a file, the wording of an ADR) — STOP. Read the
source or ask. Do NOT guess. ADR-030 makes guessing a defect.

If this session ends mid-task (timeout, network drop, context exhaustion):
the next session must be able to resume from .design/ alone. Per ADR-031
that means: append a session-log row BEFORE stopping; if you're at a phase
boundary, also write the snapshot.
```

## ↑ end of prompt

---

## What the model should ask first (and the answers, in case it asks)

The model may ask up to a handful of one-at-a-time questions before starting. Likely candidates with their pre-answered defaults:

| Likely question | Pre-answer |
|---|---|
| Python version target | **3.12+** (per `sange-architecture-prompt.md` §6.1) |
| Build backend | **`hatchling`** (per §6.1 + CLAUDE.md global) |
| Linter / formatter | **`ruff`** with `E, F, W, I, N, UP, B, SIM, RUF` (per `/Users/imanimanyara/Artisan/projects/opensource/CLAUDE.md`) |
| Type checker | **`mypy --strict`** + `pydantic` plugin |
| Test runner | **`pytest` + `pytest-asyncio`** (per §43.2 of `sange-architecture.md`) |
| Pre-commit hooks | **ruff, mypy, gitleaks, shellcheck, hadolint, prettier** (per §16.2 of the prompt) |
| Git commit author identity | `Imani Manyara <19682005+imanimanyara@users.noreply.github.com>` per project (per `/Users/imanimanyara/.claude/CLAUDE.md`) — set per-repo, not global |
| License header in source files | **SPDX `Apache-2.0`** (per ADR-007 + REUSE convention) |
| First Python entrypoint | `src/sange/cli/app.py` — a `typer.Typer()` with one no-op command, so T-G-009 has something to introspect immediately |
| First generator to run end-to-end | **`tools/generators/exit_codes.py`** (T-G-008) — minimal input (an `Enum` in `src/sange/exit_codes.py`), maximally simple output. Use it to validate the generator pipeline before tackling the heavier ones. |

If the model asks something not on this list and you're unsure, the answer is almost certainly in `sange-architecture-prompt.md` — point the model at the relevant §-anchor.

## Fork-friendliness (per ADR-025 godmode workbook)

This file is **`🟡 META`** — the *structure* is reusable for any future agency project. When forking:

1. Replace "Sange" / VCS-specific cells / the §6/§7/§8 anchor list with the new project's equivalents.
2. Keep ADR-019, ADR-023, ADR-024, ADR-028, ADR-029 invariants — they describe how the model should behave regardless of project.
3. The "what the model should ask first" table needs project-specific defaults.
4. The "Phase 0a output expectations" block describes Sange's specific scaffolding; replace it with the new project's equivalent (this is the largest fork-time edit).

For a Python+web project the §0 fork procedure produces a build-kickoff prompt that resembles this one closely. For a non-Python project (Go, Rust, Node, PHP-only) the toolchain rows shift but the ADR-driven invariants survive.

---

*Maintained alongside the design workbook. Last reviewed: 2026-05-13, v4.3. Update when ADR-019 (CLI library stack) or ADR-029 (generators-first scaffolding) change.*
