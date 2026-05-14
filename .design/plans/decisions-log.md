# Decisions log

ADR-001 through ADR-031. Mirrors §15 of `../sange-architecture-prompt.md`. Add a new row on every accepted ADR.

| ADR | Title | Status | Summary |
|---|---|---|---|
| ADR-033 | Multi-arch Docker + Linux images (amd64 / arm64 / armv7) | Accepted | Every Sange-shipped container image and every Linux package layer installed by Sange is built and tested across `linux/amd64` + `linux/arm64` from v1.0 (and `linux/arm/v7` from v2.0). Build via `docker buildx --platform linux/amd64,linux/arm64`; OCI manifest lists ship one tag per arch tuple; pin base images by digest; multi-arch CI matrix on native runners (no QEMU for release builds); `sange doctor --container` warns on QEMU emulation. Apple Silicon dev hosts, Hetzner Ampere ARM VPS, AWS Graviton, Raspberry Pi 4/5 all run natively. Detailed in `docs/adr/0033-multi-arch-docker.md`; specified in prompt §6.1 + §6.6. |
| ADR-032 | Multi-dimensional variant matrix for gitignore-swap (Android-Studio-inspired) | Accepted | Replaces the binary `dev | prod` axis with a Cartesian product over user-declared dimensions: stages (linear, e.g. dev/staging/production) × zero-or-more flavor dimensions (audience/surface/region/tenant). Source-set composition mirrors Android Studio's merge priority (matrix > stage > dimension flavors > _core > profile-registry defaults). Adds variant filters, suffix-based bundle naming (`applicationIdSuffix` analog), stage-locked operations, intelligent auto-detection (CLI > env > `.active-variant` > branch-map > heuristic), variant-aware secret/AI/audit subsystems, and ambient awareness in every Sange surface. Binary config is default-minimal — existing projects need no changes. Detailed in `docs/adr/0032-variant-matrix-android-studio-inspired.md`; specified in prompt §6.5.2; CLI surface in §7.6.1. |
| ADR-001 | Python core + Laravel UI (separated by JSON-RPC) | Accepted | Python core daemon (`sanged`) + Laravel 13 web UI client, decoupled by JSON-RPC 2.0 over loopback (HMAC) or mTLS (remote). CLI/TUI also talks to the same daemon. |
| ADR-002 | Laravel 13 + Livewire 4 + `laravel/passkeys` | Accepted | Laravel 13 (2026-03-17), PHP 8.3 floor / 8.4 recommended; Livewire 4 (2026-01-15); passkeys via the first-party-but-separate `laravel/passkeys` Composer package + `@laravel/passkeys` npm package (released 2026-05-12), NOT in L13 core. |
| ADR-003 | Don't use Laravel 13's first-party AI SDK in the web layer | Accepted | Keep all AI in the Python core enhancer + provider abstraction. Laravel calls core via JSON-RPC. One AI implementation, one redaction layer, one audit trail. |
| ADR-004 | Multi-DB strategy | Accepted | SQLite default; PostgreSQL, MySQL/MariaDB, SQL Server via Laravel's database abstraction. Only SQLite bundled in installer. |
| ADR-005 | Prompt Enhancer subsystem | Accepted | BYOK + MCP client + MCP server + Prompt Enhancer (§6.7.1). Single path from user input → AI provider; versioned + auditable + inspectable. |
| ADR-006 | Auth: WebAuthn passkey + PIN fallback + password alternative | Accepted | Three methods, all first-party Laravel where possible. |
| ADR-007 | License: Apache 2.0, © Simtabi LLC | Accepted | Patent grant matters for plugin ecosystem + enterprise adoption. |
| ADR-008 | Telemetry: local-only in v1; opt-in external send in v2+ | Accepted | Off-by-default; preview before send; aggregation window minimum 24 hours. |
| ADR-009 | Config: both TOML and JSON, picked per file by extension | Accepted | TOML for human-edited (comments), JSON for machine-generated; same Pydantic model. |
| ADR-010 | Remote Web UI supported from v1 via four topologies | Accepted | Cloudflare Tunnel / Tailscale / WireGuard / reverse proxy on VPS — see §8.5. mTLS + MFA + IP allowlist mandatory. |
| ADR-011 | Release Bundling from v1 (§6.9) | Accepted | First-class lifecycle covering 6 destinations + SLSA 3 + sigstore + SBOM. |
| ADR-012 | Container VCS Secret Management from v0.5 (§6.10) | Accepted | Five mechanisms ranked by preference; SSH agent forwarding default for local dev. |
| ADR-013 | `sanged` daemon supervision per OS | Accepted | `launchd` (macOS user agent), `systemd --user` (Linux), Windows Service via `pywin32` (preferred) with NSSM/WinSW fallback. Never root/admin. |
| ADR-014 | Etymology: "named after the *sengi*" framing | Accepted | Do not assert *sange* is itself a Swahili dictionary word. Glosbe is peripheral; standard term is *sengi* (Kingdon 1997). |
| ADR-015 | URL scheme | Accepted | Canonical metadata uses `opensource.simtabi.com/products/sange` + `/documentation/sange`; `sange.sh` is the marketing redirect; repo at `github.com/sangedev/sange` (Simtabi LLC owns the `sangedev` GitHub org dedicated to the Sange ecosystem; `sangedev/documentation` will host the docs site). Updated 2026-05-16. |
| ADR-016 | Final v3 source-repo layout (§16.2) | Accepted | v1/v2 sub-directories deleted post-handoff; v3 occupies the sange repository root. |
| ADR-017 | Documentation split | Accepted | One root `README.md` (index + install + tagline only); manual under `docs/` split per-tool, per-topic. `sange-architecture.md` exists only inside the design-time bundle. |
| ADR-018 | History Purge subsystem invariants | Accepted | Synchronous, interactive, CLI/TUI-initiated only. No async / scheduled / partial rollout. Web UI cannot execute destructive transition. `--batch` requires four explicit precondition flags + rate-limited per operator. |
| ADR-019 | CLI / TUI library stack | Accepted | `typer` + `rich` + `questionary` + `textual` (TUI only) + `structlog` + `wcwidth` + `shellingham` + `python-magic` + stdlib `asyncio` / `subprocess`. Disallowed by default: `tqdm`, `colorama`, `inquirer`, `loguru`, `plumbum`/`sh`, `click`. |
| ADR-020 | Premade Operations Kit policy | Accepted | Curated, signed (`templates/MANIFEST.toml.sig`), versioned. No run-time download of arbitrary remote content. Plugin extensions require signed manifests + provenance tagging. Weekly integration matrix surfaces failures as `kit_status: needs_attention`. |
| ADR-021 | Subgrouped Category convention | Accepted | `_core/`, `_local/`, plus purpose-named sub-dirs from the canonical list. Flat fragments are a quality-gate failure. New categories require an ADR. |
| ADR-022 | Positioning + audience scope + engineering bar | Accepted | Sange does NOT replace existing VCS tools. Seven personas (non-dev founder, CTO, cyber-sec reviewer, junior engineer, senior staff engineer, DevOps/SRE, OSS maintainer). Engineering bar: SOLID + DRY + KISS + zero internal repetition + no design flaws + enterprise / military-grade security + simple-yet-powerful. |
| ADR-023 | Generate-first, fine-tune-second | Accepted | Token-heavy deliverable sections (catalogs, manifest, docs index, exit codes, CLI reference, JSON-RPC schema, config schema, STRIDE, CHANGELOG) are produced by **deterministic generator scripts** under `tools/generators/`, not hand-typed. Every generated file carries §16.4.1 frontmatter with `output_sha256`; `verify_generated.py` enforces integrity in CI. Responding model fine-tunes prose-bearing additions only. Generators are deterministic, versioned, hash-emitting, no LLM in the loop. |
| ADR-024 | One question at a time | Accepted | The responding model (executing this prompt) and Sange itself (CLI / TUI / Web UI) ask **one confirmation question per interaction**, never batched. Confirmations are sequential so the operator can stop the sequence at any point. Multi-field information-entry forms remain allowed for data, not confirmation gates. The MCP server translates batched LLM confirmations into sequential prompts. |
| ADR-025 | Godmode workbook framing + fluent / chainable OOP API style | Accepted | The prompt + `.design/plans/` + `sange-architecture.md` together form an agency-reusable workbook (§0 of the prompt); per-section `🟡 META` / `🟦 SANGE` markers indicate what travels to future projects. Every Sange domain object exposes a chainable API alongside its data-class form (`@chainable` decorator in `src/sange/utils/fluent.py`); chain methods return `self`, are side-effect-free until an explicit terminal verb (`.execute()`, `.push()`, `.materialize()`), and round-trip through `to_dict()` / `from_dict()` for JSON-RPC. Recovers the missing turn-1 design rule never previously captured. |
| ADR-026 | Profile Registry policy | Accepted | The Profile Registry (§6.5.1) is the single source of truth for which languages / frameworks / infrastructure / editors / OS layers Sange supports. v1.0 ships 35 profiles. Each declares auto-detect signals + `always` / `dev_only` / `prod_only` pattern scopes + `extends` composition + version + maintainer. Per-project activation via `sange profile use` writes `.sange/config.toml::gitignore.{dev,prod}.profiles`. Renames forbidden in minor releases (semver). Plugins extend via signed manifests. `_core/license` safety profile blocks any composition from excluding LICENSE/README/NOTICE/COPYING. Generated round-trippably by `tools/generators/profile_registry.py` (T-G-015). |
| ADR-027 | `.design/` workbook layout + codebase path locked in-place | Accepted | The agency design workbook (the prompt + `sange-architecture.md` deliverable + `plans/`) lives under `.design/` at the repo root. Code lives at the repo root *alongside* `.design/`; they never overlap. Confirmed by user reorganization (2026-05-13, v4.2). Canonical for all future agency projects per ADR-025 — fork `.design/` as the template for any new project's design metadata. **Closes R-001:** v3 codebase target path is confirmed in-place at `/Users/imanimanyara/Artisan/projects/opensource/sange/` (after `sange-v1/` and `sange-v2/` deletion); the prior 🧪 Open Question in §16.2 is resolved. |
| ADR-028 | Session-log artifact + audit-after-every-task method | Accepted | `.design/plans/session-log.md` is the append-only diary. Every completed task / accepted ADR / closed risk / meaningful file change / clarifying-Q-answer appends a row with `id, timestamp, actor, surface, action, files_touched, linked, audit_chain, notes`. Integrity via cross-references to other artifacts. When v0.1 runtime audit chain exists, `tools/generators/session_log.py` emits design-time rows from runtime entries automatically. The structure is fork-friendly for any future agency project (godmode workbook per ADR-025). |
| ADR-029 | Generators scaffold everything (strengthens ADR-023) | Accepted | The generate-first discipline extends to the v3 source code itself, not just catalog appendices. Phase 0 order: (1) bootstrap minimum scaffolding (`pyproject.toml`, `ruff.toml`, `mypy.ini`, pre-commit, empty `src/sange/`, `tools/generators/_lib/`, `verify_generated.py`); (2) write generators first; (3) generators emit the kit fragments, profile-registry TOMLs, GitHub workflows, Dockerfile, `.sange/` template skeleton, per-tool docs index — all carrying §16.4.1 frontmatter and verified by CI; (4) humans finesse business logic + prose. A fresh clone can run `python tools/generators/all.py --write` and produce most of the surrounding scaffolding before any business logic is written. |
| ADR-030 | Anti-hallucination discipline | Accepted | Read before reference. Cite source (`file:line` / URL+date / ADR-NNN / quoted command output). No invented IDs, file paths, library versions, or API shapes. "Cannot verify" is allowed; guessing is not. Uncertainty markers `🟡 UNVERIFIED`, `✅ Verified at <ts>`, `❌ Refuted` survive editing. Generator output is authoritative; never paraphrase the catalog from memory when the file is on disk. Red-team passes test for unverified claims. ADR-024 (one-question-at-a-time) is the tool when in doubt — ask, don't guess. |
| ADR-031 | Memory preservation + crash-recovery + resumability | Accepted | `.design/` is the memory; chat is ephemeral. Session-log row after every completed task (extends ADR-028) with new `grounding` column listing the files read before the action. Phase-boundary snapshots in `.design/plans/snapshots/phase-N.M.md` for cold-resume. Crash-recovery protocol: session-log → `git status` → `.sange/.recovery` → in-flight purge state → latest snapshot → resume with `previous_session_resume` marker in the new row. Resumability test at each phase boundary. Audit-chain integrity links design-time + runtime entries. §22 step 11.5 (Continuity Check) blocks Deliver step on failures. |

## ADR template

```markdown
### ADR-NNN: <short title>

**Status:** Proposed | Accepted | Superseded by ADR-XXX
**Date:** YYYY-MM-DD
**Context:** What is the situation? What forces are at play?
**Decision:** What was decided, in one sentence, plus elaboration.
**Alternatives Rejected:**
  - Alternative A — rejected because …
  - Alternative B — rejected because …
**Consequences:**
  - Positive: …
  - Negative: …
  - Neutral: …
**Lens Notes:** One line per relevant lens (Security / Performance / Maintainability / DX / Operability / Cost).
```

## Next ADR slot

**ADR-034** is the next available number. Use it for the next non-trivial decision; do not reuse retired numbers.

---

*Source of truth: §15 of `../sange-architecture-prompt.md` + the prose ADR definitions in §6 / §7 / §8 / §10 / §6.11 / §6.12.*
