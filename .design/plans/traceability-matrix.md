# Traceability matrix — prompt → plan → architecture → execution

Every accepted decision flows through four artifacts. This file is the cross-reference. Update it on every meaningful change.

## Flow shape

```
[user request in chat history]
       │
       ▼
[.design/plans/content-audit.md row]   ─── proof the request landed somewhere
       │
       ▼
[sange-architecture-prompt.md §-anchor]   ─── spec authority
       │
       ▼
[.design/plans/decisions-log.md ADR row]   ─── decision authority (if non-trivial)
       │
       ▼
[sange-architecture.md §-anchor]   ─── narrative authority
       │
       ▼
[.design/plans/checklist.md task ID]   ─── execution authority
       │
       ▼
[.design/plans/quality-gates.md row]   ─── done-when authority
       │
       ▼
[code commit / docs file]   ─── artifact
```

When two artifacts conflict, the resolution order is **chat-history → prompt → ADR → architecture → checklist → code**. If a code commit appears to contradict an earlier ADR, either the ADR was superseded (record the supersedence in `decisions-log.md`) or the commit is a defect (roll back).

## Cross-reference table

Each row: a major decision/capability, traced through every artifact.

| Capability | Chat-turn | content-audit row | Prompt § | ADR | SANGE_ARCHITECTURE § | Checklist | Quality gate |
|---|---|---|---|---|---|---|---|
| Sange-as-DX-layer positioning | T7 | "Sange does not replace existing tools" | §3 | ADR-022 | §2 | — | "Audience scope honored" |
| Seven personas | T7 | "Usable by non-devs / CEOs / …" | §3 | ADR-022 | §2.3 | — | "happy paths require zero config for personas 1+4" |
| Engineering bar (SOLID/DRY/KISS) | T7 | "SOLID / DRY / KISS / …" | §3 + §15-D20 | ADR-022 | §2.4 | — | "no internal repetition" |
| Codebase paths (no `/simtabi/`) | T3 | "Real codebase paths" | §4.0 + §4.1 | — | §5.1 | T-001 | "paths use `/opensource/sange/`" |
| v1 had 104-string commit array | T3 | "DEFAULT_GIT_COMMIT_MESSAGES has 104" | §4.0 + §6.8.5 | — | §5.5 + §16.5 | T-106, T-G-004 | "Appendix G has ≥50 normalized presets" |
| v2 silent regression | T3 | "v2 is a silent regression of v1" | §4.0 | — | §5.2 | T-001 | — |
| Etymology = sengi, not sange | T3 | "sange is NOT standard Swahili" | §3 + §15-D12 | ADR-014 | §3 | — | "etymology section corrected" |
| Laravel 13 + Livewire 4 + passkeys package | T3 | "Laravel 13 ships AI SDK; Passkeys separate" | §6.1 + §8.1 + §15-D1 | ADR-002 | §2.1 / §7.4 | T-160, T-163 | "`laravel/passkeys` pinned" |
| Python core + Laravel UI split | T2 | "Python core + Laravel UI" | §6.1 + §15-D0 | ADR-001 | §7.1 | T-161, T-162 | "no AI in Laravel layer" |
| No Laravel AI SDK | T3 | "Don't use Laravel 13's first-party AI SDK" | §6.1 + §15-D10 | ADR-003 | §11 | — | "ADR-003 ✓" |
| `sanged` daemon supervision | T3 | "sanged daemon per OS" | §15-D11 | ADR-013 | §7.1 | T-161 | — |
| SQLite default + multi-DB | T2 | "DB: SQLite default" | §6.1 + §15-D3 | ADR-004 | §7.4 | T-168 | "multi-DB driver test matrix" |
| Apache 2.0 license | T2 | "License: MIT/Apache 2" | §3 + §15-D4 | ADR-007 | header | — | "LICENSE present" |
| Local-only telemetry in v1 | T2 | "support local telemetry" | §12 + §15-D5 | ADR-008 | §11.6 | T-014 | — |
| BYOK + MCP + Prompt Enhancer | T2 | "BYOK + MCP + Prompt Enhancer" | §6.7 + §6.7.1 + §15-D6 | ADR-005 | §11 + §12 + §13 | T-009, T-010 | — |
| TOML + JSON dual config | T2 | "support both config formats" | §6.3 + §15-D7 | ADR-009 | §10 | T-002 | — |
| Remote Web UI in v1 | T2 | "we can add this support right of the bat" | §8.5 + §15-D8 | ADR-010 | §7.4 | T-187..T-192 | "remote topologies have setup wizards" |
| Release Bundling | T2 | "support release bundling" | §6.9 + §15-D9 | ADR-011 | §17 | T-193..T-199 | "6 destinations" |
| Container VCS secret mgmt | T2 | "vcs tools security in container" | §6.10 + §15-D9 | ADR-012 | §10.4 | T-104, T-105 | "5 mechanisms" |
| Final v3 repo layout | T3 | "final sange codebase here" | §16.2 + §15-D14 | ADR-016 | §14 | — | "Final v3 layout fully specified" |
| Docs split (README + /docs/) | T3 | "only one main readme file" | §16.3 + §15-D15 | ADR-017 | (this file) | — | "docs strategy implemented" |
| VCS history purge subsystem | T4 | "best way to remove histories" | §6.11 + §15-D16 | ADR-018 | (item §18 — to be generated) | T-111..T-114, T-203..T-208 | "all 4 VCS targets; 8 gates; 8 verifications" |
| `docs/tools/security/purge.md` | T4 | "well-organized playbook" | §6.11.8 | ADR-018 | (item §19 — to be generated) | T-208 | "produced from user playbook" |
| CLI/TUI presentation conventions | T4 | "tree UI, progress bars, spinners" | §7.0 + §15-D17 | ADR-019 | (item §20 — to be generated) | T-107..T-110 | "TerminalProfile + 7 sub-rules" |
| Top-25 Git command floor | T5 | "Top 25 Git Commands image" | §9.0.1 + §7.2 | — | (Appendix D — to be generated) | T-G-001 | "no §9.0 row marked `(deferred)`" |
| Wrapping discipline | T5 | "no thin facades" | §9.4 | — | (item §35 — to be generated) | — | "every wrapper does ≥1 of 7 augmentations" |
| Innovation surface | T5 | "what Sange adds beyond vanilla VCS" | §9.5 | — | (item §36 — to be generated) | — | "§9.5 cross-referenced from catalog" |
| Subgrouped Category convention | T6 | "files subgrouped by tool/tech/usage" | §10.4 + §15-D19 | ADR-021 | §14 | T-012 | "no flat fragments" |
| Premade Operations Kit | T6 | "actions/workflows/bundlers/push-to-prod/VPS" | §6.12 + §15-D18 | ADR-020 | (item §20 — to be generated) | T-115, T-209..T-212 | "9 CI providers + 8 bundlers + 9 deploy + 9 VPS" |
| `sange scaffold` CLI | T6 | "premade scripts" | §7.11 | ADR-020 | — | T-209 | "scaffold subcommands exist" |
| Generate-first / fine-tune-second | T8 | "long tasks → automation scripts" | §2.4 + §16.4 + §15-D21 | ADR-023 | (note in items 18+) | T-G-001..T-G-014 | "every generated section has frontmatter" |
| One question at a time | T8 | "ask question one at a time" | §1 + §7.0.9 + §15-D22 | ADR-024 | (in §13 + §16.4) | — | "no batched confirmations" |
| Godmode workbook framing | T9 | "godmode workbook + agency-reusable" | §0 + §15-D23 | ADR-025 | header note | — | — |
| Fluent / chainable OOP | T1 (latent), T9 | "fluent oop chainable" | §6.13 + §15-D23 | ADR-025 | §8.1 (chained example) | — | — |
| `.design/plans/` companion folder | T7 | ".design/plans/ for plans / checklist / audit" | §3 + §19 gate | — | — | — | "`.design/plans/` exists with 8 files" |
| Profile Registry (35 profiles + auto-detect + per-project activation) | T10 | "all tools and language support … profile in use per project … files present" | §6.5.1 + §7.6 + §15-D24 | ADR-026 | §15.4 | T-G-015 | "Profile Registry v1.0 ships all 35 profiles" + auto-detect timing gate + safety profile + rename enforcement |
| `.design/` workbook layout + codebase path in-place | T11 | "review changes I have made to filenames and folders … correct project path" | §0 + §16.2 (resolved) + §15-D25 | ADR-027 | (header refers to `.design/` indirectly) | — | "design metadata lives under `.design/`; no stale cross-references" |
| Session-log + audit-after-every-task method | T12 | "add method to track session and task progress and history + checklist + audit after every step/task is complete" | (new artifact) + §15-D26 | ADR-028 | (process artifact, not narrative) | — | "session-log row appended after every completed task" |
| Generators scaffold everything (Phase 0a before 0b) | T12 | "generators to scaffold everything and then finesse later" | §2.4.1 + §22 step 5 + §15-D27 | ADR-029 | §16.4 + §47 | T-015..T-017 + T-G-001..T-G-015 in Phase 0a | "every generator listed in §16.4 produces valid output with valid frontmatter" |
| §43 Testing Strategy + §44 Performance Budgets substantive | T12 | "fill now so that when we start development we have little to worry about" | §17 outline items 43/44 + `sange-architecture.md` §43/§44 | — | §43 + §44 | T-211 (per architecture; test infra is part of Phase 3) | "test pyramid + coverage + fixtures + CI order + budgets all specified" |
| `sange.sh` registered + v1/v2 hold-until-beta | T12 | "sange.sh already registered" + "hold v1/v2 until v0.1.0 beta" | R-016 + R-017 in risk-register | — | §3 notes domain status | — | "domain status tracked; v1/v2 hold gates the deletion" |
| Doc-length 80k target | T12 | "standardize the value to right about ~80k" | §19 quality gate updated | — | (target applies to `sange-architecture.md` as it grows during Phase 0a) | — | "deliverable approaches ~80k words once generators populate Appendices D-G + the docs/reference/* surface" |
| Anti-hallucination discipline | T13 | "safely handle hallucinations and prevent them" | §2.5.1 + §15-D28 | ADR-030 | (rule applies project-wide — see §39 STRIDE) | (rule applies to every task; no specific T-NNN) | "every non-trivial claim cites file:line / URL / ADR-NNN; no invented IDs / versions / paths; CI's verify_generated.py rejects catalog drift" |
| Memory preservation + crash-recovery + resumability | T13 | "preserve memory, and progress and history" | §2.5.2 + §15-D29 + §22 step 11.5 | ADR-031 | (rule applies project-wide; snapshots in `.design/plans/snapshots/`) | T-G-016 (verify_session_log.py) | "every completed task has session-log row with grounding; every phase boundary has snapshot; latest snapshot newer than last git commit; resumability test passes" |

