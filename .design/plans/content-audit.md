# Content audit — every requirement mapped

This file is the proof that **no user-supplied requirement has been lost** between the chat history and the architecture prompt. Each row: source quote → architecture-prompt section that captured it → status.

Update on every meaningful edit. Re-check before any session hand-off.

## Source: original brief (chat turn 1)

| User requirement (paraphrased) | Captured in | Status |
|---|---|---|
| Automate common VCS commands (git, svn, hg, …) | §6.1 stack, §6.2 layered arch, §9.0 command floor | ✓ |
| Start with full Git + SVN support; grow into others | §6.11.1 tier table, §14 roadmap (Hg/Fossil/Pijul v2, P4 v3) | ✓ |
| Name = "sange" from a Swahili / Bantu term — *to verify* | §3 etymology — verified as *sengi* (not "sange"); ADR-014 | ✓ |
| Domain = `sange.sh` | §3 product domain + ADR-015 URL scheme | ✓ |
| Automate dev-setup boilerplate (brew, docker, oh-my-zsh, …) | §7.1 `sange bootstrap`, §6.12 templates/scripts/bootstrap/ | ✓ |
| One-liner installer per OS (oh-my-zsh-style) — security-hardened | §7.1 + §4.4 image-1 + ADR-020 kit policy | ✓ |
| Commit message templates + presets the user can pre-select | §6.8.5 (104 v1 strings curated to ≥50 normalized presets in Appendix G) | ✓ |
| AI support during commit + issue identification + commit message generation | §6.7 AI subsystem + §6.7.1 prompt enhancer + §6.8 commit lifecycle | ✓ |
| AI providers: Claude / OpenAI / others; MCP connections | §6.7 (Anthropic / OpenAI / Ollama / Gemini / Azure / Bedrock) + §6.7 MCP client + MCP server | ✓ |
| Comprehensive list of git, svn commands (incl. under-used ones) | §9.0 floor + §9.1–9.3 catalogs + Appendices D / E / F | ✓ |
| Installer that scripts the platform OS (shell on *nix, PowerShell on Win) | §7.1 + §16.2 `installer/` (install.sh + install.ps1 + verify.sh + verify.ps1) | ✓ |
| Docker container, self-contained tools, JSON config | §6.1 container + §16.2 `container/` + §6.10 secret mgmt | ✓ |
| MCP + AI support | §6.7 (both directions: client + server) | ✓ |
| gitignore profiles by VCS, with dev vs prod variants | §6.5 gitignore-swap + §6.4 `.sange/gitignore/profiles/` subgrouped | ✓ |
| `.sange/` folder at repo level, env-specific contents + `config.json` | §6.4 + §6.3 config hierarchy | ✓ |
| Enterprise security + privacy | §11 STRIDE + §12 telemetry + §8.3 web UI security matrix | ✓ |
| Prevent prompt injection | §6.7 content firewall + redaction + §11 prompt-injection row + ≥ 3 independent controls | ✓ |
| User-level settings (`~/.sange/`), `.env` for sensitive items | §6.3 config hierarchy + secrets path | ✓ |
| Pure-Python, fluent OOP, SOLID, DRY, KISS, framework-agnostic | §6.1 + ADR-022 engineering bar | ✓ |
| Makefile aliases, dotfile commands | §10 modular Makefile + §10.4 Category convention | ✓ |
| Excellent error + logging + audit | §7.0.7 hash-chained audit + §7.0.8 errors + §13 observability | ✓ |
| Docker-portable | §6.1 + §16.2 container/ + §6.10 | ✓ |
| Makefile commands to interact with container from inside + outside | §6.6 + §10 | ✓ |
| CI/CD DevOps companion + workflow helper + toolkit | §7.5 + §6.12 premade kit | ✓ |
| Mukora-style per-package Makefiles to replace | §4.3 Mukora vocabulary + §10.3 replacement table | ✓ |
| Web UI in Laravel for approve/review/manage commits, rollback, schedule releases | §8.2.* (21 modules), §8.5 remote access, ADR-002 | ✓ |
| Web UI local + secure + SSL + `.test` domain + monitor local portals | §8.1 + §8.2.14 Local Tools Hub + §8.5 + ADR-006 auth | ✓ |
| List all git, svn commands; `.makefiles/<tool>` per-tool + main include | §9.0 + §10.2 subgrouped fragments | ✓ |
| Top 25 Git Commands (user-provided image) | §9.0.1 + §7.2 explicit mapping | ✓ |
| All commands map to a `sange` equivalent with augmentation | §9.4 wrapping discipline + §7.2 mapping table | ✓ |

