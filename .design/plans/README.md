# `.design/plans/` — Sange v3 hand-off folder

> The stable companion to `../sange-architecture-prompt.md`. Use this folder as the entry point for any future session that needs to resume Sange v3 work without re-reading the chat history.

## What lives here

| File | Purpose |
|---|---|
| `README.md` | This index. Start here. |
| `positioning.md` | Product positioning, audience scope, engineering bar (mirrors §3 + ADR-022 of the architecture prompt). |
| `implementation-plan.md` | Phased delivery plan (v0.1 → v3.0+) with the critical path and gating criteria. |
| `checklist.md` | Single canonical task list, dependency-aware, mirrors §18 of the architecture prompt. |
| `content-audit.md` | Every user requirement from the chat history mapped to the section of the architecture prompt that captured it. The proof that nothing was lost. |
| `decisions-log.md` | ADR-001 … ADR-031 one-line summary table. |
| `traceability-matrix.md` | Every capability traced from chat-turn → audit row → prompt § → ADR → sange-architecture.md § → checklist task → quality gate. |
| `quality-gates.md` | Mirrors §19 of the architecture prompt — the gates that must all pass before v1.0 ship. |
| `risk-register.md` | Open risks, owners, mitigations. |
| `session-log.md` | Append-only diary of every completed task. Updated after every step per ADR-028. |
| `build-kickoff-prompt.md` | The exact prompt to paste into a fresh Claude Code / Cursor / agentic-IDE session to start the build phase. Self-contained; references all other files. |
| `snapshots/` | Phase-boundary snapshots — cold-resume artifacts per ADR-031. One file per phase boundary (`phase-0a.md`, `phase-0b.md`, `phase-1.md`, …). Template + crash-recovery protocol in `snapshots/README.md`. |

## How this folder is used

- **At the start of a new session** — read `positioning.md` then `content-audit.md` then `checklist.md`. That is the full context.
- **After every meaningful architecture-prompt edit** — update `content-audit.md` so the audit stays current.
- **After every ADR is introduced or accepted** — append a row to `decisions-log.md`.
- **At the end of v1.0 sign-off** — verify every row in `quality-gates.md` is green; archive `.design/plans/` to `docs/governance/closeout-v1.0/`.

## Canonical artifacts elsewhere in the repo

- **`../sange-architecture-prompt.md`** — the prompt fed to the responding model. Authoritative for *what to build* and *how to build it*. v4.0 reframed it as the **godmode workbook** — re-forkable for non-Sange agency projects.
- **`../sange-architecture.md`** — the architecture document. Items 1–17 hand-authored (Executive Summary through Release Bundling); items 18+ produced by `tools/generators/all.py`. This is what stakeholders read.
- **`../../sange-v1/`, `../../sange-v2/`** — to be deleted after v3 handoff. Their audit findings are preserved in `content-audit.md`, §4.0 of the architecture prompt, and §5 of `sange-architecture.md`.

## Document authority order (if two sources conflict)

1. The user's most-recent stated requirement in the chat history (re-validate against `content-audit.md`).
2. `../sange-architecture-prompt.md` (the prompt itself — current version stamped at the top).
3. `decisions-log.md` (accepted ADRs).
4. `../sange-architecture.md` (the architecture deliverable narrative).
5. This `.design/plans/` folder.
6. The v1/v2 codebase audit findings (history only; never a constraint on v3 design).

When in doubt, read `positioning.md` first; for the deliverable narrative read `../sange-architecture.md` §1 (Executive Summary).

## Reading order for a new session

1. `README.md` (this file) — get oriented
2. `positioning.md` — what we're building and for whom
3. `traceability-matrix.md` — what flows from where
4. `content-audit.md` — proof of completeness
5. `decisions-log.md` — accepted decisions
6. `../sange-architecture.md` §1–§17 — narrative answers
7. `../sange-architecture-prompt.md` §-specific — when you need the spec for items 18+
8. `checklist.md` + `quality-gates.md` + `risk-register.md` — when you start coding

---

*Maintained alongside the architecture prompt. Last reviewed: 2026-05-13 (v4.0).*
