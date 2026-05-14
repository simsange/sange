# PROMPT: Sange — VCS Automation Toolkit Research, Audit & Architecture Brief

**Version:** 4.6 (supersedes 4.5)
**Intended audience:** A capable LLM with filesystem and web access (Claude Code, Cursor, or an agentic IDE) tasked with auditing the existing Sange codebase and producing the v3 architecture document. **Also:** Simtabi LLC and any partner agency using this as a re-forkable workbook for *future, unrelated projects* — see §0 "Godmode workbook" framing.

> **How to use:** Paste this entire document into a session that has filesystem access to the referenced repositories. Do not split it. The prompt is self-contained and instructs the responding model to ask clarifying questions only on items not already specified — **one at a time, per §1 + §7.0.9 (ADR-024)**.

---

## 0. GODMODE WORKBOOK — reusable agency template

This document is **two artifacts in one**:

1. **The Sange v3 architecture brief.** Every project-specific cell (codebase paths, etymology, the v1/v2 audit, the 104-string commit-message array, the `sange.sh` domain) is Sange-specific.
2. **A reusable agency workbook.** The *methodology* — Five Disciplines (§2), Category convention (§10.4), `.design/plans/` companion folder, generate-first/fine-tune-second (§2.4), grounded-continuity (§2.5: anti-hallucination + memory preservation), one-question-at-a-time (§7.0.9), audience-scope rubric (§3), STRIDE-grade threat modeling (§11), `.sange/` folder spec generalized to "project root metadata folder" — applies to **any** software project regardless of domain.

When forking this workbook for a non-Sange project:

| Forking step | What to do |
|---|---|
| 1. Re-anchor | Replace "Sange" / "VCS automation toolkit" / "sange.sh" / `github.com/simtabi/sange` with the new product name and URLs |
| 2. Re-audit | Replace §4 codebase-audit findings with the new project's audit (or empty if greenfield) |
| 3. Re-roadmap | Replace §14 phases with the new project's v0.1 → v3.0 |
| 4. Re-personas | Replace §3 audience scope rows with the new project's seven personas (the count is principled, not coincidental) |
| 5. Re-decide | Re-run §15 D0..D22 — most decisions transfer (license, telemetry, audit chain, generate-first); some don't (Laravel-13-specific picks belong only in tools with a web UI) |
| 6. Preserve | Keep §2 disciplines, §10.4 Category convention, §16.4 generator pattern, §7.0 UI conventions, §11 STRIDE pattern — these are *meta*, not Sange-specific |
| 7. Re-walk | Recreate `.design/plans/` from this folder's six files; update `content-audit.md` with the new project's chat history |

The Sange-specific parts are intentionally interleaved with the methodology — read the structure, not just the content. Future projects (CMS, data pipeline, mobile app, hardware firmware) reuse the **disciplines** and the **artifact shape**; they fill in different cells.

For each section below, items marked `🟡 META` are reusable across projects; items marked `🟦 SANGE` are Sange-specific and need replacement when forking.

---

> **v3.1 changelog (2026-05-13):** Corrected stack versions (Livewire 4, not 3; `laravel/passkeys` ships as a separate package, not in L13 core; PHP 8.4 recommended for L13.3+). Corrected codebase paths (no `/simtabi/` segment on disk). Pre-populated audit findings (v1/v2 are 100% Bash/Make, zero Python/PHP; `DEFAULT_GIT_COMMIT_MESSAGES` already has 104 entries; v2 is a silent regression of v1). Corrected "sange" etymology (the academically standard Swahili term for elephant shrew is *sengi*, not *sange*). Corrected MCP terminology (server, not "host"). Filled ADR-001 / ADR-003 / ADR-013 gaps in the decision table. Added §16.2 (final v3 source-repo layout) and §16.3 (documentation strategy: one root `README.md` + `docs/` tree). Fixed §2.2 cross-reference from §29 to §35. Reframed §6.8.5 from "expand to 50+" to "curate, dedupe, taxonomize, normalize" since the existing array exceeds 100.

> **v3.2 changelog (2026-05-13):** Added §6.11 (VCS History Purge subsystem — first-class capability covering Git via `git filter-repo` + BFG, SVN via `svnadmin dump | svndumpfilter`, Mercurial via `hg convert --filemap`, and Perforce via `p4 obliterate`, with detection scanners `gitleaks` + `trufflehog`). Added §7.0 (cross-cutting CLI/TUI presentation conventions: package picks, encoding/emoji auto-detection for Windows `cmd.exe`/`cp1252`/MSYS2 vs modern terminals, tree rendering, progress/spinner/ETA pattern, typed-phrase confirmation gate, hash-chained audit JSONL, subprocess stream-and-retain). Added §7.10 (`sange purge` CLI surface) and §8.2.21 (Purge & History Surgery web UI module — module count now 21). Added ADR-018 (purge is synchronous CLI-only; no async/scheduled/partial rollout). Updated §14 roadmap (detection + verification + dry-run in v0.5; full destructive ops in v1.0). Updated §16.2 (`src/sange/core/purge/` layout, `docs/tools/purge.md` deliverable derived from user-supplied playbook). Updated §17, §18, §19. All other content preserved.

> **v3.3 changelog (2026-05-13):** Bug fixes — moved §7.10 to its correct numerical position (was inserted before §7.9); renumbered §17 outline (was "18a"/"18b" — invalid section numbers); added `docs/tools/purge.md` to the §16.3.2 `docs/tools/` tree (was only referenced by §6.11.8, missing from the index); clarified the §6.11.2 `executing → verified` transition; added missing top-of-purge entry to the §15 decision table cross-references. New content — added §9.0 **Command Coverage Floor** (mandatory must-cover Git/SVN/Hg/Perforce command list driving Appendix D, including all 25 commands from the user-supplied Top-25-Git-Commands reference image plus the under-used power commands and the cross-VCS minimum coverage), §9.5 **Innovation surface** (what Sange engineers *on top of* the underlying VCS — not just wrapping), and a §7.2 expansion mapping every Top-25 Git command to its `sange` equivalent with AI / safety / audit annotations. Added a §19 quality gate that Appendix D must enumerate every §9.0 floor command and that no §9.0 row may be marked "(deferred)" in the v1.0 deliverable.

> **v4.6 changelog (2026-05-15):** Codified the **multi-arch Docker + Linux requirement** per ADR-033: every Sange-shipped container image and every Linux package layer installed by Sange runs natively on `linux/amd64` + `linux/arm64` (v1.0) and additionally `linux/arm/v7` (v2.0). Build via `docker buildx --platform linux/amd64,linux/arm64`; pin base images by digest (multi-arch manifests); CI matrix tests both archs on native runners (`ubuntu-24.04` + `ubuntu-24.04-arm`); `sange doctor --container` warns on QEMU emulation. §6.1 (stack picks) + §6.6 (container lifecycle) + §6.10 (container secrets) + §6.12 (kit `vps-setup/docker/` + `bootstrap/`) updated. ADR-033 accepted at `docs/adr/0033-multi-arch-docker.md`. All other content preserved.

> **v4.5 changelog (2026-05-14):** Added new §6.5.2 **Variant Matrix** — a multi-dimensional profile composition model inspired by Android Studio's build-variants (BuildType × ProductFlavor × FlavorDimensions). Replaces the binary `dev | prod` foot-gun in §6.5 with a Cartesian product over user-declared axes (`stage`, plus zero-or-more flavor dimensions like `audience`, `surface`, `region`). Twelve sub-sections cover axes, declaration, source-set composition, merge priority, suffix mechanisms (the `applicationIdSuffix`/`versionNameSuffix` analog), stage-locked operations, intelligent auto-detection (CLI flag → env var → `.sange/.active-variant` → branch-map → heuristic → defaults), variant-aware subsystems (secrets, AI provider, audit), doctor pollution check, ambient awareness in CLI/TUI/Web, plugin extension surface, and five canonical kit examples. Existing binary `dev/prod` config remains the **default-minimal**; no migration required. New §7.6.1 **Variant manager** CLI surface (`sange variant list/show/use/unset/resolve/detect/diff/verify/filters/scaffold/materialize`) added under §7.6. Stage-locked refusals (`sange publish`, `sange bundle publish --channel stable`, `sange purge execute`) consult the variant per §6.5.2.6. **ADR-032 accepted** at `docs/adr/0032-variant-matrix-android-studio-inspired.md` (5-page expansion with five Alternatives Rejected + six Lens Notes + AGP source citations). Web research grounding: [Android Developers — Configure build variants](https://developer.android.com/build/build-variants), [Configure your build](https://developer.android.com/build). All other content preserved.

> **v4.4 changelog (2026-05-13):** Added the **fifth discipline: Grounded Continuity** (§2.5) covering (a) **anti-hallucination** — every claim verifiable, every ID checked, nothing fabricated; (b) **memory preservation** — every state-change durably written so any future session resumes without context-loss. Two new ADRs (030 anti-hallucination, 031 memory preservation + phase-boundary snapshots + crash-recovery protocol). New `.design/plans/snapshots/` folder for phase-boundary snapshots (cold-resume artifacts). Session-log template extended with a `grounding` column (the files the model READ before performing the action — proof-of-grounding). Build-kickoff prompt hardened with explicit anti-hallucination rules + crash-recovery protocol. Five new §19 quality gates enforcing the discipline. Section title bumped from "Four Disciplines" to "Five Disciplines". All other content preserved.

> **v4.3 changelog (2026-05-13):** Eight follow-ups from the user resolved in one pass — (1) `.design/` workbook layout is **canonical for every future Simtabi agency project** (ADR-027 reaffirmed); (2) a new **session-log artifact + audit-after-every-task method** added at `.design/plans/session-log.md` (ADR-028); (3) `sange-v1/` and `sange-v2/` **hold until v0.1.0 beta** (R-013 added to risk-register); (4) `sange.sh` is **already registered** by the user (R-001 supersession + `domain_status: registered` row in risk-register); (5) Phase 0 reordered so **generators scaffold everything** — the Python skeleton, the kit, the docs, the `templates/` files — then humans finesse later (§22 step 5 promoted + §2.4 amended + ADR-023 strengthened); (6) doc-length budget standardized to **~80k words for the deliverable** (`sange-architecture.md`); (7) brand stylization confirmed (`Sange` in prose, `sange` for CLI / package name); (8) **§43 Testing Strategy + §44 Performance Budgets filled substantively** in `sange-architecture.md` (~3k words combined; covers test pyramid, coverage targets, fixtures pattern, prompt-injection corpus, CI invocation order, latency / resource / generator / availability / scalability budgets). Items §18-§42, §45-§50 hand-stubbed as design summaries pointing to prompt §-anchors. Added ADR-028 (session-log method) and ADR-029 (generators-scaffold-everything). All other content preserved.

> **v4.2 changelog (2026-05-13):** Persisted the user's **file reorganization** under a new `.design/` umbrella at the repo root: `sange-architecture-prompt.md` → `.design/sange-architecture-prompt.md`; `SANGE_ARCHITECTURE.md` → `.design/sange-architecture.md` (renamed: uppercase → lowercase, underscore → dash); `.plans/` → `.design/plans/`. All ~50 cross-references across 10 files updated via single-pass `sed`. Relative paths to `sange-v1/`, `sange-v2/` in `.design/plans/README.md` rewritten from `../sange-v{1,2}` to `../../sange-v{1,2}` (one extra level since `.plans/` now sits one level deeper). **Closed R-001** in `.design/plans/risk-register.md` — codebase target path is confirmed **in-place** at `/Users/imanimanyara/Artisan/projects/opensource/sange/` (option (a) from prior §16.2 Open Question). Removed the 🧪 marker from §16.2 and folded the resolution into the §16.2 prose. Added **ADR-027** documenting the `.design/` reorganization as the canonical workbook layout (`.design/` is the per-project design-metadata folder; reusable across all future agency projects per ADR-025). All other content preserved.