## Source: dual-persona refactor turn (chat turn 2)

| Requirement | Captured in | Status |
|---|---|---|
| Replace dual-persona theater with mechanical disciplines (six lenses + ADRs + red-team) | §2 (three disciplines) | ✓ |
| Eight pre-approved decisions (Laravel 12 → Laravel 13, WebAuthn primary + PIN + password, SQLite default with full multi-DB, MIT/Apache 2, telemetry local-only-then-opt-in, BYOK + MCP + Prompt Enhancer, TOML + JSON, remote in v1) | §15 ADR table D1..D9 | ✓ |
| Audit + redesign mandate — v3 is not v2-plus-features | §4 codebase audit + §4.2 redesign mandate + ADR-016 | ✓ |
| Commit-message lifecycle with JSON files + draft → approved → committed | §6.8 (8-state lifecycle, JSON schema, CLI surface) | ✓ |
| Prompt Enhancer first-class subsystem | §6.7.1 | ✓ |
| Release Bundling first-class capability | §6.9 | ✓ |
| Container VCS Secret Management | §6.10 | ✓ |
| Remote-access topologies in v1 (Cloudflare Tunnel + Tailscale + WireGuard + VPS) | §8.5 | ✓ |

## Source: v3 path / etymology / Livewire / Passkey / v1-v2 audit corrections (turn 3 = my v3.1 update)

| Requirement / fix | Captured in | Status |
|---|---|---|
| Real codebase paths (no `/simtabi/` segment on disk) | §4.0 + §4.1 verified facts | ✓ |
| `DEFAULT_GIT_COMMIT_MESSAGES` already has 104 entries → curate, not expand | §4.0 + §6.8.5 | ✓ |
| v1/v2 are pure Bash/Make (zero Python/PHP/AI) | §4.0 verified facts | ✓ |
| v2 is a silent regression of v1 (configs/config.sh, colors.sh, error_handler.sh, .github/, .sange/.state deleted) | §4.0 verified facts + §16.2 mapping table | ✓ |
| Laravel 13 (2026-03-17) ships first-party AI SDK; Passkeys are separate `laravel/passkeys` package (2026-05-12) | §4.0 + §6.1 + §8.1 + ADR-002 | ✓ |
| Livewire 4 (2026-01-15) is current major — not Livewire 3 | §6.1 + §8.1 + ADR-002 | ✓ |
| PHP 8.3 floor / 8.4 recommended (L13.3+ Symfony 8 deps) | §6.1 + §8.1 | ✓ |
| Etymology: "sange" is NOT standard Swahili (sengi is) → reframe | §3 + ADR-014 | ✓ |
| MCP terminology: server, not host | §6.7 MCP correction + §9.0.6 | ✓ |
| §15 decision table: add ADR-001 (core/UI split) + ADR-003 (no Laravel AI SDK) + ADR-013 (sanged daemon) | §15 | ✓ |
| §2.2 cross-ref §29 → §35 (now §41 ADR Index after later renumber) | §2.2 + §17 outline | ✓ |
| Final v3 source-repo layout (the actual codebase) | §16.2 | ✓ |
| Documentation strategy: one README + per-tool `docs/` tree | §16.3 + ADR-017 | ✓ |

## Source: VCS history-purge playbook (turn 4 = my v3.2 update)

| Requirement | Captured in | Status |
|---|---|---|
| First-class subsystem covering Git / SVN / Hg / Perforce purge | §6.11 (full spec) | ✓ |
| `git filter-repo` + BFG + `svnadmin dump | svndumpfilter` + `hg convert --filemap` + `p4 obliterate` | §6.11.1 scope table | ✓ |
| Detection via gitleaks + trufflehog | §6.11.4 gate-8 + §9.0.6 | ✓ |
| Pre-flight gates (rotate, fresh mirror, backup, branch-protection inventory, CI pause, collaborator notification, ref-budget, scanner regression) | §6.11.4 (8 gates) | ✓ |
| Post-rewrite verification (path-present, string-present, scanner, packfile shrinkage, fsck, LFS, tag signatures, --analyze diff) | §6.11.5 (8 checks) | ✓ |
| Hash-chained JSONL audit, per-repo + global | §6.11.6 + §7.0.7 | ✓ |
| Typed-phrase confirmation with per-session nonce | §7.0.5 + §6.11 | ✓ |
| `--batch` mode requiring four explicit flags + rate-limited | §6.11.3 + §7.10 | ✓ |
| Web UI cannot execute destructive transition | §6.11.3 + §8.2.21 + ADR-018 | ✓ |
| Refactor user playbook to `docs/tools/security/purge.md` (19 sections + 20 gotchas + Hard-Truths verbatim) | §6.11.8 + §16.3.2 + T-208 | ✓ |
| CLI/TUI presentation conventions (encoding profile, tree, progress, ETA, typed-phrase gate, subprocess streaming, audit chain) | §7.0 (8 subsections) | ✓ |
| Library picks: typer + rich + questionary + textual + structlog + wcwidth + shellingham + python-magic + stdlib asyncio | §7.0.1 + ADR-019 | ✓ |
| Encoding/emoji auto-detection for Windows cp1252 / MSYS2 / locale=C / CI | §7.0.2 | ✓ |