## Open items still in flight

| Item | Status | Where tracked |
|---|---|---|
| Generators T-G-001 through T-G-015 | Pending implementation | `checklist.md` Phase 0a |
| sange-architecture.md items 18+ | Pending generator run | This file's cross-reference table marks them "to be generated" |

## Recently closed

| Item | Resolution | Closed in |
|---|---|---|
| Codebase target path | **In-place** at `/Users/imanimanyara/Artisan/projects/opensource/sange/`; user-confirmed 2026-05-13 (v4.2). | ADR-027 + R-001 closed in `risk-register.md` |
| Workbook layout under `.design/` | All design metadata moved under `.design/` at the repo root; canonical for future agency projects | ADR-027 |

## How to use this matrix

1. **When a new user request arrives:** add a row before any code changes. The row forces you to find/create the chat-history capture, the prompt §-anchor, the ADR (if non-trivial), and the architecture section.
2. **When you wonder why something is the way it is:** find the row by capability name and trace back to the chat turn.
3. **When you superseded a decision:** mark the ADR row "superseded by ADR-NNN" in `decisions-log.md` and update this row's ADR column accordingly.
4. **When `verify_generated.py` flags drift:** the matrix's "Quality gate" column tells you which gate was supposed to catch it.

---

*Updated on every meaningful architecture change. Last reviewed: 2026-05-13 (v4.0).*