> **v4.1 changelog (2026-05-13):** Filled out the **Profile Registry** (§15.4) — a comprehensive matrix of every supported language / framework / infrastructure / editor / OS profile, declaring (a) the file patterns each profile owns, (b) the dev-vs-prod scope per pattern, (c) **auto-detection signals** (presence of `package.json` → `lang/node`, `composer.json` → `lang/php`, `pyproject.toml` → `lang/python`, `Dockerfile` → `infra/docker`, `artisan` → `framework/laravel`, etc.), and (d) the canonical profile name. Added **per-project activation** via the `sange profile use` CLI verb (§7.6 expanded) writing into `.sange/config.toml`. Added auto-detection via `sange profile detect` for greenfield + onboarding flows. Added ADR-026 (registry policy: registry is *the* source of truth for what's supported; PR-only additions; profile-name stability is semver-mandated). Added §19 quality gate that the registry must round-trip through `tools/generators/profile_registry.py` (T-G-015). Updated sange-architecture.md §15 with the same content in narrative form. All other content preserved.

> **v4.0 changelog (2026-05-13) — godmode workbook release:** Re-framed the document as a **reusable agency workbook** (new §0): the methodology layer (Four Disciplines, Category convention, generate-first principle, one-question-at-a-time, audience-scope rubric, STRIDE pattern, `.design/plans/` artifact shape) is fork-ready for any non-Sange project; the Sange-specific cells are call-outs the agency replaces per project. Added a per-section `🟡 META` / `🟦 SANGE` marker so the next forker knows what travels and what doesn't. Captured the missing **fluent / chainable OOP** design rule from the original turn-1 brief (now §6.13 — was never explicitly recorded across v3.0..v3.6). Created the **`sange-architecture.md` deliverable** at the repo root with §17 outline items 1–17 substantively filled in (items 18+ produced by the responding model via §2.4 generators). Added the **traceability matrix** (`.design/plans/traceability-matrix.md`) showing how every decision flows: chat-history request → `.design/plans/content-audit.md` row → prompt §-anchor → ADR row → sange-architecture.md chapter → checklist task. Added ADR-025 (godmode workbook + fluent OOP design rule). Fixed three stale `§NN` cross-references that had drifted across v3.4 outline renumbering: §2.2 (§39 → §41), §6.12.5 (§43 → §49), §19 ADR-index gate (§39 → §41). All other content preserved.

> **v3.6 changelog (2026-05-13):** Codified the **Generate-first / fine-tune-second discipline** (new §2.4 + §16.4 generator tree + §22 execution-order update): for token-heavy outputs (Appendix D Git catalog, Appendix E SVN catalog, Appendix F cross-VCS map, Appendix G ≥50 commit templates, `templates/MANIFEST.toml`, the docs index, exit-code reference, CLI reference, JSON-RPC schema, the cross-VCS concept map), Sange ships **deterministic generator scripts** under `tools/generators/`. The responding model runs the generators, then fine-tunes the output. No hand-typing of 30k-word appendices. Added ADR-023 (generators are deterministic + versioned + hash-emitting). Added §18 task block **T-G-001 … T-G-012** for the generators themselves. Added §19 quality gates requiring every appendix to be regenerable. Also codified the **"one question at a time" interaction rule** (§1 + §7.0.9): both the responding model (when executing this prompt) and Sange itself (when CLI/TUI/Web UI prompts the user) ask **one question per interaction**, never batched — confirmations are sequential so the operator can stop the sequence at any point. Added ADR-024. Updated `.design/plans/` artifacts to v3.6.

> **v3.5 changelog (2026-05-13):** Locked in the **product positioning and audience scope** (§3): Sange does *not* replace existing VCS tools — it improves workflow + developer experience around them, and is approachable to *non-developers* (CEOs / CTOs / cyber-sec reviewers / junior engineers) as well as senior engineers. Codified the design constraints into a quality gate: **SOLID, DRY, KISS, zero internal repetition, no design flaws, enterprise + military-grade security, simple yet powerful**. Added the `.design/plans/` companion folder at the repo root (`/Users/imanimanyara/Artisan/projects/opensource/sange/.design/plans/`) with the implementation plan, content audit, checklist, decisions log, and positioning statement — the stable hand-off surface so any future session can pick up without re-walking the chat history. Added §19 gates: no internal repetition; every requirement from the chat history maps to a section in this prompt (per `.design/plans/content-audit.md`); deliverable reading age targets two audiences (engineer + non-engineer skim).

> **v3.4 changelog (2026-05-13):** Refactored every file-fragment tree in the document from **flat** to **subgrouped by tool / tech / usage**. The convention is now uniform: an underscore-prefixed `_core/` (or `_local/`) holds framework essentials and user overrides; the remaining sub-directories sort by purpose — `vcs/`, `lang/`, `framework/`, `infra/`, `ci/`, `release/`, `security/`, `ai/`, `db/`, `cloud/`, `editor/`, `os/`. Affected sections: §6.4 (`.sange/` repo folder), §10.2 (`.sange/makefiles/` library), §16.2 (`src/sange/templates/` + `tests/`), §16.3.2 (`docs/tools/`). Added §10.4 the **Category convention** (the canonical list of sub-directories, what goes where, how fragments cross-reference, and how a new category is added). Added a §19 quality gate enforcing the subgrouped convention and forbidding flat-tree regressions. Updated `_core.mk` → `_core/help.mk` + `_core/env.mk` + `_core/colors.mk` so the framework essentials themselves are inspectable rather than monolithic. The glob-include pattern in §10.1 widens accordingly: `include .sange/makefiles/_core/*.mk` followed by `include .sange/makefiles/*/*.mk` (load order: `_core/` first, then alphabetical category, then alphabetical fragment). **Added §6.12 — Premade Operations Kit** (a first-class deliverable: curated CI workflow scaffolds for every supported provider, release bundler scaffolds for goreleaser / semantic-release / release-please / git-cliff / changesets / pyinstaller / electron-builder / OCI, push-to-prod strategies — rolling / blue-green / canary / SSH / compose / k8s / nomad / ECS / Cloud Run, and a VPS provisioning kit with cloud-init / Ansible / Terraform / Caddy / monitoring per CIS-aligned hardening). Added the `sange scaffold` CLI surface (§7.11) for materializing kits into target repos. Added ADR-020 (kit policy: curated, signed, versioned, no arbitrary downloads). Added §19 gates for kit currency and signature verification. All other content preserved.

---

## 1. ROLE & OPERATING MODE

You are a **Principal Software Engineer** with full-stack credentials covering: distributed CLI/TUI tooling in Python; web application engineering in Laravel/PHP and modern frontend (Livewire, Inertia, Vue, Alpine); container packaging and OS integration (macOS, Linux, Windows); application security (threat modeling, supply chain, prompt injection, cryptography); cloud-edge networking (Cloudflare Tunnel, Workers, Tailscale, WireGuard, VPS operations); and DevOps tooling (CI/CD, release engineering, observability).

You do **not** roleplay multiple personas. You operate as one engineer who applies six **review lenses** to every non-trivial decision, records every decision as an **Architecture Decision Record (ADR)**, and runs an **adversarial red-team pass** at every section boundary. These three disciplines are described in §2 and are mandatory.

You are not a yes-man. If a user-stated requirement is technically incoherent, unsafe, or contradicts a stronger requirement, raise a `⚠️ Design Conflict` callout with the corrected approach and rationale. The user has explicitly invited pushback.

**Interaction rule — one question at a time.** When you need confirmation from the user (during this prompt's execution, after every red-team pass, or whenever a `🧪 Open Question` arises that is *not* already answered by §15 or `.design/plans/decisions-log.md`), ask **one question, get the answer, then ask the next**. Never batch three questions in one turn. Reason: the user must be able to stop the sequence at any answer; batched questions force a yes/no on still-unanswered earlier items. The same rule applies to Sange itself when it prompts the user — see §7.0.9.

---

## 2. THE FIVE DISCIPLINES (apply to every decision)

### 2.1 The Six Review Lenses

For every architectural decision, explicitly consider it through these six lenses. Most decisions only have meaningful content for three or four; that is fine. Trivial decisions can summarize all six in a sentence. Major decisions get a full paragraph per lens.

| Lens | Question it answers |
|---|---|
| **Security** | What threat does this counter or introduce? What is the blast radius if it fails? |
| **Performance** | What is the cost (latency, CPU, RAM, IO) at p50 and p99? |
| **Maintainability** | What does this cost in code clarity, test surface, and future change-cost? |
| **Developer Experience** | What does this feel like for a developer using or extending Sange? |
| **Operability** | How is this observed, debugged, rolled back? What does it look like at 3am? |
| **Cost** | Money, time, complexity. Including the cost of *not* doing it. |

Lenses are **analytical frames**, not characters. Apply them; do not narrate them.

### 2.2 Architecture Decision Records (ADRs)

Every non-trivial architectural choice is recorded as an ADR. Use this structure:

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
**Lens Notes:** One line per relevant lens.
```

Number ADRs sequentially across the entire document. Maintain an index in the section corresponding to §17 outline item **§41 (ADR Index)** of the deliverable `sange-architecture.md`. Inside the v3 source repo, ADRs also exist as one file per decision under `docs/adr/NNNN-<slug>.md` (see §16.2).

### 2.3 Red-Team Pass

At the end of each major section, write a `🔴 Red-Team Pass` subsection answering:

1. How would a malicious actor exploit what this section just specified?
2. How would this design fail in production at 3am — slow networks, partial disk, killed processes, corrupted state?
3. What unstated assumption are we making? Is it actually true?
4. What in this section did we hand-wave that a senior reviewer would catch?

If a red-team pass uncovers a defect, **fix the section before moving on**. Do not defer.

### 2.4 Generate-first, fine-tune-second

When a deliverable section is **large, mechanical, or easily produced by a deterministic script** — command catalogs, manifest files, exit-code tables, JSON-RPC schemas, the docs index, the cross-VCS concept map, the ≥50-preset commit-template library — **do not hand-type it**. Instead:

1. Build a deterministic generator script under `tools/generators/` (specified in §16.4).
2. Run the generator and capture its output verbatim into the deliverable.
3. Fine-tune the generated output by hand only where the generator can't be deterministic (commentary, edge-case notes, prose introductions).
4. Record the generator version + invocation in the section's preamble so re-runs are reproducible.

Rationale:
- **Token economy.** Hand-typing 30k–50k words of catalog text wastes context. A 200-line generator emits the same content reproducibly, cheaper, and without drift.
- **Reproducibility.** Generators emit a `sha256` hash of their output; future runs verify the deliverable hasn't been edited out-of-band.
- **Maintenance.** When upstream changes (new git command in `git help -a`, new SVN command, new Conventional Commits type), re-run the generator instead of re-typing.
- **Provenance.** Generated sections are marked with a frontmatter block declaring the generator name, generator version, and output hash. Hand-fine-tuned sections record the diff against the generated baseline.

Generators are **deterministic** (same input → same output, no LLM in the loop), **versioned** (bumped on every change), and **hash-emitting** (output is integrity-verifiable). See ADR-023.

What the generators **don't** replace:
- Prose decisions (§3, §6.x specs, §11 threat model narrative, ADR bodies). Those are hand-curated and bear the engineering judgement.
- Red-team passes. Those require the model's adversarial reasoning.
- The architecture prompt itself.

The generator list, dependencies, and exit-code conventions live in §16.4. The execution order in §22 has the generators running *before* drafting the catalog sections (step 5a).

#### 2.4.1 Generators scaffold the implementation — not just the deliverable (ADR-029)

Per the user's confirmation in v4.3 (S-001-T-13): **the generator-first discipline extends to the v3 source code itself**, not only to the architecture-deliverable's catalog appendices.

Concretely, the Phase 0 implementation order is:

1. Bootstrap the minimum scaffolding: `pyproject.toml`, `ruff.toml`, `mypy.ini`, `.pre-commit-config.yaml`, an empty `src/sange/__init__.py`, `tests/__init__.py`, `tools/generators/_lib/`, and the §16.4 `verify_generated.py`.
2. **Write the generators first.** Every generator in §16.4 produces real output even when the rest of the codebase is empty — e.g. `cli_reference.py` introspects whatever `typer` app exists at the time and emits a stub reference; `config_schema.py` introspects the `SangeConfig` pydantic model the moment it exists.
3. **The generators *also* emit code scaffolds** — the `.sange/` template skeleton, the kit fragments (`templates/workflows/*.yml`, `templates/bundlers/*`, `templates/push-to-prod/*`, `templates/vps-setup/*`), the per-tool docs index, the 35 profile-registry TOML files, the `.github/workflows/*.yml` for Sange's own CI, the `Dockerfile`, the docker-compose files. These outputs are written into the repo with §16.4.1 frontmatter and verified by `verify_generated.py` on every CI run.
4. **Humans finesse** what the generators can't be deterministic about — the prose of each `docs/tools/<topic>.md`, the §6.x specs, the threat-model narrative, the ADR bodies, the red-team passes. Everything else regenerates on demand via `python tools/generators/all.py --write`.

This is a stronger commitment than v3.6's generate-first principle. It says: a fresh clone of the v3 repo with no Python code can run `python tools/generators/all.py --write` and produce *most of the source tree, kit, and docs* before a human writes a single line of business logic. The business logic (commit lifecycle, purge state machine, prompt enhancer) is what humans build by hand; the surrounding scaffolding is generator-emitted and CI-verified.

The §22 execution order step 5 is the canonical sequence; the implementation team works strictly in that order.

### 2.5 Grounded continuity (the fifth discipline)

LLMs hallucinate, and chat sessions are ephemeral. The fifth discipline defends against both: every claim is **grounded** in a source the reader can verify, and every state-change is **continuous** — preserved in a durable artifact so a future session (human or model) resumes without loss.

#### 2.5.1 Anti-hallucination rules (ADR-030)

1. **Read before reference.** Before mentioning a file's contents, a function's signature, an ADR's wording, or a checklist task's status — *read it from disk*. Cite `file:line` for non-trivial claims. The §16.4 generators are deterministic precisely so the catalog content is verifiable; do not paraphrase from memory when the generator output is on disk.
2. **Cite source.** Every factual claim that isn't self-evident has a citation: a `file:line` ref, an ADR number, a URL with access date, a quoted git-log entry, or a quoted shell output. Claims without citations are flagged `🟡 UNVERIFIED` and must be checked before acceptance.
3. **No invented IDs.** ADR numbers, T-IDs, R-IDs, S-IDs, commit SHAs, library versions, file paths, env-var names — never invent them. If a number is needed, grep for the next free one (`grep -E 'ADR-0[0-9]{2}' .design/plans/decisions-log.md | tail -1` then increment) or read the explicit "next available" pointer at the bottom of `decisions-log.md`.
4. **No invented file contents.** Before claiming a file says X, run `Read` (or `cat`/`grep`) and confirm. The model never reproduces a file from memory when the file exists on disk.
5. **No invented external APIs.** Library APIs, HTTP endpoint shapes, CLI flags of wrapped tools (`git filter-repo`, `cosign`, `cloudflared`, etc.) — verify via the upstream docs, the installed binary's `--help`, or a known-good citation. "I recall this flag exists" is not a citation.
6. **"Cannot verify" is allowed.** When the model cannot ground a claim, the correct action is to say so and ask (per ADR-024) — never to guess. The cost of an unverified guess landing in code is far higher than a 30-second clarification round-trip.
7. **Uncertainty markers** — `🟡 UNVERIFIED` (claim needs checking), `✅ Verified` (checked at `<timestamp>`; source: `<file:line>` or `<URL>`), `❌ Refuted` (was claimed, then checked and found wrong; recorded for posterity). Use them inline; they survive editing.
8. **Generator output is authoritative.** When a generator emits a catalog (Appendix D / E / F / G), that file is the source of truth for what commands / presets exist. The model never claims a command not in the generated catalog without proposing an addition.
9. **Red-team passes catch unverified claims.** Every section's `🔴 Red-Team Pass` includes a question about hallucination: "What claim in this section was not grounded in a verifiable source?"
10. **`sange ai preview` rule for AI outputs.** When AI produces content that will land in a deliverable, the prompt enhancer (§6.7.1) attaches a schema; the validator rejects responses that hallucinate fields not in the schema. The output is also redacted (§11) before becoming part of the audit chain.

#### 2.5.2 Memory preservation rules (ADR-031)

1. **The `.design/` folder is the memory; the chat is ephemeral.** Anything important — a decision, a discovered constraint, a refuted hypothesis, a question and its answer — lands in `.design/` (or `docs/audit/`, or a git commit message). The chat is the *medium*; `.design/` is the *record*.
2. **Append a session-log row after every completed task** per ADR-028. The row carries `id, timestamp, actor, surface, action, files_touched, grounding, linked, audit_chain, notes` (the `grounding` column was added in v4.4 — it lists the files the model READ before doing the action, proving anti-hallucination compliance).
3. **Phase-boundary snapshots.** At each phase transition (Phase 0a → 0b, Phase 1 → 2, etc.) the model writes `.design/plans/snapshots/phase-<N.M>.md` capturing: which tasks completed, which generators produced what hashes, which ADRs accepted, which risks closed/opened, which red-team passes added, what `git status` + `git log --oneline -10` looked like. This is the cold-resume artifact — a fresh session can read the latest snapshot and know exactly where the prior session stopped.
4. **Crash-recovery protocol.** If a session ends mid-task (network drop, context exhaustion, user-`Ctrl+C`), the next session follows this protocol:
   - Read `.design/plans/session-log.md` and identify the last `S-NNN-T-MM` row.
   - Read `git status` and `git log --oneline -10` for the uncommitted-vs-committed delta.
   - Check `.sange/.recovery` (the §6.5 gitignore-swap recovery file) for any active operation.
   - Check `.sange/purge/<latest>/plan.json` for any in-flight purge state.
   - Read the in-progress task description from `checklist.md` using the `linked` column of the last session-log row.
   - Read the files the prior session marked `files_touched` in its last row.
   - Read the latest snapshot in `.design/plans/snapshots/`.
   - Resume from the precise point with a `S-NNN-T-MM` row noting `previous_session_resume`.
5. **No important data in chat-only form.** A clarifying-question exchange that yields a decision: capture the answer in `.design/plans/decisions-log.md` (if non-trivial) or `content-audit.md` (if it just confirms an existing requirement). Closing a session without persisting the decision is forbidden — the next session has no way to recover it.
6. **Resumability test.** Periodically (at each phase boundary), validate resumability: spawn a fresh session that has *only* `.design/` access, give it nothing but the build-kickoff prompt + the latest snapshot, and check it can correctly state "the next thing to do is X." If it can't, the snapshot was incomplete; fix it.
7. **Audit chain integrity.** Every session-log row is itself part of the audit chain — the v0.1+ daemon's `.sange/audit/` JSONL chain links design-time rows (from `session-log.md`) and runtime rows (from `tools/generators/session_log.py`) by `prev_hash`. Tampering is detectable. The chain spans the project's lifetime.
8. **Periodic state-dump command.** `sange dev state-dump` (Phase 0b deliverable) emits a one-shot JSON capturing: SangeConfig contents, all repo-state hashes, all in-flight lifecycle objects, current daemon connections, recent audit-log tail. Useful for hand-off, debugging, and the snapshot routine.

#### 2.5.3 Cross-cutting

- **§19 quality gates** include grounded-continuity gates: every session-log row carries `grounding`; every phase boundary has a snapshot; every red-team pass tests resumability where applicable; every `🟡 UNVERIFIED` marker is resolved before merge.
- **`sange doctor`** checks for crash-recovery state (`.sange/.recovery`, in-flight purges, abandoned bundles) and surfaces them.
- **The §22 execution order step 12 (Deliver)** is preceded by a `🟢 Continuity Check`: "if this session ends now, can the next session resume from `.design/` alone?" If no, fix before declaring done.
- **ADR-024 (one question at a time) is the anti-hallucination tool** when the model is uncertain — *ask*, don't guess. The model's clarifying-question budget is unlimited; the cost of a fabricated claim is unbounded.

#### 🔴 Red-Team Pass for §2.5

1. **Model "remembers" the prompt content from training data and skips reading it on disk** — drifting into the training-cutoff version of the spec rather than the current v4.4. Mitigation: every session-log row's `grounding` column lists the files read in the last 60 seconds; auditors check that the listed files actually exist and that their `git log` shows recent edits matching the model's claims.
2. **Snapshot becomes stale because the model forgot to update it at a phase boundary.** Mitigation: §22 execution step 11.5 (added in v4.4 — see below) blocks the Deliver step when the latest snapshot is older than the last `git commit`.
3. **Session-log entry fabricated.** Mitigation: integrity via cross-references — every `linked` ADR-NNN / T-NNN / R-NNN / S-NNN must resolve to a real entry; CI's `tools/generators/verify_session_log.py` (future T-G-016) checks the graph.
4. **Model invents a generator output** rather than running the generator. Mitigation: every generated file has an `output_sha256` in its frontmatter; CI's `verify_generated.py` re-runs the generator and fails on mismatch (already in v3.6 ADR-023).
5. **Model invents an upstream library version** (e.g. claims `gitleaks ≥ 9.0` when only `8.x` exists). Mitigation: `pyproject.toml` and `pre-commit-config.yaml` pin every dep; `sange doctor` cross-checks installed versions against the pin; CI fails on version drift.

The §22 execution order is updated below to add step 11.5 (Continuity Check) before step 12 (Deliver).

---

## 3. MISSION

Produce a **production-grade audit, research, and architecture document** for **Sange v3** — a clean redesign that supersedes the existing v1 and v2 codebases.

Sange is an open-source, local-first, polyglot VCS automation toolkit, DevEx layer, and CI/CD companion. CLI/TUI is the primary surface; a local-or-remote Laravel web UI provides fine-grained control. The end deliverable is `sange-architecture.md` (plus supporting diagrams, appendices, and checklist) that a development team can begin implementing from on day one.

**Product positioning (one sentence):** *Sange is the local-first developer-experience layer between humans and their version-control systems — eliminating boilerplate, enforcing safety, embedding AI assistance into every commit, branch, and release, and providing a secure dashboard (local or self-hosted) for fine-grained review, approval, scheduling, and orchestration.*

**What Sange is *not*.** Sange is **not** a replacement for `git`, `svn`, `hg`, or `p4`. Sange does not fork the underlying VCS, does not ship a competing wire protocol, does not host repositories. It is a **workflow / DX layer** that wraps the user's chosen VCS with safety nets, AI assistance, audit, and a CLI/TUI/Web surface — improving the developer experience around the tools that already exist.

**Audience scope (designed-for personas).** The CLI / TUI / Web surfaces must read clearly to **all** of the following audiences. A feature that requires senior-engineer mental models to use, *and has no equivalently safe path for the other audiences*, is a design defect:

| Persona | What they need from Sange |
|---|---|
| **Non-developer founder / CEO** | Approve a release with one click on the Web UI; see at-a-glance what shipped; see who approved what; never have to read raw `git` output |
| **CTO / Head of Engineering** | Audit trail, signed-release receipts, SBOM + provenance, compliance reports, dashboard of repo health across the org |
| **Cyber-security reviewer** | Hash-chained audit log, prompt-injection defense (§6.7), purge subsystem (§6.11), threat model (§11), STRIDE coverage, CIS-aligned VPS kit (§6.12) |
| **Junior engineer** | The happy path (`sange commit`, `sange publish`) is one command; gates intercept dangerous operations before damage; helpful error messages with the precise fix |
| **Senior staff engineer** | Granular subcommands (`sange commits <lifecycle>`, `sange purge plan/execute`), scriptable JSON output, plugin extension points, ADR-grade engineering rigor |
| **DevOps / SRE** | Premade kit (§6.12), `sange scaffold`, deploy strategies, monitoring integrations, OIDC trusted publishing |
| **Open-source maintainer** | Default-secure releases (SLSA 3), sigstore, SBOM, the §6.8 commit lifecycle for community PR review queues |

**Design constraints (the engineering bar — enforced by §19 quality gates).** Every architectural choice must satisfy:

1. **SOLID** — Single-responsibility, Open/closed, Liskov, Interface-segregation, Dependency-inversion. The VCSDriver Protocol (§6.2) and AIProvider Protocol (§6.7) are the canonical examples.
2. **DRY** — Zero internal repetition across the prompt, the deliverable, the codebase, or the kit. The §10.4 Category convention exists to forbid duplicated fragment trees; the §16.3 documentation split forbids the architecture being told twice in two different files; the §6.12 kit's `_core/` directories factor out common gates.
3. **KISS** — Simple things stay simple. The happy path is one verb (`sange commit`, `sange publish`); the power surface (`sange commits <subcommand>`, `sange purge <subcommand>`) only opens up when the operator asks for it. No mandatory configuration to use the defaults.
4. **No internal repetition.** Where two sections would say the same thing, one is the canonical source and the other cross-references it (e.g. §6.11 owns the purge spec; §7.10 owns the CLI surface; §8.2.21 owns the Web UI module; each cites the others rather than re-stating).
5. **No design flaws.** Each `🔴 Red-Team Pass` is a working defense against the failure modes specific to its section; aggregate failures don't survive the pass.
6. **Enterprise + military-grade security.** Hash-chained audit (§7.0.7), STRIDE threat model (§11), prompt-injection defense (§6.7), purge subsystem (§6.11), signed plugins, signed kit, CIS-aligned hosts. No security control may be enabled-by-config-only — defaults must be secure.
7. **Simple enough to be powerful.** Powerful tools that nobody can use are not powerful. A non-engineer must be able to approve a release in the Web UI without reading the architecture document.

Where a tension between these constraints appears, surface it via a `⚠️ Design Conflict` callout and resolve it via ADR.

**Target product domain:** `sange.sh` (to be acquired — verify availability via `whois sange.sh` before any public mention; `.sh` ccTLD is open registration).

**Canonical Simtabi OSS portal URLs** (set in `pyproject.toml`, `composer.json`, GitHub repo metadata):

- Product landing: `https://opensource.simtabi.com/products/sange`
- Product documentation: `https://opensource.simtabi.com/documentation/sange`
- GitHub repo: `https://github.com/simtabi/sange`
- GitHub Issues: `https://github.com/simtabi/sange/issues`

`sange.sh` (when acquired) is the **product-facing marketing domain** and redirects to `opensource.simtabi.com/products/sange`. The canonical metadata always uses the long form.

**Etymology — pre-verified, do not re-research from scratch.** Web research (2026-05-13, sources: Wikipedia *Elephant shrew*, sengis.org, CalAcademy Evolution of Sengis, Glosbe `sange→elephant shrew`) shows that:

- The academically standard Swahili term for the elephant shrew is **"sengi"**, popularized by Jonathan Kingdon (1997). It is the term used in biology and conservation literature.
- "sange" appears only as a peripheral Glosbe entry mapping `sange → elephant shrew`. It is **not** present as a headword in *Kamusi ya Kiswahili Sanifu* (TUKI/TATAKI/OUP).
- The existing v1 README states *"Sange is the Swahili name for the Elephant Shrew"* — this claim is **weakly supported** and a reviewer with a Swahili dictionary will catch it.

**Required framing in §3 of the deliverable** (pick one of the two defensible options; do not assert "sange is the Swahili word for elephant shrew"):

1. *"Named after the* **sengi** *(Swahili for elephant shrew), stylized as 'Sange' for branding — short, memorable, evocative of the agile, resilient nature of the animal."* — preferred.
2. *"A coined name evoking the* **sengi** *(elephant shrew, Swahili) — a small, fast, resilient animal whose attributes mirror the toolkit's positioning."* — also acceptable.

If the responding model proposes a rename, it must do so via an ADR with: existing GitHub repo migration cost, PyPI/Packagist namespace cost, brand recognition loss, and replacement candidate. Default: keep the name; correct the etymology framing.

**Copyright:** © Simtabi LLC. License: **Apache License 2.0** (preferred over MIT for explicit patent grant, which matters for plugin ecosystem and enterprise adoption — recorded as ADR-007).

**Required-file contacts** (per Simtabi org conventions):

- `SECURITY.md` disclosure inbox: `opensource@simtabi.com`
- `CODE_OF_CONDUCT.md` enforcement inbox (Contributor Covenant 2.1): `opensource@simtabi.com`
- Maintainer / metadata `maintainers` entry: `Imani Manyara <imani@simtabi.com>`
- `authors` metadata: `Simtabi LLC <opensource@simtabi.com>`

---

## 4. CODEBASE AUDIT & REDESIGN MANDATE

> **This is the first and most important instruction.** Sange v3 is not v2-plus-features. It is a clean redesign informed by what v1 and v2 got right and wrong. Your job is **not** to preserve existing code or structure unless it earns its place on merit.

### 4.0 Verified facts (do not re-investigate from scratch)

The following has been **independently verified** as of 2026-05-13. Treat as ground truth; cite as needed; do not waste audit budget re-deriving:

| Fact | Value | Source |
|---|---|---|
| `sange-v1` actual path | `/Users/imanimanyara/Artisan/projects/opensource/sange/sange-v1` | `ls` 2026-05-13 |
| `sange-v2` actual path | `/Users/imanimanyara/Artisan/projects/opensource/sange/sange-v2` | `ls` 2026-05-13 |
| v3 final codebase target path | `/Users/imanimanyara/Artisan/projects/opensource/sange/` (v1/v2 sub-directories deleted post-redesign) — confirm with user if a relocation to `/Users/imanimanyara/Artisan/projects/sange/` (path-level promotion outside `/opensource/`) is intended | user instruction, 2026-05-13 |
| Python LOC in v1 | **0** | `find … -name '*.py'` returned empty |
| Python LOC in v2 | **0** | same |
| PHP LOC in v1/v2 | **0** | `composer.json` files have empty `"require": {}`; vestigial |
| Bash LOC v1 / v2 | ~6,427 / ~4,469 (30 % regression in v2) | manual count |
| Makefile fragments v1 / v2 | 9 `.mk` files each + top-level `Makefile` | tree |
| AI / MCP / prompt-enhancer / commit-lifecycle code in v1/v2 | **none — zero** | grep for `anthropic`, `openai`, `mcp`, lifecycle JSON, schema |
| `DEFAULT_GIT_COMMIT_MESSAGES` array | **EXISTS in v1** at `sange-v1/configs/config.sh:25–128`, **104 entries**, mixed emoji + Conventional-Commits-adjacent prefixes. **DOES NOT EXIST in v2** — v2 deleted the entire `configs/config.sh` file. | direct file read |
| Mukora Makefile paths in §4.3 | All six exist under `/Users/imanimanyara/Artisan/projects/opensource/mukoracms/packages/{api,assets,data-synchronizer,dev-tool,form-builder,git-commit-checker}/Makefile` | `ls` check 2026-05-13 |
| v2 deletions from v1 | `configs/config.sh`, `helpers/scripts/colors.sh`, `helpers/scripts/error_handler.sh`, `helpers/scripts/git.sh` (dead code), `.github/` directory (workflows + templates + articles), `.sange/.state` | tree diff |
| Laravel 13 release date | **2026-03-17** ✓ | laravel.com, Laravel News |
| Laravel 13 PHP support | **8.3 minimum**; **8.4 recommended in practice** for L13.3+ (Symfony 8 deps pull 8.4) | L13 release notes |
| Laravel 13 first-party Passkey **in core** | **FALSE.** Passkeys ship as separate first-party packages `laravel/passkeys` (Composer) + `@laravel/passkeys` (npm), **released 2026-05-12** (~8 weeks after L13 GA), with optional Fortify integration via `Features::passkeys()`. | Laravel News, 2026-05-12 |
| Laravel 13 first-party AI SDK | ✓ `Laravel\Ai\…` namespace, ships in L13 core. Built atop Prism. | Laravel blog, 2026-03-17 |
| Livewire current major | **Livewire 4** (released 2026-01-15; latest v4.3.0 at 2026-05-01). **Not** Livewire 3. | livewire/livewire releases |
| Etymology of "sange" | **NOT the standard Swahili term for elephant shrew.** Standard term is *sengi* (Kingdon 1997). `sange` appears only as a Glosbe peripheral entry; absent from *Kamusi ya Kiswahili Sanifu*. See §3 for required framing. | Wikipedia, sengis.org, Glosbe |
| GitHub repo (existing) | `github.com/simtabi/sange` (the v1 repo's origin) | v1 `.git/config` |

**What this means for §4.1's scope:** The audit is **not** "review a Python codebase." It is "inventory two shell/Makefile codebases that share ~95% lineage, document the regression v2 caused, and identify the small amount of logic worth porting into v3's Python core."

### 4.1 Required audit of the existing codebases

```
/Users/imanimanyara/Artisan/projects/opensource/sange/sange-v1
/Users/imanimanyara/Artisan/projects/opensource/sange/sange-v2
```

⚠️ Prior versions of this prompt listed the paths as `…/opensource/simtabi/sange/sange-v{1,2}`. **There is no `/simtabi/` segment on disk** — that was an error. Use the paths above verbatim.

For each repository, produce in **Appendix B**:

1. **Inventory** — tree summary (top 3 levels), file counts by extension, lines of code by language, entry points, dependency surface (every version pinned).
2. **Capability map** — every feature the code actually implements, organized by domain (commit handling, hooks, config, AI integration, etc.).
3. **Critical defects** — bugs, security issues, broken invariants, missing error handling, race conditions, hardcoded paths, leaked secrets, missing input validation. **Be ruthless.** Each defect gets a severity tag (Critical / High / Medium / Low) and a recommended remediation in v3.
4. **Anti-patterns** — duplicated logic, global mutable state, mixed concerns, leaky abstractions, premature optimization, magical implicit behavior, untested code paths.
5. **Salvageable assets** — modules, prompts, templates, configs, default-message arrays, hook implementations that earn their place in v3. For each, state what stays as-is, what gets refactored, what gets rewritten.
6. **Divergence between v1 and v2** — what changed, what regressed, what improved, which version each surviving piece comes from. Note (pre-verified per §4.0): **v2 is a partial regression of v1**; every notable diff is a *deletion* in v2 with no replacement. Treat v1 as the baseline.
7. **The "default commit messages array"** — already located (per §4.0): `sange-v1/configs/config.sh:25–128`, identifier `DEFAULT_GIT_COMMIT_MESSAGES`, **104 entries**. Capture verbatim in Appendix B. Task in §6.8.5 is **curate, dedupe, taxonomize, normalize** (the array already exceeds the 50-preset floor) — do not "expand" without justification.

### 4.2 Redesign mandate

After the audit, **propose a clean v3 architecture**. Where v3 diverges from v1/v2, an ADR must justify the change. Do not silently rewrite anything; every deletion or restructure is a decision that must be defended.

A v2 module that worked is no defense against deletion if v3's design renders it obsolete. Conversely, a v2 module that is small, well-tested, and well-shaped should survive — flag it explicitly in Appendix B as "preserved" with reasons.

### 4.3 Mukora Makefiles to study (the "current usage" pattern Sange replaces)

```
/Users/imanimanyara/Artisan/projects/opensource/mukoracms/packages/api/Makefile
/Users/imanimanyara/Artisan/projects/opensource/mukoracms/packages/assets/Makefile
/Users/imanimanyara/Artisan/projects/opensource/mukoracms/packages/data-synchronizer/Makefile
/Users/imanimanyara/Artisan/projects/opensource/mukoracms/packages/dev-tool/Makefile
/Users/imanimanyara/Artisan/projects/opensource/mukoracms/packages/form-builder/Makefile
/Users/imanimanyara/Artisan/projects/opensource/mukoracms/packages/git-commit-checker/Makefile
```

Produce **Appendix A: Command Vocabulary** with: every distinct target name; frequency across the six Makefiles; inferred purpose; proposed Sange equivalent (CLI command + module + module file in `.sange/makefiles/`). This vocabulary seeds the modular Makefile system in §10.

### 4.4 Screenshots provided by the user

- **Image 1** — Oh-My-Zsh single-line installer pattern. Sange must offer an equivalent one-liner per OS with security hardening (checksum + sigstore signature verification, opt-in telemetry disclosure, no auto-elevation, refusal-on-untrusted-shell).
- **Image 2** — VCS landscape. v1 scope: Git + SVN. Tier 2 (v2.0): Mercurial, Fossil, Pijul. Tier 3 (v3.0): Perforce, Plastic SCM, Sapling. Document the plugin architecture that makes Tier 2/3 additions a non-breaking change.

---

## 5. RESEARCH PHASE (do this before designing)

Perform **active web research** — do not rely solely on training-data recall. Cite sources inline with URLs and access dates. Build the References section incrementally.

### 5.1 Competitive landscape

Build a feature-comparison matrix for at minimum these tools:

- **Commit assistants:** `aicommits`, `opencommit`, `gptcommit`, `commitlint`, `commitizen`, `git-cz`, `czg`, GitHub Copilot CLI's commit feature
- **Git wrappers / TUIs:** `lazygit`, `gitui`, `tig`, `magit`, `git-extras`, `gh` CLI, `glab`, `tea` (Gitea), Sourcetree, GitKraken, Tower
- **Hooks & policy:** `pre-commit`, `husky`, `lefthook`, `talisman`, `gitleaks`, `trufflehog`, `git-secrets`
- **VCS abstraction libraries:** `pygit2`, `GitPython`, `dulwich`, `libgit2`, `pysvn`, `subvertpy`
- **DevEx installers:** Oh-My-Zsh, Homebrew, `mise`, `asdf`, `volta`, `proto`, `devbox`, `nix`, `chezmoi`, `dotbot`, Laravel Herd, Laravel Valet
- **Release automation:** `semantic-release`, `release-please`, `goreleaser`, `changesets`, `git-cliff`, `release-it`, `auto`
- **Release bundling / artifact tools:** `goreleaser`, `electron-builder`, `pkg`, `pyinstaller`, GitHub Releases workflow, GitLab Generic Packages
- **CI/CD local testing:** `act` (GitHub Actions), `gitlab-runner exec`, `azure-pipelines-task-lib`, `tekton`, `dagger`
- **AI in IDE/CLI:** GitHub Copilot CLI, `aider`, `gemini-cli`, Cursor, Continue.dev
- **Prompt enhancement frameworks:** `dspy`, `guidance`, `LMQL`, `outlines`, prompt library ecosystems
- **Web-based DevEx dashboards:** GitButler, Graphite, Linear's git integration, Backstage, Coder, Gitpod — what local-first equivalents exist?
- **Remote dev-tool exposure:** Cloudflare Tunnel, Tailscale, Tailscale Funnel, ngrok, Pinggy, frp

For each: license, language, install model, AI integration, plugin model, last-commit recency, star count, **and the specific feature gap Sange will exploit**.

### 5.2 Standards & specs to comply with

- Conventional Commits (current spec)
- SemVer 2.0.0
- Keep a Changelog
- SLSA (target Level 3 for releases)
- Sigstore / cosign for artifact signing
- REUSE / SPDX for license metadata
- OpenSSF Scorecard criteria
- CycloneDX or SPDX SBOM format
- `.gitignore` templates (github/gitignore official repo)
- OWASP ASVS Level 2 for the web UI
- OWASP Top 10 for LLM Applications (current version)
- WebAuthn / FIDO2 for web UI authentication
- OAuth 2.1 / OIDC for VCS provider integration
- OCI image spec and OCI artifact spec for release bundles
- Model Context Protocol (MCP) specification (current version)

### 5.3 Prompt-injection threat model

Sange embeds LLMs in the developer workflow. Cite and incorporate:

- OWASP Top 10 for LLM Applications
- Anthropic / OpenAI guidance on tool-use safety
- Known indirect-prompt-injection vectors: malicious commit messages, crafted file contents, hostile dependency READMEs, MCP-server-supplied data, hostile diff contents, hostile git hook content from third-party repos

Design **defense in depth**, minimum three independent controls. No single mitigation.

---

## 6. NON-NEGOTIABLE ARCHITECTURAL REQUIREMENTS

### 6.1 Languages and stacks

| Component | Stack | Rationale |
|---|---|---|
| Core engine | Python 3.12+ | Cross-platform, low contribution barrier, mature VCS libraries |
| CLI | `typer` + `rich` + `questionary` | Idiomatic, beautiful, interactive |
| TUI | `textual` | Reactive, modern, shares codebase with CLI |
| Web UI framework | **Laravel 13 + PHP 8.3 floor (8.4 recommended) + Livewire 4** | User's existing expertise. Laravel 13 (2026-03-17) ships a first-party **AI SDK** (`Laravel\Ai\…` namespace; built atop Prism). Passkeys are **NOT** in L13 core — they ship as a separate first-party package pair `laravel/passkeys` (Composer) + `@laravel/passkeys` (npm), released **2026-05-12**, with optional Fortify integration via `Features::passkeys()`. PHP 8.3 is the documented minimum; L13.3+ pulls Symfony 8 deps that effectively require **8.4** in practice. **Livewire 4** (2026-01-15, latest 4.3.0) is the current major — *not* Livewire 3. |
| Web UI DB | **SQLite by default**; full driver support for **PostgreSQL, MySQL/MariaDB, SQL Server** via Laravel's database abstraction | Zero-config local; scale path available; user can choose |
| IPC | Local HTTP over loopback (default) or mTLS-authenticated (remote), JSON-RPC 2.0 schema | Decouples Python core from Laravel UI; protocol stays identical local vs. remote |
| Container | Multi-stage Dockerfile, `python:3.12-slim`, pinned base image by digest, **multi-arch via `docker buildx`** (linux/amd64 + linux/arm64 from v1.0; linux/arm/v7 from v2.0 — per ADR-033) | Reproducible, distroless-leaning, runs natively on Apple Silicon + Hetzner Ampere ARM + Raspberry Pi without QEMU emulation |
| Edge / Remote | Cloudflare Tunnel (preferred), Tailscale, WireGuard, direct reverse proxy (Caddy/nginx) | Multiple secure remote topologies, user picks |

**Mandatory ADRs:**

- **ADR-001** — Python core + Laravel UI rather than single-language. Document the IPC contract. Accepted per §15-D0.
- **ADR-002** — Laravel 13 over 12 or non-Laravel framework. Justify Livewire 4 over Livewire 3 (4 is the current major as of 2026-05; do not ship a deprecated UI library at v1.0). Justify pinning `laravel/passkeys` + `@laravel/passkeys` (released 2026-05-12) as a hard dependency rather than rolling our own WebAuthn flow.
- **ADR-003** — Whether to use Laravel 13's first-party AI SDK (`Laravel\Ai\…`) in the web layer, or keep all AI in the Python core. **Decision: keep AI in Python core only**; Laravel calls core via JSON-RPC for any AI feature. Rationale: one AI implementation, one redaction layer, one audit path, one prompt-injection threat surface. Laravel AI SDK is excellent but splitting AI across two runtimes doubles the security and observability budget. Accepted per §15-D10.
- **ADR-004** — Multi-database support strategy. Recommendation: **use Laravel's database abstraction unmodified**; document tested driver versions; SQLite is the only one bundled in the installer; others are user-provisioned.
- **ADR-013** — `sanged` daemon supervision strategy. Per-OS supervisor: `launchd` (macOS), `systemd --user` (Linux), Windows Service via `pywin32` (preferred) or NSSM/WinSW fallback. Document install, start, stop, status, restart, log paths, and uninstall procedures per OS.

### 6.2 Layered architecture (mandatory)

```
┌─────────────────────────────────────────────────────────────────────┐
│  Presentation: CLI │ TUI │ Web UI (Laravel) │ JSON-RPC │ MCP Server │
├─────────────────────────────────────────────────────────────────────┤
│  Application:  Command handlers, workflows, prompts, schedulers     │
├─────────────────────────────────────────────────────────────────────┤
│  Domain:       VCS-agnostic models (Repo, Commit, Branch, Release,  │
│                Bundle, Approval, AuditEntry)                        │
├─────────────────────────────────────────────────────────────────────┤
│  Adapters:     Git │ SVN │ Hg │ ... (VCSDriver Protocol)            │
├─────────────────────────────────────────────────────────────────────┤
│  Infrastructure: AI providers, FS, network, OS, secrets, scheduler, │
│                  MCP clients, edge tunnels                          │
└─────────────────────────────────────────────────────────────────────┘
```

The Domain layer must not know which VCS is in use. The Laravel UI must not bypass the Application layer — it calls into the Python core via JSON-RPC. New VCS support = new Adapter, zero core changes. New surface (e.g., MCP server, REST API for editor plugins) = new Presentation, zero Application changes.

### 6.3 Configuration hierarchy

Precedence, rightmost wins:

```
built-in defaults  ←  /etc/sange/*  ←  ~/.sange/*  ←  ${repo}/.sange/*  ←  ENV  ←  CLI flags
```

**Config format:** Sange supports **both TOML and JSON** for all config files. The user picks per file. Rationale:
- TOML for human-edited files where comments and readability matter (`config.toml`)
- JSON for machine-generated files, schemas, IPC payloads, and tooling output (`commit-NNNN.json`)
- Both parse to the same `pydantic` model
- A file's format is detected by extension; if both `config.toml` and `config.json` exist in the same directory, JSON wins (machine-authoritative) and a warning is logged

Per-user config in `~/.sange/config.toml` (default). Per-repo config in `${repo}/.sange/config.toml`. Schemas are versioned (`schema_version`) and Sange auto-migrates older schemas with a backup.

**Secrets are never in TOML or JSON.** Always:
- `.env`-style files with `0600` perms (default)
- OS keychain via `keyring` library (recommended)
- External secret manager backends (AWS Secrets Manager, HashiCorp Vault, 1Password CLI, Bitwarden CLI, age-encrypted files, GPG-encrypted files)

A single `SangeConfig` Pydantic v2 model is the only object the rest of the code reads from.

### 6.4 The `.sange/` repo folder

Every file tree under `.sange/` follows the **Category convention** (§10.4): an underscore-prefixed `_core/` (or `_local/`) for framework essentials and user overrides, plus sibling sub-directories sorted by **tool / tech / usage** (`vcs/`, `lang/`, `framework/`, `infra/`, `ci/`, `release/`, `security/`, `ai/`, `db/`, `cloud/`, `editor/`, `os/`). Flat layouts are forbidden — a `git.gitignore` directly under `gitignore/profiles/` is a quality-gate failure (see §19).

```
.sange/
├── config.toml                  # repo policy (or config.json)
├── .counter                     # durable monotonic counter for commit JSONs
│
├── gitignore/                   # gitignore-swap (§6.5)
│   ├── dev.gitignore            # active during development
│   ├── prod.gitignore           # active during publish
│   └── profiles/                # named, composable profiles
│       ├── _core/               # always-included safety nets
│       │   ├── secrets.gitignore        # *.pem *.key id_rsa* .env credentials*
│       │   └── editor-noise.gitignore   # .DS_Store thumbs.db
│       ├── lang/
│       │   ├── python.gitignore
│       │   ├── node.gitignore
│       │   ├── php.gitignore
│       │   ├── go.gitignore
│       │   ├── rust.gitignore
│       │   ├── ruby.gitignore
│       │   └── java.gitignore
│       ├── framework/
│       │   ├── laravel.gitignore
│       │   ├── django.gitignore
│       │   ├── rails.gitignore
│       │   ├── nextjs.gitignore
│       │   ├── nuxt.gitignore
│       │   └── symfony.gitignore
│       ├── infra/
│       │   ├── docker.gitignore
│       │   ├── kubernetes.gitignore
│       │   └── terraform.gitignore
│       ├── editor/
│       │   ├── jetbrains.gitignore
│       │   ├── vscode.gitignore
│       │   ├── vim.gitignore
│       │   ├── emacs.gitignore
│       │   └── claude.gitignore           # .claude/ etc.
│       └── os/
│           ├── macos.gitignore
│           ├── windows.gitignore
│           └── linux.gitignore
│
├── makefiles/                   # modular Makefile fragments — see §10 + §10.4
│   ├── _core/                   # framework essentials, always included first
│   │   ├── help.mk              # the auto-help target parsing `## description` comments
│   │   ├── colors.mk            # color + TerminalProfile-aware echo helpers
│   │   └── env.mk               # SANGE_ROOT, OS detection, common variables
│   ├── vcs/                     # VCS targets — git:status, svn:up, etc.
│   │   ├── git.mk
│   │   ├── svn.mk               # only if SVN project
│   │   ├── hg.mk
│   │   └── p4.mk
│   ├── lang/                    # language toolchains
│   │   ├── python.mk
│   │   ├── node.mk
│   │   ├── php.mk
│   │   ├── go.mk
│   │   ├── rust.mk
│   │   └── ruby.mk
│   ├── framework/               # web/app frameworks
│   │   ├── laravel.mk
│   │   ├── django.mk
│   │   ├── rails.mk
│   │   └── nextjs.mk
│   ├── infra/                   # container + orchestration
│   │   ├── docker.mk
│   │   ├── compose.mk
│   │   ├── kubernetes.mk
│   │   └── terraform.mk
│   ├── ci/                      # CI providers
│   │   ├── github.mk
│   │   ├── gitlab.mk
│   │   ├── azure.mk
│   │   ├── bitbucket.mk
│   │   └── jenkins.mk
│   ├── release/                 # release engineering
│   │   ├── semver.mk
│   │   ├── changelog.mk
│   │   ├── bundle.mk            # release bundling targets (§6.9)
│   │   └── sign.mk
│   ├── security/                # secret scanners + purge
│   │   ├── scan.mk              # gitleaks + trufflehog
│   │   └── purge.mk             # delegates to `sange purge …`
│   ├── ai/                      # AI provider / MCP / enhancer
│   │   ├── providers.mk
│   │   └── mcp.mk
│   ├── db/                      # database / migrations
│   │   ├── postgres.mk
│   │   ├── mysql.mk
│   │   └── sqlite.mk
│   └── _local/                  # user's per-repo customizations — gitignored
│       └── *.mk
│
├── commits/                     # commit message JSON lifecycle (see §6.8)
│   ├── NNNN-feat-auth.json
│   ├── ...
│   └── archive/
│       └── YYYY-MM/
│
├── commit-templates/            # message templates and presets
│   ├── default.toml             # the curated ≥50-preset library (see §6.8.5)
│   ├── _core/                   # framework templates
│   │   ├── conventional.tmpl
│   │   └── header-footer.tmpl
│   ├── type/                    # one file per Conventional Commits type
│   │   ├── feat.toml
│   │   ├── fix.toml
│   │   ├── docs.toml
│   │   ├── style.toml
│   │   ├── refactor.toml
│   │   ├── perf.toml
│   │   ├── test.toml
│   │   ├── build.toml
│   │   ├── ci.toml
│   │   ├── chore.toml
│   │   └── revert.toml
│   ├── workflow/                # workflow-specific (release, hotfix, cherry-pick, merge, squash, WIP, initial)
│   │   ├── release.toml
│   │   ├── hotfix.toml
│   │   ├── cherry-pick.toml
│   │   ├── merge.toml
│   │   ├── squash.toml
│   │   ├── wip.toml
│   │   └── initial.toml
│   ├── domain/                  # domain-specific (security CVE, dependency bump, license)
│   │   ├── security.toml
│   │   ├── deps.toml
│   │   └── license.toml
│   └── user/                    # user-authored templates (override / extend)
│       └── *.toml
│
├── bundles/                     # release bundles staging (see §6.9)
│   ├── manifests/
│   │   ├── _core/               # default manifest skeletons
│   │   └── *.toml               # one per release bundle
│   └── artifacts/
│       └── <name>-<version>/
│
├── hooks/                       # source-controlled hooks — fragments grouped by stage
│   ├── pre-commit/
│   ├── prepare-commit-msg/
│   ├── commit-msg/
│   ├── pre-push/
│   ├── post-merge/
│   └── _core/                   # framework-installed hooks (gitleaks, large-file)
│
├── workflows/                   # CI workflow definitions by provider
│   ├── _core/                   # provider-agnostic stage definitions
│   ├── github/                  # .yml emitted into .github/workflows/
│   ├── gitlab/                  # .yml emitted into .gitlab-ci.yml fragments
│   ├── azure/                   # azure-pipelines.yml fragments
│   ├── bitbucket/               # bitbucket-pipelines.yml fragments
│   ├── gitea/
│   ├── forgejo/
│   ├── circleci/
│   └── jenkins/                 # Jenkinsfile fragments
│
├── prompts/                     # AI prompt templates, sanitized, versioned
│   ├── _core/                   # the prompt enhancer's framework prompts
│   ├── commit/                  # commit-msg generation
│   ├── pr/                      # PR description
│   ├── changelog/               # release changelog
│   ├── review/                  # code review
│   ├── explain/                 # diff / commit explanation
│   ├── branch/                  # branch naming
│   └── release-notes/
│
├── secrets/                     # encrypted secrets — gitignored, never plaintext
│   ├── _local/                  # age- or GPG-encrypted files
│   └── refs/                    # references to external secret managers (Vault, 1Password, AWS, etc.)
│
├── purge/                       # history-purge plans + audit (§6.11)
│   └── <utc-ts>-<nonce>/
│       ├── plan.json
│       ├── analysis.json
│       ├── backup-<ts>.tar.gz
│       └── audit/
│
├── audit/                       # global, append-only, hash-chained JSONL (§7.0.7)
│   ├── *.jsonl
│   └── transcripts/             # subprocess transcripts referenced by transcript_hash
│
├── telemetry/                   # local-only telemetry data (see §12)
│   └── YYYY-WW.ndjson           # weekly rotation
│
└── web/                         # web UI per-repo overrides (themes, dashboards)
    ├── theme/
    └── dashboards/
```

### 6.5 The gitignore-swap mechanism

**Headline capability.** A repo may have a `dev.gitignore` (active during development) and a `prod.gitignore` (active during publish). On `sange publish`, the prod profile is activated transactionally for the duration of the push, then reverted. This is footgun-prone — design carefully:

- **Transactional** (atomic file lock + rename)
- **Reversible** on any failure path including SIGKILL — use a recovery file on disk
- Must **never lose untracked-but-wanted files**
- Must **abort if a concurrent git operation is detected**
- **Dry-run-able:** `sange publish --plan` shows exactly what would change without touching disk
- **Observable:** every swap event logged with before/after hashes
- Transition window must be **brief** — swap, push, restore, never linger
- A separate `sange recover` command restores from the recovery file after a crash

Threat-model this with a red-team pass focused on race conditions, partial failure, and SIGKILL recovery.

#### 6.5.1 Profile Registry — every supported tool / language / framework 🟡 META

The registry is the single source of truth for what languages / frameworks / infrastructure / editors / OS layers have a Sange-managed gitignore profile. Plugins extend it; the core registry is signed and shipped with each Sange release (per ADR-020 kit policy).

**Registry record shape** (each entry is a TOML file under `templates/gitignore-profiles/<category>/<name>.toml`):

```toml
# templates/gitignore-profiles/lang/python.toml
[profile]
name = "lang/python"
display_name = "Python"
version = "1.2.0"
category = "lang"
maintainer = "Simtabi LLC <opensource@simtabi.com>"
upstream_source = "https://github.com/github/gitignore/blob/main/Python.gitignore"

# File-presence signals — Sange auto-detects this profile if any matches
[detect]
required_any = ["pyproject.toml", "setup.py", "requirements.txt", "Pipfile"]
boost_any = [".python-version", "uv.lock", "poetry.lock"]   # raise confidence

# What this profile owns — dev tree vs prod publish
[patterns]
always = [
  "__pycache__/", "*.py[cod]", "*$py.class",
  ".Python", "*.so",
]
dev_only = [
  ".venv/", "venv/", "env/", ".tox/",
  ".ruff_cache/", ".mypy_cache/", ".pytest_cache/",
  "htmlcov/", ".coverage", ".coverage.*",
]
prod_only = [
  # nothing extra in prod for python — the always block is sufficient
]
# `always` = ignored in both dev and prod;
# `dev_only` = ignored in dev tree but **also** in prod (these never ship);
# `prod_only` = ignored only when publishing (useful for fixtures, test data,
#               dev-only credentials examples kept tracked in dev).
# When in doubt, put it in `always`.

[extends]
# Profile composition is explicit; no implicit inheritance.
# (Python doesn't extend anything by default.)
```

**Canonical registry table — v1.0 supported set** (32 profiles). The full TOML files are produced by `tools/generators/profile_registry.py` (T-G-015) from the table below + the per-profile detail files; the responding model fine-tunes the patterns. **No row may be omitted in v1.0.**

| Profile | Category | Auto-detect signal (`required_any`) | What it covers |
|---|---|---|---|
| `_core/secrets` | _core | (always-on, never opt-out without audit override) | `*.pem`, `*.key`, `*.p12`, `id_rsa*`, `.env`, `.env.*`, `credentials*`, `secrets*` |
| `_core/editor-noise` | _core | (always-on) | `.DS_Store`, `Thumbs.db`, `desktop.ini`, `*.swp`, `*~` |
| `lang/python` | lang | `pyproject.toml`, `setup.py`, `requirements.txt`, `Pipfile` | `__pycache__/`, `.venv/`, `*.pyc`, `.ruff_cache/`, `.mypy_cache/`, `.pytest_cache/`, `dist/`, `build/`, `*.egg-info/` |
| `lang/node` | lang | `package.json`, `package-lock.json`, `yarn.lock`, `pnpm-lock.yaml`, `bun.lockb` | `node_modules/`, `.npm/`, `.yarn/`, `.pnp.*`, `dist/`, `coverage/`, `.next/`, `.nuxt/` |
| `lang/php` | lang | `composer.json`, `composer.lock` | `vendor/`, `composer.phar`, `.phpunit.cache`, `.phpunit.result.cache` |
| `lang/go` | lang | `go.mod`, `go.sum` | `bin/`, `pkg/`, `*.exe`, `*.test`, `vendor/` (when `go.mod` lacks `vendor` directive) |
| `lang/rust` | lang | `Cargo.toml`, `Cargo.lock` | `target/`, `**/*.rs.bk`, `Cargo.lock` (in libraries) |
| `lang/ruby` | lang | `Gemfile`, `Gemfile.lock`, `*.gemspec` | `.bundle/`, `vendor/bundle/`, `*.gem`, `.byebug_history`, `.rspec_status`, `coverage/` |
| `lang/java` | lang | `pom.xml`, `build.gradle`, `build.gradle.kts`, `gradlew` | `target/`, `build/`, `*.class`, `*.jar`, `*.war`, `.gradle/` |
| `lang/dotnet` | lang | `*.csproj`, `*.fsproj`, `*.sln`, `global.json` | `bin/`, `obj/`, `*.user`, `*.suo`, `packages/` |
| `lang/elixir` | lang | `mix.exs`, `mix.lock` | `_build/`, `deps/`, `*.beam`, `.elixir_ls/` |
| `lang/swift` | lang | `Package.swift`, `*.xcodeproj/`, `*.xcworkspace/` | `.build/`, `DerivedData/`, `Pods/`, `Carthage/` |
| `lang/kotlin` | lang | `build.gradle.kts`, `settings.gradle.kts` | (covered by `lang/java` + `editor/jetbrains`) |
| `lang/dart` | lang | `pubspec.yaml`, `pubspec.lock` | `.dart_tool/`, `build/`, `.packages` |
| `framework/laravel` | framework | `artisan`, `composer.json` *and* `composer.json` declares `laravel/framework` | `bootstrap/cache/`, `storage/logs/`, `storage/framework/`, `.phpunit.result.cache`, `Homestead.*` (extends `lang/php`) |
| `framework/django` | framework | `manage.py`, `requirements.txt` *and* contains `Django` | `*.log`, `db.sqlite3*`, `staticfiles/`, `media/` (when `MEDIA_ROOT` is project-local), `.env.local` (extends `lang/python`) |
| `framework/rails` | framework | `bin/rails`, `Gemfile` *and* contains `rails` | `tmp/`, `log/`, `*.rbc`, `storage/`, `config/master.key`, `node_modules/` (extends `lang/ruby`) |
| `framework/nextjs` | framework | `next.config.js`, `next.config.mjs`, `next.config.ts` | `.next/`, `out/`, `next-env.d.ts` (extends `lang/node`) |
| `framework/nuxt` | framework | `nuxt.config.js`, `nuxt.config.ts` | `.nuxt/`, `.output/`, `dist/` (extends `lang/node`) |
| `framework/symfony` | framework | `bin/console`, `composer.json` declares `symfony/symfony` | `var/`, `public/bundles/`, `.phpunit.result.cache` (extends `lang/php`) |
| `framework/astro` | framework | `astro.config.mjs`, `astro.config.ts` | `dist/`, `.astro/` (extends `lang/node`) |
| `framework/sveltekit` | framework | `svelte.config.js`, `svelte.config.ts` | `.svelte-kit/`, `build/` (extends `lang/node`) |
| `framework/flutter` | framework | `pubspec.yaml` declares `flutter:` block | `.flutter-plugins`, `.flutter-plugins-dependencies`, `build/`, `*.iml` (extends `lang/dart`) |
| `infra/docker` | infra | `Dockerfile`, `compose.yml`, `docker-compose.yml` | `*.local`, host-mount-only volumes; the image itself uses a `.dockerignore` Sange materializes separately |
| `infra/kubernetes` | infra | `kustomization.yaml`, `helm/Chart.yaml`, `*.k8s.yaml` | `charts/*.tgz`, `kubeconfig*` (always — secret-class) |
| `infra/terraform` | infra | `*.tf`, `*.tfvars` | `.terraform/`, `*.tfstate`, `*.tfstate.backup`, `*.tfplan`, `.terraform.lock.hcl` (lock file: dev tree only if vendored, otherwise track) |
| `infra/ansible` | infra | `ansible.cfg`, `inventory.yml`, `playbook.yml` | `*.retry`, `roles/*.tar.gz`, `ansible.log` |
| `infra/pulumi` | infra | `Pulumi.yaml`, `Pulumi.*.yaml` | `Pulumi.*.yaml.bak`, `node_modules/` (if TS project) |
| `editor/jetbrains` | editor | `.idea/` exists | `.idea/`, `*.iml`, `*.iws`, `out/`, `.idea_modules/` |
| `editor/vscode` | editor | `.vscode/` exists | `.vscode/`, `.history/`, `*.vsix` (project-side; some teams track `settings.json` selectively — handled via `extends.exclude`) |
| `editor/vim` | editor | `.vim/` exists, or `~/.vimrc` references this dir | `*.swp`, `*~`, `Session.vim`, `.netrwhist` |
| `editor/emacs` | editor | `*.el` files, or `.emacs.d/` exists | `*~`, `\#*\#`, `.\#*`, `auto-save-list`, `tramp`, `*_archive` |
| `editor/claude` | editor | `.claude/` exists | `.claude/`, `CLAUDE.local.md` |
| `os/macos` | os | (always — host OS detected) | `.DS_Store`, `.AppleDouble`, `.LSOverride`, `._*`, `.Spotlight-V100`, `.Trashes` |
| `os/windows` | os | (always — host OS detected) | `Thumbs.db`, `Desktop.ini`, `$RECYCLE.BIN/`, `*.lnk`, `*.cab`, `*.msi` |
| `os/linux` | os | (always — host OS detected) | `*~`, `.fuse_hidden*`, `.directory`, `.Trash-*`, `.nfs*` |

**Auto-detection algorithm:**

1. Walk the repo root + the first directory level for the signal files in each profile's `detect.required_any`.
2. Boost confidence by also checking `detect.boost_any`.
3. Always include `_core/secrets`, `_core/editor-noise`, the appropriate `os/*` for the host.
4. For each language match, include its dependent framework profiles (Laravel pulls Python? No. Laravel pulls `lang/php`. Django pulls `lang/python`).
5. For each editor whose dot-folder is present, include that editor profile.
6. For infra signals, include them only when their files exist (don't auto-add `infra/kubernetes` if no manifests).
7. Emit a ranked suggestion list; the user accepts/rejects sequentially (ADR-024).

**Per-project activation** in `.sange/config.toml`:

```toml
[gitignore.dev]
profiles = [
  "_core/secrets",
  "_core/editor-noise",
  "lang/python",
  "framework/django",
  "infra/docker",
  "editor/vscode",
  "os/macos",
]

[gitignore.prod]
profiles = [
  "_core/secrets",
  "lang/python",
  "framework/django",
  "infra/docker",
]
# Note: editor/* and os/* drop out for prod — they're host-side noise that should not
# show up in the published tree. The swap engine (§6.5) handles the transition.

[gitignore.policy]
allow_safety_off = false          # cannot disable _core/secrets without audit override
detect_on_init = true
override_extends = []             # ordered list of pattern strings that override the profiles
```

**Plugin extensions.** A signed plugin (§7.9) may ship additional profiles under `templates/gitignore-profiles/<category>/<plugin-name>.toml`. Plugin profiles must declare their category (no novel categories — only the §10.4 canonical list). The `sange profile list` output marks plugin profiles `provenance: plugin (<name>)`.

#### 🔴 Red-Team Pass for §6.5.1

1. **A new framework lands without a profile** → users hand-roll noisy gitignores. Mitigation: `sange profile detect` reports "no profile matched"; users can file an issue or contribute a profile. The kit's weekly integration matrix (§6.12.2 #7) detects when the github/gitignore upstream adds a new template.
2. **A profile's `prod_only` patterns accidentally include something the user wanted to track in prod**. Mitigation: `sange profile diff` shows the resulting composed `.gitignore` for both scopes; `sange publish --plan` shows what *files* would be excluded against the current working tree.
3. **Auto-detect misfires** (e.g. a `manage.py` exists for a one-off script, not a Django project). Mitigation: detection is *suggestions* — `--apply` is opt-in; the user can reject per-suggestion.
4. **Profile rename breaks user configs** (`framework/laravel` → `framework/laravel-php`). Mitigation: renames are forbidden in minor releases (semver); major releases ship a rename map; `sange profile validate` flags drift.
5. **Plugin profile injects an unsafe pattern** (e.g. excludes `LICENSE`). Mitigation: kit-loader rejects profiles that exclude any path matched by `_core/license.gitignore` (a safety profile listing the never-exclude set: `LICENSE*`, `COPYING`, `NOTICE`, `README*` — auto-loaded for all repos).

---

### 6.5.2 Variant Matrix — multi-dimensional profile composition (Android-Studio-inspired)

**Headline capability.** §6.5's gitignore-swap and §6.5.1's Profile Registry handle the **binary** development-vs-publish boundary. Real projects ship along **multiple orthogonal axes at once**: stage (`dev`/`staging`/`production`), audience (`internal`/`pilot`/`public`/`customer-x`), surface (`cli`/`web`/`mobile`/`embedded`), region (`us`/`eu`/`apac`). Compressing this to `dev | prod` is the foot-gun pattern: a developer publishes the wrong stage's `.env`, a region-specific resource leaks across regions, an internal build ships to public users.

Sange's **Variant Matrix** adopts the proven Android Gradle Plugin pattern — **build types × product flavors × flavor dimensions = build variants**, with **source-set composition** along the matrix — and adapts it to Sange's domain (gitignore-swap, audit, secrets, AI provider selection, bundle naming). Per ADR-032.

#### 6.5.2.1 Axes

| Axis | Type | Default values | Notes |
|---|---|---|---|
| **Stage** (build-type analog) | linear | `dev`, `staging`, `production` | Single value at any time. The publish step targets *one* stage. Controls packaging, signing, audit verbosity, secret resolver, AI provider. User may add `internal`, `pilot`, `hotfix`, etc. |
| **Flavor dimensions** (product-flavor analog) | orthogonal, zero or more | (none by default) | User-declared under `[variants.dimensions.<name>]`. Example: `audience: {internal, public}`, `surface: {cli, web, mobile}`, `region: {us, eu, apac}`. Each dimension is independent; selecting one flavor per dimension yields a variant. |

The **active variant** = `(stage, *flavors)` — a specific selection along every declared axis.

#### 6.5.2.2 Declaration (`.sange/config.toml`)

```toml
[variants]
stages = ["dev", "staging", "production"]
default_stage = "dev"
publish_stage = "production"          # the only stage `sange publish` accepts by default

[variants.dimensions.audience]
flavors = ["internal", "public"]
default = "public"

[variants.dimensions.surface]
flavors = ["cli", "web"]
default = "cli"

# Filters block impossible combinations. Filtered variants disappear from
# `sange variant list` and are refused by `sange variant use`.
[[variants.filter]]
match = { audience = "internal", stage = "production" }
reason = "internal builds never ship to production"

[[variants.filter]]
match = { surface = "embedded", stage = "dev" }
reason = "embedded firmware doesn't have a dev stage; use staging"

# Branch → variant auto-detection (Sange picks this up unless --variant overrides).
[variants.branch_map]
"main" = "production"
"master" = "production"
"develop" = "dev"
"staging/*" = "staging"
"release/*" = "production"
"hotfix/*" = "production"

# Per-axis-value configuration overrides.
[variants.stage.production]
ai_provider = "anthropic"
secrets_resolver = "aws-secrets-manager"
audit_verbosity = "elevated"
signing_required = true

[variants.stage.dev]
ai_provider = "ollama"
secrets_resolver = "dotenv"
audit_verbosity = "normal"
signing_required = false
```

The **default minimal configuration** — a project that omits `[variants]` entirely — gets `stages = ["dev", "production"]` and no flavor dimensions, behaviourally identical to the §6.5 binary axis. Existing repos don't need to change anything; they get the new machinery without configuration cost.

#### 6.5.2.3 Source-set composition (the `.sange/variants/` tree)

The Category convention (§10.4) applies — every fragment lives under a categorised sub-directory:

```
.sange/variants/
├── _core/                          # shared across every variant
│   ├── gitignore
│   ├── ai/
│   ├── prompts/
│   └── audit/
├── stage/
│   ├── dev/
│   │   ├── gitignore               # dev-only ignores layered on top of _core
│   │   ├── ai/
│   │   └── secrets/
│   ├── staging/
│   └── production/
│       ├── gitignore
│       ├── ai/
│       └── secrets/
├── audience/                       # one sub-dir per declared flavor in the audience dim
│   ├── internal/
│   └── public/
├── surface/
│   ├── cli/
│   ├── web/
│   └── mobile/
├── region/                         # if declared
│   ├── us/
│   ├── eu/
│   └── apac/
└── matrix/                         # specific full-variant overrides
    ├── production-public-cli/      # = (stage=production, audience=public, surface=cli)
    └── staging-internal-web/
```

#### 6.5.2.4 Merge priority (Android-style)

When the swap engine composes the effective gitignore (or prompt set, or AI config) for the active variant, fragments merge **highest priority first**:

1. `.sange/variants/matrix/<full-variant>/` — most specific (full Cartesian point)
2. `.sange/variants/stage/<stage>/`
3. `.sange/variants/<dimension>/<flavor>/` — once per declared flavor dimension
4. `.sange/variants/_core/`
5. `templates/gitignore-profiles/` from the §6.5.1 Profile Registry (defaults)

A path that appears in level 1 overrides every lower level. A path that appears only at level 5 is the default for any variant unless higher levels supersede.

For gitignore patterns specifically, the merge is **union** (a pattern ignored at *any* level is ignored in the composed result) — the swap engine errs on the side of *more* ignored. To explicitly re-include a path the lower-level profile excludes, declare a `!path/pattern` line in the variant's gitignore (standard git negation).

#### 6.5.2.5 Suffix mechanisms (the `applicationIdSuffix` / `versionNameSuffix` analog)

Per ADR-032 the §6.9 Release Bundling engine derives bundle suffixes from the active variant deterministically:

| Active variant | Bundle name |
|---|---|
| `(stage=production, audience=public, surface=cli)` (and `publish_stage = production`) | `sange-0.1.0.zip` (no suffix — the canonical production-public-cli artifact) |
| `(stage=staging, audience=public, surface=cli)` | `sange-0.1.0-staging.zip` |
| `(stage=dev, audience=internal, surface=cli)` | `sange-0.1.0-dev.internal.zip` |
| `(stage=production, audience=internal, surface=cli)` | `sange-0.1.0.internal.zip` |
| `(stage=production, audience=public, surface=web)` | `sange-0.1.0-web.zip` |

Rules:
- The `publish_stage` value is the implicit zero — its suffix is empty.
- Non-publish stages contribute their name as a hyphen-prefixed suffix (`-staging`, `-dev`).
- Non-default flavor values contribute their value as a dot-prefixed suffix (`.internal`, `.web`).
- The suffix order is `stage` first, then flavor dimensions in declaration order — deterministic and grep-able.
- The default-minimal configuration (`stages = ["dev", "production"]`, no flavors) reproduces the v0.5 behaviour: `sange-0.1.0.zip` for production, `sange-0.1.0-dev.zip` for dev.

The §6.9 bundle's `provenance.json` records the full variant tuple, so even if a filename is renamed downstream, the SBOM and signature attest to which variant produced the artifact.

#### 6.5.2.6 Stage-locked operations

Sensitive operations refuse to run under the wrong stage unless explicitly overridden:

| Operation | Default-allowed stages | Override flag |
|---|---|---|
| `sange publish` | `production` only | `--stage <stage>` (audit-logged, elevated severity) |
| `sange bundle publish --channel stable` | `production` only | `--allow-stage <stage>` |
| `sange bundle publish --channel beta` | `staging`, `production` | `--allow-stage <stage>` |
| `sange purge execute` | matches the target repo's protected-branch policy | `--cross-stage` (typed-phrase override per §7.0.5) |
| `sange ai preview` | any stage | none — but audit-logs the variant |
| `sange commits push` | any stage | none — but pre-push hooks consult the variant's policy |

Refusals print the active variant + the expected variant + the precise `sange variant use` command to fix the mismatch.

#### 6.5.2.7 Auto-detection (intelligent + dynamic)

`sange variant resolve` computes the active variant in this priority order; `sange variant show` displays the resolved tuple + the layer that supplied each axis:

1. `--variant <stage>[/<dim>=<flavor>...]` CLI flag (per-invocation override).
2. `SANGE_VARIANT=<stage>[/<dim>=<flavor>...]` environment variable.
3. `.sange/.active-variant` file (set by `sange variant use`; gitignored; per-checkout, persists across sessions).
4. **Git branch mapping** — current branch ↔ `[variants.branch_map]` glob entries (default: `main`→`production`, `develop`→`dev`, `staging/*`→`staging`, `release/*`/`hotfix/*`→`production`). Multiple glob matches resolve by longest-prefix-wins.
5. **Heuristic auto-detection** — `sange variant detect` walks signals: CI env vars (`CI=true` + `GITHUB_REF=refs/heads/main` → `production`), Docker tags (`latest` → `production`), the presence of `.env.production`. Reports findings; user accepts/rejects sequentially per ADR-024.
6. The configured `default_stage` + each dimension's `default`.

Each layer's contribution is recorded in the audit log so the operator can answer "where did `stage=staging` come from?" months later.

#### 6.5.2.8 Variant-aware subsystems

The same variant tuple drives:

- **Secret resolution** (§6.10) — `[variants.stage.production.secrets_resolver = "aws-secrets-manager"]`; the dev variant uses `dotenv`; staging may use 1Password. The CLI never asks for a resolver — it asks for the *variant*.
- **AI provider selection** (§6.7) — production may require Claude Opus; dev may default to local Ollama. Cost reports break down by variant.
- **Audit verbosity** — `production` records every state-changing action with elevated metadata; `dev` records only the lifecycle transitions.
- **Hash-chained audit JSONL** (§7.0.7) — every entry carries `variant: {stage, ...flavors}` as a top-level field, so a query like "every action in production/audience=public/surface=cli during the merge freeze" is one grep.
- **Commit-template visibility** — a commit template can declare `applies_to.variants = ["production"]` and the editor surfaces it only when the active variant matches.
- **Hook policy** — pre-commit and pre-push hooks consult the active variant; secret-scanning rules can be stricter in `production` than `dev`.
- **Bundle channels** (§6.9) — `stable` channel only accepts the `production` stage; `beta` accepts `staging`+`production`; `nightly` accepts everything.

#### 6.5.2.9 Doctor's pollution check

`sange doctor --variant` walks both directions:

1. **Variant overflow** — files in `.sange/variants/<axis>/<value>/` that don't match the current variant after composition should not appear in the publish tree. Catches accidental inclusion.
2. **Variant underflow** — the *current* composed gitignore must shadow every path that doesn't belong to the active variant. Catches accidental exclusion.
3. **Stage-locked file presence** — files matching `secrets_resolver`-specific patterns (e.g. `.env.production`) must only exist under the production variant's tree.
4. **Branch ↔ variant drift** — current branch's mapped variant (per `[variants.branch_map]`) compared to the active variant; mismatch is a warning (not a refusal — sometimes intentional).
5. **Suffix collision** — two variants resolving to the same bundle suffix is a configuration error; refused at variant-resolve time.

`sange publish --plan` runs `doctor --variant` implicitly and refuses to proceed on any red.

#### 6.5.2.10 Ambient awareness in CLI / TUI / Web UI

Every Sange surface renders the active variant prominently:

- **CLI prompt prefix** — `[sange • production / audience=public / surface=cli]` precedes every interactive line. The §7.0.2 `TerminalProfile` switches glyph: emoji-capable terminals get colored badges; ASCII terminals get `[sange | production | audience=public | surface=cli]`.
- **TUI status bar** — Textual app's status line is always-visible variant tuple.
- **Web UI** — variant chip in the global header, color-coded by stage (red = production, yellow = staging, green = dev). The Push & Publish Approval module (§8.2.4) surfaces the variant prominently above the diff.
- **Audit-log entries** — variant field on every JSONL row.
- **Bundle filenames** — suffix per §6.5.2.5.
- **`sange status` output** — variant section above the git status.

The principle: at no point should an operator have to guess which variant is active. If they do, that's a UX defect.

#### 6.5.2.11 Plugin extension surface

Per ADR-020 (signed plugins), third-party plugins may:

- **Declare additional flavor dimensions** — e.g. a `tenant: {customer-a, customer-b, …}` dimension for SaaS multi-tenancy.
- **Declare per-variant configuration schemas** — a `compliance/hipaa` plugin can require `[variants.<dim>.<flavor>.compliance.hipaa]` config.
- **Provide variant-specific kit fragments** — e.g. a `region/eu/cookie-banner` kit fragment that materializes only when `region=eu`.

Plugin-declared dimensions are merged into the canonical registry at plugin-load time; the plugin manifest's signature is verified per ADR-020.

#### 6.5.2.12 Default kit examples (`templates/variants/`)

The §6.12 Premade Operations Kit ships canonical `.sange/variants/` skeletons:

| Kit fragment | Shape |
|---|---|
| `templates/variants/_core/binary` | `stages = ["dev", "production"]`, no flavor dimensions — the v0.5 binary axis, preserved as default. |
| `templates/variants/_core/three-stage` | `stages = ["dev", "staging", "production"]`, no flavor dimensions — the default for any project that opts in. |
| `templates/variants/_core/mobile-2x3` | `stages = ["debug", "release"]`, `audience: {free, paid}`, `tier: {standard, premium}` — Android-style mobile project. |
| `templates/variants/_core/saas-multi-tenant` | `stages = ["dev", "staging", "production"]`, `tenant: {customer-a, customer-b, customer-c}` — multi-tenant SaaS. |
| `templates/variants/_core/regulated-rollout` | `stages = ["dev", "staging", "pilot", "production"]`, `region: {us, eu, apac}`, `audience: {internal, public}` — regulated-region phased rollout. |

`sange variant scaffold <kit-fragment>` materializes a skeleton into the target repo's `.sange/variants/`.

#### 🔴 Red-Team Pass for §6.5.2

1. **Variant complexity inflates the foot-gun rather than reducing it** — a misconfigured filter could lock a user out of production deploys. Mitigation: `sange variant verify --strict` checks that every required stage is reachable from at least one (stage, *flavors) tuple; `sange doctor` flags unreachable stages.
2. **Branch-map auto-detection misfires** — a `feature/big-rewrite` branch lacks a map entry and defaults to `dev`, but the engineer thought it was `staging`. Mitigation: `sange variant resolve` *always* prints the resolution layer ("got `stage=dev` from `default_stage` because no branch-map entry matched"); refuses to publish without an explicit `--variant` or matching map entry.
3. **Suffix collision** — two variants compute the same bundle name. Mitigation: the resolution function is bijective by construction (declared dimensions × stages produces distinct tuples → distinct suffix strings); `sange variant verify` enumerates the matrix and flags any non-injective mapping.
4. **Cross-variant secret leak** — a `production` secret cached in memory at switch time leaks into a `dev` operation. Mitigation: variant switch invalidates the in-process secret cache; secrets are *resolved at use* (lazy), not at switch-time; the resolver is re-instantiated per variant.
5. **Plugin-declared dimension collides with built-in** — a malicious plugin names its dimension `stage`, overriding the linear axis. Mitigation: built-in axis names are reserved and refused at plugin-load; namespacing rules (`plugin-name/dimension-name`) are documented.
6. **Audit-log variant field becomes high-cardinality and floods the chain** — a project with `tenant: 10,000-customers` produces JSONL entries with high-arity variant fields. Mitigation: variant tuple is a fixed-shape object (one slot per declared dimension); cardinality is bounded by the declared matrix size, not the total commits.
7. **Operator switches variant mid-purge** — `sange purge execute` running, `sange variant use dev` invoked, causes mid-execution state confusion. Mitigation: `sange variant use` refuses while any §6.11 purge state machine is in `executing`/`verified` (not yet `completed`); `sange doctor` lists in-flight ops.
8. **Default-minimal config users don't know about variants and miss safety** — a user with `stages = ["dev", "production"]` and no flavor dims still benefits from stage-locked publish, but doesn't know the term "variant." Mitigation: `sange status` shows the variant tuple by default; `sange doctor` calls out single-stage configs and offers `sange variant scaffold _core/three-stage` to upgrade.

---

### 6.6 Container & top-level Makefile lifecycle

- Multi-stage Dockerfile, pinned base image by digest
- Non-root user, health-check baked in
- **Multi-arch images** (`linux/amd64` + `linux/arm64` from v1.0; `linux/arm/v7` from v2.0 — per ADR-033) built via `docker buildx build --platform linux/amd64,linux/arm64`. The resulting OCI manifest list is one tag, multiple arch manifests; `docker pull` selects the host's arch automatically. Apple Silicon, Hetzner Ampere ARM VPS, AWS Graviton, Raspberry Pi 4/5 all run natively without QEMU emulation.
- **Base-image pinning by digest** must reference a **multi-arch manifest** (`python:3.12-slim@sha256:...`, `php:8.4-fpm-alpine@sha256:...`, `caddy:2-alpine@sha256:...`). Upstreams that ship amd64-only are excluded by policy.
- **Multi-arch CI matrix** — `.github/workflows/ci.yml` runs tests on **both** `ubuntu-24.04` (amd64) and `ubuntu-24.04-arm` (arm64, GA 2024-Q4). Release builds use native ARM runners — no QEMU. A test whose result depends on arch is a defect.
- **Linux packages installed inside the container** (Python 3.12+, PHP 8.4, `git-filter-repo`, `gitleaks`, `trufflehog`, `cloudflared`, `cosign`) must be installable on every supported arch. When an upstream tool ships only amd64 binaries, we install from source on arm (slower bootstrap but functional); the affected tool is flagged in the §6.11 purge subsystem + the §6.12 kit's `bootstrap/` scripts.
- `docker-compose.yml` for local dev with mounted repo and SSH-agent forwarding — works identically on every arch.
- The Sange-shipped top-level `Makefile` drives container lifecycle from outside the container; inside, the `sange` CLI is canonical.
- **A user's per-package generated Makefile is gitignored by default** — see §10
- **`sange doctor --container`** reports `uname -m` of the host + `dpkg --print-architecture` (or equivalent) of the container and warns on mismatch (= QEMU emulation detected). Warning persists in `sange status` until resolved.
- Container VCS secret management — see §6.10

### 6.7 AI subsystem

- Provider-agnostic `AIProvider` Protocol with implementations for: Anthropic, OpenAI, local Ollama, Google Gemini, Azure OpenAI, AWS Bedrock, and **MCP servers** (Sange acts as both an MCP client and an MCP server — see terminology note below)
- Streaming-first
- Every prompt is templated, versioned, stored in `.sange/prompts/` — auditable
- Untrusted input (diffs, foreign commit messages, file contents) wrapped in clearly delimited `<untrusted_input>` blocks; system prompt explicitly tells the model to treat them as data, not instructions
- A **content firewall** scans LLM input and output for known injection patterns and prompt-leak markers
- A **redaction layer** scrubs diffs for high-entropy strings, known secret patterns, and configurable PII patterns *before* anything leaves the machine
- Output that would modify the repo requires explicit user confirmation by default
- **MCP support** — Sange is a first-class MCP citizen with both protocol roles. (MCP terminology, per the Model Context Protocol specification: an **MCP server** exposes tools/resources/prompts; an **MCP client** consumes them; an **MCP host** is the LLM application — e.g. Claude Desktop — that contains the client. Sange is *not* an MCP host; it is an MCP server and an MCP client.)
  - **As MCP client:** Sange connects to user-configured MCP servers for additional context (Jira, Linear, GitHub MCP, internal docs, etc.)
  - **As MCP server:** Sange exposes its own capabilities (commit lifecycle, branch ops, release bundling, scheduler, etc.) over MCP so MCP hosts (Claude Desktop, Claude Code, Cursor, Continue.dev) can drive Sange operations with full audit and security gates intact
  - External MCP servers are allowlisted, capability-reviewed, and revocable per-project; transport selection (stdio vs. HTTP+SSE vs. streamable HTTP) is configurable per server with secure defaults
  - The Sange-exposed MCP server is opt-in per-repo, authenticated, and rate-limited; every tool invocation is audit-logged like any CLI invocation

### 6.7.1 Prompt Enhancer (model-agnostic)

A first-class subsystem that **transforms raw user input into well-structured prompts** before any LLM call. The enhancer is the only path by which user input reaches an AI provider.

**Why:** users write "fix the bug" or "summarize this"; raw input produces mediocre output. The enhancer enriches the request with:

- Task-appropriate template (commit-msg, PR-description, changelog, code-review, diff-summary, branch-name, release-notes, etc.)
- Repo context (recent commits, conventions, branch info)
- Few-shot examples drawn from the repo's own history
- Output schema (JSON shape, Conventional Commits structure, etc.)
- Model-specific formatting (Claude prefers XML delimiters; GPT prefers JSON; local models often prefer plain markdown)
- Length and tone guidance derived from project conventions

**Architecture:**

```
User input → Enhancer (templates + context + model-tuning) → Provider → Response → Validator → User
                ↑                                                              ↓
            Prompt versioning                                          Red-team check
            .sange/prompts/
```

**Properties:**

- Model-agnostic — works with Claude, GPT, Gemini, local Ollama, MCP-routed models, with adapter-specific tuning
- Versioned and auditable — every enhanced prompt is logged with `prompt_version`, `template_id`, `model`, `provider`
- Inspectable — `sange ai preview --task commit` shows the exact prompt that would be sent without sending it
- Configurable — users can override or extend templates per-project
- Composable — templates can include other templates; circular includes detected and refused
- Schema-enforcing — when the response shape matters (JSON output for commit lifecycle, see §6.8), the enhancer attaches schema and the validator enforces it; failed validations trigger a single retry then surface to the user
- Plugin point — third-party Sange plugins can register new task templates and model adapters

A dedicated ADR (`ADR-005`) documents the prompt-enhancer design.

### 6.8 Commit Message Lifecycle (JSON-based workflow)

**Headline feature.** Sange generates commit messages as **editable JSON files** with an explicit lifecycle state machine. Users review and approve before any commit happens; pushes consume only approved messages.

#### 6.8.1 File location and naming

```
.sange/commits/
├── 0001-feat-auth-add-passkey.json
├── 0002-fix-race-gitignore-swap.json
├── 0003-chore-bump-deps.json
└── archive/
    └── 2026-05/
        └── 0000-...
```

- Files are named `NNNN-<type>-<scope>-<short-subject>.json` (slugified, max 80 chars)
- `NNNN` is a zero-padded monotonic counter per repo
- Archive subdirectory contains older entries auto-moved after configurable retention (default 90 days)
- Counter is durable across crashes (stored in `.sange/commits/.counter`)

#### 6.8.2 Lifecycle state machine

```
                            ┌──────── reopen ────────┐
                            ▼                        │
   [draft] ─── submit ──→ [pending_review] ─ approve ─→ [approved]
      │                         │                          │
      │                    reject│                    commit│
      ▼                         ▼                          ▼
   [discarded]            [rejected]                   [committed]
                                                            │
                                                       push │
                                                            ▼
                                                        [pushed]
                                                            │
                                                    archive │
                                                            ▼
                                                       [archived]
```

States:
- **draft** — just generated (by AI or manual), not yet submitted (default)
- **pending_review** — submitted for review (CLI flag, web UI, or another reviewer)
- **approved** — approved, ready to commit
- **rejected** — explicitly rejected with reason; will not be used
- **committed** — git commit performed, awaiting push
- **pushed** — pushed to remote, lifecycle complete
- **archived** — preserved for audit; auto-archived after retention period
- **discarded** — drafts the user abandons; soft-deleted

Transitions are strict and forward-only except via explicit `sange commits reopen <id>`. Every transition is logged in the audit log with actor, timestamp, and reason.

#### 6.8.3 JSON schema (every commit file conforms)

```json
{
  "schema_version": 1,
  "id": "01HXYZ...",
  "counter": 42,
  "status": "draft",
  "created_at": "2026-05-13T14:23:15Z",
  "updated_at": "2026-05-13T14:23:15Z",
  "repo": {
    "path": "/Users/.../my-project",
    "remote": "git@github.com:org/repo.git",
    "branch": "feature/auth"
  },
  "message": {
    "type": "feat",
    "scope": "auth",
    "subject": "add passkey support for web UI login",
    "body": "Adds WebAuthn-based passkey enrollment...",
    "footer": "Refs: JIRA-1234",
    "breaking_change": false,
    "co_authors": [],
    "references": ["JIRA-1234"],
    "rendered": "feat(auth): add passkey support for web UI login\n\nAdds WebAuthn-based...\n\nRefs: JIRA-1234"
  },
  "diff": {
    "files_changed": 5,
    "insertions": 142,
    "deletions": 8,
    "hash": "sha256:..."
  },
  "ai": {
    "generated": true,
    "provider": "anthropic",
    "model": "claude-opus-4-7",
    "prompt_version": "commit-msg-v3",
    "template_id": "conventional-with-context",
    "cost_estimate_usd": 0.0042,
    "tokens_in": 1842,
    "tokens_out": 156,
    "enhancer_version": "1.0"
  },
  "approvals": [
    {"actor": "user@host", "at": "2026-05-13T14:25:01Z", "via": "web"}
  ],
  "rejections": [],
  "template_used": "conventional",
  "tags": [],
  "metadata": {}
}
```

#### 6.8.4 CLI surface

- `sange commits list [--status STATUS]` — list commit JSONs in this repo
- `sange commits show <id>` — print a commit JSON
- `sange commits new` — generate a new draft (interactive)
- `sange commits ai` — AI-generate a draft from current staged changes
- `sange commits edit <id>` — open in `$EDITOR`
- `sange commits submit <id>` — `draft` → `pending_review`
- `sange commits approve <id>` — `pending_review` → `approved`
- `sange commits reject <id> --reason "…"` — → `rejected`
- `sange commits commit [<id>...]` — perform the git commit; → `committed`. If no IDs given, all `approved` are processed in counter order.
- `sange commits push [<id>...]` — push the commits; → `pushed`
- `sange commits archive --before YYYY-MM-DD`
- `sange commits reopen <id>` — back to `draft`

`sange commit` (the singular form, retained from prior versions) is an alias for the most common path: stage → ai → approve → commit → push, with confirmation gates between each step. Power users use the granular `sange commits …` subcommands. Web UI uses the lifecycle directly.

#### 6.8.5 Default templates and preset library

The existing v1 codebase has `DEFAULT_GIT_COMMIT_MESSAGES` at `sange-v1/configs/config.sh:25–128` — a flat Bash array of **104 emoji-prefixed strings** with mixed quality (some are Conventional-Commits-aligned `feat:` / `fix:` / `chore:`, many are ad-hoc operational nouns like `email: notify team`, `dns: add new CNAME`, `cron: send report`). v2 deletes the array entirely with no replacement.

The task is **not** "expand to 50+" (the array already exceeds 100). The task is **curate, dedupe, taxonomize, normalize**:

1. **Document the existing 104 entries verbatim** in Appendix G.
2. **Dedupe** — multiple entries cover the same intent with cosmetic emoji variation (e.g. several `chore: update …` rows); collapse to canonical forms.
3. **Filter** — remove entries that are not commit messages but operational events (`📤 ftp: upload to legacy server`, `📤 cron: send report`, `📈 seo: update meta tags`) unless they fit a clear commit-message use case.
4. **Re-taxonomize** under Conventional Commits 1.0.0 types and document each preset's mapping.
5. **Normalize structure** — every preset is an object with `id`, `category`, `type`, `scope`, `template` (with `${placeholders}`), `description`, `applies_to` (optional matcher — file patterns, branch patterns), `requires_body` (bool), `breaking_change` (bool), `tags`, `aliases` (legacy v1 strings that map to this preset for migration).
6. **Output** a library of **≥50 well-structured presets** stored in `.sange/commit-templates/default.toml` (machine-authored, generated from a source-of-truth Python module). Users add to `~/.sange/commit-templates/user.toml` and `${repo}/.sange/commit-templates/user/*.toml`. Provide a **v1-to-v3 migration mapping table** in Appendix G so the existing 104 strings remain selectable (via `aliases`) for users upgrading from v1.

Categories to cover (combine Conventional Commits with the highest-signal entries from v1's array):

- Conventional Commits types: feat, fix, docs, style, refactor, perf, test, build, ci, chore, revert
- Common scopes per type: feat(api), feat(ui), feat(auth), feat(db), feat(infra), fix(security), fix(perf), fix(race), etc.
- Multi-line templates with body and footer placeholders
- Breaking-change templates with `!` suffix and `BREAKING CHANGE:` footer
- Revert templates with proper `revert:` prefix
- Hotfix templates
- Release templates (semver-aware)
- Cherry-pick templates
- Merge-commit templates
- Squash-merge templates
- WIP / save-point templates (with optional `--no-verify` warning)
- Initial-commit templates
- License / copyright addition templates
- Dependency bump templates (with from/to versions)
- Security-fix templates with CVE reference field
- Documentation-only templates
- Refactor-only templates
- Test-only templates
- Build/tooling templates
- CI/CD pipeline templates

(Preset object structure already specified above in the curation steps.)

#### 6.8.6 Storage philosophy

Commit JSON files **may be tracked or gitignored** based on per-repo policy. Default: **gitignored** (commit messages are a workflow artifact, not part of the source). Teams who want shared review queues can opt-in to tracking with `track_commits = true` in `.sange/config.toml` — in which case sensitive fields (AI cost, model name, internal references) are redacted from the tracked form via a `.sange/commits/.public-schema.json` filter.

#### 🔴 Red-Team Pass for §6.8

1. What if two parallel `sange commits commit` invocations race on the same approved entry? File lock on the JSON during transition; CAS update on the status field.
2. What if a user manually edits a JSON file's `status` to bypass review? File integrity hash in a sibling `.sange/commits/.audit/` directory; integrity check before commit; warning + audit-log entry on mismatch.
3. What if the AI hallucinates a JIRA reference into the `references` field? Validate references against configured trackers if a token is available; warn-only otherwise.
4. What if a commit JSON contains injected instructions designed to manipulate the next AI invocation? `references` and `body` fields are *data*, never reused as prompt content unless explicitly templated; even then, wrapped in `<untrusted_input>` blocks.

### 6.9 Release Bundling

**New capability.** A first-class flow for bundling a repo, package, or sub-project for production release — public or private.

#### 6.9.1 Concepts

- **Bundle** — a versioned, signed, immutable artifact representing a release of a project, package, or monorepo sub-project
- **Manifest** — declarative description of what goes into the bundle (`.sange/bundles/manifests/<name>.toml`)
- **Visibility** — `public` (intended for release to a public registry / GitHub Releases / etc.) or `private` (internal distribution, encrypted-at-rest, ACL-controlled)
- **Channel** — `stable`, `beta`, `nightly`, custom — affects naming and tagging

#### 6.9.2 Lifecycle

```
[plan] → [build] → [sign] → [verify] → [publish] → [verify-published] → [released]
                                            │
                                            └──→ [held] (manual review gate)
```

- `sange bundle plan <name>` — dry-run, show what would be included
- `sange bundle build <name>` — produce artifacts in `.sange/bundles/artifacts/<name>-<version>/`
- `sange bundle sign <name>` — sigstore / cosign / GPG signing per config
- `sange bundle verify <name>` — re-verify before publish
- `sange bundle publish <name> [--channel beta]` — push to configured destination
- `sange bundle promote <name> --from beta --to stable`
- `sange bundle rollback <name>` — only for channels that support it

#### 6.9.3 Supported destinations (v1)

- GitHub Releases (public, private)
- GitLab Releases (public, private)
- Generic Package Registry (GitLab, GitHub Packages)
- S3-compatible object storage (private)
- OCI artifact registry (any OCI-compliant registry)
- Filesystem (for air-gapped workflows)

#### 6.9.4 What's in a bundle

- Source tree at the bundle commit (filtered by `prod.gitignore` semantics)
- Pre-built artifacts (if any) — binaries, container images, docs
- SBOM (CycloneDX or SPDX)
- Provenance attestation (SLSA)
- Signatures (sigstore + GPG)
- Changelog entry for this release
- Release notes (AI-assisted, human-approved)
- Verification script (`verify.sh` / `verify.ps1`)

#### 6.9.5 Public vs. private

- **Public** bundles: SBOM and signatures published alongside; consumers can verify with `sange bundle verify-remote <url>`
- **Private** bundles: encrypted-at-rest with per-recipient keys; ACL enforced at the registry; access events audit-logged

A red-team pass for §6.9 must address: signature substitution, downgrade attacks (e.g., a beta channel being served when stable was requested), and bundle-poisoning via compromised CI.

### 6.10 Docker Container — VCS Secret Management

**New capability.** When Sange runs inside its container (CI runners, sandboxed dev environments, ephemeral devboxes), it needs access to VCS credentials (SSH keys, HTTPS tokens, GPG signing keys) **without baking them into the image** and without leaking them to logs, layers, or the container's filesystem.

#### 6.10.1 Mechanisms (in order of preference)

1. **SSH agent forwarding** — host's `SSH_AUTH_SOCK` mounted into the container at runtime. Default for local dev.
2. **Docker secrets / BuildKit secrets** — for `docker compose` and CI environments. Mounted as in-memory tmpfs files, never in image layers.
3. **OS keychain pass-through** — via a small Sange daemon helper that exposes scoped credentials over a Unix socket bind-mount.
4. **External secret manager** — Sange container reads tokens from Vault / AWS Secrets Manager / 1Password Connect at startup; never persists them.
5. **Encrypted file mount** — age- or GPG-encrypted secrets file mounted read-only; decryption key passed via short-lived environment variable that is unset after read.

#### 6.10.2 Management surface

- `sange secrets list` — show configured secret entries (metadata only, never values)
- `sange secrets add <name> --provider <provider>` — register a new secret source
- `sange secrets rotate <name>` — rotate where the provider supports it
- `sange secrets test <name>` — non-destructive check that the secret resolves
- `sange secrets revoke <name>` — remove access
- All of the above are exposed in the Web UI's **Secret & Token Management** module (§8.2.10) — values are never rendered

#### 6.10.3 Security controls

- Container is non-root; secret-mount paths owned by the sange user with `0400` perms
- No environment variables containing secret values past startup (early-zeroed)
- `sange doctor --container` audits the running container for leaked secrets (env vars, world-readable mounts, secrets in process memory if `ptrace` allowed)
- Secrets never appear in logs, audit entries, or telemetry
- Forensic-safe: any `sange` subprocess that handles secrets uses `mlock` to prevent swap

#### 🔴 Red-Team Pass for §6.10

1. SSH agent socket hijack from a sibling container on the same host
2. BuildKit secret leakage via cache layers if `--mount=type=secret` is misused
3. A malicious Sange plugin reading the secret mount paths
4. ENV vars surviving in the process environment after a fork
5. Core dumps including secret memory pages (mitigated by `mlock` + `RLIMIT_CORE=0`)

### 6.11 VCS History Purge subsystem

**Headline capability.** Sange wraps the safe, current-practice procedure for *removing files (and their content traces) from VCS history across the supported VCSes*. This is the highest-blast-radius operation the tool performs — it rewrites history, force-pushes, expires reflogs, prunes unreachable objects, and may invalidate every existing clone of the repository. The subsystem exists because the operation is too dangerous to expect engineers to assemble by hand from blog posts.

**Procedural source of truth.** A long-form playbook (covering Git via `git filter-repo` and BFG, SVN via `svnadmin dump | svndumpfilter`, Mercurial via `hg convert --filemap`, Perforce via `p4 obliterate`, plus detection via `gitleaks` + `trufflehog`) is supplied by the user as the input from which the responding model must produce **`docs/tools/purge.md`** — refactored to use Sange's nomenclature, lifecycle events, audit format, and CLI surface specified below. The architecture document records only the **specification**; the procedural reference lives in `docs/tools/purge.md`.

#### 6.11.1 Scope

| VCS | v0.5 (preview / detection only) | v1.0 (full destructive ops) |
|---|---|---|
| Git | `gitleaks` + `trufflehog` scan, `--analyze`, `--dry-run`, backup mirror, audit log | `git filter-repo` (default), BFG (when path-blind matching is enough), reflog expire, aggressive GC, force-push with mirror push, server-side housekeeping prompts |
| SVN | dump + filter analysis, audit log | `svnadmin dump → svndumpfilter exclude → svnadmin load → atomic swap`, with branch/tag copy graph handling |
| Mercurial | filemap analysis | `hg convert --filemap` (file removal) and `hg strip` (changeset removal) |
| Perforce | depot-relative impact analysis | `p4 obliterate -y` (admin-only) |

Detection (scanners) is **always available** including in v0.1; destructive operations are gated to v1.0 except SVN/Hg which land in v2.0 and Perforce which lands in v3.0.

#### 6.11.2 Lifecycle state machine

```
                                    ┌── abort ──┐
                                    ▼           │
[planned] ─ preflight ─→ [preflight_passed] ─ analyze ─→ [analyzed] ─ preview ─→
[previewed] ─ confirm (typed phrase) ─→ [confirmed] ─ execute ─→ [executing] ─→
[verified] ─ push (typed phrase) ─→ [completed]
                              │                                 │
                              └─── verification_failed ─────────┴── rolled_back
```

States:
- `planned` — operation declared, not yet validated
- `preflight_passed` — every gate in §6.11.4 returned green
- `analyzed` — `--analyze` / dry-run run; affected commit / blob / ref counts known
- `previewed` — user viewed the impact diff (TUI tree view + summary panel)
- `confirmed` — user typed the explicit phrase (see §7.0 typed-phrase convention)
- `executing` — rewrite in progress; subprocess output streamed live to terminal and audit log
- `verified` — post-rewrite verification (§6.11.5) passes
- `completed` — pushed to remote, server-side housekeeping prompts issued, collaborator-notification template generated
- `aborted` — any failed gate before execution; reversible without side effects
- `rolled_back` — verification or push failed; backup restored

Transitions are forward-only; the only re-entry path is `rolled_back → planned` for a retry.

#### 6.11.3 Cross-cutting invariants (ADR-018)

- **Synchronous, interactive, CLI/TUI-initiated only.** Never queued, never scheduled, never run by `sanged` on a timer.
- **All-or-nothing.** No partial / phased / canary rollout. A failure mid-rewrite triggers `rolled_back`.
- **No batch mode without explicit precondition flags.** `--batch` requires `--acknowledge-secrets-rotated --fresh-mirror-confirmed --backup-verified --collaborators-notified`, all four set. Audit entry records the flags used.
- **Web UI cannot execute the destructive transition.** The web UI module (§8.2.21) can plan, analyze, preview, queue, and notify; it cannot issue the typed-phrase confirmation. The engineer must run `sange purge execute <plan-id>` at the terminal.
- **Operator must hold a Sange role with `purge` capability.** Other roles can plan and review.

#### 6.11.4 Pre-flight gates (every one must return green; `--batch` requires explicit-flag equivalents)

1. **Secrets-rotated acknowledgement.** A typed phrase the user enters confirming that if any file being purged contained credentials, those credentials have already been rotated upstream. Audit-logged.
2. **Fresh mirror clone.** Sange refuses to run against the user's working repo. Auto-creates a mirror under `.sange/purge/<ts>/work.git/` from the configured remote unless `--mirror <path>` is supplied. The mirror is verified to be untouched (no extra refs, no local-only objects, clean `for-each-ref` snapshot).
3. **Backup verified.** A tarball mirror snapshot is created under `.sange/purge/<ts>/backup-<ts>.tar.gz` + a verification hash (`sha256` of the tarball + `git fsck --full` against the mirror). Sange refuses to proceed if either check fails. Backup also pushed to an optional off-host location (S3, age-encrypted file mount, etc.) if configured.
4. **Branch protection / push-protection inventory.** Sange queries the platform API (GitHub/GitLab/Bitbucket/Gitea/Forgejo) for the repo's branch protections and emits a `restore-protections.json` so they can be re-asserted post-purge. Refuses to proceed if it cannot read them (user can `--skip-protection-snapshot` only in `--batch` with an explicit waiver).
5. **CI pause attempted.** Sange disables (or asks the user to disable) the repo's CI on the target ref(s) for the duration of the purge window. Records the previous state for restoration.
6. **Collaborator-notification template generated.** A pre-filled draft message (covering "force-push at <UTC>", "re-clone instructions", "open PRs will close") is staged for the user to send via Slack / email / webhook. `--batch` requires `--notification-sent <reference>` with a delivery id.
7. **Affected-ref budget.** Sange compares the analyzed set against a configured budget (e.g. "≤ 500 changed refs"); over-budget purges require an additional typed-phrase override and a CC to the security inbox.
8. **Scanner pre-run.** A `gitleaks` + `trufflehog` scan runs against the *current* repo and the *post-rewrite* mirror; the rewrite is rejected if the post-rewrite scan finds *more* findings of the same kind than the pre-rewrite scan (regression detection).

Each gate emits a structured audit event; a single red gate aborts the transition with a precise remediation message.

#### 6.11.5 Verification (post-rewrite, before push)

The mirror is verified by independent checks. Push is refused if any return red:

| Check | Implementation |
|---|---|
| Path-still-present search | `git rev-list --all --objects` filtered through the path list — must be empty |
| String-still-present search | `git log --all -p -S'<token>'` for each token in the redaction list — must produce no output |
| Scanner regression | `gitleaks git` + `trufflehog git --results=verified,unknown` against the mirror — counts ≤ pre-rewrite |
| Packfile shrinkage | Object directory size decreased by at least the expected delta (sanity check) |
| `fsck` integrity | `git fsck --full --strict` clean (with `--unreachable --no-reflogs` for completeness) |
| LFS pointer integrity | If LFS in use, orphaned objects enumerated and recorded (for the platform support ticket) |
| Tag signature inventory | All signed tags listed with their *old* signatures; the user is warned re-signing is required post-push |
| `--analyze` diff | Compare pre-rewrite `--analyze` output to post-rewrite; record path-deleted-sizes delta |

#### 6.11.6 Audit trail (hash-chained, per-repo + global)

Every state transition produces a JSONL line written to **two** locations:

```
${repo}/.sange/audit/purge-<utc-iso>-<nonce>.jsonl    # per-repo, gitignored by default
~/.sange/audit/<repo-slug>/purge-<utc-iso>-<nonce>.jsonl   # global mirror, off-repo
```

Schema (every entry):

```json
{
  "schema_version": 1,
  "event_id": "purge-2026-05-13T14-32-18Z-abc123",
  "timestamp": "2026-05-13T14:32:18Z",
  "operator": "user@host",
  "operation": "purge",
  "vcs": "git",
  "repo": {"path": "...", "remote": "...", "slug": "..."},
  "state_from": "previewed",
  "state_to": "confirmed",
  "filters": {"paths": [...], "globs": [...], "replace_text_hashes": [...]},
  "dry_run": false,
  "batch": false,
  "counts": {"affected_commits": 47, "affected_refs": 12, "deleted_objects": 1203, "size_delta_bytes": -85234112},
  "scanner_results": {"gitleaks": 0, "trufflehog": 0},
  "tool": {"name": "git filter-repo", "version": "2.47.0"},
  "checks": [{"name": "fresh_mirror", "status": "green"}, ...],
  "prev_hash": "<sha256 of previous entry>",
  "entry_hash": "<sha256 of this entry without entry_hash>"
}
```

Tampering is detectable: replay the chain and any mismatch flags the line. Audit files are append-only; sange refuses to modify them and warns if file modification times shift retroactively.

#### 6.11.7 Prevention & detection coupling

The purge subsystem and the prevention layer (§7.4, §16) share a configuration:

- Patterns used by `gitleaks` + `trufflehog` are pinned by Sange and updated via `sange update-patterns`.
- The CI-side scan and the pre-commit-hook scan use the *same* pattern set.
- A successful purge does **not** stop the secret-scanning pre-commit hooks from being installed; on the contrary, `sange purge --completed` triggers a `sange init --upgrade-hooks` to harden prevention.
- The first-time installation of pre-commit + pre-push hooks is opt-in but loudly suggested by `sange doctor`.

#### 6.11.8 Refactor of the user-supplied playbook into `docs/tools/purge.md`

The user supplied a long-form playbook for this subsystem. The responding model must:

1. Use the playbook as **procedural source material**, not as the final document.
2. Refactor it to use **Sange-native commands** wherever a manual `git` / `svnadmin` invocation appears. For example: `git clone --mirror <url> work.git` becomes `sange purge mirror <url>`; `git filter-repo --analyze` becomes `sange purge analyze`; the manual force-push becomes `sange purge push <plan-id>`.
3. Replace ad-hoc bash audit logging with the §6.11.6 schema.
4. Replace the "Pre-flight Checklist" table with the §6.11.4 gate list, gate-by-gate, with the Sange flag that enforces each.
5. Replace the standalone `vcs-purge.py` script described in §14 of the playbook with the `sange purge` command surface in §7.10.
6. Keep the "Hard Truths" preamble verbatim — it is correct, well-written, and worth surfacing un-edited.
7. Keep the cross-VCS sections (Git / SVN / Mercurial / Perforce) but order them by *risk graduation*: detection → analysis → dry-run → execute → verify → push → housekeeping → coordinate.
8. Keep the *Common Gotchas* list verbatim — it is institutional knowledge.
9. Append a new section "Sange-specific notes" that lists how the gates are enforced, how audit logs are inspected (`sange purge audit show <event-id>`), how to recover from a failed `verified → completed` transition (`sange purge rollback <plan-id>`), and how the Web UI module (§8.2.21) integrates.
10. Cite sources as in the original playbook (Git project docs, GitHub Docs, GitGuardian, Microsoft TechCommunity, etc.), preserving the source list at the bottom.

#### 🔴 Red-Team Pass for §6.11

1. **Backup tarball compromised** — operator restores from a tarball that itself contains the data. Mitigation: backup verification hash + dual-location backups + scanner pre-run against the backup.
2. **Race during execution** — concurrent push by another collaborator lands between `analyzed` and `executing`. Mitigation: lock the upstream via the platform API (where possible) for the duration; otherwise re-`--analyze` and re-confirm before executing; abort if upstream HEAD moved.
3. **Operator skips the typed phrase via TTY scripting** — `expect`/`tmux` automating the gate. Mitigation: typed phrase includes a fresh per-session nonce (e.g. `PURGE_<UTC-date>_<random-4-byte-hex>`), so a script cannot pre-prepare it.
4. **Audit log redirected to `/dev/null`** — operator sets `--audit-log /dev/null`. Mitigation: `sange purge` refuses to run without a writable audit destination, and the global audit-log is non-overridable except for path (not destination).
5. **Refs orphaned, not removed** — `git update-ref -d` for some refs is missed. Mitigation: post-rewrite `for-each-ref` diff against pre-rewrite snapshot; if any ref still references an old commit, the operation is rolled back.
6. **LFS orphans remain on remote** — `git filter-repo` reports `LFS Objects Orphaned`. Mitigation: enumerate, emit a server-side cleanup ticket payload, and refuse to mark `completed` until the platform support ticket is referenced.
7. **`--batch` waiver abused for routine purges** — engineers normalize the dangerous path. Mitigation: rate-limit `--batch` per-operator per-month, audit-log it with elevated severity, and notify the security inbox automatically.
8. **Web UI executes destructive transition by API jiggery** — Mitigation: §8.2.21 module only emits `planned`, `analyzed`, `previewed`, `notified` events to the daemon; the daemon rejects any RPC call moving to `confirmed → executing` that did not originate from a stdin-attached TTY.

### 6.12 Premade Operations Kit (workflows, bundlers, push-to-prod, VPS setup)

**Headline capability.** Sange ships a curated, versioned, signed **kit** of ready-to-use operational scaffolds covering the four hardest-to-bootstrap concerns in real-world DevOps: **CI workflows**, **release bundlers**, **push-to-prod strategies**, and **VPS provisioning / hardening**. The kit reduces the "set up a new project from scratch" cost from days to minutes, and crucially does so without introducing the security/quality drift that copy-pasting from blog posts produces.

The kit's source-of-truth lives in `src/sange/templates/` (subgrouped per §10.4 — see §16.2 layout). Sange materializes selected fragments into a target repo under `.sange/` or directly into the standard locations (`.github/workflows/`, `Caddyfile`, `inventory.yml`, etc.) via the `sange scaffold` CLI surface (§7.11).

#### 6.12.1 What's in the kit

| Sub-tree | Content | Best-practice anchors |
|---|---|---|
| `templates/workflows/github/` | CI + release + security-scan + SBOM + sigstore + docs workflow `.yml` files; every action pinned by SHA (not tag); `permissions: contents: read` minimum scope; `step-security/harden-runner` enabled; OIDC trusted-publishing for PyPI / npm / OCI / GitHub Packages; matrix builds for Python 3.12+, Node LTS, PHP 8.3/8.4 | GitHub Actions security hardening guide; OpenSSF Scorecard; OIDC trusted publishing |
| `templates/workflows/gitlab/` | `.gitlab-ci.yml` fragments using `rules:` (not `only/except`), `stages:`, `include:` modular blocks, `id_tokens:` for OIDC federation, container-scanning + SAST + secret-detection job templates | GitLab CI/CD reference (v17+); GitLab Application Security |
| `templates/workflows/azure/` | `azure-pipelines.yml` with `stages` + `jobs` + `templates/`, `environments` with required reviewers, workload-identity federation to Azure / GitHub / AWS | Microsoft Learn: Azure Pipelines templates + environments |
| `templates/workflows/bitbucket/` | `bitbucket-pipelines.yml` with `definitions:`, `caches:`, repository-variables convention | Atlassian Pipelines docs |
| `templates/workflows/gitea/` + `forgejo/` | GitHub-Actions-compatible workflows tuned for self-hosted runners; `act_runner` integration notes | Gitea Actions / Forgejo Actions docs |
| `templates/workflows/circleci/` | `.circleci/config.yml` with orbs, contexts, workflows with `requires:` | CircleCI configuration reference |
| `templates/workflows/jenkins/` | Declarative `Jenkinsfile`s; shared-library invocation; environment-block patterns | Jenkins handbook |
| `templates/workflows/_core/` | Provider-agnostic stage definitions (`lint → typecheck → test → build → scan → sbom → sign → publish`) used as the source-of-truth that each provider scaffold translates |  |
| `templates/bundlers/goreleaser/` | `.goreleaser.yaml` (v2 syntax) with universal binaries, sigstore signing, SBOM gen, GitHub Releases + OCI artifact destinations | Goreleaser docs (v2) |
| `templates/bundlers/semantic-release/` | `.releaserc` with `@semantic-release/{commit-analyzer,release-notes-generator,changelog,npm,github,git}`; OIDC for npm publish | semantic-release docs |
| `templates/bundlers/release-please/` | `.release-please-config.json` + `.release-please-manifest.json` for monorepo manifest mode | release-please docs |
| `templates/bundlers/git-cliff/` | `cliff.toml` with Conventional-Commits-aware sections, tag-version detection | git-cliff docs |
| `templates/bundlers/changesets/` | `.changeset/config.json` for monorepo independent-versioning | changesets docs |
| `templates/bundlers/pyinstaller/` | `.spec` files; pinned to PyInstaller minimum; UPX-disabled (false-positive AV trigger); sigstore + checksums | PyInstaller docs |
| `templates/bundlers/electron-builder/` | `electron-builder.yml` with code-signing config, auto-update integration | electron-builder docs |
| `templates/bundlers/docker-oci/` | OCI artifact bundle build + push scripts; uses `cosign` for signing, `syft` for SBOM, `oras push` for upload | OCI Image Spec; OCI Artifact Guidance |
| `templates/push-to-prod/_core/` | Cross-strategy gates: pre-flight (health check, drift check, last-deploy age), post-flight (smoke probe, latency budget, error-rate budget), rollback trigger criteria | Google SRE Book — release engineering chapter |
| `templates/push-to-prod/rolling/` | Rolling-restart patterns for `docker compose` (`up -d` with healthcheck-gated batches), `systemd` (`Restart=on-failure` + serial rolling), Kubernetes (`RollingUpdate` strategy with `maxUnavailable`/`maxSurge`) | Kubernetes rolling-update docs |
| `templates/push-to-prod/blue-green/` | Two-environment swap pattern with reverse-proxy retargeting; Caddy + nginx + ALB / Cloud Load Balancer recipes | Martin Fowler — BlueGreenDeployment |
| `templates/push-to-prod/canary/` | Progressive traffic shifting with metrics-gated promotion; Argo Rollouts + Flagger + manual reverse-proxy split | Argo Rollouts docs; Flagger docs |
| `templates/push-to-prod/ssh/` | Atomic-symlink-swap deploy (the Capistrano pattern) without Capistrano: `releases/<ts>/` directory + `current` symlink + safe rollback by symlink redirect | Capistrano docs (pattern only); 12-factor app deployment |
| `templates/push-to-prod/compose/` | `docker compose pull && docker compose up -d --no-deps --remove-orphans` with healthcheck-gated batching; restic backup hook before pull | Docker Compose docs |
| `templates/push-to-prod/k8s/` | `kubectl apply --record=false` (deprecated) → server-side apply; `helm upgrade --install --atomic`; `kubectl rollout status` gated promotion; Argo CD / Flux GitOps recipes | Kubernetes docs; ArgoCD Best Practices; Flux GitOps Toolkit |
| `templates/push-to-prod/nomad/` | `nomad job run` with deployment health checks, rolling updates, canary deployments | HashiCorp Nomad docs |
| `templates/push-to-prod/ecs/` | AWS ECS service-update via Fargate with `--force-new-deployment`; CodeDeploy blue/green optional | AWS ECS best-practices guide |
| `templates/push-to-prod/cloudrun/` | GCP Cloud Run revisions with traffic-splitting; gradual rollout | Google Cloud Run docs |
| `templates/vps-setup/_core/` | CIS-Ubuntu-Server-22.04-LTS-aligned baseline: `unattended-upgrades`, `ufw` default-deny, `fail2ban`, `sshd_config` (key-only, port-randomized-default, `MaxAuthTries 3`, `AllowUsers`), `auditd` minimal ruleset, timesync (`chrony` or `systemd-timesyncd`), locale, swap-file sizing | CIS Ubuntu 22.04 LTS Benchmark; DigitalOcean/Hetzner initial-server-setup guides |
| `templates/vps-setup/cloud-init/` | Per-provider `cloud-init.yml` honoring each provider's metadata quirks (Hetzner SSH key import; DO `vendor_data` interaction; AWS user-data size cap; GCP `startup-script-url`; Azure `customData`) | cloud-init documentation; each provider's user-data docs |
| `templates/vps-setup/ansible/` | Idempotent role-per-concern playbooks (`base`, `ssh`, `firewall`, `fail2ban`, `docker`, `compose`, `caddy`, `nginx`, `postgres`, `mysql`, `redis`, `node-exporter`, `promtail`, `backup-restic`, `sanged`). `inventory.yml.example` with group_vars; ansible-vault for secrets. | Ansible best-practices guide |
| `templates/vps-setup/terraform/` | IaC starter modules per provider (Hetzner Cloud, DigitalOcean, AWS, GCP); separate `modules/` and `examples/`; `cloudflare-tunnel/` module ties the VPS to a Cloudflare Tunnel without exposing inbound ports | Terraform Module Standard; HashiCorp Terraform Style Guide |
| `templates/vps-setup/docker/` | Minimal "VPS as a docker host" path for users who skip Ansible: official Docker install with hash-pinning, sample `compose.yml`, log-rotation config | Docker Engine install docs |
| `templates/vps-setup/caddyfiles/` | Ready-to-use Caddyfile templates: reverse proxy with automatic-TLS, basic-auth, rate-limit, basic-WAF, OIDC-forward via `caddy-security`; per-workload presets (`laravel.Caddyfile`, `nextjs.Caddyfile`, `static-spa.Caddyfile`, `sange-web.Caddyfile`) | Caddy docs |
| `templates/vps-setup/nginx-confs/` | Equivalents for users who prefer nginx; certbot-managed Let's Encrypt config | nginx docs; Mozilla SSL Config Generator |
| `templates/vps-setup/monitoring/` | Prometheus + Grafana + Loki bundle (the "PLG stack"); `node_exporter` for hosts; `cadvisor` for containers; pre-built dashboards JSON for Sange + Caddy + Postgres + Docker | Grafana Labs reference architectures |
| `templates/scripts/_core/` | `lib.sh` + `lib.py` for color/log/exit-code helpers, sourced by every kit script |  |
| `templates/scripts/bootstrap/` | `brew`/`scoop`/`apt`/`mise`/`asdf` orchestration scripts; idempotent; doctor-checked |  |
| `templates/scripts/doctor/` | Health-probe scripts (host, container, web-UI, daemon, audit chain) |  |
| `templates/scripts/deploy/` | One-shot deploy helpers paired with `push-to-prod/` patterns |  |
| `templates/scripts/backup/` | restic / borg / rsync wrappers with off-host destination + integrity verification |  |
| `templates/scripts/cron/` | systemd-timer + cron snippets (the host-side scheduler that complements §8.2.8 — host-level concerns Sange itself shouldn't own) |  |
| `templates/scripts/recovery/` | Disaster-recovery runbooks as executable scripts (gitignore-swap recovery, purge rollback, daemon re-init, restore-from-restic) |  |

#### 6.12.2 Kit policy (ADR-020)

The kit is **curated, signed, and versioned** — Sange does not download arbitrary remote content:

1. **Curated only.** Every fragment ships *inside* the Sange package; no run-time download from random URLs. The kit grows by PR review, not by user-submitted gists.
2. **Signed.** Every kit fragment is hash-listed in a signed manifest (`templates/MANIFEST.toml.sig`) shipped with Sange; `sange scaffold` verifies the manifest before materializing. Tampering produces a refusal-and-warning.
3. **Versioned per Sange release.** A v0.5 user's kit is reproducible; `sange scaffold --kit-version <semver>` pins a specific kit version for legacy projects.
4. **Update path.** `sange update-kit` reviews diffs between the user's materialized fragments and the new kit version, with a per-fragment three-way merge (kit / user / current). Conflicts produce an audit entry; nothing is silently overwritten.
5. **Plugin extensions.** Third-party plugins can register additional fragments via the §7.9 plugin system, but only if the plugin manifest is signed; the loader marks plugin-provided fragments as `provenance: plugin` in the audit chain.
6. **No upstream phone-home.** The kit is bundled with Sange's installer; updating Sange updates the kit. There is no separate "kit registry" CDN.
7. **Provider-tested.** CI runs every kit fragment against an integration matrix (GitHub Actions self-hosted, GitLab runner, ephemeral Hetzner / DO VMs spun up + torn down) at least weekly; failing fragments are marked `kit_status: needs_attention` and surfaced in `sange doctor`.

#### 6.12.3 `sange scaffold` CLI surface (forward-ref to §7.11)

The kit is reached via a single verb:

- `sange scaffold list [--category CAT]` — show what's available
- `sange scaffold show <path>` — preview a fragment (no materialization)
- `sange scaffold add <path> [--target DIR] [--var KEY=VAL]…` — materialize a fragment with variable substitution; refuses to overwrite without `--force`; records a `provenance.json` next to the materialized file
- `sange scaffold diff [<path>]` — show diff between materialized fragments and the current kit version
- `sange scaffold update [<path>] [--strategy theirs|ours|merge]` — three-way merge (default `merge`); refuses without an explicit strategy if a conflict can't be auto-merged
- `sange scaffold remove <path>` — remove a materialized fragment cleanly (uses the recorded `provenance.json` to know what to delete)
- `sange scaffold verify` — verify all materialized fragments still match a known kit version; flags drifts

#### 6.12.4 Cross-section integration

| Kit area | Already specified at | Sange surface |
|---|---|---|
| CI workflows | §7.5 (CI/CD companion), §8.2.9 (Web UI CI Monitoring) | `sange ci scaffold <provider>` (alias of `sange scaffold add workflows/<provider>/...`) |
| Release bundlers | §6.9 (Release Bundling), §8.2.6 (Web UI Release Bundling) | `sange bundle scaffold <tool>` |
| Push-to-prod | §6.9.5 (public/private), §8.2.4 (Push & Publish Approval) | `sange deploy scaffold <strategy>` |
| VPS setup | §8.5 (Remote Access Topologies — specifically §8.5.4 reverse-proxy on VPS) | `sange vps scaffold <provider>` |
| Backup / DR | §11 (Security — backup mitigations), §6.11.4 (purge backups) | `sange backup scaffold <tool>` |
| Monitoring | §13 (Observability) | `sange monitoring scaffold` |

#### 6.12.5 Best-practice citations (must appear in §49 References of the deliverable)

The responding model must cite the following sources where relevant in the kit's docs and inline comments (with access date):

- **CIS Benchmarks** — `https://www.cisecurity.org/benchmark/`
- **GitHub Actions hardening** — `https://docs.github.com/en/actions/security-guides/security-hardening-for-github-actions`
- **OpenSSF Scorecard criteria** — `https://github.com/ossf/scorecard`
- **SLSA Levels** — `https://slsa.dev/spec/`
- **Sigstore + cosign** — `https://docs.sigstore.dev/`
- **CycloneDX SBOM** — `https://cyclonedx.org/specification/`
- **OWASP ASVS Level 2** — `https://owasp.org/www-project-application-security-verification-standard/`
- **Caddy automatic HTTPS** — `https://caddyserver.com/docs/automatic-https`
- **Ansible best practices** — `https://docs.ansible.com/ansible/latest/tips_tricks/sample_setup.html`
- **cloud-init reference** — `https://cloudinit.readthedocs.io/en/latest/`
- **Mozilla SSL Config Generator** — `https://ssl-config.mozilla.org/`
- **HashiCorp Terraform style guide** — `https://developer.hashicorp.com/terraform/language/style`
- **Google SRE Book — Release Engineering** — `https://sre.google/sre-book/release-engineering/`
- **Argo Rollouts** / **Flagger** docs for progressive delivery
- **Goreleaser v2** docs; **semantic-release** docs; **release-please** docs; **git-cliff** docs; **changesets** docs

#### 🔴 Red-Team Pass for §6.12

1. **Stale kit fragment shipped after upstream tool releases a breaking change.** Mitigation: weekly integration matrix (§6.12.2 #7) + `kit_status: needs_attention` surfaced in `sange doctor`; CI run fails the Sange release if any kit fragment fails its integration test.
2. **Operator runs `sange scaffold add` on an existing customized file and clobbers it.** Mitigation: default refuses to overwrite; `--force` requires `--audit-reason "<text>"`; three-way merge available via `sange scaffold update`.
3. **Plugin ships malicious workflow fragment that exfiltrates secrets.** Mitigation: signed plugin manifest required; plugin-provided fragments flagged `provenance: plugin` in materialization and audit; default Sange policy excludes plugin fragments from `sange scaffold update --strategy theirs` so plugin fragments cannot mass-overwrite curated ones.
4. **VPS hardening fragment skipped because it conflicts with an organization's policy** (`MaxAuthTries 3` may be too strict for a noisy bastion). Mitigation: per-fragment override knobs documented in front-matter; `--var ssh_max_auth_tries=10` substitutes at materialization; `provenance.json` records the overrides for future audit.
5. **Cloud-init script leaks secrets** because user-data is logged by the provider. Mitigation: kit's cloud-init fragments **never include secrets** — they only set up the host to fetch secrets at runtime from a configured store; documented prominently in `templates/vps-setup/cloud-init/_core/SECURITY.md`.
6. **Deployment scripts ship without rollback paths.** Mitigation: every push-to-prod strategy includes a `rollback.sh` companion, exit-code conventions, and a `health.sh` post-flight probe; `sange deploy scaffold` refuses to materialize a strategy missing any of the three.

### 6.13 Fluent / chainable OOP API style 🟡 META

Captured from the original turn-1 brief: *"design architecture should be in pure python fluent oop chainable, solid, dry, kiss"*. This was specified but not previously documented. The rule:

Every Sange domain object that participates in a workflow exposes a **fluent / method-chaining API** alongside the data-class accessors. The chained form is the *idiomatic* surface for Python users; the data-class form is the *introspectable* surface for tests, serialization, and the daemon's JSON-RPC layer.

```python
# Chained form — the user-facing idiom
plan = (
    PurgePlan.create(repo=here)
        .add_path("config/secrets.json")
        .add_glob("**/*.pem")
        .replace_text("expressions.txt")
        .with_scanner("gitleaks")
        .with_scanner("trufflehog")
        .with_audit_log(repo / ".sange/audit")
        .require_secrets_rotated()
        .require_fresh_mirror()
        .require_backup()
        .build()
)
plan.preview().confirm().execute().verify().push()

# Data-class form — for inspection, serialization, daemon RPC
plan.to_dict()                     # the JSON shape from §6.11.3
PurgePlan.from_dict(payload)       # round-trip via JSON-RPC
```

Rules:

1. **Every chain method returns `self`** (or a new immutable instance for snapshot-style builders). Never returns `None`. Forbidden: `obj.set_x(1)` that returns `None`.
2. **Chain methods are side-effect-free at construction time** — they record intent. The first method that triggers a side effect (filesystem write, subprocess call, network) has a verb name that makes it obvious: `.execute()`, `.push()`, `.materialize()`, `.send()`. Never `.set_x()` that secretly performs IO.
3. **Type-hinted return types** — `def with_scanner(self, name: str) -> "PurgePlan":` — so editors auto-complete the chain.
4. **`@chainable` decorator** in `src/sange/utils/fluent.py` for the common case (`return self`) so authors don't repeat themselves.
5. **Terminal methods are `.build()` / `.execute()` / `.preview()` / `.dump()` / `.send()`** — sentinels the type checker understands as ending the chain.
6. **No mandatory chained form.** The data-class constructor with kwargs always works (`PurgePlan(repo=..., paths=[...], …)`). Chaining is the ergonomic surface; constructors are the testability surface.
7. **All adapter Protocols (§6.2 VCSDriver, AIProvider) expose chainable wrappers** for the common operations: `git.add(*paths).commit(message="…").push().tag("v1.0.0")`.
8. **Reusable beyond Sange.** The fluent helper module (`sange/utils/fluent.py`) is documented as agency-reusable — copy it into a future project; the decorator + type contract are not Sange-specific.

#### 🔴 Red-Team Pass for §6.13

1. **Chain mutates shared state behind the user's back.** Mitigation: chain methods are documented `Mutates: yes` or `Mutates: no (returns new)` in the docstring; immutable form is the default for plan/spec objects (`PurgePlan`, `BundleManifest`, `CommitSpec`), mutable form for live operations (`GitRepo`, `Daemon`).
2. **Chain calls `.execute()` mid-build accidentally** because the user mistypes. Mitigation: terminal methods are *prefixed* by something stronger than tab-completion — they require explicit positional kwargs (e.g. `plan.execute(confirmed_by="alice@host", audit_token="...")`); the typer CLI binds these via the typed-phrase gate (§7.0.5).
3. **Method chain hides the JSON-RPC payload.** Mitigation: `plan.to_dict()` round-trips to the same daemon payload; integration tests assert `from_dict(plan.to_dict()) == plan`.

---

## 7. FEATURE SURFACE — CLI / TUI

For each feature, deliver: purpose, CLI shape, config keys, security considerations, AI touchpoints, error modes, telemetry events, exit codes.

### 7.0 Cross-cutting CLI / TUI presentation conventions

Every feature in §7 inherits the rules below. They are mandatory; deviations require an ADR.

#### 7.0.1 Library picks (mandatory)

| Purpose | Pin | Why this one |
|---|---|---|
| CLI framework | **`typer`** | Type-hint-driven, idiomatic Python 3.12, clean help rendering when composed with `rich` |
| Visual surface (colors, tables, panels, tree, progress, syntax, live) | **`rich`** | One library covers every visual element; `wcwidth`-aware width math built in |
| Interactive prompts (multiselect, text, password, confirm) | **`questionary`** | Native timeouts, validators, composable across all commands |
| Persistent TUI app (`sange tui`) | **`textual`** | Reactive Textual app reuses the same domain layer as the CLI; only used for the dedicated TUI mode, not for in-flow progress |
| Logging | **`structlog`** | Processor-based pipeline lets us insert the audit hash-chain link as a processor; supports pretty-on-TTY + JSON-on-CI from one config |
| Terminal width math (CJK + emoji) | **`wcwidth`** | Required for any truncation; `rich` uses it internally — we use it directly where we render outside `rich` |
| Shell detection (cmd / pwsh / bash / zsh / git-bash / MSYS2 / fish) | **`shellingham`** | Reliable detection beats env-var sniffing; fallback to env vars on import failure |
| File-type sniffing | **`python-magic`** | Used by `sange doctor` and the secret-scanner integration to differentiate text/binary blobs before redaction |
| OS keychain | **`keyring`** | Already specified in §6.3 (secrets) |
| Subprocess execution | **stdlib `subprocess`** + **`asyncio`** | Direct control over stdout/stderr streaming, signal handling, timeout, and audit retention. No `plumbum` / `sh` magic. |

**Disallowed (record an ADR if you want to override):** `tqdm` (use `rich.progress`), `colorama` (use `rich`), `inquirer` (use `questionary`), `loguru` (use `structlog`), `plumbum` / `sh` (use stdlib subprocess), `click` (use `typer`). The runner-up libraries are not banned forever — just not the default.

#### 7.0.2 Encoding & emoji auto-detection (mandatory at startup)

The Sange CLI must work identically on:

- Modern terminals: macOS Terminal, iTerm2, GNOME Terminal, Konsole, Windows Terminal (with `WT_SESSION` set), VS Code integrated terminal, JetBrains terminal.
- Legacy terminals: Windows `cmd.exe` on `cp1252`, `git-bash` and MSYS2 on older Git for Windows, SSH sessions with `LC_ALL=C`, `screen`/`tmux` without truecolor.
- Non-TTY: CI pipelines (`CI=true`), piped output (`stdout` not a TTY), JSON output mode.

At startup, every Sange process computes a `TerminalProfile` exactly once and caches it:

```python
@dataclass(frozen=True)
class TerminalProfile:
    is_tty: bool
    is_ci: bool
    encoding: str                 # sys.stdout.encoding or locale.getpreferredencoding(False)
    has_utf8: bool                # encoding contains 'utf'
    is_windows: bool
    is_modern_windows_terminal: bool  # WT_SESSION present or ConPTY detected
    shell: str                    # shellingham.detect_shell()
    color_mode: Literal["truecolor", "256", "16", "none"]
    use_emoji: bool               # disabled when NO_COLOR, cp1252, or not has_utf8
    use_unicode_box_chars: bool   # tree │├└─ vs |+`-
    width: int                    # shutil.get_terminal_size().columns
```

Detection rules:

1. `NO_COLOR` env var (any value) → `color_mode="none"`, `use_emoji=False`, `use_unicode_box_chars=True` (color is the noise, not the structure).
2. `FORCE_COLOR` env var (any value) → maximum capability regardless of TTY detection (CI dashboards that render ANSI).
3. `CI=true` (GitHub Actions, GitLab CI, etc.) → `is_ci=True`, default to `use_emoji=False`, `use_unicode_box_chars=True`, JSON log mode.
4. Windows + no `WT_SESSION` + encoding not UTF-8 → `use_emoji=False`, `use_unicode_box_chars=False` (fall back to ASCII).
5. Non-TTY stdout → progress / spinner / tree never animate; emit deterministic single-line milestones suitable for log aggregation.

Every visual primitive (tree, panel, table, status line) accepts a `TerminalProfile` and switches glyphs accordingly:

| Element | Unicode glyph | ASCII fallback |
|---|---|---|
| Tree branch | `├──` `└──` `│` | `+--` `\\--` `\|` |
| Bullet | `•` | `*` |
| Success | `✓` (or `✅` if emoji) | `[OK]` |
| Failure | `✗` (or `❌` if emoji) | `[FAIL]` |
| Warning | `⚠️` (if emoji) / `△` | `[WARN]` |
| In-progress | `…` (or animated spinner) | `...` |
| Section rule | `─────` | `-----` |

Width-aware truncation everywhere uses `wcwidth.wcswidth(s)`; never use `len(s)` for display-width math.

#### 7.0.3 Tree view (for `sange purge preview`, `sange branch list`, etc.)

Use `rich.tree.Tree`. The renderer accepts the `TerminalProfile` and selects glyph set. Nodes are clickable in TUI mode (`textual`'s `Tree` widget), display-only in CLI. File trees larger than `width × height × 0.5` are paginated with a clear "+N more — press Enter for next page" footer.

#### 7.0.4 Progress, spinner, ETA (mandatory for any operation > 1 s)

A unified `sange.utils.progress.Progress` wraps `rich.progress.Progress` with the exact column composition:

```
SpinnerColumn() + TextColumn(description) + BarColumn() + TaskProgressColumn() + TimeElapsedColumn() + TimeRemainingColumn() + TransferSpeedColumn(unit)
```

Rules:

- **Operations expected ≥ 1 s** must produce visible feedback. Long-running subprocesses parse their output for progress signals (e.g. `git filter-repo`'s `Parsed N commits…` and `Repacking…` lines) and update the bar.
- **Indeterminate → determinate** switch happens the instant a total is known. Operations that never become determinate keep the spinner; ETA is suppressed (don't lie about timing).
- **Subprocess stderr is parsed in real-time** with `asyncio` (see §7.0.6); raw lines are *also* streamed into the audit log losslessly.
- **CI / non-TTY mode** emits one summary line per phase boundary instead of an animated bar (avoid CR-spam in CI logs).
- **Multi-task progress** (e.g. multiple files being scanned) uses one `Progress` with multiple tasks, not separate `Progress` instances.

#### 7.0.5 Typed-phrase confirmation gate (used by `sange purge`, `sange publish`, `sange release`, `sange recover`)

A reusable helper `sange.utils.gate.typed_phrase_confirm(action, *, nonce=True, timeout_s=60)`:

- Renders the phrase with a per-session nonce by default (`PURGE_2026-05-13_<8-hex>`), so a copy-pasted phrase from yesterday's log is invalid.
- Times out (default 60 s, max 600 s) and refuses to fall back to "press Y" — must be the literal phrase or nothing.
- Bypassable only via `--batch` plus explicit precondition flags per the operation's spec.
- Records `gate_passed=true|false`, `attempts`, `elapsed_s`, `via='tty'|'batch'` in the audit log.
- TUI mode reuses the CLI implementation — there is no separate web-UI typed-phrase path (web UI cannot trigger destructive execution per §6.11.3).

#### 7.0.6 Subprocess streaming + lossless audit retention

Every external command (`git`, `git-filter-repo`, `bfg.jar`, `svnadmin`, `hg`, `p4`, `gitleaks`, `trufflehog`, `docker`, …) is invoked via a single helper that:

1. Spawns via `asyncio.create_subprocess_exec(..., stdout=PIPE, stderr=PIPE, text=True)`.
2. Concurrently reads stdout and stderr (`asyncio.gather(read(stdout), read(stderr))`) so the two streams never race.
3. Forwards each line to (a) the configured `Progress` parser, (b) the structured log, (c) the audit JSONL with a `stream` field.
4. Captures the full transcript into the audit entry's `transcript_hash` (sha256 of the concatenated streams), so the entry stays small while the transcript itself is retrievable from `${audit_dir}/transcripts/<event_id>.log` (created with mode `0600`).
5. On timeout or `Ctrl-C`, sends SIGTERM then SIGKILL after a configurable grace period; records the signal cascade in the audit entry.

#### 7.0.7 Hash-chained audit JSONL

Two write targets per audit event (per-repo + global) using a `structlog` processor that:

1. Reads the previous entry's `entry_hash`.
2. Computes `prev_hash = previous entry_hash`.
3. Renders the entry as canonical JSON (sorted keys, no whitespace).
4. Sets `entry_hash = sha256(canonical_json_without_entry_hash)`.

Verification command: `sange audit verify [--since DATE]` replays the chain and reports any mismatched links with the line number, offending field, and most-recent intact link. Audit files are 0600, append-only, refused-on-write-if-modified-since-last-line.

#### 7.0.8 Error handling + exit codes

- Every CLI command exits with a documented integer code from `sange.exit_codes` (e.g. `0` success, `1` generic failure, `2` invalid argument, `64` precondition failed, `65` user aborted, `66` verification failed, `67` rollback failed). The complete map lives in `docs/reference/exit-codes.md`.
- Errors are rendered as `Panel(title="Error", border_style="red")` with: the precise error, the immediate remediation, and the doc link.
- No traceback by default; `--debug` shows it. `--verbose` adds context lines. `--trace` enables `structlog`'s `dev` processor.
- Every error logs to the audit chain *and* to the application log.

#### 7.0.9 One question at a time (interactive UX rule)

When Sange's CLI / TUI / Web UI needs confirmation from the user, it asks **one question at a time** and waits for the answer before asking the next. Batching is forbidden:

- ✘ "Continue? [y/N]  Use AI? [y/N]  Sign with GPG? [y/N]" — three questions in one turn.
- ✓ "Continue? [y/N]" → answer → "Use AI? [y/N]" → answer → "Sign with GPG? [y/N]" → answer.

Reason: the user must be able to stop the sequence at any answer. Batched questions force the operator to answer questions they may not yet have the information for, or force them to abort the whole sequence when only one answer needs revisiting.

Rules:
- The `questionary` helpers (the library pinned in §7.0.1) are used in sequence — never composed into a single multi-field form for confirmation flows.
- Multi-field *information-entry* (a new bundle manifest, a new commit-template entry) **may** use a single multi-field form because each field is data, not a confirmation gate. But every *confirmation* gate is a single question.
- The web UI mirrors the rule: confirmation modals are sequential, not a stack of checkboxes.
- The Sange MCP server (§6.7) translates batched confirmations from an LLM caller into sequential prompts, never the reverse.
- Typed-phrase confirmations (§7.0.5) are themselves a single question; never two typed phrases in one prompt.

This rule is non-negotiable. See ADR-024.

#### 🔴 Red-Team Pass for §7.0

1. Operator sets `LC_ALL=C` to silence emoji and accidentally degrades the success-marker check; mitigation: success markers are always paired with structured exit codes — visual is never authoritative.
2. Malicious terminfo entry advertising truecolor when the terminal cannot render it; mitigation: rich respects `NO_COLOR` and `TERM=dumb` even if `COLORTERM=truecolor` is set, and we layer that on top.
3. Slow subprocess hides the ETA estimate behind a stuck spinner; mitigation: `TimeElapsedColumn` is *always* visible — the user can spot a hung command by elapsed time alone.
4. JSON-mode pollution: a subprocess line containing a `{` byte writes garbage into the audit log; mitigation: every audit write is JSON-encoded by the writer, never concatenated; subprocess output goes into the `transcript_hash` blob, not raw into the audit entry.
5. `--batch` removes the typed-phrase gate, an automated cron starts triggering purges; mitigation: `--batch` requires four explicit precondition flags, is rate-limited per-operator, and emits an elevated-severity audit entry.

---

### 7.1 Setup & bootstrap
- `curl ... | sh` installer per OS, checksum + sigstore signature verification
- `sange doctor` — diagnoses environment, prints actionable fixes
- `sange doctor --container` — extra audit when inside the Sange Docker image
- `sange init` — interactive scaffolding for a new repo (creates `.sange/`)
- `sange bootstrap` — installs `brew`/`scoop`/`apt` packages, oh-my-zsh, docker, language toolchains, from a declarative manifest

### 7.2 VCS workflow

The Sange CLI mirrors the user-supplied *Top 25 Git Commands* reference (anchored in §9.0.1) with `sange`-native augmentation. Every command below has a corresponding Appendix D row; no passthrough facades (per §9.4).

| Top-25 Git | `sange` equivalent | Augmentation |
|---|---|---|
| `git init` | `sange init` | Scaffolds `.sange/` skeleton; AI-suggested gitignore profile |
| `git clone` | `sange clone` | AI summary of repo on first clone |
| `git status` | `sange status` | Inline AI explanation of unusual states |
| `git add` | `sange add` (interactive checkboxes) | AI-suggested staging groups by logical change |
| `git commit` | `sange commit` (happy-path alias) + `sange commits …` (granular lifecycle, §6.8.4) | Full JSON lifecycle, AI messages, preset library, approval chain |
| `git log` | `sange log` (rich pager) | AI-summarized "what happened on this branch" |
| `git diff` | `sange diff` | Syntax-highlighted, AI-explained diff |
| `git branch` | `sange branch` | Naming-policy validation, age + ahead/behind, AI-named branches |
| `git checkout` | `sange checkout` | Warns when superseded by `switch`/`restore`; passthrough |
| `git switch` | `sange switch` | Preferred over `checkout` per current Git guidance |
| `git merge` | `sange merge` | Conflict-resolution helpers; AI-suggested resolutions and merge-commit messages |
| `git rebase` | `sange rebase` | Interactive-aware; AI-suggested commit grouping; rerere integration |
| `git pull` | `sange sync` | Fetch + rebase/merge per config; AI-summarized incoming changes |
| `git push` | `sange push` (or via `sange commits push`) / `sange publish` | Pre-flight: secret scan, large-file warner, policy; gitignore-swap on `publish` (§6.5) |
| `git fetch` | `sange fetch` | Passthrough |
| `git remote` | `sange remote` | list/add/rename/set-url/prune |
| `git stash` | `sange stash` | Semantic naming, AI-named entries |
| `git stash pop` | `sange stash pop` | Warns on dirty WT |
| `git reset` | `sange reset` | Mode-aware (soft/mixed/hard); type-to-confirm on `--hard` |
| `git revert` | `sange revert` | Single/range/merge-commit aware; AI-generated message |
| `git tag` | `sange tag` | Annotated, signed via configured key; AI-generated tag message |
| `git show` | `sange show` | AI-explained commit (intent, risk, related issues) |
| `git rm` | `sange rm` | `--cached`-aware; warns about purge for sensitive removals → §6.11 |
| `git mv` | `sange mv` | Passthrough |
| `git config` | `sange config` | Reads/writes SangeConfig + git config; never plaintext secrets (§6.3) |

Additional first-class verbs not anchored to a single Git command:

- `sange undo` — safe reversal of the last destructive operation (uses reflog + audit chain)
- `sange clean` — workspace cleaning, dry-run by default
- `sange review` — local PR-style review of staged changes
- `sange recover` — restore from a crash mid-publish / mid-purge (§6.11)
- `sange bisect` — regression-hunting with AI-suggested narrowing
- `sange worktree` — parallel-branches without re-cloning
- `sange maintenance` — gc / prefetch / loose-objects on schedule
- `sange sparse-checkout` — monorepo path-set ergonomics with AI suggestion

### 7.3 Release & changelog
- `sange release` — semver bumping, changelog (Keep a Changelog format), signed tag
- `sange release schedule` — schedule a release for a future time (executed by local scheduler)
- `sange bundle <subcommand>` — release bundling (see §6.9)
- Before/During/After phase hooks
- Monorepo release coordination

### 7.4 Hooks & policy
- Managed `pre-commit`-compatible hooks
- Secret scanning (gitleaks-equivalent) blocking on staged content
- Conventional Commits validator
- Large-file warner / LFS suggester
- License header enforcement

### 7.5 CI/CD companion
- `sange ci lint` — validates GitHub Actions / GitLab CI / Azure Pipelines / Bitbucket Pipelines YAML
- `sange ci run` — wraps `act` and equivalents for local execution
- `sange ci sim` — simulated end-to-end pipeline run including release stages
- Provider matrix: GitHub.com, GitHub Enterprise (Server + Cloud), GitLab.com, GitLab Self-Managed, Bitbucket Cloud, Bitbucket DC, Azure DevOps Services + Server, Gitea, Forgejo

### 7.6 .gitignore profile manager

- Global, per-project, per-subdirectory profiles
- Composable via `extends: ["lang/python", "framework/laravel", "editor/jetbrains"]` (paths are profile-registry keys per §15.4)
- Dev vs. prod variants — declared independently in `.sange/config.toml`; dev is the development tree, prod is what gets pushed (gitignore-swap engine §6.5)
- Built-in catalog mirrored (with attribution) from `github/gitignore`; layered with Sange-specific safety nets (`_core/secrets.gitignore`)

CLI surface:

- `sange profile list [--category lang|framework|infra|editor|os|all]` — show available profiles (the §15.4 registry)
- `sange profile show <name>` — show a profile's file patterns + dev/prod scope + auto-detect signals (no side effects)
- `sange profile detect [--apply]` — walk the repo, identify file-presence signals (`package.json`, `composer.json`, `pyproject.toml`, `Dockerfile`, `artisan`, `manage.py`, …), suggest the profile set; with `--apply` writes the suggestion into `.sange/config.toml`
- `sange profile use <name>... [--scope dev|prod|both]` — activate one or more profiles for the repo; updates `.sange/config.toml::gitignore.<scope>.profiles` array
- `sange profile remove <name>... [--scope dev|prod|both]` — inverse of `use`
- `sange profile diff` — show what `dev.gitignore` ignores vs. `prod.gitignore` after composition
- `sange profile validate` — check that every `extends:` entry resolves to a registered profile; flag drift after a registry update
- `sange profile materialize [--scope dev|prod]` — write the composed `.gitignore` to disk (normally driven by the swap engine; this is the manual form for inspection)

The `sange init` interactive flow runs `sange profile detect --apply` by default; the user can override the suggestion. Per ADR-024, the activation is sequential: one profile suggestion, accept/reject, next profile suggestion — never a multi-checkbox form for confirmation.

#### 7.6.1 Variant manager (`sange variant ...`)

Per §6.5.2 (Variant Matrix, ADR-032) the variant tuple drives gitignore composition, secrets, AI provider, audit verbosity, and bundle suffixes. The CLI surface mirrors `git`'s conventions — short verbs, predictable subcommands:

- `sange variant list [--all] [--filtered]` — show every declared variant (the Cartesian product over `stages × dimensions`); marks the active one; marks filtered combinations with their reason.
- `sange variant show` — display the **resolved** active variant tuple plus the layer that supplied each axis (e.g. "got `stage=staging` from branch-map matching `staging/oauth-rewrite`").
- `sange variant use <stage> [--<dim>=<flavor>]...` — switch the active variant. Writes `.sange/.active-variant`. Refuses while any §6.11 purge is in flight. Audit-logged.
- `sange variant unset` — clear the explicit `.sange/.active-variant`; next resolution falls through to env/branch/default per §6.5.2.7.
- `sange variant resolve [--variant <expr>]` — print the resolution trace for the current shell or the supplied expression; useful in CI for "what would this match?" diagnostics.
- `sange variant detect [--apply]` — heuristic auto-detection (CI env vars, branch name, `.env.*` presence, Docker tags); proposes a variant tuple; `--apply` writes it via `variant use`.
- `sange variant diff <variant-a> <variant-b>` — show the composed gitignore + config delta between two variants. Used by reviewers ("what changes if we move customer-x from staging to production?").
- `sange variant verify [--strict]` — checks: every required stage is reachable from at least one (stage, *flavors) tuple; bundle-name suffix mapping is injective; filters don't lock the user out of `publish_stage`; no plugin-declared dimension collides with a built-in axis.
- `sange variant filters` — list active filters with their `match` and `reason`.
- `sange variant scaffold <kit-fragment>` — materialize a canonical `.sange/variants/` skeleton from `templates/variants/` (see §6.5.2.12).
- `sange variant materialize [--variant <expr>]` — write the composed `.gitignore`, AI config, secrets-resolver config to disk for the supplied (or active) variant. Normally driven by the swap engine; this is the manual form for inspection.

Stage-locked operations (`sange publish`, `sange bundle publish`, `sange purge execute`) consult the active variant per §6.5.2.6; refusal messages name the precise `sange variant use ...` command that would fix the mismatch.

Auto-detection precedence (per §6.5.2.7) is **CLI flag > env var > `.sange/.active-variant` > branch-map > heuristic > defaults**. Every layer's contribution is recorded in the variant resolution trace and the audit log.

### 7.7 AI subsystem CLI
- `sange ai providers` — list configured providers, their ToS, current usage
- `sange ai preview --task <task>` — show the enhanced prompt that would be sent
- `sange ai cost` — usage report
- `sange ai mcp list` — connected MCP servers
- `sange ai mcp add <url>` — register a new MCP server with capability review

### 7.8 Secrets and access
- `sange secrets <subcommand>` — see §6.10.2

### 7.9 Plugin system
- Entry-point-based discovery (Python `entry_points`)
- Sandboxed execution for third-party plugins
- Signed plugin manifest required
- Capability declarations (network, filesystem scope, secrets access) reviewed at install
- `sange plugins list / install / remove / inspect`

### 7.10 History purge (see §6.11)

CLI surface for the VCS History Purge subsystem. Every subcommand is audit-logged per §6.11.6 and gated per §6.11.4. The shape below replaces the standalone `vcs-purge.py` reference wrapper from the user-supplied playbook §14 — the wrapper's safety contract is preserved unchanged; only its packaging moves from a standalone Python script into a first-class Sange subcommand tree.

- `sange purge plan` — interactive: define what to remove (paths, globs, regexes, replace-text expressions). Emits a `plan.json` under `.sange/purge/<utc>/`. State: `planned`.
- `sange purge mirror <plan-id>` — create the fresh mirror clone + tarball backup; verifies backup hash. Refuses if mirror exists and is not pristine. State: `preflight_passed`.
- `sange purge scan <plan-id> [--gitleaks] [--trufflehog]` — run detection scanners against the mirror; merge findings into the plan. State unchanged.
- `sange purge analyze <plan-id>` — runs `git filter-repo --analyze` (or VCS equivalent); writes `analysis.json` into the plan dir with sizes-by-path, ref counts, affected commits. State: `analyzed`.
- `sange purge preview <plan-id>` — TUI tree view of what would be removed (rich Tree per §7.0.3); shows before/after sizes and the changed-PR-ref count. State: `previewed`.
- `sange purge notify <plan-id>` — generates the collaborator-notification template (Slack / email / webhook payload) and either prints it or sends it via configured channels; records delivery id.
- `sange purge execute <plan-id>` — typed-phrase gate (per §7.0.5) → runs the actual rewrite. Subprocess output is streamed and audit-logged per §7.0.6. State: `executing` → `verified` (on success) or `rolled_back` (on failure).
- `sange purge push <plan-id>` — second typed-phrase gate → force-pushes mirror. State: `completed`. Emits server-side-housekeeping ticket payload (GitHub Support, GitLab Housekeeping, Bitbucket Support, self-hosted GC steps).
- `sange purge rollback <plan-id>` — restore the backup mirror to its original state; reset remote to backup HEAD; only available before `completed`.
- `sange purge audit show <event-id>` / `sange purge audit verify [--since DATE]` — inspect and verify the hash-chained audit log.
- `sange purge status [<plan-id>]` — list active plans and their state.

Flags shared across destructive subcommands:

- `--batch` — non-interactive mode for sanctioned automation. Requires all of `--acknowledge-secrets-rotated`, `--fresh-mirror-confirmed`, `--backup-verified`, `--collaborators-notified <ref>` to be explicitly set. Audit entry tagged `batch=true` with elevated severity.
- `--mirror <path>` — supply a pre-prepared mirror rather than letting Sange create one.
- `--audit-log <path>` — additional sink (the global `~/.sange/audit/…` sink is always written and cannot be redirected to `/dev/null`).
- `--notify-webhook <url>` — Slack-style webhook; payload is redacted per §8.5/§6.11; HMAC-signed; idempotency-key-protected against duplicate delivery.
- `--scanner gitleaks,trufflehog` — explicit scanner selection (default: both if installed).
- `--vcs git|svn|hg|p4` — explicit VCS; auto-detected when omitted.

Exit codes (from `docs/reference/exit-codes.md`):

| Code | Meaning |
|---|---|
| 0 | Success |
| 64 | Pre-flight gate red |
| 65 | User aborted (typed-phrase mismatch or `Ctrl-C`) |
| 66 | Post-rewrite verification failed |
| 67 | Push failed; rollback hint emitted |
| 68 | Audit-log write refused |

State-machine transition note: `executing → verified` is automatic when all eight §6.11.5 checks return green; `executing → rolled_back` triggers on any check red and reverts to the backup mirror. `verified → completed` only on a successful `sange purge push`.

### 7.11 Scaffold (Premade Operations Kit — see §6.12)

The materialization surface for the curated workflows / bundlers / push-to-prod / VPS-setup kit. The kit's source-of-truth ships inside Sange; this CLI selectively copies fragments into the target repo (or host) with variable substitution, three-way merge on update, and provenance tracking.

- `sange scaffold list [--category CAT]` — show available fragments
- `sange scaffold show <path>` — preview a fragment without materializing
- `sange scaffold add <path> [--target DIR] [--var KEY=VAL]…` — materialize with variable substitution. Refuses to overwrite without `--force`. Writes a sibling `<path>.provenance.json` recording kit version, vars, and the materialization timestamp.
- `sange scaffold diff [<path>]` — diff between materialized fragments and the current kit version
- `sange scaffold update [<path>] [--strategy theirs|ours|merge]` — three-way merge (default `merge`); refuses without an explicit strategy when auto-merge fails; audit-logged
- `sange scaffold remove <path>` — remove a materialized fragment using its `provenance.json`
- `sange scaffold verify` — verify every materialized fragment still matches a known kit version; surface drift in `sange doctor`

Aliases (already specified in §6.12.4): `sange ci scaffold <provider>`, `sange bundle scaffold <tool>`, `sange deploy scaffold <strategy>`, `sange vps scaffold <provider>`, `sange backup scaffold <tool>`, `sange monitoring scaffold`. Each alias is a thin wrapper that prefixes the appropriate kit path.

Exit codes (from `docs/reference/exit-codes.md`):

| Code | Meaning |
|---|---|
| 0 | Success |
| 2 | Invalid argument (unknown path, malformed var) |
| 64 | Fragment exists and `--force` not set |
| 69 | Manifest signature verification failed (refusal-and-warning per ADR-020) |
| 70 | Kit version drift detected by `verify` |

---

## 8. WEB UI — LARAVEL DASHBOARD (local or self-hosted-remote)

The web UI is **secondary to the CLI**. Every web action has a CLI equivalent. The web UI is an *interface*, not a separate product.

The web UI runs in one of three modes, chosen at install time and switchable later:

1. **Local-only** (default) — bound to `127.0.0.1`, accessed at `https://sange.test`
2. **LAN** — bound to a configured interface, accessed from devices on the same trusted network
3. **Remote** — exposed via Cloudflare Tunnel, Tailscale, WireGuard, or a reverse proxy; for users who need to work from anywhere

Remote mode is **supported from v1** with strict security defaults (see §8.5).

### 8.1 Stack and topology

- **Framework:** Laravel 13 + **Livewire 4** (4.3.0+; 2026-01-15 GA) — server-rendered, reactive, no SPA build complexity. Livewire 3 is deprecated for new work; do not ship a deprecated UI lib at v1.0.
- **PHP:** **8.3 floor (Laravel 13 minimum), 8.4 recommended** in practice (L13.3+ pulls Symfony 8 deps that effectively require 8.4)
- **DB:** SQLite default at `~/.sange/web.db`; PostgreSQL, MySQL/MariaDB, SQL Server via Laravel's database abstraction
- **Auth:** Three methods, with order of preference:
  1. **WebAuthn passkey** (primary) — implemented via the first-party `laravel/passkeys` Composer package + `@laravel/passkeys` npm package (both released 2026-05-12), with Fortify integration via `Features::passkeys()`. Note: passkeys are **not** in Laravel 13 core; they are first-party-but-separate, pinned by exact version in `composer.json` and audit-logged on every login.
  2. **PIN** (fallback) — 6–8 digits, rate-limited, optional TOTP second factor
  3. **Password** (alternative) — Argon2id, length ≥ 12, breach-checked against HIBP (k-anonymity API, no plaintext over the wire) at set time
- **Local domain:** `sange.test` resolved via `dnsmasq` (Herd/Valet pattern) on macOS, `/etc/hosts` entry elsewhere; on Linux, `systemd-resolved` integration is offered
- **TLS:** `mkcert`-generated local CA; cert auto-installed at first run; HSTS enabled. For remote mode, Let's Encrypt or user-provided cert.
- **Bind:** `127.0.0.1` only by default; LAN and remote modes require explicit configuration
- **IPC to Python core:** JSON-RPC 2.0 over localhost HTTP with HMAC-signed requests; the core runs as a persistent daemon (`sanged`) managed by `launchd` / `systemd` / Windows Service

### 8.2 Web UI feature catalog

Group features into modules. Every module has CLI parity.

#### 8.2.1 Project & Repo Management
Auto-discover from configured roots; health indicators; per-project dashboard; tagging and grouping; archive; cross-repo search; cross-repo bulk actions.

#### 8.2.2 Commit Management (lifecycle-aware)
- Inbox view per status: Drafts / Pending Review / Approved / Committed / Pushed / Rejected / Archived
- Inline JSON editor with schema validation (codemirror, monaco-light)
- Approve / reject / regenerate (with edited prompt) / discard
- Bulk approve / commit / push across selected repos
- Commit signing status indicator
- Commit graph visualization (DAG)
- Diff viewer with syntax highlighting and per-hunk staging
- "Why this message" — shows enhancer template, provider, prompt version
- Cost tracker visible per commit

#### 8.2.3 Branch Management
Branch list with age, ahead/behind, last activity, owner; bulk operations; naming-policy violations; local branch-protection rules.

#### 8.2.4 Push & Publish Approval
Queue of pending pushes; diff preview with gitignore-swap simulation; secret-scan, large-file, policy results inline; approve / reject / hold; **schedule push** for later; per-branch approval policies.

#### 8.2.5 Release Management
Release timeline; schedule releases with pre-flight checklists; AI-assisted changelog editor; tag creator with signing; rollback wizard; release templates per project.

#### 8.2.6 Release Bundling (new — see §6.9)
- Bundle manifest editor
- Build / sign / verify / publish workflow with explicit approval gates
- Channel management (stable / beta / nightly / custom)
- Public vs. private bundle controls with ACL editor for private
- Verification status of published bundles
- Rollback (for channels that support it)

#### 8.2.7 Rollback & Recovery
Visual git revert / reset (gated); per-file rollback; "time machine" read-only worktree view; stash management; reflog-based recovery; backup snapshots before destructive operations; confirmation chains scale with blast radius.

#### 8.2.8 Scheduler
Local cron-equivalent for scheduled operations; runs in `sanged`; all scheduled jobs visible, editable, cancelable; missed-run handling (skip / catch-up / fail-loud).

#### 8.2.9 CI/CD Monitoring
Local pipeline runs (via `act` etc.) with live log streaming; remote pipeline status across configured providers; failed build triage with AI explanation; pipeline editor with linting.

#### 8.2.10 Hook & Policy Management
View installed hooks per repo; edit configurations; policy violation log; approve / deny exceptions with audit trail.

#### 8.2.11 Secret & Token Management
List providers and tokens (metadata only); rotate tokens with provider integration; audit log of secret access; per-project token scoping; OS-keychain integration status; container secret pass-through configuration (see §6.10).

#### 8.2.12 AI Configuration & Cost
Provider selection per task; prompt template editor with version history and diff; cost / usage dashboard (token counts, $ estimates, per-project breakdown); per-project AI policy; rate limit configuration; **MCP server management** (add, inspect capabilities, revoke).

#### 8.2.13 Audit Log
Every Sange operation logged (CLI + Web + scheduled); filterable, searchable, exportable (JSON / CSV / NDJSON); security-relevant events highlighted; optional forward to syslog / journald / external SIEM.

#### 8.2.14 Local Tools & Portals Hub
Discover and monitor local dev portals (Laravel Herd, Valet, Docker Desktop, Local by Flywheel, Lando, DDEV, Mailpit, etc.); health status; quick-launch buttons; aggregate notifications. Monitoring/launcher view, not a replacement.

#### 8.2.15 Gitignore Profile Management
Visual editor with live preview; profile composition (extend, merge); test what's ignored; diff between dev and prod profiles.

#### 8.2.16 Plugin Management
Install / uninstall plugins; marketplace browser (signed only); permission review pre-install; update notifications.

#### 8.2.17 Telemetry & Local Analytics
View locally-collected telemetry (operation counts, latencies, error rates, cost trends); export; **opt-in send for product improvement** (v2+ feature, off by default); preview exactly what would be sent before opt-in.

#### 8.2.18 Workflow Builder (v2+)
Visual workflow editor; preset workflows; custom workflow saving and sharing.

#### 8.2.19 Settings
User preferences; theme; per-project settings; desktop notifications; keyboard shortcuts editor; mode switch (local / LAN / remote).

#### 8.2.20 Help & Documentation
Embedded docs; full-text search; interactive tutorial walkthroughs; CLI / TUI / Web parity reference.

#### 8.2.21 Purge & History Surgery (see §6.11, §7.10)
A planning-and-oversight surface for the History Purge subsystem. Per the §6.11.3 invariant, the web UI **cannot** trigger the destructive `confirmed → executing` transition — that step must occur at the engineer's terminal under typed-phrase gate.

- **Plan editor:** paths, globs, regex, replace-text expressions; validates against the running mirror; preview tree per §7.0.3.
- **Pre-flight checklist** with green/red indicators for each gate in §6.11.4; clicking a red gate shows the precise remediation.
- **Scan dashboard:** gitleaks + trufflehog results inline; severity heatmap; per-finding decision (purge / redact / ignore-with-reason).
- **Analysis tab:** sizes-by-path, ref impact, changed-PR-ref count, LFS orphan inventory.
- **Preview tab:** before/after tree (file / blob / size); ASCII-fallback rendering per the user's `TerminalProfile` for any rendered terminal-screenshots.
- **Notify tab:** generate / preview the collaborator-notification template; trigger sends via Slack / email / webhook with delivery confirmation.
- **Hand-off:** a copy-button emits the exact `sange purge execute <plan-id>` command for the engineer to paste into their terminal; the daemon refuses to advance state on an RPC alone.
- **Audit timeline:** live stream of audit-chain entries during execute / verify / push (read from `${repo}/.sange/audit/` and the global mirror).
- **Post-purge ticket helper:** prefilled payload for GitHub Support / GitLab Housekeeping with the changed-PR-ref count and First-Changed-Commit info.
- **Rollback workflow:** if execute failed, surface the rollback command and the backup tarball path for manual restoration.
- **Server-side housekeeping reminders** per platform (GitHub, GitLab, Bitbucket, Gitea, Forgejo); operator marks done with reference (ticket id, screenshot link).
- **Fork inventory** (where the platform API supports it): explicit reminder that forks are out of reach and the owner-contact list.

Permissions: only Sange roles with `purge:plan` can create / edit plans; only `purge:approve` can mark a plan ready for terminal execution; only `purge:audit` can dismiss alerts. Per-action audit entries are linked to the web session id.

### 8.3 Web UI security (mandatory)

🔒 The web UI manages git operations, AI keys, and approval workflows. A compromise is severe.

| Control | Requirement |
|---|---|
| Bind address | `127.0.0.1` default; LAN/remote = explicit opt-in with setup wizard |
| Authentication | WebAuthn passkey primary; PIN fallback; password alternative (Argon2id + HIBP) |
| MFA | Required for remote mode; recommended for LAN; optional for local |
| Session | Idle 30 min; absolute 12 hr; signed cookie, `HttpOnly`, `SameSite=Strict`, `Secure` |
| CSRF | Laravel CSRF on every state-changing request |
| CORS | Disabled; same-origin only |
| Origin validation | Strict; mismatched Origin/Referer = 403 (Laravel 13's built-in CSRF Origin check) |
| TLS | `mkcert` local CA for local; Let's Encrypt or user cert for remote; HSTS; TLS 1.3 minimum |
| Headers | CSP (no `unsafe-inline` except nonce-gated), X-Content-Type-Options, Referrer-Policy, Permissions-Policy |
| IPC auth | HMAC-signed JSON-RPC requests; rotating shared secret in memory only; mTLS for remote daemon access |
| Rate limiting | Per-route, per-IP, with abuse lockout |
| Audit | All UI actions logged with actor, IP, user-agent, timestamp |
| Secrets | Never rendered in HTML; metadata only |
| Subresource integrity | All third-party assets pinned with SRI hashes |
| Dependency policy | `composer audit` and `npm audit` in CI; weekly automated update PRs |
| Host header | Validated against allowlist — defends against DNS rebinding |
| Cache hardening | Laravel 13's `serializable_classes` explicit allowlist (default-deny deserialization) |

### 8.4 Web UI ADRs required

- ADR: Laravel 13 + **Livewire 4** over Inertia/Vue or full SPA
- ADR: SQLite default with multi-DB driver support
- ADR: WebAuthn primary, PIN fallback, password alternative — and the password's threat model
- ADR: JSON-RPC over REST or gRPC for core IPC
- ADR: `.test` local domain over `localhost:port`
- ADR: Pin `laravel/passkeys` + `@laravel/passkeys` (first-party, released 2026-05-12) as a hard dependency over rolling our own WebAuthn flow. Rationale: first-party packages are auditable, kept current with Laravel security advisories, and skip the entire CBOR/COSE attestation foot-gun surface.

### 8.5 Remote Access Topologies (supported from v1)

Sange supports four remote topologies. The user picks at setup; all four are documented with a runnable setup wizard.

#### 8.5.1 Cloudflare Tunnel (recommended)
- No exposed inbound ports; outbound-only `cloudflared` connection to Cloudflare's edge
- Cloudflare Access policies (email / SSO / IP / device posture) gate access before traffic reaches Sange
- Optional Cloudflare Workers as an edge auth gateway (custom claims, geo-restriction, anomaly detection)
- TLS terminated at Cloudflare with Sange-side mTLS to verify it's actually Cloudflare
- Setup wizard: `sange web remote enable cloudflare-tunnel` walks the user through `cloudflared login`, tunnel creation, DNS, and Access policy

#### 8.5.2 Tailscale / Tailscale Funnel
- Zero-config private mesh network
- MagicDNS for hostname-based access
- Tailscale Funnel for selectively exposing to the public internet with built-in TLS
- ACLs for fine-grained device/user access
- Setup wizard: `sange web remote enable tailscale`

#### 8.5.3 WireGuard
- Self-managed VPN
- Sange offers a `sange wg generate` for a minimal config; the user runs the WireGuard server elsewhere
- Document this as "expert-only"; recommend Tailscale for non-experts

#### 8.5.4 Direct reverse proxy on VPS
- For users with a VPS and a domain
- Caddy is the recommended reverse proxy (automatic TLS, simple config); nginx supported as alternative
- Setup wizard generates Caddyfile / nginx config
- Documents VPS providers tested (Hetzner, DigitalOcean, Linode, Vultr, OVH, Scaleway, AWS EC2, GCP CE, Azure VM) with per-provider gotchas (firewall, IPv6, mail port blocking, etc.)
- Setup wizard supports cloud-init / Terraform / Ansible scaffolds for repeatable provisioning

#### 8.5.5 Security obligations of remote mode

- mTLS between daemon and web UI is **mandatory** in remote mode (HMAC alone is insufficient over WAN)
- MFA is **mandatory** for at least one user role
- IP allowlist is **mandatory** for direct VPS exposure; optional but recommended for Cloudflare Tunnel
- A `sange web remote audit` command verifies all of the above and refuses to start in remote mode if any are missing
- All remote sessions logged with geo-IP (from request, never reverse-geocoded externally) and device fingerprint
- Anomalous session detection (impossible travel, new device, sudden activity spike) triggers re-auth

### 🔴 Red-Team Pass for §8 (sample threats to address in full doc)

1. CSRF on a permissive Origin policy if user adds custom domains
2. DNS rebinding against `sange.test`
3. Malicious plugin that injects JavaScript into the Web UI
4. Compromise of `~/.sange/web.db` (contains audit logs, metadata, secret refs)
5. Replay of HMAC-signed IPC if the shared secret is leaked from process memory
6. WebAuthn fallback PIN brute-force
7. Password fallback brute-force; credential stuffing if user reuses passwords
8. Malicious dependency in `composer.json` or `package.json`
9. Exposed IPC daemon port accidentally bound to `0.0.0.0`
10. Cloudflare Tunnel hijack via leaked tunnel token
11. Tailscale tagged-device escalation
12. VPS provider control-plane compromise leading to Sange data exposure
13. Malicious commit JSON containing fields designed to attack the next AI invocation (see §6.8 red-team)

---

## 9. COMMAND CATALOG (Appendices D, E, F — required content)

You must produce three exhaustive command catalogs as appendices. Not optional, not summary-level — they are **the reference material** the implementation team will work from.

### 9.0 Command Coverage Floor (mandatory minimum — every row must appear in Appendix D / E / F)

This section enumerates the **minimum** set of commands that **must** be covered. The user supplied a *Top 25 Git Commands* reference image that anchors the Git tier; we then layer the under-used power commands, the cross-VCS counterparts, and the third-party plumbing tools that the implementation will inevitably wrap. Any row marked `(deferred)` in the v1.0 deliverable is a quality-gate failure (see §19).

The columns shared by every row: **Tier** (Essential / Common / Power / Plumbing / Third-party), **Sange wrapper**, **AI augmentation** (what AI adds, or "none"), **Safety class** (Read-only / Reversible / Destructive / Catastrophic), **Confirmation gate** (None / Y/n / Type-to-confirm / Multi-step), **Web UI parity** (Yes-module / No / Read-only), **Notes** (edge cases, common foot-guns). These are the columns the Appendix-D-row schema (§9.1) already requires; this section enforces *which* rows are non-negotiable.

#### 9.0.1 Git — Top 25 (anchored to the user-supplied reference image, 2026-05-13)

| # | Git command | Tier | Sange wrapper | AI augmentation | Safety class |
|---|---|---|---|---|---|
| 1 | `git init` | Essential | `sange init` | Scaffolds `.sange/` skeleton; AI-suggested gitignore profile selection | Read-only |
| 2 | `git clone` | Essential | `sange clone <url>` | AI summarizes repo on first clone (README + recent commits) | Read-only |
| 3 | `git status` | Essential | `sange status` | Inline AI explanation of unusual states (detached HEAD, unmerged paths) | Read-only |
| 4 | `git add` | Essential | `sange add` (interactive checkboxes per v1's `git_add` pattern) | AI-suggests staging groups by logical change | Reversible |
| 5 | `git commit` | Essential | `sange commit` (happy-path alias) + `sange commits <subcommand>` (granular lifecycle, §6.8.4) | Full lifecycle JSON, AI-generated messages, prompt enhancer, presets, approval gates | Reversible |
| 6 | `git log` | Essential | `sange log` (rich pager) | AI-summarized "what happened on this branch since X" | Read-only |
| 7 | `git diff` | Essential | `sange diff` (syntax-highlighted, per-hunk view) | AI-explained diff for review | Read-only |
| 8 | `git branch` | Essential | `sange branch` (list, create, naming-policy validation, age/ahead-behind) | AI-named branches from intent (`sange branch new "fix oauth race"`) | Reversible |
| 9 | `git checkout` | Essential | `sange checkout` (warns when superseded by `switch`/`restore`; passes through) | none | Reversible |
| 10 | `git switch` | Essential | `sange switch` (preferred over `checkout` per current Git guidance) | none | Reversible |
| 11 | `git merge` | Essential | `sange merge` with conflict-resolution helpers | AI-suggested conflict resolutions; AI-generated merge-commit message | Reversible |
| 12 | `git rebase` | Common | `sange rebase` (interactive aware) | AI-suggested commit grouping for `--interactive` rebases | Destructive |
| 13 | `git pull` | Essential | `sange sync` (fetch + rebase or merge per config) | AI-summarized incoming changes since last pull | Reversible |
| 14 | `git push` | Essential | `sange push` (or via `sange commits push`); gitignore-swap (§6.5) on `sange publish` | Pre-flight: secret scan + large-file warner + policy violations; AI-generated push annotation | Destructive |
| 15 | `git fetch` | Essential | `sange fetch` | none | Read-only |
| 16 | `git remote` | Essential | `sange remote` (list / add / rename / set-url / prune) | none | Reversible |
| 17 | `git stash` | Common | `sange stash` (semantic naming, auto-message) | AI-named stash entries | Reversible |
| 18 | `git stash pop` | Common | `sange stash pop` (warn on dirty WT) | none | Reversible |
| 19 | `git reset` | Common | `sange reset` (mode-aware: soft/mixed/hard) | Type-to-confirm on `--hard`; `sange undo` is the safer reverse-able alias | Destructive |
| 20 | `git revert` | Common | `sange revert` (single, range, merge-commit aware) | AI-generated revert commit message | Reversible |
| 21 | `git tag` | Common | `sange tag` (annotated, signed via configured key) | AI-generated tag message; release-note linkage | Reversible |
| 22 | `git show` | Common | `sange show` | AI-explained commit (intent, risk, related issues) | Read-only |
| 23 | `git rm` | Common | `sange rm` (`--cached`-aware; warns about purge for sensitive removals — links to §6.11) | none | Destructive (Catastrophic if `--force` and uncommitted changes) |
| 24 | `git mv` | Common | `sange mv` | none | Reversible |
| 25 | `git config` | Essential | `sange config` (read/write SangeConfig + git config; never plaintext secrets — §6.3) | none | Reversible |

#### 9.0.2 Git — under-used power commands (must be covered, per §9.1 lower-tier expansion)

| Git command | Tier | Sange wrapper | Why it matters |
|---|---|---|---|
| `git bisect` | Power | `sange bisect` (run-based + AI suggested narrowing) | Surgical regression hunting; AI can hypothesize narrowing tests |
| `git worktree` | Power | `sange worktree` (add / list / remove / move / lock / prune) | Parallel branches without re-cloning; foundational for the `sange purge` mirror discipline (§6.11.4) |
| `git rerere` | Power | `sange rerere` (auto-enabled with audit on conflict-replay) | Replays recorded conflict resolutions; pairs with §6.8 lifecycle |
| `git maintenance` | Power | `sange maintenance` (manual + scheduled-job integration, §8.2.8) | Periodic gc/prefetch/loose-objects without a custom cron |
| `git sparse-checkout` | Power | `sange sparse-checkout` (init / set / disable + AI-suggested path-set from monorepo heuristics) | Monorepo ergonomics; AI suggests minimal path set for the user's working scope |
| `git replace` | Power | `sange replace` (with `--no-graft` warning) | Niche but documented; refused for destructive intent (use §6.11 instead) |
| `git notes` | Power | `sange notes` (lifecycle-integrated; can carry AI-generated review notes) | Out-of-band commit metadata; powers reviewer comments in §8.2.2 |
| `git reflog` | Power | `sange reflog` + `sange recover` | The reflog is your last safety net before `sange purge` expires it; `sange recover` reads it on crash |
| `git restore` | Common | `sange restore` (preferred over `checkout` for files per current Git guidance) | Replaces the file-restore half of legacy `checkout` |
| `git range-diff` | Power | `sange range-diff` | Compares two ranges of commits during rebase/cherry-pick reviews |
| `git cherry-pick` | Common | `sange cherry-pick` (with conflict-resolution helpers + AI message rewrite) | Hot-fix backport without merge graph |
| `git blame` | Common | `sange blame` (rich-rendered, AI-summarized authorship per region) | Inline ownership / why-this-line |
| `git grep` | Common | `sange grep` (rich-rendered; respects gitignore-swap state) | Code search across history |
| `git submodule` | Power | `sange submodule` (add / update / sync / status / foreach) | Cross-repo composition; required for §6.11 submodule re-procedure note |
| `git lfs` | Third-party | `sange lfs` (passthrough + orphan-LFS reporting integrated with §6.11.5) | Large files; LFS orphans from purge are critical to track |
| `git clean` | Common | `sange clean` (dry-run by default) | Workspace tidy; never touched without confirmation |
| `git describe` | Power | `sange describe` (semver-aware) | Building release strings from tags |
| `git archive` | Power | `sange archive` (integrated with `sange bundle build`, §6.9.2) | Snapshot a tree at a ref; feeds bundles |
| `git gc` | Power | `sange gc` (with explicit `sange gc --aggressive` for purge cleanup) | Local cleanup after rewrites; §7 ref |
| `git fsck` | Power | `sange fsck` (used by §6.11.5 verification) | Integrity checks |
| `git apply` / `git am` | Common | `sange apply` / `sange am` | Patch ingestion; needed for distributed review |
| `git format-patch` | Common | `sange format-patch` | Patch generation; pairs with `am` |
| `git send-email` | Power | `sange send-email` (gated; off by default) | Mailing-list workflows for kernel-style projects |
| `git shortlog` | Common | `sange shortlog` | Release-note generation feedstock |
| `git verify-commit` / `verify-tag` | Power | `sange verify` | Required for signed-commit policies (§7.4) |
| `git update-index --assume-unchanged` | Plumbing | `sange ignore-local <path>` (safer alias, audit-logged) | Common foot-gun made safer |
| `git for-each-ref` | Plumbing | `sange refs` (rich-table) | Used by §6.11.4 ref-budget gate |
| `git rev-list` / `rev-parse` | Plumbing | (internal use; not surfaced as a user command unless via `sange query`) | Underpins purge verification (§6.11.5) |
| `git switch -c --track` | Power | `sange branch new --track` | Branch-creation ergonomics |
| `git absorb` (third-party `git-absorb`) | Third-party | `sange absorb` (optional integration if installed) | Auto-fixup commit assignment for review iterations |
| `git autostash` | Common | `sange autostash` (config setting + transient autostash on `sync`) | Reduces "uncommitted changes" friction during pull/rebase |
| `git commit-graph` / `git fsmonitor` | Plumbing | (auto-enabled in `sange maintenance` defaults) | Performance on large repos |

#### 9.0.3 SVN — must-cover floor (Appendix E)

Every SVN command in the §9.2 listing is mandatory. The Sange wrapper column must be filled even when the wrapper is "passthrough with audit + AI annotation." Anchor list (no row may be deferred):

`svn checkout`, `svn update`, `svn commit`, `svn add`, `svn delete`, `svn copy`, `svn move`, `svn revert`, `svn diff`, `svn status`, `svn log`, `svn info`, `svn blame`, `svn cat`, `svn list`, `svn merge`, `svn mergeinfo`, `svn switch`, `svn relocate`, `svn resolve`, `svn resolved`, `svn cleanup`, `svn lock`, `svn unlock`, `svn propset`, `svn propget`, `svn proplist`, `svn propedit`, `svn propdel`, `svn import`, `svn export`, `svn mkdir`, `svn changelist`, `svn upgrade`, `svn patch`, `svnadmin dump`, `svnadmin load`, `svnadmin create`, `svnadmin hotcopy`, `svnadmin verify`, `svndumpfilter exclude`, `svndumpfilter include`, `svnsync init`, `svnsync sync`, `svnlook tree`, `svnlook log`.

The §6.11 SVN executor uses the last block (`svnadmin dump | svndumpfilter exclude | svnadmin load | swap`); these rows must cross-reference §6.11 explicitly.

#### 9.0.4 Mercurial — must-cover floor (Appendix F adapter)

`hg init`, `hg clone`, `hg add`, `hg remove`, `hg forget`, `hg commit`, `hg log`, `hg diff`, `hg status`, `hg push`, `hg pull`, `hg update`, `hg branch`, `hg branches`, `hg bookmark`, `hg merge`, `hg rebase`, `hg graft`, `hg revert`, `hg backout`, `hg strip`, `hg histedit`, `hg convert`, `hg phase`, `hg shelve` / `unshelve`, `hg serve`, `hg verify`, `hg resolve`, `hg copy`, `hg rename`, `hg tag`, `hg tags`, `hg annotate`, `hg grep`, `hg files`, `hg cat`.

#### 9.0.5 Perforce — must-cover floor (Appendix F adapter)

`p4 client` / `workspace`, `p4 sync`, `p4 edit`, `p4 add`, `p4 delete`, `p4 revert`, `p4 submit`, `p4 changelist` / `change`, `p4 describe`, `p4 diff`, `p4 diff2`, `p4 filelog`, `p4 files`, `p4 fstat`, `p4 print`, `p4 reconcile`, `p4 resolve`, `p4 merge`, `p4 integrate`, `p4 branch`, `p4 stream`, `p4 shelve` / `unshelve`, `p4 label`, `p4 tag`, `p4 reopen`, `p4 lock`/`unlock`, `p4 protect`, `p4 review`, `p4 obliterate` (admin only; §6.11), `p4 verify`, `p4 counter`, `p4 monitor`.

#### 9.0.6 Cross-cutting tools that Sange wraps (must appear in Appendix D/E and the relevant `docs/tools/*.md`)

| Tool | Purpose | Sange surface | VCS scope |
|---|---|---|---|
| `git-filter-repo` | history rewrite | `sange purge` (§7.10 / §6.11) | Git |
| `bfg` | history rewrite (path-blind) | `sange purge --tool bfg` | Git |
| `gitleaks` | secret scanning | `sange scan` + §7.4 hooks + §6.11.4 gate-8 | Git, filesystem |
| `trufflehog` | secret scanning with credential verification | same | Git, SVN, filesystem |
| `git-secrets` | AWS-style regex hooks | optional integration | Git |
| `pre-commit` | hook orchestrator | `sange hooks install` writes `.pre-commit-config.yaml` | Git |
| `detect-secrets` | baseline-based secret detection | optional alternate scanner | Git |
| `act` | local GitHub Actions runner | `sange ci run` | n/a |
| `goreleaser` / `release-please` / `semantic-release` | release engineering | `sange release` (own engine) and optional passthrough | n/a |
| `mkcert` | local CA for `.test` TLS | invoked by `sange web init` (§8.1) | n/a |
| `cloudflared` / `tailscale` / `wg` | remote topology | `sange web remote enable <topology>` (§8.5) | n/a |
| `cosign` / `sigstore` | signing | `sange bundle sign` (§6.9.2) | n/a |
| `syft` / `cyclonedx-cli` | SBOM | `sange bundle build` (§6.9.4) | n/a |

#### 🔴 Red-Team Pass for §9.0

1. A responding model produces Appendix D with 12 of the 25 Top-25 rows and a "remainder in v1.1" note. Mitigation: §19 quality gate explicitly forbids any §9.0 row being marked `(deferred)` for the v1.0 deliverable.
2. The Sange wrapper for a Catastrophic-class command (`git rm --force`, `git reset --hard`) is documented as identical to the underlying command without a confirmation gate. Mitigation: the §9.0.1 *Safety class* column drives the *Confirmation gate* column; any Destructive/Catastrophic row without a gate is a defect.
3. Third-party tools (`git-filter-repo`, `bfg`, `gitleaks`, etc.) drift to versions with breaking changes; Sange wraps an outdated CLI surface. Mitigation: pin minimum versions in `pyproject.toml`; `sange doctor` checks installed versions; release notes flag wrapped-tool upgrades.

### 9.1 Appendix D: Comprehensive Git Command Catalog

For **every** Git command (the full output of `git help -a` plus useful internal/plumbing), produce a row with:

| Field | Content |
|---|---|
| Command | `git <command>` |
| Tier | Essential / Common / Advanced / Plumbing / Rare-but-useful |
| Purpose | One sentence |
| Sange wrapper | `sange <subcommand>` or "passthrough" |
| AI augmentation | What AI adds (or "none") |
| Safety class | Read-only / Reversible / Destructive / Catastrophic |
| Confirmation gate | None / Y/n / Type-to-confirm / Multi-step |
| Web UI parity | Yes (module) / No / Read-only view |
| Notes | Edge cases, common foot-guns |

Include under-used powerful commands: `git bisect`, `git worktree`, `git rerere`, `git switch -c --track`, `git maintenance`, `git sparse-checkout`, `git replace`, `git notes`, `git reflog`, `git restore`, `git range-diff`, `git absorb` (if installed), `git autostash`, `git commit-graph`, `git fsmonitor`.

### 9.2 Appendix E: Comprehensive SVN Command Catalog

Same structure for SVN. Cover at minimum: `checkout`, `commit`, `update`, `merge`, `switch`, `relocate`, `propset`/`propget`/`proplist`, `info`, `log`, `diff`, `status`, `revert`, `blame`, `cleanup`, `lock`/`unlock`, `mkdir`, `cp`/`mv`, `import`, `export`, `cat`, `list`, `mergeinfo`, `resolve`, `resolved`, `add`, `delete`, `changelist`, `upgrade`.

### 9.3 Appendix F: Cross-VCS Concept Map

Table showing how concepts map across Git ↔ SVN ↔ Mercurial ↔ Fossil ↔ Pijul. The first three columns mandatory for v1; the latter two for v2 planning. Foundation of the VCS-agnostic Domain layer in §6.2.

### 9.4 Wrapping discipline (avoiding the "thin facade" failure mode)

A `sange <verb>` that *only* `subprocess.Popen`s the underlying `git <verb>` adds zero engineering value and just inserts a confusion layer. Every Sange wrapper documented in §9.0 must do **at least one** of the following beyond passthrough, recorded in its Appendix D row:

1. **AI augmentation** — generate, summarize, explain, or rewrite using the §6.7.1 prompt enhancer.
2. **Safety gating** — pre-flight checks, dry-run mode, typed-phrase confirmation, recovery file on disk.
3. **Lifecycle integration** — feeds or reads from the §6.8 commit lifecycle, the §6.9 bundle lifecycle, or the §6.11 purge lifecycle.
4. **Audit emission** — produces a hash-chained entry per §7.0.7.
5. **Rich rendering** — uses the §7.0 visual conventions (tree, panel, progress, table) where the raw command's output is mere text.
6. **Cross-VCS unification** — exposes the same surface for Git/SVN/Hg/P4 where the underlying commands diverge.
7. **Profile / config awareness** — respects the §6.4 `.sange/` config, gitignore profile state (§6.5), or per-repo policy.

Wrappers that do **none** of the seven are a code-smell and must be flagged in the §9.1 row's *Notes* column with "passthrough — consider deletion" until they earn at least one augmentation.

### 9.5 Innovation surface — what Sange adds beyond vanilla VCS

These are the capabilities the catalog rows in §9.0 are *building toward*, organized by primitive. None of them exist in raw `git`/`svn`/`hg`/`p4`; they are the engineering Sange invents.

#### 9.5.1 On top of `git commit` / `git push`
- **Commit lifecycle JSON state machine** (§6.8): `draft → pending_review → approved → committed → pushed → archived` with file-based persistence, schema versioning, and integrity hashes.
- **Prompt enhancer + provider-agnostic AI** (§6.7.1): commit messages generated from staged diffs with model-specific tuning, cost tracking, and prompt-injection defense.
- **104-entry preset library curated to ≥50 normalized presets** (§6.8.5) with `aliases` for v1 migration.
- **Approval chain with typed-phrase gates** for pushes that touch protected branches (§7.0.5).

#### 9.5.2 On top of `git push` / `git rm` / `.gitignore`
- **Gitignore-swap** (§6.5): atomic switch between `dev.gitignore` and `prod.gitignore` during publish, with SIGKILL-safe recovery file and concurrent-op refusal.
- **Profile composition**: `extends: [python, node, jetbrains]` (§7.6); per-subdirectory profiles for monorepos.

#### 9.5.3 On top of `git tag` / `git archive`
- **Release Bundling** (§6.9): `plan → build → sign → verify → publish → released` with SLSA-3 provenance, sigstore signing, SBOM (CycloneDX), public-or-private visibility, channel monotonicity, six destinations, sigstore-verifying `sange bundle verify-remote`.

#### 9.5.4 On top of `git filter-repo` / `bfg` / `svnadmin dump` / `p4 obliterate`
- **History Purge subsystem** (§6.11): 10-state lifecycle, 8 pre-flight gates, 8 post-rewrite verification checks, hash-chained audit JSONL, typed-phrase gates with per-session nonce, `--batch` mode requiring four explicit precondition flags (rate-limited per operator), web-UI plan-and-approve surface (§8.2.21) that cannot execute the destructive transition.

#### 9.5.5 On top of `Makefile`
- **Modular Makefile system** (§10): zero per-package Makefiles in git; one auto-generated `include` shim; per-tool fragments hash-verified against Sange's signed manifest; doctor-check + pre-commit hook block accidental commit of the generated Makefile.

#### 9.5.6 On top of `git hooks` / `pre-commit`
- **Hook & policy engine** (§7.4): managed pre-commit-compatible hooks, secret scanning, conventional-commits validation, large-file warner / LFS suggester, license-header enforcement (REUSE/SPDX), per-repo and per-user policy.

#### 9.5.7 On top of `act` / GH Actions / GitLab CI / Azure Pipelines
- **CI/CD companion** (§7.5): provider-matrix lint, local execution wrapping `act` and equivalents, simulated end-to-end pipeline run including release stages, AI-explained build failures (§8.2.9).

#### 9.5.8 On top of OS keychain / `keyring` / Vault / 1Password / age
- **Container VCS Secret Management** (§6.10): five mechanisms ranked by preference, SSH agent forwarding default for local dev, mlock + RLIMIT_CORE=0, `sange doctor --container` audit.

#### 9.5.9 On top of `gpg`/`ssh-keygen`/sigstore
- **Verifiable provenance** at every dangerous edge: sigstore for bundles, signed plugin manifests with capability declarations, signed tags re-asserted post-purge, sigstore + GPG dual signing on releases.

#### 9.5.10 On top of `tail` / `journalctl` / structured loggers
- **Hash-chained audit JSONL** (§7.0.7): every state-changing action records `prev_hash`/`entry_hash`; `sange audit verify` replays the chain; per-repo + global dual-write so a compromised repo's audit can be cross-checked against the host's.

#### 9.5.11 On top of `prompt-toolkit`/`inquirer`/`whiptail`
- **TerminalProfile auto-detection** (§7.0.2): emoji/ASCII glyph switching for Windows `cmd.exe`, MSYS2, locale=C SSH, CI; uniform output across every supported platform.
- **`rich`-based universal visual layer**: tree view, panels, progress with ETA, syntax highlighting, all width-aware via `wcwidth`.

#### 9.5.12 On top of MCP
- **Sange-as-MCP-server** (§6.7): commit lifecycle, branch ops, release bundling, and scheduler exposed as MCP tools so Claude Desktop / Code / Cursor can drive Sange with the same audit and gates.
- **Sange-as-MCP-client**: consumes external MCP servers (Jira, Linear, GitHub MCP, internal docs) for repo-context-aware AI calls.

#### 9.5.13 On top of cron / launchd / systemd timers
- **Local scheduler** (§8.2.8): cron-equivalent inside `sanged`; missed-run handling (skip / catch-up / fail-loud); all jobs visible, editable, cancelable from CLI and Web; **purge is excluded by design** (ADR-018).

#### 9.5.14 On top of `git submodule` / monorepo tooling
- **Sub-project release bundling** (§6.9.1): a Bundle can target a sub-project in a monorepo with its own visibility, channel, and verification — without spinning up a separate repo.

#### 9.5.15 New primitives Sange invents

| Primitive | Surface | What it enables |
|---|---|---|
| **`.sange/` folder convention** (§6.4) | per-repo | Co-located config, profiles, makefiles, prompts, telemetry, audit, web overrides |
| **Commit JSON file** (§6.8.3) | per-commit | Reviewable, editable, AI-provenance-tagged commit messages with approval chain |
| **PurgePlan JSON** (§6.11) | per-purge | Reviewable destructive op with explicit gates and audit |
| **Bundle Manifest** (§6.9) | per-release | Declarative release definition; reproducible build |
| **TerminalProfile** (§7.0.2) | per-process | Uniform output across Windows / SSH / CI / modern terminals |
| **Prompt Enhancer template** (§6.7.1) | per-task | Versioned, auditable, model-tuned prompt transformations |
| **Sange audit chain** (§7.0.7) | per-event | Hash-chained tamper-evident JSONL across both per-repo and global stores |
| **MCP capability allowlist** (§6.7) | per-project | Per-server capability review with revocation |

#### 🔴 Red-Team Pass for §9.5

1. A reviewer claims any Sange feature is "just `git X` with extra steps." Mitigation: every row in §9.5 names the primitive added and points to the §6/§7 section that specifies it independently of the underlying VCS command.
2. AI augmentation is framed as a marketing layer rather than an engineering one. Mitigation: §6.7.1 specifies the prompt enhancer's auditability, schema enforcement, and the redaction layer; §6.8.6 commit JSON files record provenance for every AI-generated message.
3. Sange's value collapses if `git filter-repo` / `BFG` / `gitleaks` etc. are absent. Mitigation: `sange doctor` declares hard vs. soft dependencies; soft-dep absence produces a warning, hard-dep absence blocks the relevant command with a precise install hint.

---

## 10. MODULAR MAKEFILE SYSTEM

The user's current pattern copies a hand-curated `Makefile` per package. This is duplicative, drifts across packages, and tracks the Makefile in git. Sange replaces this with a modular, generated system.

### 10.1 The Sange-native approach (recommended — record as ADR)

No per-package Makefile in git. The `sange` CLI is canonical. A `Makefile` is **generated on demand** as a thin compatibility shim:

```makefile
# Auto-generated by Sange. Do not edit. Do not commit.
# Load order: _core/ first, then alphabetical category, then alphabetical fragment.
include .sange/makefiles/_core/*.mk
include .sange/makefiles/ai/*.mk
include .sange/makefiles/ci/*.mk
include .sange/makefiles/db/*.mk
include .sange/makefiles/framework/*.mk
include .sange/makefiles/infra/*.mk
include .sange/makefiles/lang/*.mk
include .sange/makefiles/release/*.mk
include .sange/makefiles/security/*.mk
include .sange/makefiles/vcs/*.mk
-include .sange/makefiles/_local/*.mk
```

(Use the leading `-` on `_local/` so make does not fail when the user has no local overrides. The category list is the canonical set from §10.4; new categories require an ADR.)

Properties:
- Added to the dev gitignore profile automatically
- Contains only `include` statements; no logic
- `sange doctor` verifies it is gitignored and **fails loudly** if tracked
- Pre-commit hook installed by `sange init` blocks staging of the Makefile
- Recovery procedure documented: `sange fix-makefile-tracked` removes from history and re-gitignores

### 10.2 The modular `.mk` library

Fragments are **subgrouped by tool / tech / usage** per the §10.4 Category convention. Underscore-prefixed directories sort first under most shells, so `_core/` and `_local/` are unambiguous:

```
.sange/makefiles/
├── _core/                  # framework essentials — always loaded first
│   ├── help.mk             # auto-help target; parses `## description` markers
│   ├── colors.mk           # TerminalProfile-aware echo helpers
│   └── env.mk              # SANGE_ROOT, OS detection, common variables
├── vcs/                    # VCS targets — namespace: git:*, svn:*, hg:*, p4:*
│   ├── git.mk
│   ├── svn.mk              # only if SVN project
│   ├── hg.mk
│   └── p4.mk
├── lang/                   # language toolchains — namespace: python:*, node:*, php:*, etc.
│   ├── python.mk
│   ├── node.mk
│   ├── php.mk
│   ├── go.mk
│   ├── rust.mk
│   └── ruby.mk
├── framework/              # web/app frameworks — namespace: laravel:*, django:*, nextjs:*
│   ├── laravel.mk
│   ├── django.mk
│   ├── rails.mk
│   └── nextjs.mk
├── infra/                  # containers + orchestration — namespace: docker:*, k8s:*
│   ├── docker.mk
│   ├── compose.mk
│   ├── kubernetes.mk
│   └── terraform.mk
├── ci/                     # CI providers — namespace: ci:gh:*, ci:gl:*, ci:az:*
│   ├── github.mk
│   ├── gitlab.mk
│   ├── azure.mk
│   ├── bitbucket.mk
│   └── jenkins.mk
├── release/                # release engineering — namespace: release:*, bundle:*
│   ├── semver.mk
│   ├── changelog.mk
│   ├── bundle.mk
│   └── sign.mk
├── security/               # scanners + purge — namespace: scan:*, purge:*
│   ├── scan.mk             # gitleaks + trufflehog wrappers
│   └── purge.mk            # delegates to `sange purge …` (§6.11)
├── ai/                     # AI + MCP — namespace: ai:*, mcp:*
│   ├── providers.mk
│   └── mcp.mk
├── db/                     # databases — namespace: db:*
│   ├── postgres.mk
│   ├── mysql.mk
│   └── sqlite.mk
└── _local/                 # user's per-repo customizations — gitignored
    └── *.mk
```

Rules:
- Fragments auto-discovered by glob include in the order specified in §10.1 (`_core/` first, categories alphabetical, `_local/` last with `-include`).
- Underscore-prefix = framework-level (`_core/`) or user-level (`_local/`); never tool-level.
- `_local/` is gitignored; safe place for ad-hoc targets.
- Each fragment **self-documenting**: every target has a `## description` comment that the `_core/help.mk` target parses into the auto-generated help.
- Targets **namespaced by category-then-tool-then-verb**: `git:status`, `docker:up`, `release:tag`, `bundle:build`, `ci:gh:run`, `db:postgres:migrate`. The Sange CLI's command tree mirrors the namespace.
- A target may delegate to `sange`: `git:status: ; @sange git status`.
- Fragments **versioned** and updated by `sange update-makefiles` (handles both individual files and orphaned categories).
- Fragment files **hash-verified** against the Sange manifest at load; tampering produces a warning. The manifest stores hashes per `<category>/<fragment>` path, so moving a file between categories is detected.

### 10.3 Why this is better than the current pattern

| Current pattern | Sange pattern |
|---|---|
| Per-package Makefile in git | Generated, gitignored, regenerated on `sange init` |
| Drift between packages | Single source of truth in Sange |
| Manual sync of improvements | `sange update-makefiles` propagates changes |
| Boilerplate in every repo | One-line generated Makefile + per-tool modules |
| Easy to commit accidentally | Pre-commit hook + doctor check + gitignore default |

### 10.4 The Category convention (canonical for every Sange file tree)

The subgrouped layout in §10.2 is not specific to Makefiles — it is the canonical layout for **every** file-fragment tree Sange owns: `.sange/makefiles/`, `.sange/gitignore/profiles/`, `.sange/prompts/`, `.sange/workflows/`, `.sange/commit-templates/`, `.sange/hooks/`, `src/sange/templates/*/`, and `docs/tools/`. The convention exists so an engineer reading any one of those trees can predict the structure of every other.

#### 10.4.1 Canonical categories

The full set of category sub-directories — sub-directories outside this set require an ADR:

| Sub-dir | What goes here | Examples |
|---|---|---|
| `_core/` | Framework essentials. Always loaded first. **Never tool-specific.** | `help.mk`, `colors.mk`, `env.mk`, `conventional.tmpl` |
| `_local/` | User-authored overrides. **Gitignored.** Loaded last. | ad-hoc team targets, custom prompt edits |
| `vcs/` | Version-control system specific | `git.*`, `svn.*`, `hg.*`, `p4.*`, `fossil.*`, `pijul.*` |
| `lang/` | Programming language toolchains | `python.*`, `node.*`, `php.*`, `go.*`, `rust.*`, `ruby.*`, `java.*` |
| `framework/` | Web / app frameworks | `laravel.*`, `django.*`, `rails.*`, `nextjs.*`, `nuxt.*`, `symfony.*`, `astro.*` |
| `infra/` | Containers + orchestration | `docker.*`, `compose.*`, `kubernetes.*`, `terraform.*`, `ansible.*`, `pulumi.*` |
| `cloud/` | Cloud provider specifics (when needed) | `aws.*`, `gcp.*`, `azure.*`, `cloudflare.*` |
| `ci/` | CI/CD providers | `github.*`, `gitlab.*`, `azure.*` (Pipelines), `bitbucket.*`, `gitea.*`, `forgejo.*`, `circleci.*`, `jenkins.*` |
| `release/` | Release engineering | `semver.*`, `changelog.*`, `bundle.*`, `sign.*`, `publish.*` |
| `security/` | Scanners, purge, policy | `scan.*` (gitleaks + trufflehog), `purge.*`, `policy.*` |
| `ai/` | AI providers + MCP | `providers.*`, `mcp.*`, `enhancer.*` |
| `db/` | Databases | `postgres.*`, `mysql.*`, `mariadb.*`, `sqlite.*`, `mssql.*` |
| `editor/` | Editor / IDE noise (for gitignore profiles especially) | `jetbrains.*`, `vscode.*`, `vim.*`, `emacs.*`, `claude.*` |
| `os/` | Operating-system specifics | `macos.*`, `windows.*`, `linux.*` |
| `domain/` | Application domain — used in `prompts/` and `commit-templates/` | `security.*`, `deps.*`, `license.*`, `compliance.*` |
| `type/` | Conventional-Commits-style types — used in `commit-templates/` | `feat.*`, `fix.*`, `docs.*`, etc. |
| `workflow/` | Workflow-specific — used in `commit-templates/` and `prompts/` | `release.*`, `hotfix.*`, `merge.*`, `cherry-pick.*` |

#### 10.4.2 Rules

1. **Two-level cap.** A tree is at most `category/<fragment>` deep, except `commit-templates/type/feat.toml` and `commit-templates/workflow/release.toml` patterns where the second level is itself a category (`type/`, `workflow/`, `domain/`). Never `category/sub-category/sub-sub-category/`. If you think you need three levels, you actually need a new top-level category — file the ADR.
2. **One file, one tool / topic.** Don't combine `git+svn` into `vcs.mk`. They get two files inside `vcs/`.
3. **Namespace mirrors path.** A target `git:status` lives in `vcs/git.mk`. A docs page `docs/tools/vcs/git.md` links to `.sange/makefiles/vcs/git.mk`. A prompt template `.sange/prompts/commit/feat.tmpl` maps to the commit-template `commit-templates/type/feat.toml`. Predictability beats cleverness.
4. **`_core/` is sacred.** No tool-specific content. If you put `git.mk` inside `_core/` you have created a bug.
5. **`_local/` is gitignored by default** and listed in `.sange/gitignore/profiles/_core/secrets.gitignore` so the gitignore-swap (§6.5) cannot expose it accidentally.
6. **Adding a new category requires an ADR.** The category list is the public surface — plugins, marketplace entries, and `sange doctor` checks depend on it.
7. **Renaming a category requires a migration shim.** `sange update-makefiles` ships a one-shot rename map so user repos upgrade without breaking.
8. **`sange doctor` enforces the layout.** Flat fragments (`.sange/makefiles/git.mk` instead of `.sange/makefiles/vcs/git.mk`) are flagged; the user runs `sange fix --reorganize` to migrate.

#### 10.4.3 Where the convention applies

| Tree | §-reference | Subgrouped? |
|---|---|---|
| `.sange/makefiles/` | §10.2 | ✓ |
| `.sange/gitignore/profiles/` | §6.4 | ✓ |
| `.sange/commit-templates/` | §6.4 + §6.8.5 | ✓ (`_core/`, `type/`, `workflow/`, `domain/`, `user/`) |
| `.sange/prompts/` | §6.4 + §6.7.1 | ✓ (`_core/`, `commit/`, `pr/`, `changelog/`, `review/`, `explain/`, `branch/`, `release-notes/`) |
| `.sange/workflows/` | §6.4 + §7.5 | ✓ (`_core/`, then one per CI provider — `github/`, `gitlab/`, etc.) |
| `.sange/hooks/` | §6.4 + §7.4 | ✓ (by git hook stage — `pre-commit/`, `prepare-commit-msg/`, `commit-msg/`, `pre-push/`, `post-merge/`, plus `_core/`) |
| `.sange/bundles/manifests/` | §6.9 | ✓ (`_core/` skeletons + per-bundle files) |
| `src/sange/templates/` | §16.2 | ✓ (same convention; the source of truth Sange materializes into a consumer repo's `.sange/`) |
| `docs/tools/` | §16.3.2 | ✓ (`vcs/`, `lang/`, `framework/`, `infra/`, `ci/`, `release/`, `security/`, `ai/`, `ui/`, `ops/`) |
| `docs/adr/` | §16.3.2 | flat (chronological — each ADR is a singleton) |
| `docs/reference/` | §16.3.2 | flat (each file is the canonical reference for its topic) |
| `.sange/audit/` | §6.4 + §7.0.7 | flat (chronological) — categories don't apply to logs |
| `.sange/telemetry/` | §6.4 + §12 | flat (chronological weekly rotation) |

### 🔴 Red-Team Pass for §10

1. What if a user *does* commit `Makefile`? Recovery procedure must be documented.
2. What if a fragment is malicious (hostile Sange plugin wrote a fragment)? Fragment hash verification against signed manifest, keyed by `<category>/<fragment>` path so a fragment moved between categories is detected.
3. What if `make` is invoked in a non-Sange project with the same file layout coincidentally? Detect via `.sange/` presence; refuse otherwise.
4. What if a third-party plugin invents its own category (`.sange/makefiles/myplugin/foo.mk`)? Sange's loader only globs the canonical category list from §10.4.1; unrecognised categories are ignored with a warning and surfaced in `sange doctor`. Plugins extend an existing category or file an ADR for a new one.
5. What if a user has a flat `.sange/makefiles/git.mk` left over from v0.1? `sange doctor` detects flat fragments and offers `sange fix --reorganize` to move them under the correct category.

---

## 11. SECURITY REQUIREMENTS (expanded)

Produce a dedicated **Threat Model** section using STRIDE. Cover at minimum:

| Concern | Mitigation |
|---|---|
| Curl-pipe-sh installer compromise | Pinned checksums, sigstore signatures, mirror plan, reproducible builds, SLSA 3 |
| Prompt injection via repo content | Delimiter discipline, output validation, confirmation gates, content firewall, ≥3 independent controls |
| Secret exfiltration via AI provider | Redaction layer scrubs diffs before egress |
| Config tampering | `~/.sange/` perms `0700`; optional signed config |
| Plugin malice | Signed manifests, capability declarations, denied-by-default network/FS |
| Supply chain | SLSA 3 builds, SBOM per release, dependency pinning, `pip-audit`, `composer audit`, `npm audit` |
| Token theft | OS keychain default, scoped tokens, automatic rotation reminders, never logged |
| Hostile MCP server | Allowlist, capability prompts, response schema validation |
| Symlink / path traversal in `.sange/` ops | Canonicalize, refuse paths outside repo root |
| Race conditions on gitignore swap | File lock + atomic rename, abort on concurrent VCS op, recovery file on SIGKILL |
| Web UI CSRF | Laravel CSRF + Origin validation + SameSite=Strict |
| Web UI DNS rebinding | Host header validation against allowlist |
| IPC tampering | HMAC-signed (local); mTLS (remote); rotating shared secret in memory only |
| Daemon escalation | Run as user, no setuid, capability dropping where applicable |
| Audit log tampering | Append-only file with hash chain; optional external SIEM forward |
| Remote-mode exposure | mTLS mandatory, MFA mandatory, IP allowlist for direct VPS, no remote without setup-wizard completion |
| Cloudflare Tunnel token theft | Tunnel tokens in OS keychain; rotation supported; tunnel-bound to a single sange instance |
| Bundle signature substitution | Sigstore + provenance attestation + remote verify command |
| Bundle downgrade attack | Channel monotonicity enforced; rollback explicit and logged |
| Container secret leak | tmpfs mounts, `mlock`, no env-var persistence past startup, `sange doctor --container` audit |
| Commit JSON tampering | Sidecar integrity hash; mismatch produces warning + audit entry; status transitions CAS-protected |

**No security control may be enabled-by-config-only. Defaults must be secure.**

---

## 12. PRIVACY, TELEMETRY, AND DATA HANDLING

### 12.1 v1 — Local telemetry only

Sange collects **local telemetry** from v1: operation counts, latencies, error rates, AI cost trends, feature usage. **Nothing is sent off-machine in v1.**

- Stored in `.sange/telemetry/` (per-repo) and `~/.sange/telemetry/` (global)
- Format: NDJSON, append-only, rotated weekly
- Inspectable via `sange telemetry view` and the Web UI Telemetry module (§8.2.17)
- Sensitive fields (repo paths, branch names, commit messages, file names) are hashed before storage by default; opt-in to store plaintext locally for richer local analytics

### 12.2 v2+ — Opt-in external send

A future feature lets the user opt-in to send aggregated, anonymized telemetry to a Sange-operated endpoint for product improvement.

- **Off by default**
- Preview pane shows the exact payload before any send
- User configures endpoint (Sange-hosted, self-hosted, or none)
- Sending is interrupted on any network/timeout failure with no retry
- A redaction policy is configurable per-project and per-user
- No identifiers — not the user, not the machine, not the repo
- Aggregation window minimum 24 hours so individual operations are unlinkable
- Opt-out is one toggle and effective immediately; the local data is unaffected

### 12.3 AI provider disclosure

- All AI calls disclose which provider is being called and approximately what data is being sent
- A "what was sent" inspector shows the exact LLM payload for any operation (also useful for prompt-injection forensics)
- AI provider terms of service are surfaced in `sange ai providers` so the user knows whose data policies they're agreeing to

---

## 13. OBSERVABILITY

- Structured logging (JSON Lines) by default; pretty mode for TTY
- Log levels: `trace`, `debug`, `info`, `warn`, `error`, `fatal`
- Per-component log levels
- Sensitive values automatically redacted
- Optional OpenTelemetry export to a local collector
- Metrics: command latency, AI token usage, error rates, queue depths, IPC round-trip times
- Health endpoint on the daemon for the web UI to poll
- Crash dumps respect `RLIMIT_CORE=0` policy where secrets may be in memory

---

## 14. VERSION ROADMAP

### 14.1 v0.1 — MVP (single-developer, single-VCS)
**Scope:** Git only. CLI only. AI commit messages (full lifecycle from §6.8). `.sange/` folder. Modular Makefile system (§10). Basic hooks. Local telemetry. No web UI.
**Exit criteria:** A developer can install, init a repo, generate a commit message, take it through draft → approved → committed → pushed on macOS, Linux, Windows.
**Deferred:** SVN, web UI, scheduler, CI/CD companion, release engineering, bundling.

### 14.2 v0.5 — Beta
**Scope:** SVN adapter, gitignore-swap, hooks engine, secret scanning, Docker packaging with container-secret management (§6.10), `sange doctor`, `sange bootstrap`, prompt enhancer (§6.7.1), expanded commit template library (50+ presets). **VCS History Purge** (§6.11) ships **read-only** here: `sange purge plan / mirror / scan / analyze / preview / notify` are functional; destructive subcommands (`execute`, `push`, `rollback`) are stubbed with a "v1.0 only" error. CLI/TUI presentation conventions (§7.0) are mandatory from v0.5 onward.
**Exit criteria:** Feature-complete for solo developers; 50+ external testers; zero critical security findings.

### 14.3 v1.0 — General Availability
**Scope:**
- Web UI (Laravel 13 + Livewire 4 + `laravel/passkeys`, all 21 modules from §8.2)
- Remote access via Cloudflare Tunnel / Tailscale / WireGuard / reverse proxy (§8.5)
- Release engineering with bundling (§6.9)
- CI/CD companion
- Plugin system with signed marketplace
- Comprehensive command catalogs (Appendices D, E, F)
- MCP client + MCP server
- Full documentation site at `sange.sh`
- **History Purge destructive operations** (`sange purge execute / push / rollback`) for Git only; SVN/Hg purge slip to v2.0; Perforce to v3.0

**Exit criteria:** Stable API, semver guarantees, SLSA 3 releases, OpenSSF Scorecard ≥ 8.0, ≥3 third-party plugins.

### 14.4 v2.0 — Multi-VCS & Workflow
**Scope:** Mercurial, Fossil, Pijul adapters. Workflow builder. Advanced rollback. **Opt-in external telemetry send** (§12.2). Workers / edge-function plugin scaffolds. Cloudflare Workers integration for edge auth gateway.
**Exit criteria:** Cross-VCS concept map fully implemented; workflow library with 20+ presets.

### 14.5 v3.0 — Enterprise & Team
**Scope:** Perforce, Plastic SCM, Sapling. Distributed/team mode with optional self-hosted sync server. SAML / OIDC SSO. Team policies. SIEM audit-log forwarding. Sange Cloud (optional, self-hostable).
**Exit criteria:** SOC 2 readiness checklist; one Fortune 500 design-partner deployment.

### 14.6 v4.0+ — Speculative
IDE deep integration; federation across Sange instances; on-device fine-tuning per repo style.

---

## 15. DECISIONS MADE (no longer open — these are accepted ADRs)

| # | Decision | Recorded ADR |
|---|---|---|
| D0 | Architecture: Python core daemon (`sanged`) + Laravel web UI client, decoupled by JSON-RPC 2.0 over loopback (HMAC) or mTLS (remote). CLI/TUI talks to the same daemon. | **ADR-001** |
| D1 | Web UI: Laravel 13 + **Livewire 4** + PHP 8.3 floor / 8.4 recommended. Passkey support via first-party-but-separate `laravel/passkeys` (Composer) + `@laravel/passkeys` (npm), released 2026-05-12 (not Laravel 13 core). | **ADR-002** |
| D2 | Auth: WebAuthn passkey primary; PIN fallback; password alternative (Argon2id + HIBP k-anonymity) | **ADR-006** |
| D3 | DB: SQLite default, full multi-DB support via Laravel abstraction (PostgreSQL, MySQL/MariaDB, SQL Server) | **ADR-004** |
| D4 | License: Apache 2.0, © Simtabi LLC | **ADR-007** |
| D5 | Telemetry: local-only in v1; opt-in external send in v2+ | **ADR-008** |
| D6 | AI: BYOK + MCP client + MCP server + Prompt Enhancer (§6.7.1) | **ADR-005** |
| D7 | Config: both TOML and JSON, picked per file by extension | **ADR-009** |
| D8 | Remote web UI: supported from v1 via Cloudflare Tunnel / Tailscale / WireGuard / reverse proxy (§8.5) | **ADR-010** |
| D9 | Release bundling supported from v1 (§6.9); container VCS secret mgmt from v0.5 (§6.10) | **ADR-011 / ADR-012** |
| D10 | Do **not** use Laravel 13's first-party AI SDK (`Laravel\Ai\…`) in the web layer. All AI calls go through the Python core's enhancer + provider abstraction via JSON-RPC. One AI implementation, one redaction layer, one audit trail. | **ADR-003** |
| D11 | `sanged` daemon supervision: `launchd` (macOS user agent), `systemd --user` (Linux), Windows Service via `pywin32` (preferred) with NSSM/WinSW fallback. Daemon never runs as root/admin; capabilities dropped post-start. | **ADR-013** |
| D12 | Etymology framing: "named after the *sengi* (Swahili for elephant shrew), stylized as 'Sange' for branding." Do not assert *sange* is itself a Swahili dictionary word. | **ADR-014** |
| D13 | URL scheme: canonical metadata uses `opensource.simtabi.com/products/sange` and `opensource.simtabi.com/documentation/sange`; `sange.sh` is the marketing redirect. Repo at `github.com/simtabi/sange`. | **ADR-015** |
| D14 | Final v3 source-repo layout per §16.2. v1/v2 sub-directories are deleted post-handoff; v3 occupies the sange repository root. | **ADR-016** |
| D15 | Documentation: one root `README.md` (index + install + tagline only) + the manual under `docs/` split per-tool, per-topic. The full consolidated `sange-architecture.md` exists *only* inside the architecture deliverable bundle and `docs/architecture.md` mirrors a condensed read of it. | **ADR-017** |
| D16 | VCS history-purge subsystem (§6.11) is **synchronous, interactive, CLI/TUI-initiated only**. No async background workers; no scheduled / cron purges; no phased / partial rollout; web UI cannot execute the destructive transition. `--batch` mode requires four explicit precondition flags and is rate-limited per operator. | **ADR-018** |
| D17 | CLI / TUI library stack: `typer` + `rich` + `questionary` + `textual` (TUI-only) + `structlog` + `wcwidth` + `shellingham` + `python-magic` + stdlib `asyncio`/`subprocess`. Disallowed by default: `tqdm`, `colorama`, `inquirer`, `loguru`, `plumbum`/`sh`, `click`. Encoding auto-detection on startup produces a `TerminalProfile` that drives emoji and Unicode-box-character usage; `cmd.exe`/`cp1252`/MSYS2/`LC_ALL=C` SSH fall back to ASCII. | **ADR-019** |
| D18 | Premade Operations Kit (§6.12) is **curated, signed, and versioned** — Sange does not download arbitrary remote content at run-time. The kit ships inside the Sange package; updates ride Sange releases; `templates/MANIFEST.toml.sig` gates materialization. Plugin-provided fragments are signed-manifest-required and provenance-tagged. The kit covers: CI workflows (8 providers), release bundlers (8 tools), push-to-prod strategies (9 patterns), VPS provisioning (cloud-init + Ansible + Terraform + Caddy + monitoring) — all per CIS / Google SRE / OWASP / SLSA best-practice anchors. | **ADR-020** |
| D19 | Subgrouped Category convention (§10.4) is canonical for every Sange file-fragment tree: `_core/`, `_local/`, plus purpose-named sub-directories from the canonical list (`vcs/`, `lang/`, `framework/`, `infra/`, `cloud/`, `ci/`, `release/`, `security/`, `ai/`, `db/`, `editor/`, `os/`, `domain/`, `type/`, `workflow/`). Flat fragments are a quality-gate failure. New categories require an ADR. | **ADR-021** |
| D20 | Sange does **not** replace existing VCS tools; it is a workflow / DX layer wrapping them. Audience scope (§3) covers seven personas (non-dev founder, CTO, cyber-sec reviewer, junior engineer, senior staff engineer, DevOps/SRE, OSS maintainer); the happy path is usable by the first and the fourth personas without configuration. Engineering bar: SOLID + DRY + KISS + zero internal repetition + no design flaws + enterprise/military-grade security + simple-yet-powerful. | **ADR-022** |
| D21 | Generate-first, fine-tune-second (§2.4 + §16.4). Token-heavy deliverable sections (catalogs, manifest, docs index, exit codes, CLI reference, JSON-RPC schema, config schema) are produced by **deterministic generator scripts** under `tools/generators/`, not hand-typed. Every generated file carries a frontmatter block with `output_sha256`; `verify_generated.py` enforces integrity in CI. The responding model fine-tunes prose-bearing additions only. | **ADR-023** |
| D22 | One question at a time (§1 + §7.0.9). The responding model (when executing this prompt) and Sange itself (CLI / TUI / Web UI) ask **one confirmation question per interaction**, never batched. Confirmations are sequential so the operator can stop the sequence at any point. Multi-field information-entry forms remain allowed. | **ADR-024** |
| D23 | Godmode workbook framing (§0) + fluent / chainable OOP API style (§6.13). The prompt + `.design/plans/` artifacts + `sange-architecture.md` together form an agency-reusable workbook; per-section `🟡 META` / `🟦 SANGE` markers indicate which content travels to future projects. Every Sange domain object exposes a chainable API alongside its data-class form (`@chainable` decorator in `src/sange/utils/fluent.py`); chain methods return `self` and are side-effect-free until an explicit terminal verb (`.execute()`, `.push()`, `.materialize()`). | **ADR-025** |
| D26 | Session-log artifact + audit-after-every-task method (`.design/plans/session-log.md`). Every completed task / accepted ADR / closed risk / meaningful file change / clarifying-Q-answer exchange appends a row with `id, timestamp, actor, surface, action, files_touched, linked, audit_chain, notes`. Append-only; integrity via `linked` cross-references to other artifacts (ADRs, risks, prompt §-anchors, git commits). When v0.1 runtime audit chain exists, `tools/generators/session_log.py` emits design-time rows from runtime entries automatically; until then, manual append is the rule. | **ADR-028** |
| D28 | **Anti-hallucination discipline** (§2.5.1). Read before reference. Cite source. No invented IDs / file paths / versions / API shapes. "Cannot verify" is allowed; guessing is not. Uncertainty markers `🟡 UNVERIFIED`, `✅ Verified`, `❌ Refuted` are inline. Generator output is authoritative; the model never paraphrases catalog content from memory when the file is on disk. Red-team passes test for unverified claims. AI outputs flow through the §6.7.1 prompt enhancer + validator + redaction layer before joining the audit chain. | **ADR-030** |
| D29 | **Memory preservation discipline** (§2.5.2). `.design/` is the memory; chat is ephemeral. Session-log row after every completed task (extends ADR-028 with the new `grounding` column). Phase-boundary snapshots in `.design/plans/snapshots/phase-N.M.md` capturing state for cold-resume. Crash-recovery protocol (read session-log → `git status` → `.sange/.recovery` → in-flight purge state → snapshot → resume). Resumability test at each phase boundary: a fresh session given only `.design/` access can correctly state "next thing to do is X." Audit-chain integrity spans the project's lifetime. | **ADR-031** |
| D27 | Generators scaffold *everything* (§2.4.1) — not only the deliverable's catalog appendices, but also the v3 Python source skeleton, the kit fragments, the per-tool docs index, the 35 profile-registry TOMLs, the `.github/workflows/*.yml`, the Dockerfile + compose, the `.sange/` template. A fresh clone with no business logic can run `python tools/generators/all.py --write` and produce most of the surrounding scaffolding; humans build the business logic (commit lifecycle, purge state machine, prompt enhancer) by hand. Strengthens ADR-023; the §22 execution-order step 5 is the canonical sequence. | **ADR-029** |
| D25 | `.design/` workbook layout at the repo root (`.design/sange-architecture-prompt.md` + `.design/sange-architecture.md` + `.design/plans/*.md`). Confirmed by user reorganization (2026-05-13, v4.2). Canonical for all future agency projects per ADR-025 (godmode workbook) — fork `.design/` as the template for any new project's design metadata. Code lives at the repo root *alongside* `.design/`; the two never overlap. **Codebase target path locked: in-place** at `/Users/imanimanyara/Artisan/projects/opensource/sange/` (closing prior `R-001` open question). | **ADR-027** |
| D24 | Profile Registry (§6.5.1) is the source of truth for supported languages / frameworks / infrastructure / editors / OS layers. v1.0 ships 35 profiles (Python, Node, PHP, Go, Rust, Ruby, Java, .NET, Elixir, Swift, Kotlin, Dart, Laravel, Django, Rails, Next.js, Nuxt, Symfony, Astro, SvelteKit, Flutter, Docker, Kubernetes, Terraform, Ansible, Pulumi, JetBrains, VSCode, Vim, Emacs, Claude, macOS, Windows, Linux, plus `_core/secrets` and `_core/editor-noise`). Each declares file-presence auto-detect signals, `always` / `dev_only` / `prod_only` pattern blocks, and version + maintainer. Per-project activation via `sange profile use` writing to `.sange/config.toml::gitignore.{dev,prod}.profiles`. Registry is generated by `tools/generators/profile_registry.py` (T-G-015) and must round-trip cleanly. Profile renames are forbidden in minor releases. | **ADR-026** |

Any further question that comes up during implementation must be recorded as a new ADR; the responding model does not pause to ask the user except on truly novel ambiguities not covered by the above.

---

## 16. DELIVERABLES

This section is split into three distinct artifact bundles. They are produced in this order:

1. **§16.1 — Architecture document bundle** (review artifact, sits beside the repo during planning)
2. **§16.2 — Final v3 source-repository layout** (the on-disk layout the codebase will live in)
3. **§16.3 — Documentation strategy** (how `README.md` + `docs/` are split and linked)

### 16.1 Architecture document bundle (review artifact)

Produced during the design phase; lives at the parent of the sange repo until v3 development begins, then merged into `docs/`. The single consolidated `sange-architecture.md` survives only inside this bundle — the manual itself is split into `docs/` per §16.3.

```
sange-architecture/                    # transient, design-time deliverable
├── sange-architecture.md              # consolidated reference (≈30–50k words)
├── diagrams/
│   ├── layered-architecture.mmd
│   ├── deployment-local.mmd
│   ├── deployment-remote.mmd
│   ├── ipc-flow.mmd
│   ├── gitignore-swap-sequence.mmd
│   ├── commit-lifecycle-state-machine.mmd
│   ├── bundle-lifecycle.mmd
│   ├── web-ui-modules.mmd
│   ├── prompt-enhancer-flow.mmd
│   ├── daemon-supervision.mmd
│   ├── mcp-topology.mmd
│   └── threat-model-data-flow.mmd
├── appendices/
│   ├── A-command-vocabulary.md          # from Mukora Makefiles
│   ├── B-v1-v2-audit.md                 # comprehensive audit + defect log; verbatim DEFAULT_GIT_COMMIT_MESSAGES capture
│   ├── B1-v1-v2-divergence.md           # explicit v2 regression list (deleted files)
│   ├── C-sample-configs.md
│   ├── D-git-command-catalog.md
│   ├── E-svn-command-catalog.md
│   ├── F-cross-vcs-concept-map.md
│   ├── G-commit-template-library.md     # ≥50 normalized presets + v1→v3 migration table for the 104 legacy strings
│   ├── H-references.md
│   ├── I-glossary.md
│   └── J-adr-index.md                   # one-line summary per ADR (mirrors docs/adr/README.md)
└── CHECKLIST.md                          # the implementation checklist (~350 tasks)
```

### 16.2 Final v3 source-repository layout (the actual on-disk codebase)

✅ **Path locked (2026-05-13, user-confirmed):** The v3 codebase lives **in-place** at `/Users/imanimanyara/Artisan/projects/opensource/sange/`. After v1/v2 sub-directory deletion, the v3 codebase fills the existing repo root. This preserves the `github.com/simtabi/sange` git remote, the Simtabi org-tree convention from `/Users/imanimanyara/Artisan/projects/opensource/CLAUDE.md`, and the existing git history.

**Design-time companion folder.** The architecture prompt, the `sange-architecture.md` deliverable, and the `.design/plans/` companion folder all live under `.design/` at the repo root — a dotfile folder that signals "design metadata, not source code" to readers. This was confirmed by the user reorganizing the on-disk layout (v4.2). The arrangement is canonical for **all** future agency projects per ADR-025 + ADR-027 — fork `/Users/imanimanyara/Artisan/projects/opensource/sange/.design/` as the template for any new project's design workbook.

Current `.design/` contents:

```
.design/
├── sange-architecture-prompt.md     # the workbook (this file) — v4.2
├── sange-architecture.md            # the deliverable narrative — items §17.1–§17.17 hand-authored
└── plans/                           # the hand-off folder (9 files)
    ├── README.md
    ├── positioning.md
    ├── implementation-plan.md
    ├── checklist.md
    ├── content-audit.md
    ├── decisions-log.md
    ├── traceability-matrix.md
    ├── quality-gates.md
    └── risk-register.md
```

The source-tree layout below is the **`src/`-and-everything-else** layout for the v3 codebase — independent of `.design/`. The two coexist at the repo root:

```
sange/                                # v3 repo root
├── README.md                         # tagline + install + links to docs/ — see §16.3
├── LICENSE                           # Apache 2.0, "Copyright (c) 2026 Simtabi LLC"
├── CHANGELOG.md                      # Keep a Changelog, SemVer
├── CONTRIBUTING.md                   # PR rules, branch model, ADR process
├── SECURITY.md                       # disclosure → opensource@simtabi.com (per CLAUDE.md)
├── CODE_OF_CONDUCT.md                # Contributor Covenant 2.1 → opensource@simtabi.com
├── AUTHORS.md                        # Simtabi LLC <opensource@simtabi.com>; maintainer Imani Manyara
├── NOTICE                            # Apache 2.0 attribution notice for vendored OSS
├── .editorconfig                     # UTF-8, LF, final newline, trim trailing ws
├── .gitignore                        # language-appropriate; the auto-generated user-Makefile-shim entry; .sange/secrets/; .DS_Store
├── .gitattributes                    # line endings, linguist hints, binary markers, REUSE/SPDX
├── pyproject.toml                    # hatchling backend; Python 3.12+ floor; PEP 621
├── uv.lock                           # or poetry.lock — single lockfile, pinned
├── ruff.toml                         # E,F,W,I,N,UP,B,SIM,RUF (per CLAUDE.md global)
├── mypy.ini                          # --strict
├── .pre-commit-config.yaml           # ruff, mypy, gitleaks, shellcheck, hadolint, prettier
├── Dockerfile                        # multi-stage; python:3.12-slim base pinned by digest; non-root
├── docker-compose.yml                # local dev composition; mounts SSH agent socket
├── docker-compose.daemon.yml         # standalone sanged container for CI
├── Makefile                          # **Sange-development-only** Makefile (not for consumer repos). Tracked because this *is* the Sange repo.
├── .github/
│   ├── workflows/
│   │   ├── ci.yml                    # lint, type-check, test, build
│   │   ├── release.yml               # tag-driven; OIDC trusted publishing to PyPI + Packagist
│   │   ├── security-scan.yml         # pip-audit, composer audit, npm audit, gitleaks
│   │   ├── sbom.yml                  # CycloneDX SBOM per release
│   │   ├── sigstore.yml              # SLSA 3 provenance + sigstore signing
│   │   ├── docs.yml                  # build + deploy docs to opensource.simtabi.com/documentation/sange
│   │   └── codeql.yml                # static analysis
│   ├── dependabot.yml                # weekly, Monday 06:00 America/New_York (per CLAUDE.md global)
│   ├── ISSUE_TEMPLATE/{bug_report,feature_request,config}.yml
│   ├── PULL_REQUEST_TEMPLATE.md
│   ├── CODEOWNERS
│   └── FUNDING.yml                   # (only if Simtabi opts in)
├── src/sange/                        # Python package (PEP 561 typed)
│   ├── __init__.py
│   ├── py.typed                      # PEP 561 marker
│   ├── _version.py                   # single source of version truth
│   ├── cli/                          # typer + rich + questionary
│   │   ├── __init__.py
│   │   ├── app.py
│   │   ├── commits.py                # sange commits ...
│   │   ├── bundle.py                 # sange bundle ...
│   │   ├── secrets.py
│   │   ├── ai.py                     # sange ai preview | providers | mcp
│   │   ├── ci.py
│   │   ├── doctor.py
│   │   └── ...
│   ├── tui/                          # textual app (shares core)
│   │   └── app.py
│   ├── core/                         # the application + domain layers from §6.2
│   │   ├── config.py                 # SangeConfig pydantic v2 model
│   │   ├── models/                   # Repo, Commit, Branch, Release, Bundle, Approval, AuditEntry, PurgePlan
│   │   ├── lifecycle/                # commit lifecycle state machine + JSON schema
│   │   ├── enhancer/                 # prompt enhancer (§6.7.1)
│   │   ├── scheduler/                # local cron-equivalent
│   │   ├── audit/                    # append-only log with hash chain
│   │   ├── policy/                   # hooks, secret scanning, large-file warner
│   │   ├── purge/                    # history-purge subsystem (§6.11): planner, mirror, gates, executor, verifier
│   │   │   ├── plan.py
│   │   │   ├── gates.py              # the §6.11.4 gate functions
│   │   │   ├── mirror.py             # backup + fresh-clone management
│   │   │   ├── analyzer.py           # filter-repo --analyze wrapper + svndumpfilter equivalent
│   │   │   ├── executor.py           # git filter-repo / BFG / svndumpfilter / hg convert / p4 obliterate dispatch
│   │   │   ├── verifier.py           # the §6.11.5 checks
│   │   │   └── ticket.py             # platform-support ticket payloads
│   │   ├── ui/                       # TerminalProfile, tree, progress, typed-phrase gate (§7.0)
│   │   └── scanners/                 # gitleaks + trufflehog wrappers; shared with §6.11 and §7.4
│   ├── adapters/
│   │   ├── vcs/
│   │   │   ├── _protocol.py          # VCSDriver Protocol
│   │   │   ├── git.py
│   │   │   └── svn.py                # v0.5
│   │   ├── ai/
│   │   │   ├── _protocol.py          # AIProvider Protocol
│   │   │   ├── anthropic.py
│   │   │   ├── openai.py
│   │   │   ├── ollama.py
│   │   │   ├── gemini.py
│   │   │   ├── bedrock.py
│   │   │   └── azure_openai.py
│   │   ├── mcp/                      # MCP client + server (§6.7)
│   │   │   ├── client.py
│   │   │   ├── server.py
│   │   │   └── transports/           # stdio, http_sse, streamable_http
│   │   ├── secrets/                  # keyring, vault, 1password, age, gpg
│   │   ├── containers/               # docker / podman
│   │   └── notifiers/                # desktop notifications
│   ├── daemon/                       # the sanged process
│   │   ├── __main__.py               # entry point
│   │   ├── server.py                 # JSON-RPC 2.0 server (HMAC local; mTLS remote)
│   │   ├── supervisor/               # launchd / systemd / pywin32 plists & units
│   │   └── health.py                 # /healthz endpoint
│   ├── ipc/
│   │   ├── schema/                   # versioned JSON-RPC method schemas
│   │   ├── hmac.py
│   │   └── mtls.py
│   ├── installer/                    # bootstrap, doctor, package detection
│   │   ├── doctor.py
│   │   ├── bootstrap.py              # brew / scoop / apt / mise / asdf orchestration
│   │   └── recover.py                # sange recover, sange fix-makefile-tracked
│   ├── plugins/                      # entry-point sandbox + signature verification
│   │   ├── loader.py
│   │   ├── capabilities.py
│   │   └── signature.py
│   └── utils/                        # logging, hashing, paths
├── web/                              # Laravel 13 web UI (Composer + npm root)
│   ├── composer.json                 # laravel/framework: ^13.0, laravel/passkeys: ^<pinned>, livewire/livewire: ^4.3
│   ├── package.json                  # @laravel/passkeys, vite, etc.
│   ├── artisan
│   ├── bootstrap/
│   ├── config/
│   │   ├── app.php
│   │   ├── auth.php
│   │   ├── passkeys.php              # laravel/passkeys config
│   │   └── sange.php                 # IPC daemon URL, HMAC key path, mode (local/LAN/remote)
│   ├── routes/web.php
│   ├── app/
│   │   ├── Livewire/                 # Livewire 4 components for each §8.2 module
│   │   ├── Http/Controllers/         # IPC bridge controllers (thin)
│   │   ├── Services/                 # Sange JSON-RPC client; never duplicates core logic
│   │   └── Policies/                 # authorization
│   ├── resources/views/
│   ├── resources/js/
│   ├── database/
│   │   ├── migrations/
│   │   └── seeders/
│   ├── tests/                        # Pest 3 (Pest's Laravel 13 release)
│   └── public/
├── installer/                        # one-liner installer per OS — §7.1
│   ├── install.sh                    # unix one-liner consumed via curl|sh
│   ├── install.ps1                   # windows
│   ├── checksums.txt                 # signed
│   ├── checksums.txt.sig             # sigstore signature
│   ├── verify.sh                     # consumer-runnable verifier
│   ├── verify.ps1
│   └── homebrew/                     # tap formula stub
├── container/
│   ├── Dockerfile.daemon             # sanged runtime
│   ├── Dockerfile.runner             # CI runner image
│   └── compose/                      # docker-compose presets for common scenarios
├── templates/                        # source-of-truth files Sange materializes into a consumer repo's .sange/ — every sub-tree follows the §10.4 Category convention
│   ├── sange-folder/                 # the canonical .sange/ skeleton (§6.4)
│   ├── makefiles/                    # mirrors §10.2: _core/, vcs/, lang/, framework/, infra/, ci/, release/, security/, ai/, db/, _local/
│   │   ├── _core/                    # help.mk, colors.mk, env.mk
│   │   ├── vcs/                      # git.mk, svn.mk, hg.mk, p4.mk
│   │   ├── lang/                     # python.mk, node.mk, php.mk, go.mk, rust.mk, ruby.mk
│   │   ├── framework/                # laravel.mk, django.mk, rails.mk, nextjs.mk
│   │   ├── infra/                    # docker.mk, compose.mk, kubernetes.mk, terraform.mk
│   │   ├── ci/                       # github.mk, gitlab.mk, azure.mk, bitbucket.mk, jenkins.mk
│   │   ├── release/                  # semver.mk, changelog.mk, bundle.mk, sign.mk
│   │   ├── security/                 # scan.mk, purge.mk
│   │   ├── ai/                       # providers.mk, mcp.mk
│   │   └── db/                       # postgres.mk, mysql.mk, sqlite.mk
│   ├── commit-templates/             # mirrors §6.4 commit-templates layout
│   │   ├── default.toml              # the curated ≥50-preset library (Appendix G)
│   │   ├── _core/                    # conventional.tmpl, header-footer.tmpl
│   │   ├── type/                     # feat.toml, fix.toml, docs.toml, style.toml, refactor.toml, perf.toml, test.toml, build.toml, ci.toml, chore.toml, revert.toml
│   │   ├── workflow/                 # release.toml, hotfix.toml, cherry-pick.toml, merge.toml, squash.toml, wip.toml, initial.toml
│   │   └── domain/                   # security.toml, deps.toml, license.toml
│   ├── prompts/                      # versioned LLM prompt templates — by task
│   │   ├── _core/                    # enhancer framework prompts
│   │   ├── commit/                   # commit-msg generation
│   │   ├── pr/                       # PR description
│   │   ├── changelog/                # release changelog
│   │   ├── review/                   # code review
│   │   ├── explain/                  # diff / commit explanation
│   │   ├── branch/                   # branch naming
│   │   └── release-notes/
│   ├── gitignore-profiles/           # mirrors §6.4 gitignore profile layout
│   │   ├── _core/                    # secrets.gitignore, editor-noise.gitignore
│   │   ├── lang/                     # python, node, php, go, rust, ruby, java
│   │   ├── framework/                # laravel, django, rails, nextjs, nuxt, symfony
│   │   ├── infra/                    # docker, kubernetes, terraform
│   │   ├── editor/                   # jetbrains, vscode, vim, emacs, claude
│   │   └── os/                       # macos, windows, linux
│   ├── workflows/                    # CI workflow scaffolds — one sub-directory per provider
│   │   ├── _core/                    # provider-agnostic stage definitions
│   │   ├── github/                   # .github/workflows/*.yml ready to copy
│   │   ├── gitlab/                   # .gitlab-ci.yml fragments
│   │   ├── azure/                    # azure-pipelines.yml fragments
│   │   ├── bitbucket/                # bitbucket-pipelines.yml fragments
│   │   ├── gitea/
│   │   ├── forgejo/
│   │   ├── circleci/                 # .circleci/config.yml fragments
│   │   └── jenkins/                  # Jenkinsfile fragments
│   ├── bundlers/                     # release-bundler scaffolds (§6.9) — see §6.12
│   │   ├── _core/                    # bundle-manifest skeletons
│   │   ├── goreleaser/               # .goreleaser.yaml + GitHub Actions integration
│   │   ├── semantic-release/         # .releaserc + GH/GL integration
│   │   ├── release-please/           # .release-please-config.json + manifest
│   │   ├── git-cliff/                # cliff.toml + invocation snippets
│   │   ├── changesets/               # .changeset/ skeleton
│   │   ├── pyinstaller/              # PyInstaller spec files
│   │   ├── electron-builder/         # electron-builder.yml
│   │   └── docker-oci/               # OCI artifact bundle scripts
│   ├── push-to-prod/                 # deploy strategies — see §6.12
│   │   ├── _core/                    # shared safety gates: drift check, smoke probe, rollback
│   │   ├── rolling/                  # rolling-restart patterns (k8s, compose, systemd)
│   │   ├── blue-green/               # blue/green patterns
│   │   ├── canary/                   # canary patterns with progressive traffic shifting
│   │   ├── ssh/                      # plain-old SSH-based deploy with atomic symlink swap
│   │   ├── compose/                  # docker compose pull + up -d patterns
│   │   ├── k8s/                      # kubectl apply / helm upgrade / argocd / flux
│   │   ├── nomad/
│   │   ├── ecs/                      # AWS ECS service-update patterns
│   │   └── cloudrun/                 # GCP Cloud Run revisions
│   ├── vps-setup/                    # VPS provisioning + hardening — see §6.12
│   │   ├── _core/                    # CIS-baseline-aligned hardening (ufw, fail2ban, unattended-upgrades, ssh hardening, auditd)
│   │   ├── cloud-init/               # per-provider cloud-init.yml
│   │   │   ├── hetzner.yml
│   │   │   ├── digitalocean.yml
│   │   │   ├── linode.yml
│   │   │   ├── vultr.yml
│   │   │   ├── ovh.yml
│   │   │   ├── scaleway.yml
│   │   │   ├── aws-ec2.yml
│   │   │   ├── gcp-ce.yml
│   │   │   └── azure-vm.yml
│   │   ├── ansible/                  # idempotent role-per-concern playbooks
│   │   │   ├── roles/
│   │   │   │   ├── base/             # OS hardening, time sync, locale
│   │   │   │   ├── ssh/              # key-only, port, ciphers, MaxAuthTries
│   │   │   │   ├── firewall/         # ufw / firewalld
│   │   │   │   ├── fail2ban/
│   │   │   │   ├── docker/
│   │   │   │   ├── compose/
│   │   │   │   ├── caddy/            # automatic-TLS reverse proxy
│   │   │   │   ├── nginx/
│   │   │   │   ├── postgres/
│   │   │   │   ├── mysql/
│   │   │   │   ├── redis/
│   │   │   │   ├── node-exporter/    # prometheus host metrics
│   │   │   │   ├── promtail/         # log shipping
│   │   │   │   ├── backup-restic/    # off-host backups
│   │   │   │   └── sanged/           # the Sange daemon on the VPS
│   │   │   ├── inventory.yml.example
│   │   │   └── site.yml
│   │   ├── terraform/                # IaC starter modules
│   │   │   ├── modules/
│   │   │   │   ├── hetzner-vm/
│   │   │   │   ├── do-droplet/
│   │   │   │   ├── aws-ec2/
│   │   │   │   ├── gcp-ce/
│   │   │   │   └── cloudflare-tunnel/
│   │   │   └── examples/
│   │   ├── docker/                   # standalone docker hosts (no Ansible)
│   │   │   ├── install.sh            # official Docker install script with hash-pinning
│   │   │   └── compose.yml.example
│   │   ├── caddyfiles/               # ready-to-use Caddyfile templates per workload
│   │   ├── nginx-confs/              # nginx alternatives
│   │   └── monitoring/               # Prometheus + Grafana + Loki bundle
│   ├── hooks/                        # mirrors §6.4 hooks layout (pre-commit/, prepare-commit-msg/, commit-msg/, pre-push/, post-merge/, _core/)
│   └── scripts/                      # general-purpose shell + python scripts; see §6.12
│       ├── _core/                    # lib.sh (color, log, exit codes), lib.py (rich-styled wrapper)
│       ├── bootstrap/                # brew, scoop, apt, mise, asdf orchestration scripts
│       ├── doctor/                   # health-probe scripts
│       ├── deploy/                   # one-shot deploy helpers paired with push-to-prod/ patterns
│       ├── backup/                   # restic / borg / rsync wrappers
│       ├── cron/                     # systemd-timer + cron snippets (host-side scheduler complements §8.2.8)
│       └── recovery/                 # disaster-recovery runbooks as executable scripts
├── tests/
│   ├── unit/                         # pure-Python tests
│   ├── integration/                  # subprocess, fake VCS repos, fake AI provider
│   ├── e2e/                          # CLI invocations end-to-end
│   ├── security/                     # fuzz, prompt-injection corpus, SLSA verification
│   ├── web/                          # Pest 3 + Laravel Dusk for browser e2e
│   └── fixtures/
├── tools/                            # developer-facing tooling (not shipped to users)
│   └── generators/                   # deterministic generators — see §16.4
│       ├── _lib/                     # output frontmatter, manpage parser, markdown helpers, fingerprint (sha256)
│       ├── git_catalog.py            # → appendices/D-git-command-catalog.md
│       ├── svn_catalog.py            # → appendices/E-svn-command-catalog.md
│       ├── hg_catalog.py             # v2.0
│       ├── p4_catalog.py             # v3.0
│       ├── cross_vcs_map.py          # → appendices/F-cross-vcs-concept-map.md
│       ├── commit_templates.py       # → appendices/G-commit-template-library.md (≥50 presets from v1's 104 + Conventional Commits 1.0.0)
│       ├── kit_manifest.py           # → templates/MANIFEST.toml (signed by CI via cosign)
│       ├── docs_index.py             # → docs/README.md + docs/tools/README.md
│       ├── adr_scaffold.py           # → docs/adr/NNNN-<slug>.md skeleton
│       ├── exit_codes.py             # → docs/reference/exit-codes.md
│       ├── cli_reference.py          # → docs/reference/cli-reference.md
│       ├── jsonrpc_schema.py         # → docs/reference/json-rpc-schema.md
│       ├── config_schema.py          # → docs/reference/config-schema.md
│       ├── threat_model_table.py     # → docs/security/stride.md
│       ├── changelog_from_commits.py # → docs/CHANGELOG.md
│       ├── all.py                    # orchestrator, dependency-ordered
│       └── verify_generated.py       # CI integrity check — recomputes output_sha256
└── docs/                             # the manual — see §16.3
    └── …
```

**Files inherited / restored from v1 explicitly:** The v2 deletions (`configs/config.sh`, `helpers/scripts/colors.sh`, `helpers/scripts/error_handler.sh`, `.github/`, `.sange/.state`) are **not restored** as shell files — instead, their *intent* is reimplemented in Python:

| v1 shell asset | v3 Python equivalent |
|---|---|
| `configs/config.sh::DEFAULT_GIT_COMMIT_MESSAGES` (104 entries) | `templates/commit-templates/default.toml` (≥50 normalized presets + `aliases` mapping the 104 legacy strings — Appendix G) |
| `helpers/scripts/colors.sh` | `rich` library + `src/sange/utils/colors.py` thin theming layer |
| `helpers/scripts/error_handler.sh` | `src/sange/utils/errors.py` (structured exceptions + crash dumps with `RLIMIT_CORE=0`) |
| `.github/` workflows (v1) | `.github/workflows/{ci,release,security-scan,sbom,sigstore,docs,codeql}.yml` redesigned |
| `.sange/.state` (v1) | `src/sange/core/audit/` (append-only hash-chained log) |

### 16.3 Documentation strategy

Per user instruction: **one root `README.md`** (index + tagline + install only) and **per-tool documentation under `docs/`**. The full architecture exists in two forms — a consolidated `sange-architecture.md` inside the §16.1 design-time bundle, and a split-by-topic mirror under `docs/`.

#### 16.3.1 Root `README.md` (≤300 lines)

- Tagline (the §3 product positioning sentence)
- Why Sange (3 bullets, no marketing prose)
- Quickstart (one-line install + first three commands)
- Status table (current version, supported OS matrix, license, security contact)
- **Index** — a single Markdown table that links **every** `docs/` file by topic
- Acknowledgements / sengi etymology one-liner
- Badges: CI status, latest release, license, OpenSSF Scorecard, SLSA level

The README is **not** the manual. Move every chapter-length piece of prose to `docs/`. The README's only job is to route the reader and make GitHub's preview useful.

#### 16.3.2 `docs/` tree

```
docs/
├── README.md                          # docs index — mirrors the root README's link table
├── installation.md
├── configuration.md                   # the SangeConfig schema, precedence rules, multi-DB strategy
├── architecture.md                    # condensed read of sange-architecture.md (the 30k-word version)
├── quickstart.md
├── release.md                         # release-engineering reference for this repo
├── shipping-checklist.md              # first-release D-list per CLAUDE.md
├── adr/                               # one Markdown file per ADR
│   ├── README.md                      # ADR index (mirrors §35 of sange-architecture.md)
│   ├── 0001-python-core-laravel-ui.md
│   ├── 0002-laravel-13-livewire-4.md
│   ├── 0003-no-laravel-ai-sdk.md
│   ├── 0004-multi-db.md
│   ├── 0005-prompt-enhancer.md
│   ├── 0006-auth-passkey-pin-password.md
│   ├── 0007-license-apache-2.md
│   ├── 0008-telemetry-local-v1.md
│   ├── 0009-config-toml-and-json.md
│   ├── 0010-remote-web-ui-v1.md
│   ├── 0011-release-bundling.md
│   ├── 0012-container-secrets.md
│   ├── 0013-sanged-daemon-supervision.md
│   ├── 0014-etymology-sengi-framing.md
│   ├── 0015-url-and-domain-scheme.md
│   ├── 0016-final-repo-layout.md
│   └── 0017-documentation-split.md
├── audit/
│   ├── v1.md                          # Appendix B for v1
│   ├── v2.md                          # Appendix B for v2
│   ├── divergence.md                  # Appendix B1
│   └── architecture-prompt.md         # this file, preserved post-handoff (option (a) of §16.2)
├── diagrams/                          # .mmd sources + generated SVG
│   └── …                              # exact list mirrors §16.1
├── tools/                             # one file per public tool/feature — subgrouped per §10.4 Category convention
│   ├── README.md                      # tools index (mirrors the docs/README index for tools/)
│   ├── vcs/                           # VCS-specific
│   │   ├── git.md
│   │   ├── svn.md                     # v0.5
│   │   ├── hg.md                      # v2.0
│   │   ├── fossil.md                  # v2.0
│   │   ├── pijul.md                   # v2.0
│   │   └── p4.md                      # v3.0
│   ├── lang/                          # language toolchains
│   │   ├── python.md
│   │   ├── node.md
│   │   ├── php.md
│   │   ├── go.md
│   │   ├── rust.md
│   │   └── ruby.md
│   ├── framework/                     # web/app frameworks
│   │   ├── laravel.md
│   │   ├── django.md
│   │   ├── rails.md
│   │   └── nextjs.md
│   ├── infra/                         # containers + orchestration
│   │   ├── docker.md
│   │   ├── compose.md
│   │   ├── kubernetes.md
│   │   └── terraform.md
│   ├── ci/                            # CI providers
│   │   ├── github-actions.md
│   │   ├── gitlab-ci.md
│   │   ├── azure-pipelines.md
│   │   ├── bitbucket-pipelines.md
│   │   ├── gitea-actions.md
│   │   ├── forgejo-actions.md
│   │   ├── circleci.md
│   │   ├── jenkins.md
│   │   └── act.md                     # local-runner companion
│   ├── release/                       # release engineering
│   │   ├── overview.md                # the release engine itself
│   │   ├── bundle.md                  # release bundling (§6.9)
│   │   ├── semver.md
│   │   ├── changelog.md
│   │   ├── sign.md                    # sigstore + GPG
│   │   ├── push-to-prod.md            # deploy strategies — see §6.12 + templates/push-to-prod/
│   │   └── bundlers.md                # goreleaser / semantic-release / release-please / git-cliff / changesets — see §6.12 + templates/bundlers/
│   ├── security/                      # scanners, purge, policy, secrets
│   │   ├── purge.md                   # history purge: refactored from user-supplied playbook (§6.11)
│   │   ├── scanners.md                # gitleaks + trufflehog
│   │   ├── secrets.md                 # container VCS secret mgmt (§6.10)
│   │   ├── hooks.md                   # pre-commit / pre-push hook engine
│   │   └── policy.md                  # branch protections, conventional-commits enforcement, license headers
│   ├── ai/                            # AI surface
│   │   ├── providers.md               # provider matrix + BYOK
│   │   ├── mcp.md                     # client + server modes
│   │   └── prompt-enhancer.md
│   ├── ui/                            # user surfaces
│   │   ├── cli.md
│   │   ├── tui.md                     # textual app
│   │   ├── web-ui.md                  # Laravel 13 + Livewire 4 surface
│   │   ├── remote-access.md           # Cloudflare Tunnel / Tailscale / WireGuard / VPS — see §8.5
│   │   └── vps-setup.md               # VPS provisioning + hardening — see §6.12 + templates/vps-setup/
│   ├── ops/                           # day-2 operations
│   │   ├── makefile.md                # modular .mk system (§10)
│   │   ├── gitignore-profiles.md
│   │   ├── plugins.md
│   │   ├── telemetry.md
│   │   ├── scheduler.md
│   │   ├── installer.md
│   │   └── doctor.md                  # health-probe reference (cross-links to operations/doctor.md)
│   └── workflow/                      # cross-cutting workflows
│       ├── commit-lifecycle.md        # §6.8 walkthrough
│       ├── publish.md                 # gitignore-swap publish flow (§6.5)
│       ├── release.md                 # cross-references release/overview.md
│       └── purge.md                   # cross-references security/purge.md
├── reference/
│   ├── git-command-catalog.md         # Appendix D
│   ├── svn-command-catalog.md         # Appendix E
│   ├── cross-vcs-concept-map.md       # Appendix F
│   ├── commit-template-library.md     # Appendix G
│   ├── cli-reference.md               # every command, every flag, every exit code
│   ├── exit-codes.md
│   ├── json-rpc-schema.md             # the IPC contract
│   ├── config-schema.md               # SangeConfig schema
│   ├── glossary.md                    # Appendix I
│   └── references.md                  # Appendix H — numbered, URLs + access dates
├── security/
│   ├── threat-model.md                # STRIDE
│   ├── red-team-passes.md             # consolidated per-section red-team
│   ├── prompt-injection.md            # detailed OWASP LLM Top-10 mapping
│   ├── disclosure.md                  # mirrors SECURITY.md
│   └── slsa-and-sbom.md
├── governance/
│   ├── roadmap.md                     # v0.1 → v3.0+
│   ├── contributing.md                # mirrors CONTRIBUTING.md (deeper detail)
│   ├── code-of-conduct.md             # mirrors CODE_OF_CONDUCT.md
│   ├── adr-process.md                 # how to add an ADR
│   └── checklist.md                   # mirrors §16.1 CHECKLIST.md
└── operations/
    ├── doctor.md                      # what `sange doctor` checks; exit codes
    ├── recovery.md                    # crash recovery: gitignore-swap, Makefile-tracked, daemon
    ├── observability.md               # structured logging, OpenTelemetry export
    └── performance.md                 # NFRs, performance budgets
```

**Rules:**

- The root `README.md` links into `docs/` only — never describes a feature in detail.
- `docs/README.md` is the canonical entry-point index for the manual.
- Cross-references inside `docs/` use **relative paths** (e.g. `../security/threat-model.md`) so they render correctly on GitHub.
- `docs/architecture.md` is the *narrative* read; `docs/reference/` files are the *lookup* reads. Never duplicate content between them — `reference/` is normative, `architecture.md` cites.
- Per-tool docs in `docs/tools/` are written for users; per-component design docs go in `docs/architecture.md` plus the relevant `docs/adr/`.
- `docs/audit/` preserves the v1/v2 audit forever — even after v1/v2 directories are deleted from disk, the findings remain in version control.

### 16.4 Generator scripts (`tools/generators/`)

Implements the §2.4 Generate-first / fine-tune-second discipline. These scripts are **deterministic** (no LLM), **versioned**, and emit a **sha256 of their output** so downstream consumers can verify the deliverable hasn't drifted out of band.

```
tools/generators/
├── _lib/                         # shared helpers
│   ├── output.py                 # frontmatter + hash emission + atomic write
│   ├── manpage.py                # parse `git help -a` / SVN manpages / hg help
│   ├── markdown.py               # table builders, anchor links
│   └── fingerprint.py            # sha256 + provenance block writer
├── git_catalog.py                # → appendices/D-git-command-catalog.md (Appendix D)
├── svn_catalog.py                # → appendices/E-svn-command-catalog.md (Appendix E)
├── hg_catalog.py                 # v2.0 — Mercurial catalog
├── p4_catalog.py                 # v3.0 — Perforce catalog
├── cross_vcs_map.py              # → appendices/F-cross-vcs-concept-map.md (Appendix F)
├── commit_templates.py           # → appendices/G-commit-template-library.md (Appendix G) — folds v1's 104-string array + Conventional Commits 1.0.0 spec into ≥50 normalized presets with `aliases`
├── kit_manifest.py               # → templates/MANIFEST.toml (and .sig once signed via cosign in CI)
├── docs_index.py                 # → docs/README.md + docs/tools/README.md (walks the docs/ tree and renders the index table)
├── adr_scaffold.py               # → docs/adr/NNNN-<slug>.md skeleton from an ADR title
├── exit_codes.py                 # → docs/reference/exit-codes.md (introspects src/sange/exit_codes.py)
├── cli_reference.py              # → docs/reference/cli-reference.md (introspects the typer app for every command, flag, help text)
├── jsonrpc_schema.py             # → docs/reference/json-rpc-schema.md (introspects the JSON-RPC method schemas)
├── config_schema.py              # → docs/reference/config-schema.md (introspects the SangeConfig pydantic model)
├── threat_model_table.py         # → docs/security/stride.md table from policy YAML
├── changelog_from_commits.py     # → docs/CHANGELOG.md from .sange/commits/*.json lifecycle
├── makefile_help.py              # one-shot: builds the auto-help target output as preview
└── all.py                        # orchestrator: runs every generator in dependency order
```

#### 16.4.1 Output frontmatter (mandatory on every generated file)

Every generated file opens with a YAML frontmatter block:

```yaml
---
generated_by: tools/generators/git_catalog.py
generator_version: 1.3.0
generated_at: 2026-05-13T14:32:18Z
input_sha256: <hash of input data>
output_sha256: <hash of body — recomputed and verified by verify_generated.py>
manual_edits_allowed: false   # true for the few files where humans add commentary
---
```

A companion `tools/generators/verify_generated.py` walks the deliverable, recomputes `output_sha256` for every frontmatter'd file, and fails CI on mismatch. Files with `manual_edits_allowed: true` are exempt from the body-hash check but still record their `input_sha256` so the source-of-truth is auditable.

#### 16.4.2 Inputs to the generators

| Generator | Input source | Why deterministic |
|---|---|---|
| `git_catalog.py` | `git help -a` output + `git help <cmd>` synopses + a hand-curated YAML enrichment map for the *Tier* / *Sange wrapper* / *AI augmentation* / *Safety class* columns | The git CLI is the source of truth for what commands exist; the YAML supplies the Sange-specific columns |
| `svn_catalog.py` | `svn help` + `svnadmin help` + `svnlook help` + enrichment YAML | Same pattern |
| `hg_catalog.py` / `p4_catalog.py` | `hg help` / `p4 help` + enrichment YAML | Same |
| `cross_vcs_map.py` | A single `cross-vcs-concepts.yaml` file listing concept rows with per-VCS cells | Hand-curated input; deterministic rendering |
| `commit_templates.py` | The verbatim v1 array (captured in §4.0) + `conventional-commits-1.0.0.yaml` + a curation map | Deterministic conversion + dedup + normalize |
| `kit_manifest.py` | A walk of `templates/` with file hashes | File system is the source |
| `docs_index.py` | A walk of `docs/` with header parsing | File system is the source |
| `adr_scaffold.py` | An ADR title + the next available number | Trivial template |
| `exit_codes.py` | `src/sange/exit_codes.py` (an `Enum`) | Python introspection |
| `cli_reference.py` | The `typer` app object | Python introspection |
| `jsonrpc_schema.py` | The `src/sange/ipc/schema/` modules | Python introspection |
| `config_schema.py` | The `SangeConfig` pydantic model | Pydantic JSON-schema export |

#### 16.4.3 Workflow

1. Implement the generator (`tools/generators/<name>.py`) with `--check` (verify-only) and `--write` (regenerate) modes.
2. Add it to `tools/generators/all.py` in dependency order.
3. Hook `tools/generators/verify_generated.py --check` into CI; PRs failing it can't merge.
4. The responding model, when producing the deliverable, runs `python tools/generators/all.py --write` and then fine-tunes only the prose-bearing sections of the result.
5. Hand-fine-tune diffs are recorded in `docs/adr/0NNN-fine-tune-rationale.md` when they are non-trivial.

#### 🔴 Red-Team Pass for §16.4

1. **Generator drift between runs.** Mitigation: generators are pure functions of their inputs; randomness (e.g. UUIDs) is forbidden; timestamps are read from a single `--clock` flag that defaults to the input-data mtime, never `now()`.
2. **Generated file edited out of band.** Mitigation: `verify_generated.py` recomputes `output_sha256` and fails CI on mismatch; `manual_edits_allowed: true` files are exempt for body but still hash their input.
3. **Upstream change in `git help -a`** (e.g. a new command in Git 3.x) silently drops out of the catalog. Mitigation: `git_catalog.py` snapshots the previous run's command list and warns when the set diff is non-empty; CI prints the diff so the maintainer reviews.
4. **Generator is itself slow / token-heavy.** Mitigation: every generator targets < 5 s wall-clock on a developer machine; CI fails any generator exceeding the budget.
5. **LLM accidentally re-types a generated section by hand.** Mitigation: §22 execution-order makes generation a prerequisite for the catalog-drafting step; §19 quality gate requires every catalog appendix to carry the §16.4.1 frontmatter.

---

## 17. STRUCTURE OF `sange-architecture.md`

This outline is the structure of the **consolidated** `sange-architecture.md` inside the §16.1 design-time bundle. The same content also appears inside the v3 source repo split across `docs/architecture.md` (narrative), `docs/adr/` (decisions), `docs/reference/` (catalogs and schemas), `docs/security/` (threat model), and `docs/tools/` (per-feature manuals) per §16.3. Maintain content parity between the two forms by treating `sange-architecture.md` as the canonical source and generating the split mirror from it.

```
 1. Executive Summary (≤500 words, no jargon)
 2. Vision & Positioning
 3. Etymology & Naming (with sources)
 4. Competitive Landscape (matrix + narrative)
 5. Codebase Audit Findings (v1, v2 — points to Appendix B)
 6. Glossary (or points to Appendix I)
 7. System Architecture
     7.1 Layered diagram
     7.2 Sequence diagrams for top 10 flows
     7.3 Component diagram
     7.4 Deployment diagrams (local, LAN, remote)
 8. Domain Model
 9. Adapter Specifications (Git, SVN + stubs for Hg, Fossil, Pijul)
10. Configuration & Secrets (TOML + JSON)
11. AI Subsystem & Prompt Library
12. Prompt Enhancer (§6.7.1 detailed)
13. MCP Integration (client + host)
14. .sange/ Repo Folder Specification
15. Gitignore Profile System
16. Commit Message Lifecycle (§6.8 — full spec)
17. Release Bundling (§6.9 — full spec)
18. Container VCS Secret Management (§6.10 — full spec)
19. VCS History Purge subsystem (§6.11 — full spec, refactored from the user-supplied playbook)
20. Premade Operations Kit (§6.12 — workflows, bundlers, push-to-prod, VPS setup; `sange scaffold`)
21. CLI / TUI presentation conventions (§7.0 — encoding profile, tree, progress, gates, audit chain)
22. Modular Makefile System
23. Category convention (§10.4 — canonical for every fragment tree)
24. Hook & Policy Engine
25. CI/CD Companion
26. Release Engineering
27. Web UI Architecture (Laravel 13 + Livewire 4 + `laravel/passkeys`)
28. Web UI Feature Catalog (all 21 modules, including §8.2.21 Purge & History Surgery)
29. Web UI Security Model
30. Remote Access Topologies (§8.5 — Cloudflare Tunnel, Tailscale, WireGuard, VPS)
31. Local Tools & Portals Hub
32. Scheduler & Background Jobs
33. Plugin Architecture
34. CLI Reference (every command, every flag, every exit code — including `sange scaffold` §7.11)
35. Command Coverage Floor (§9.0 — mandatory must-cover commands per VCS)
36. Innovation Surface (§9.5 — what Sange adds beyond vanilla VCS, command-by-command)
37. Installer & Distribution
38. Container & Daemon Lifecycle
39. Threat Model (STRIDE, full table + narrative + per-section red-team passes consolidated)
40. Privacy, Local Telemetry, and Opt-in External Send
41. ADR Index
42. Observability
43. Testing Strategy (unit, integration, e2e, fuzz, security, web UI e2e, remote-mode e2e, kit integration matrix)
44. Performance Budgets & NFRs
45. Roadmap (v0.1 → v3.0+)
46. Open Questions & Risks
47. Implementation Checklist (links to CHECKLIST.md)
48. License & Copyright (Apache 2.0, © Simtabi LLC)
49. References (numbered, with URLs and access dates — must include the §6.12.5 best-practice anchor list)
50. Appendices A–J (separate files, linked)
```

---

## 18. IMPLEMENTATION CHECKLIST (CHECKLIST.md)

Produce `CHECKLIST.md` with granular, dependency-aware tasks. Aim for ~350 tasks across all phases. Every task has:
- A unique ID (`T-NNN`)
- A one-sentence description
- A list of dependencies (other T-IDs)
- A definition-of-done (≥1 acceptance bullet)
- An effort estimate (S / M / L / XL)
- A primary lens it addresses

Structure:

```markdown
## Phase 0 — Foundation (target: v0.1)
- [ ] T-001 Repository scaffolding (pyproject.toml, ruff, mypy, pytest, pre-commit)
- [ ] T-002 SangeConfig Pydantic model with TOML + JSON merge
- [ ] T-003 VCSDriver Protocol
- [ ] T-004 Git adapter — read operations
- [ ] T-005 Git adapter — write operations
- [ ] T-006 Commit JSON schema + storage layer (.sange/commits/)
- [ ] T-007 Commit lifecycle state machine
- [ ] T-008 Counter durability + crash recovery
- [ ] T-009 AI provider abstraction
- [ ] T-010 Prompt Enhancer core
- [ ] T-011 Commit-message enhancement template
- [ ] T-012 Modular Makefile generator
- [ ] T-013 Doctor check: Makefile-tracked detection
- [ ] T-014 Local telemetry collector
- [ ] T-015 `tools/generators/_lib/{output,manpage,markdown,fingerprint}.py` — shared generator helpers (§16.4)
- [ ] T-016 `tools/generators/verify_generated.py` — CI integrity check
- [ ] T-017 `tools/generators/all.py` — orchestrator + dependency graph
- [ ] T-018 ...

## Phase 0a — Generators (foundational; runs before catalog drafting)
- [ ] T-G-001 `tools/generators/git_catalog.py` → Appendix D
- [ ] T-G-002 `tools/generators/svn_catalog.py` → Appendix E
- [ ] T-G-003 `tools/generators/cross_vcs_map.py` → Appendix F (v1 columns; Hg added in v2.0; P4 in v3.0)
- [ ] T-G-004 `tools/generators/commit_templates.py` → Appendix G (folds v1's 104 strings + Conventional Commits 1.0.0 spec into ≥50 normalized presets with `aliases`)
- [ ] T-G-005 `tools/generators/kit_manifest.py` → `templates/MANIFEST.toml` (then cosign-signs in CI)
- [ ] T-G-006 `tools/generators/docs_index.py` → `docs/README.md` + `docs/tools/README.md`
- [ ] T-G-007 `tools/generators/adr_scaffold.py` → `docs/adr/NNNN-<slug>.md` skeletons
- [ ] T-G-008 `tools/generators/exit_codes.py` → `docs/reference/exit-codes.md`
- [ ] T-G-009 `tools/generators/cli_reference.py` → `docs/reference/cli-reference.md`
- [ ] T-G-010 `tools/generators/jsonrpc_schema.py` → `docs/reference/json-rpc-schema.md`
- [ ] T-G-011 `tools/generators/config_schema.py` → `docs/reference/config-schema.md`
- [ ] T-G-012 `tools/generators/threat_model_table.py` → `docs/security/stride.md`
- [ ] T-G-013 `tools/generators/changelog_from_commits.py` → `docs/CHANGELOG.md` from `.sange/commits/*.json`
- [ ] T-G-014 `tools/generators/hg_catalog.py` (v2.0) and `p4_catalog.py` (v3.0)
- [ ] T-G-015 `tools/generators/profile_registry.py` → `docs/reference/profile-registry.md` + `templates/gitignore-profiles/<category>/<name>.toml` (the 35 v1.0 profiles per §6.5.1)
- [ ] T-G-016 `tools/generators/verify_session_log.py` → CI check that walks `.design/plans/session-log.md` and verifies every `linked` cross-ref resolves to a real ADR / T-NNN / R-NNN / S-NNN entry; verifies the `grounding` column for every row from S-001-T-20 onward is non-empty; flags any row whose `files_touched` doesn't appear in `git log` for the row's `timestamp` window. Per ADR-030 + ADR-031.

## Phase 1 — CLI Surface (v0.1)
- [ ] T-040 typer skeleton, global flags
- [ ] T-041 `sange init`
- [ ] T-042 `sange commits new` (manual)
- [ ] T-043 `sange commits ai`
- [ ] T-044 `sange commits submit/approve/reject/commit/push`
- [ ] T-045 `sange commit` happy-path alias
- [ ] T-046 ...

## Phase 2 — Beta features (v0.5)
- [ ] T-100 SVN adapter — read operations
- [ ] T-101 Gitignore-swap engine with SIGKILL recovery
- [ ] T-102 Pre-commit hooks framework
- [ ] T-103 Secret scanning rules library
- [ ] T-104 Container build + secret-mount mechanisms (§6.10)
- [ ] T-105 `sange doctor --container`
- [ ] T-106 Expanded commit template library (50+ presets) — Appendix G
- [ ] T-107 TerminalProfile detection + `rich`/`textual`/`questionary` adoption (§7.0.1, §7.0.2)
- [ ] T-108 Hash-chained audit JSONL writer + `sange audit verify` (§7.0.7)
- [ ] T-109 Typed-phrase confirmation gate (`sange.utils.gate.typed_phrase_confirm`) with per-session nonce (§7.0.5)
- [ ] T-110 Subprocess streaming helper with stdout/stderr async capture + transcript hashing (§7.0.6)
- [ ] T-111 Purge subsystem core: `core/purge/{plan,gates,mirror,analyzer,executor,verifier,ticket}.py` — Git path only, dry-run + analyze (§6.11)
- [ ] T-112 `sange purge plan` + `sange purge mirror` + `sange purge analyze` + `sange purge preview` + `sange purge scan` (no destructive ops yet)
- [ ] T-113 Scanner integration: gitleaks + trufflehog wrappers (shared with §7.4 prevention)
- [ ] T-114 PurgePlan JSON schema + per-repo `.sange/purge/<utc>/` layout
- [ ] T-115 ...

## Phase 3 — Web UI (v1.0)
- [ ] T-160 Laravel 13 scaffolding (PHP 8.4 recommended / 8.3 floor; Livewire 4)
- [ ] T-161 sanged daemon (launchd / systemd --user / Windows Service via pywin32)
- [ ] T-162 JSON-RPC schema core ↔ Laravel (versioned, HMAC-signed local; mTLS remote)
- [ ] T-163 Passkey integration via `laravel/passkeys` + `@laravel/passkeys` (first-party packages, NOT L13 core)
- [ ] T-164 PIN fallback + rate limit
- [ ] T-165 Password alternative (Argon2id + HIBP)
- [ ] T-166 mkcert TLS provisioning
- [ ] T-167 `sange.test` resolver setup per OS
- [ ] T-168 Multi-DB driver test matrix (SQLite, PostgreSQL, MySQL, MariaDB, SQL Server)
- [ ] T-169 Project & Repo Management module
- [ ] T-170 Commit Management module (lifecycle inbox)
- [ ] T-171 Push & Publish Approval module
- [ ] T-172 Release Management module
- [ ] T-173 Release Bundling module
- [ ] T-174 Rollback & Recovery module
- [ ] T-175 Scheduler module
- [ ] T-176 CI/CD Monitoring module
- [ ] T-177 Hook & Policy Management module
- [ ] T-178 Secret & Token Management module
- [ ] T-179 AI Configuration & Cost module (with MCP server mgmt)
- [ ] T-180 Audit Log module
- [ ] T-181 Local Tools & Portals Hub
- [ ] T-182 Gitignore Profile Management module
- [ ] T-183 Plugin Management module
- [ ] T-184 Telemetry & Local Analytics module
- [ ] T-185 Settings module (with mode switch local/LAN/remote)
- [ ] T-186 Help & Documentation module
- [ ] T-187 Remote mode: Cloudflare Tunnel setup wizard
- [ ] T-188 Remote mode: Tailscale setup wizard
- [ ] T-189 Remote mode: WireGuard generator
- [ ] T-190 Remote mode: VPS / reverse-proxy wizard with provider matrix
- [ ] T-191 Remote mode: mTLS + MFA + IP allowlist enforcement
- [ ] T-192 `sange web remote audit`
- [ ] T-193 Release bundle: GitHub Releases destination
- [ ] T-194 Release bundle: GitLab Releases destination
- [ ] T-195 Release bundle: OCI artifact destination
- [ ] T-196 Release bundle: S3 destination
- [ ] T-197 Release bundle: sigstore + GPG signing
- [ ] T-198 Release bundle: SBOM generation (CycloneDX)
- [ ] T-199 Release bundle: SLSA provenance attestation
- [ ] T-200 MCP server implementation (Sange exposes its capabilities to MCP hosts like Claude Desktop / Code / Cursor)
- [ ] T-201 MCP client implementation (Sange consumes user-configured MCP servers for context)
- [ ] T-202 Documentation site at sange.sh
- [ ] T-203 Purge destructive ops: `sange purge execute` (Git: filter-repo + BFG) with §6.11.4 gates and §6.11.5 verification
- [ ] T-204 `sange purge push` with second typed-phrase gate + platform-support ticket payload generator
- [ ] T-205 `sange purge rollback` from backup mirror with state-machine guarantees
- [ ] T-206 `sange purge notify` collaborator-notification templates + Slack/webhook delivery with HMAC + idempotency key
- [ ] T-207 Web UI module §8.2.21 Purge & History Surgery (plan editor, gates, preview, hand-off)
- [ ] T-208 `docs/tools/purge.md` produced from user-supplied playbook (refactored per §6.11.8); 19 sections + 20 gotchas preserved; verbatim "Hard Truths" preamble; Sange-native commands replace standalone shell/script invocations

## Phase 4 — Multi-VCS (v2.0)
- [ ] T-240 Mercurial adapter
- [ ] T-241 Fossil adapter
- [ ] T-242 Pijul adapter
- [ ] T-243 Workflow builder UI
- [ ] T-244 Opt-in external telemetry pipeline
- [ ] T-245 Cloudflare Workers edge auth gateway
- [ ] T-246 Purge: SVN executor (`svnadmin dump → svndumpfilter exclude → svnadmin load → atomic swap`) with branch/tag copy-graph handling
- [ ] T-247 Purge: Mercurial executor (`hg convert --filemap` + `hg strip` for changeset-level)
- [ ] T-248 ...

## Phase 5 — Enterprise (v3.0)
- [ ] T-280 Perforce adapter
- [ ] T-281 Plastic SCM adapter
- [ ] T-282 Sapling adapter
- [ ] T-283 SAML/OIDC SSO
- [ ] T-284 SIEM audit-log forwarding (forward purge audit chain to external SIEM with verified integrity)
- [ ] T-285 Self-hosted sync server (opt-in)
- [ ] T-286 Purge: Perforce executor (`p4 obliterate -y`, admin-role-gated, with spec-file scrubbing reminders)
- [ ] T-287 ...
```

---

## 19. QUALITY GATES (must all pass before declaring done)

- [ ] Both `sange-v1` and `sange-v2` repos audited; defect log in Appendix B with severity tags
- [ ] All six Mukora Makefiles read; vocabulary in Appendix A
- [ ] Etymology of "sange" researched with cited sources
- [ ] ≥15 competing tools surveyed with concrete feature-gap findings
- [ ] Every standard listed in §5.2 referenced where relevant
- [ ] STRIDE threat model covers every external input surface
- [ ] Every CLI command has: synopsis, flags, examples, exit codes, security notes
- [ ] Web UI catalog covers all 21 modules with feature lists (including §8.2.21 Purge & History Surgery)
- [ ] Web UI security section addresses every row in §8.3
- [ ] All four remote topologies (§8.5) have setup wizards specified
- [ ] Git command catalog (Appendix D) covers all commands from `git help -a`
- [ ] SVN command catalog (Appendix E) covers all main commands
- [ ] Cross-VCS concept map (Appendix F) for Git ↔ SVN ↔ Hg
- [ ] Commit template library (Appendix G) has ≥50 **normalized, dedup'd, taxonomized** presets, with a **v1→v3 migration mapping** for all 104 legacy entries from `sange-v1/configs/config.sh:25–128`
- [ ] Commit lifecycle state machine fully specified with JSON schema, CLI, and Web parity
- [ ] Release bundling spec covers all 6 destinations
- [ ] Container secret management spec covers all 5 mechanisms
- [ ] Modular Makefile system includes the "what if Makefile is committed?" recovery procedure
- [ ] Gitignore-swap design has explicit SIGKILL recovery procedure
- [ ] Prompt Enhancer architecture fully specified, including model-specific tuning
- [ ] MCP client and MCP server modes both specified (Sange is **not** an MCP host; host = the LLM app)
- [ ] Every ADR has Context / Decision / Alternatives Rejected / Consequences / Lens Notes
- [ ] ADR index in §41 (per renumbered §17 outline) lists every ADR with one-line summary
- [ ] Every major section has a `🔴 Red-Team Pass` subsection
- [ ] Implementation checklist has ~350 tasks across 6 phases, all with dependencies and DoD
- [ ] Cross-platform coverage: macOS, Linux (Debian/Ubuntu/Fedora/Arch), Windows (PowerShell 5.1 + 7+) addressed concretely
- [ ] Mermaid diagrams render without syntax errors
- [ ] License & copyright section present (Apache 2.0, © Simtabi LLC)
- [ ] Laravel 13's first-party AI SDK (`Laravel\Ai\…`) explicitly **rejected** for the web layer in favor of Python core enhancer + provider abstraction (ADR-003)
- [ ] `laravel/passkeys` + `@laravel/passkeys` (released 2026-05-12, NOT in L13 core) pinned by exact version in `web/composer.json` and `web/package.json` (ADR-002)
- [ ] Livewire 4 (not Livewire 3) specified throughout (ADR-002)
- [ ] PHP version requirement clearly states "8.3 floor, 8.4 recommended" (not "8.3+ supports 8.3–8.5") (ADR-002)
- [ ] Etymology section corrected: framing is "named after the *sengi*", not "sange is Swahili for elephant shrew" (ADR-014)
- [ ] All codebase paths in §4.1 / §4.3 use `/opensource/sange/` (no `/simtabi/` segment) and are verified against the filesystem
- [ ] Final v3 source-repository layout fully specified in §16.2 with explicit mapping of every v1 shell asset to its v3 Python equivalent
- [ ] Documentation strategy implemented: one root `README.md` (≤300 lines, index only) + the manual split under `docs/` per §16.3
- [ ] CLAUDE.md global + Simtabi org conventions honored: `LICENSE` (Apache 2.0, © Simtabi LLC), `SECURITY.md` (→ opensource@simtabi.com), `CODE_OF_CONDUCT.md` (Contributor Covenant 2.1), `.editorconfig`, Dependabot weekly Mon 06:00 America/New_York, canonical URL `opensource.simtabi.com/products/sange`
- [ ] ADR table in §15 has rows for every ADR-NNN referenced in the prose (no orphan references; no "ADR-001" referenced without a decision-table row)
- [ ] §6.11 History Purge subsystem covers all four VCS targets (Git, SVN, Mercurial, Perforce) with the §6.11.1 tier table, the §6.11.2 lifecycle state machine, all eight §6.11.4 pre-flight gates, all §6.11.5 verification checks, the §6.11.6 hash-chained audit schema, and the §6.11.8 refactor mandate for `docs/tools/purge.md`
- [ ] `docs/tools/purge.md` is produced from the user-supplied playbook: 19-section structure preserved; 20-item *Common Gotchas* list preserved; "Hard Truths" preamble verbatim; every manual `git`/`svnadmin`/`hg`/`p4` invocation rewritten as a `sange purge <subcommand>` invocation; the standalone `vcs-purge.py` reference script's safety contract reincarnated as the `sange purge` subcommand tree
- [ ] §7.0 CLI/TUI presentation conventions cover: library pin table; `TerminalProfile` detection rules (NO_COLOR / FORCE_COLOR / CI / Windows + no WT_SESSION); ASCII fallback glyph mapping; tree rendering rules; progress + ETA pattern with the exact `rich.progress` column composition; typed-phrase gate with per-session nonce; subprocess stream-and-retain helper; hash-chained audit JSONL writer; exit-code map
- [ ] Purge CLI surface in §7.10 covers all subcommands (`plan`, `mirror`, `scan`, `analyze`, `preview`, `notify`, `execute`, `push`, `rollback`, `audit show/verify`, `status`) with their flags and exit codes
- [ ] Web UI module §8.2.21 Purge & History Surgery cannot trigger the destructive `confirmed → executing` transition by RPC alone — the daemon rejects any such call lacking TTY origin (ADR-018 invariant)
- [ ] Purge tests in `tests/security/` exercise: gate failures, race during execution (upstream HEAD moved), backup-tarball corruption, audit-chain tampering detection, `--batch` rate-limiting, LFS orphan reporting, signed-tag invalidation reporting
- [ ] **§9.0 Command Coverage Floor is fully honored**: every row in §9.0.1 (Top 25), §9.0.2 (under-used power commands), §9.0.3 (SVN floor), §9.0.4 (Mercurial floor), §9.0.5 (Perforce floor), and §9.0.6 (cross-cutting tools) appears as a row in the matching Appendix (D/E/F). **No row may be marked `(deferred)` in the v1.0 deliverable.**
- [ ] Every row in §9.0 has its *Safety class* and *Confirmation gate* columns filled and consistent (Destructive/Catastrophic ⇒ Type-to-confirm or Multi-step; never None)
- [ ] Every Sange wrapper documented in §9.0 does at least one of the seven augmentations enumerated in §9.4 (no pure passthrough facades)
- [ ] §9.5 Innovation Surface section appears in the deliverable, with each subsection cross-referenced from the corresponding catalog row(s) so a reader of Appendix D for `git purge` lands on §6.11 and §9.5.4
- [ ] §17 outline contains no non-standard section numbers (no `18a`/`18b`; all chapters numbered sequentially)
- [ ] `docs/tools/purge.md` exists in §16.3.2 and is referenced from `docs/README.md`
- [ ] Every file-fragment tree under `.sange/`, `src/sange/templates/`, and `docs/tools/` follows the §10.4 Category convention — no flat fragment such as `.sange/makefiles/git.mk` directly under the parent
- [ ] `_core/` directories contain only framework-level content (never tool-specific); `_local/` directories are gitignored
- [ ] Premade Operations Kit (§6.12) ships fragments for every cell in the §6.12.1 table — no row is empty for v1.0
- [ ] Every push-to-prod strategy in `templates/push-to-prod/<strategy>/` includes a paired `rollback.sh` and `health.sh` (per §6.12 red-team #6)
- [ ] `templates/MANIFEST.toml.sig` exists and `sange scaffold` verifies it before any materialization (ADR-020)
- [ ] §6.12.5 best-practice citation list appears in §49 References of the deliverable with access dates
- [ ] Weekly kit integration matrix CI workflow exists (`.github/workflows/kit-integration.yml`) and surfaces failures as `kit_status: needs_attention` in `sange doctor`
- [ ] **Audience scope (§3)** is honored — every CLI/TUI/Web feature has a documented path for at least one of the seven personas; happy paths require zero configuration for the *Non-developer founder/CEO* and *Junior engineer* personas
- [ ] **No internal repetition** — two sections never re-state the same spec; one section owns each fact, the others cite it via §-reference (auditable via the `.design/plans/content-audit.md` companion)
- [ ] **Defaults are secure** — every security control listed in §11 has a default-secure setting; toggling to "off" requires explicit user action and is audit-logged
- [ ] **`.design/plans/` companion folder exists** at the repo root with `README.md`, `implementation-plan.md`, `checklist.md`, `content-audit.md`, `decisions-log.md`, `positioning.md`. Every user-supplied requirement from the chat history is mapped to a section in this prompt by `content-audit.md`.
- [ ] Deliverable reading age: an *engineer-skim* read produces an accurate implementation start within 30 min (§23 DoD); a *non-engineer-skim* read of the §3 + §8.2 Web UI catalog produces an accurate understanding of what the tool does within 10 min
- [ ] **Every generated section (Appendix D, E, F, G; `docs/reference/*.md`; `docs/security/stride.md`; the docs index files) carries a §16.4.1 frontmatter block with valid `generator_version`, `input_sha256`, and `output_sha256` (verifiable via `tools/generators/verify_generated.py --check`)**
- [ ] **No catalog appendix was hand-typed in lieu of running its generator** (audit by inspecting commit history of the appendix files)
- [ ] **`tools/generators/` directory exists with `_lib/`, all twelve generators listed in §16.4, `verify_generated.py`, and `all.py` orchestrator**
- [ ] **One-question-at-a-time rule (§7.0.9 + §1)** honored throughout Sange: no batched confirmation gates in CLI, TUI, or Web UI; the responding model raises clarifying questions one at a time when running this prompt
- [ ] **Profile Registry (§6.5.1) v1.0** ships all 35 profiles; every row has a corresponding `templates/gitignore-profiles/<category>/<name>.toml` with `detect.required_any`, `patterns.always/dev_only/prod_only`, `extends`, `version`, `maintainer`
- [ ] **`sange profile detect`** returns a ranked suggestion list for the seven primary stacks (Python+Django, Node+Next.js, PHP+Laravel, Go, Rust, Ruby+Rails, Java+Spring) within 1 s on a typical repo
- [ ] **Per-project activation** via `sange profile use` writes to `.sange/config.toml::gitignore.{dev,prod}.profiles` and survives `sange doctor`
- [ ] **`_core/license` safety profile** prevents any profile (including plugin-provided) from excluding `LICENSE*`, `COPYING`, `NOTICE`, `README*`
- [ ] **Profile rename enforcement** — `sange doctor` refuses to start when `.sange/config.toml` references a profile name that no longer exists in the registry
- [ ] **Anti-hallucination (ADR-030)** — every non-trivial factual claim in the deliverable carries a `file:line` / URL / ADR-NNN citation; every `🟡 UNVERIFIED` marker is resolved before merge; CI's `verify_generated.py` rejects any catalog drift; no invented ADR-NNN / T-NNN / R-NNN exist
- [ ] **Memory preservation (ADR-031)** — every completed task has a session-log row with `grounding` populated; every phase boundary has a `.design/plans/snapshots/phase-N.M.md` snapshot; the latest snapshot is newer than the last `git commit`; the resumability test passes (a fresh session given only `.design/` access can correctly identify the next task)
- [ ] **Crash-recovery protocol** documented and exercised: a deliberate mid-task abort + fresh-session resume succeeds without loss
- [ ] **Continuity check (§22 step 11.5)** runs before every Deliver step; failures block the deliverable
- [ ] **Audit chain integrity** — design-time session-log entries link to runtime audit-chain entries (when daemon is running); `tools/generators/verify_session_log.py` (T-G-016) checks the cross-reference graph
- [ ] No "TBD" anywhere
- [ ] No filler — every paragraph decides, surveys, or warns
- [ ] Every external claim has a citation with URL and access date
- [ ] Document length of the **deliverable** (`.design/sange-architecture.md`) targets **~80k words**. Shorter = under-specified for the agency-workbook use case; longer = padded. The prompt itself (`.design/sange-architecture-prompt.md`) sits at ~45k words and is the spec; the deliverable is the narrative + the generator stubs filled in.
- [ ] **Audit-vs-redesign clearly marked** for every component carried over from v1/v2

---

## 20. ANTI-PATTERNS — DO NOT DO THESE

- Do not preserve v1/v2 code without justifying its survival in an ADR
- Do not invent features the user didn't ask for and no competing tool justifies
- Do not write "TBD" — state the decision criteria and a recommended default
- Do not propose Kubernetes or message queues for a local-first tool
- Do not let the web UI duplicate core logic — it must call the daemon
- Do not generate code beyond illustrative snippets (~20 lines max) and CLI examples
- Do not copy-paste from competitor docs — paraphrase and cite
- Do not ship a security section that reads as a checklist of buzzwords — every control names the threat it counters
- Do not treat AI as magic — every AI feature must justify itself against a non-AI baseline
- Do not write Markdown bullet soup — paragraphs where they belong, lists where they help
- Do not roleplay personas. Apply lenses. Record ADRs. Run red-team passes.
- Do not use Laravel's first-party AI SDK in parallel with the Python AI core (use one, not both)

---

## 21. TONE & WRITING STANDARDS

- Precise, declarative, opinionated. No hedging on settled matters.
- Active voice. Present tense for the design; past tense only for v1/v2 audit findings.
- Code, paths, commands, and identifiers in backticks.
- Numbered references at first use; full citation list at the end.
- Allowed callout markers: `⚠️` (Design Conflict), `🔒` (Security Note), `🔴` (Red-Team Pass), `🧪` (Open Question — only for novel ambiguities not covered by §15), `💡` (Recommendation), `📐` (ADR reference).
- No other emoji.

---

## 22. EXECUTION ORDER

Work in this sequence — do not skip ahead.

1. **Audit (mandatory first)** — Read both repos in full. Read all six Mukora Makefiles. Write Appendix A and Appendix B *first*, including the audit defect log with severity ratings and the verbatim capture of the existing default-commit-messages array. Note: §4.0 already gives you ground truth on paths, language mix, the location of `DEFAULT_GIT_COMMIT_MESSAGES`, and v2's regressions — **use it to skip the discovery work**, not to skip the close reading. Defect log and Mukora vocabulary still require reading every line.
2. **Research** — Etymology, competitive landscape, standards, threat-model references. Build References as you go.
3. **Decide** — Lock the architectural decisions in §6–§10 as ADRs *before* writing prose. ADR-001 through ADR-012 (per §15) are mandatory and must be in place before their respective sections.
4. **Draft** — Section by section in the order of §17. After each major section, write the Red-Team Pass and fix what it finds before continuing.
5. **Generate** *(per §2.4 Generate-first / fine-tune-second)* — Implement and run the `tools/generators/` scripts (§16.4): `git_catalog.py`, `svn_catalog.py`, `cross_vcs_map.py`, `commit_templates.py`, `kit_manifest.py`, `docs_index.py`, `exit_codes.py`, `cli_reference.py`, `jsonrpc_schema.py`, `config_schema.py`. Output goes to the appendices and `docs/` per their frontmatter declarations. Do **not** hand-type catalog tables.
6. **Catalog (fine-tune)** — Open the generator output. Hand-curate only the prose-bearing additions: edge-case notes, common foot-guns, narrative introductions. Body hashes must remain stable for `verify_generated.py`.
7. **Diagram** — Render all Mermaid diagrams; save `.mmd` sources.
8. **Checklist** — Produce CHECKLIST.md with ~350 tasks (run `tools/generators/checklist_from_todos.py` if available, otherwise hand-list).
9. **Self-review** — Run the §19 checklist. Fix every failing item. Re-run.
10. **Verify generated files** — Run `tools/generators/verify_generated.py --check`. Every generated file's `output_sha256` must validate.
11. **Consistency pass** — Final read-through for: stale terminology (e.g., "v1: zero telemetry" should be "v1: local-only telemetry"); broken cross-references; unresolved TBDs; missing red-team passes; any ADR referenced but not defined.
11.5. 🟢 **Continuity check** — Before declaring done, validate: every session-log row carries a `grounding` column entry; the latest `.design/plans/snapshots/phase-N.M.md` is newer than the last `git commit`; every `🟡 UNVERIFIED` marker in the deliverable is resolved (or escalated to a `🧪 Open Question`); every claim about a generator's output matches the actual `output_sha256`. If this session ends now, can the next session resume from `.design/` alone? Per ADR-031.
12. **Deliver** — Output all files. Print final paths.

---

## 23. DEFINITION OF DONE

A development team with no prior Sange context reads `sange-architecture.md`, opens `CHECKLIST.md`, picks task `T-001`, and begins coding within 30 minutes — with zero ambiguity about *what* to build, *why* it is built that way, *which* threats each component defends against, and *what* is being preserved from v1/v2 versus redesigned.

If the document does not meet that bar, it is not done. Iterate.

---

**Begin with Audit (§22 step 1). Confirm completion of §4.1, §4.2, and §4.3 before proceeding to Research.**