## Source: Top 25 Git Commands image + bug review (turn 5 = my v3.3 update)

| Requirement | Captured in | Status |
|---|---|---|
| Top 25 Git Commands explicit floor | §9.0.1 | ✓ |
| Under-used power commands (bisect, worktree, rerere, maintenance, sparse-checkout, replace, notes, reflog, restore, range-diff, cherry-pick, blame, grep, submodule, lfs, clean, describe, archive, gc, fsck, apply/am, format-patch, send-email, shortlog, verify-commit/-tag, update-index, for-each-ref, rev-list/rev-parse, switch -c --track, absorb, autostash, commit-graph, fsmonitor) | §9.0.2 | ✓ |
| SVN command floor | §9.0.3 | ✓ |
| Mercurial command floor | §9.0.4 | ✓ |
| Perforce command floor | §9.0.5 | ✓ |
| Cross-cutting third-party tools Sange wraps | §9.0.6 | ✓ |
| Wrapping discipline (no thin facades) | §9.4 | ✓ |
| Innovation surface (15 subsections + new primitives) | §9.5 | ✓ |
| Explicit Top-25 → `sange` mapping table | §7.2 expansion | ✓ |
| §7.10 was inserted before §7.9 → fixed | §7.x order | ✓ |
| §17 had 18a / 18b non-standard numbers → fixed | §17 outline | ✓ |
| `docs/tools/purge.md` missing from index → added | §16.3.2 + §9.0 → now `docs/tools/security/purge.md` after v3.4 | ✓ |

## Source: subgrouping refactor + premade kit (turn 6 = my v3.4 update)

| Requirement | Captured in | Status |
|---|---|---|
| Files (Makefiles + everything) subgrouped by tool / tech / usage | §6.4 + §10.2 + §16.2 templates/ + §16.3.2 docs/tools/ | ✓ |
| Canonical Category convention | §10.4 + ADR-021 | ✓ |
| Add folder + premade scripts for actions / workflows / bundlers, push-to-prod, VPS setup | §6.12 + §16.2 templates/{workflows,bundlers,push-to-prod,vps-setup,scripts}/ | ✓ |
| Research best practices for each (CIS, GitHub hardening, SLSA, sigstore, Caddy, Ansible, cloud-init, Terraform, Argo, Flagger, Google SRE) | §6.12.5 citations + Appendix H references | ✓ |
| Curated + signed + versioned kit policy | §6.12.2 + ADR-020 | ✓ |
| `sange scaffold` CLI surface | §7.11 | ✓ |

## Source: positioning + audit + .design/plans/ (turn 7 = my v3.5 update)

| Requirement | Captured in | Status |
|---|---|---|
| Sange does not replace existing tools; improves DX/workflow | §3 + ADR-022 | ✓ |
| Usable by non-devs / CEOs / CTOs / cybersecs / junior-to-senior | §3 audience scope (7 personas) | ✓ |
| SOLID / DRY / KISS / zero repetition / no design flaws / enterprise + military-grade security / simple-yet-powerful | §3 engineering bar + ADR-022 | ✓ |
| `.design/plans/` folder for plans / checklist / audit / decisions / positioning | This file + sibling files | ✓ |
| No internal repetition — one canonical home per fact | §3 + §19 gate | ✓ |
| Deliverable readable by both engineer and non-engineer skims | §3 + §19 reading-age gate | ✓ |

## Source: anti-hallucination + memory preservation → v4.4 (turn 13 = my v4.4 update)

| Requirement | Captured in | Status |
|---|---|---|
| "Safely handle hallucinations and prevent them" | §2.5.1 anti-hallucination rules + ADR-030 + uncertainty markers in session-log notes | ✓ |
| "Preserve memory" | §2.5.2 memory preservation rules + ADR-031 + `grounding` column on session-log + phase-boundary snapshots | ✓ |
| "Preserve progress" | Snapshot template captures completed-tasks + ADRs accepted + risks + generators state + files changed | ✓ |
| "Preserve history" | Session-log already does (per ADR-028); v4.4 strengthens with `grounding` column + cross-reference integrity | ✓ |
| Crash-recovery protocol | §2.5.2 #4 + snapshots/README.md "How a session uses snapshots" | ✓ |
| Continuity check before Deliver | §22 step 11.5 added | ✓ |
| Resumability test at phase boundaries | §2.5.2 #6 + snapshot template's "Resumability test result" checklist | ✓ |
| Build-kickoff prompt hardened | `.design/plans/build-kickoff-prompt.md` "Hard rules" block extended with ADR-030 + ADR-031 + step 11.5 | ✓ |
| Five new §19 quality gates | Anti-hallucination, memory preservation, crash-recovery, continuity check, audit-chain integrity | ✓ |
| Section title bumped from "Four" to "Five Disciplines" | §2 header updated | ✓ |

## Source: eight-question batch resolved → v4.3 (turn 12 = my v4.3 update)

| Requirement | Captured in | Status |
|---|---|---|
| Q1 — `.design/` canonical for every future Simtabi agency project; add session/task/progress/history/checklist/audit-after-every-step method | ADR-027 reaffirmed; `.design/plans/session-log.md` created (ADR-028); session-log row appended for this session | ✓ |
| Q2 — `sange-v1/` and `sange-v2/` deletion: hold until v0.1.0 beta | R-017 added to risk-register | ✓ |
| Q3 — `sange.sh` already registered | R-016 added to risk-register; §3 of `sange-architecture.md` notes the domain status | ✓ |
| Q4 — Generators scaffold everything; humans finesse later | §2.4.1 added to the prompt + ADR-029 + implementation-plan.md Phase 0 reordered (0a = generators + scaffolding; 0b = business logic) | ✓ |
| Q5 — Don't scaffold Python repo this session | Honored (no `src/sange/` code written) | ✓ |
| Q6 — Doc-length budget = ~80k words for the deliverable | §19 quality gate updated; `sange-architecture.md` grew from 1128 → 1501 lines (~18k words; remaining growth comes from generator-emitted sections in Phase 0a) | ✓ |
| Q7 — Brand: `Sange` prose + `sange` CLI | confirmed; no changes needed (already the convention throughout) | ✓ |
| Q8 — Fill §43 Testing Strategy + §44 Performance Budgets now | Both substantively written in `sange-architecture.md` (~3k words); plus items §18-§42, §45-§50 hand-stubbed as design summaries | ✓ |
| Q8 — Find and fix bugs / issues / inconsistencies / gaps | Final sweep: fixed stale "ADR-001 through ADR-027" → "ADR-001 through ADR-029" in §41; verified zero live 🧪 markers, zero TBDs, zero stale module/ADR counts | ✓ |

## Source: file reorganization + path confirmation (turn 11 = my v4.2 update)

| Requirement | Captured in | Status |
|---|---|---|
| Move `sange-architecture-prompt.md` + `SANGE_ARCHITECTURE.md` + `.plans/` under `.design/` umbrella | All ~50 cross-references updated via single-pass `sed`; v4.2 changelog entry | ✓ |
| Rename `SANGE_ARCHITECTURE.md` → `sange-architecture.md` | All 14 prompt refs + 6 plans-README refs + 4 audit refs + 2 decisions refs + 2 traceability refs updated | ✓ |
| Confirm codebase target path = in-place at `/Users/imanimanyara/Artisan/projects/opensource/sange/` | §16.2 (🧪 → ✅), risk-register R-001 closed, ADR-027 | ✓ |
| Fix relative paths `../sange-v{1,2}` → `../../sange-v{1,2}` from the now-deeper `plans/README.md` | `plans/README.md:30` updated | ✓ |
| `.design/` reorganization is canonical for future agency projects (per ADR-025 godmode workbook) | ADR-027 records this; the v4.2 changelog cross-references ADR-025 | ✓ |

## Source: profile registry (turn 10 = my v4.1 update)

| Requirement | Captured in | Status |
|---|---|---|
| Add all tools and language support — what each tooling supports | §6.5.1 Profile Registry — 35 v1.0 profiles | ✓ |
| Config profiles: tracked vs pushed; dev vs prod scope | §6.5.1 `patterns.always / dev_only / prod_only` | ✓ |
| Set profile in use per project | `sange profile use` (§7.6) + `.sange/config.toml::gitignore.{dev,prod}.profiles` | ✓ |
| Files-present-based detection | `detect.required_any` / `detect.boost_any` in registry; `sange profile detect` CLI | ✓ |
| ADR for registry policy | ADR-026 (registry as source-of-truth; rename forbidden in minor releases) | ✓ |
| Generator script to keep registry current | T-G-015 `tools/generators/profile_registry.py` | ✓ |
| §19 quality gate for profile completeness | "Profile Registry v1.0 ships all 35 profiles" + auto-detect timing gate + safety profile + rename enforcement | ✓ |
| Mirrored in sange-architecture.md | §15.4 (4 subsections covering registry, activation, CLI, plugins) | ✓ |

## Source: godmode workbook + fluent OOP + items 1-17 + traceability (turn 9 = my v4.0 update)

| Requirement | Captured in | Status |
|---|---|---|
| "Software and design agency — godmode workbook for this and any future project" | §0 (prompt) + ADR-025 + `.design/plans/README.md` reusability section | ✓ |
| `🟡 META` vs `🟦 SANGE` markers so future forks know what travels | §0 marker convention | ✓ |
| Fluent / chainable OOP (from turn 1 brief, latent until now) | §6.13 + ADR-025 + sange-architecture.md §8.1 chained example | ✓ |
| Fill in items 1-17 of the §17 outline | `sange-architecture.md` §1..§17 hand-authored | ✓ |
| Items 18-50 produced by generator scripts | §16.4 + sange-architecture.md "Items 18 – 50" footer + §22 step 5/6 | ✓ |
| Standardize approach + flow from prompt to plan to architecture to execution | `.design/plans/traceability-matrix.md` (new file) | ✓ |
| Review entire chat history, identify gaps | This audit + traceability matrix | ✓ |
| Final cleanups (fix stale §-references caused by outline renumbering) | §2.2 (§39 → §41), §6.12.5 (§43 → §49), §19 ADR-index gate (§39 → §41) | ✓ |

## Source: generate-first + one-question-at-a-time (turn 8 = my v3.6 update)

| Requirement | Captured in | Status |
|---|---|---|
| For long token-heavy tasks, create scripts to automate generation; final task is fine-tune | §2.4 Generate-first principle + §16.4 generator tree + ADR-023 | ✓ |
| Generators are deterministic + versioned + hash-emitting | §16.4.1 frontmatter convention + §16.4.3 workflow | ✓ |
| Every catalog appendix has a generator (D Git, E SVN, F cross-VCS map, G commit templates) | §16.4 + T-G-001..T-G-014 | ✓ |
| Auxiliary generators: kit MANIFEST, docs index, exit codes, CLI reference, JSON-RPC schema, config schema, STRIDE table, CHANGELOG, ADR scaffolds | §16.4 + §18 generator tasks | ✓ |
| CI integrity check (`verify_generated.py`) | §16.4.1 + §22 step 10 + §19 gate | ✓ |
| `tools/generators/` directory added to §16.2 repo layout | §16.2 (new `tools/generators/` block) | ✓ |
| Execution order updated: generate before catalog drafting | §22 step 5 + 5a + 6 | ✓ |
| Ask one question at a time (responding model + Sange's UX) | §1 + §7.0.9 + ADR-024 | ✓ |
| Sequential confirmation modals in Web UI; sequential typed-phrase gates; MCP server translates batched LLM confirmations into sequential prompts | §7.0.9 | ✓ |

## Untouched / future-session pickups

- The actual catalog content of Appendices D / E / F is left for the responding model to produce per the §9 spec — not in this audit's scope (the requirement is captured; the output is generated downstream).
- The `docs/tools/security/purge.md` content is left for the responding model to refactor from the user-supplied playbook per §6.11.8.
- The kit fragment content under `templates/workflows/`, `templates/bundlers/`, `templates/push-to-prod/`, `templates/vps-setup/`, `templates/scripts/` is left for the implementation team per §6.12.

---

*Updated on every architecture-prompt edit. Last reviewed: 2026-05-13 after v3.5.*
