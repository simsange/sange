# Quality gates (must all pass before v1.0 ship)

Mirrors §19 of `../sange-architecture-prompt.md`. Single canonical checklist for the v1.0 readiness review.

## Audit + research

- [ ] Both `sange-v1` and `sange-v2` repos audited; defect log in Appendix B with severity tags
- [ ] All six Mukora Makefiles read; vocabulary in Appendix A
- [ ] Etymology of "sange" researched with cited sources
- [ ] ≥ 15 competing tools surveyed with concrete feature-gap findings
- [ ] Every standard listed in §5.2 referenced where relevant

## Security + threat modeling

- [ ] STRIDE threat model covers every external input surface
- [ ] Web UI catalog covers all 21 modules with feature lists (including §8.2.21 Purge & History Surgery)
- [ ] Web UI security section addresses every row in §8.3
- [ ] All four remote topologies (§8.5) have setup wizards specified
- [ ] §11 covers every mitigation row including web UI threats and prompt-injection

## Catalogs + appendices

- [ ] Git command catalog (Appendix D) covers all commands from `git help -a`
- [ ] SVN command catalog (Appendix E) covers all main commands
- [ ] Cross-VCS concept map (Appendix F) for Git ↔ SVN ↔ Hg
- [ ] Commit template library (Appendix G) has ≥ 50 normalized, dedup'd presets with v1→v3 migration mapping for the 104 legacy entries
- [ ] §9.0 Command Coverage Floor is fully honored — no row marked `(deferred)`
- [ ] Every §9.0 row has *Safety class* + *Confirmation gate* columns filled (Destructive/Catastrophic ⇒ Type-to-confirm or Multi-step; never None)
- [ ] Every Sange wrapper documented in §9.0 does at least one of the seven augmentations enumerated in §9.4
- [ ] §9.5 Innovation Surface appears with each subsection cross-referenced from matching catalog rows

## Lifecycle + audit + state machines

- [ ] Commit lifecycle state machine (§6.8) fully specified with JSON schema, CLI, and Web parity
- [ ] Release bundling spec (§6.9) covers all 6 destinations
- [ ] Container secret management spec (§6.10) covers all 5 mechanisms
- [ ] §6.11 History Purge subsystem covers all four VCS targets with §6.11.1 tier, §6.11.2 lifecycle, §6.11.4 gates, §6.11.5 verification, §6.11.6 audit schema, §6.11.8 refactor mandate
- [ ] `docs/tools/security/purge.md` produced from the user-supplied playbook (19 sections + 20 gotchas + Hard-Truths verbatim + Sange-native commands replacing manual invocations)
- [ ] §7.0 CLI/TUI conventions cover library pins, TerminalProfile detection, ASCII fallback glyphs, tree render rules, progress + ETA pattern, typed-phrase gate, subprocess stream-and-retain, hash-chained audit JSONL, exit codes
- [ ] Purge CLI surface §7.10 covers all subcommands with flags + exit codes
- [ ] Web UI module §8.2.21 cannot trigger destructive transition by RPC alone (ADR-018 invariant)
- [ ] Purge tests in `tests/security/` exercise gate failures, race during execution, backup corruption, audit-chain tampering, `--batch` rate-limiting, LFS orphan reporting, signed-tag invalidation reporting

## Premade kit + scaffold

- [ ] Premade Operations Kit (§6.12) ships fragments for every cell in §6.12.1 — no row is empty for v1.0
- [ ] Every push-to-prod strategy in `templates/push-to-prod/<strategy>/` includes a paired `rollback.sh` and `health.sh`
- [ ] `templates/MANIFEST.toml.sig` exists; `sange scaffold` verifies it before any materialization (ADR-020)
- [ ] §6.12.5 best-practice citation list appears in §49 References of the deliverable with access dates
- [ ] Weekly kit integration matrix CI workflow exists and surfaces failures as `kit_status: needs_attention` in `sange doctor`

## Modular Makefile + Category convention

- [ ] Modular Makefile system includes the "what if Makefile is committed?" recovery procedure
- [ ] Every file-fragment tree (under `.sange/`, `src/sange/templates/`, `docs/tools/`) follows the §10.4 Category convention — no flat fragments
- [ ] `_core/` directories contain only framework-level content; `_local/` directories are gitignored

## Cross-cutting design

- [ ] Gitignore-swap design has explicit SIGKILL recovery procedure
- [ ] Prompt Enhancer architecture fully specified including model-specific tuning
- [ ] MCP client + MCP server modes both specified (Sange is not an MCP host; host = the LLM app)
- [ ] Every ADR has Context / Decision / Alternatives Rejected / Consequences / Lens Notes
- [ ] ADR index in §41 (per renumbered §17 outline) lists every ADR with one-line summary
- [ ] §17 outline contains no non-standard section numbers
- [ ] `docs/tools/security/purge.md` exists in §16.3.2 and is referenced from `docs/README.md`
- [ ] Every major section has a `🔴 Red-Team Pass` subsection
- [ ] Implementation checklist has ~350 tasks across 6 phases, all with dependencies and DoD

## Stack + license + identity

- [ ] Laravel 13's first-party AI SDK explicitly rejected for the web layer (ADR-003)
- [ ] `laravel/passkeys` + `@laravel/passkeys` pinned by exact version (ADR-002)
- [ ] Livewire 4 specified throughout (not Livewire 3)
- [ ] PHP version requirement reads "8.3 floor, 8.4 recommended"
- [ ] Etymology corrected: "named after the *sengi*", not "sange is Swahili for elephant shrew" (ADR-014)
- [ ] All codebase paths use `/opensource/sange/` (no `/simtabi/` segment)
- [ ] Final v3 source-repository layout fully specified in §16.2 with explicit v1-shell → v3-Python mapping
- [ ] Documentation strategy: one root `README.md` (≤ 300 lines) + manual split under `docs/`
- [ ] CLAUDE.md global + Simtabi org conventions honored (LICENSE Apache 2.0, SECURITY.md → opensource@simtabi.com, CODE_OF_CONDUCT.md Contributor Covenant 2.1, Dependabot weekly Mon 06:00 America/New_York, canonical URL `opensource.simtabi.com/products/sange`)
- [ ] ADR table in §15 has rows for every ADR-NNN referenced in the prose (no orphan references)

## Positioning + audience

- [ ] Audience scope (§3) honored — every CLI/TUI/Web feature documents a path for at least one of the seven personas; happy paths require zero configuration for *Non-developer founder* + *Junior engineer*
- [ ] No internal repetition — two sections never re-state the same spec; auditable via `.design/plans/content-audit.md`
- [ ] Defaults are secure — every §11 control has a default-secure setting; toggling off requires explicit action + audit-log
- [ ] `.design/plans/` companion folder exists with README, implementation-plan, checklist, content-audit, decisions-log, positioning, quality-gates
- [ ] Engineer-skim read produces accurate implementation start within 30 min
- [ ] Non-engineer-skim read of §3 + §8.2 catalog produces accurate understanding within 10 min

## Generate-first + one-question-at-a-time

- [ ] Every generated section (Appendix D, E, F, G; `docs/reference/*.md`; `docs/security/stride.md`; the docs index files) carries a §16.4.1 frontmatter block with valid `generator_version`, `input_sha256`, `output_sha256` (verifiable via `tools/generators/verify_generated.py --check`)
- [ ] No catalog appendix was hand-typed in lieu of running its generator (audit by inspecting commit history)
- [ ] `tools/generators/` directory exists with `_lib/`, all twelve generators listed in §16.4, `verify_generated.py`, `all.py`
- [ ] One-question-at-a-time rule (§7.0.9 + §1) honored: no batched confirmation gates in CLI / TUI / Web UI; responding model raises clarifying questions sequentially

## Cross-platform + portability

- [ ] macOS, Linux (Debian/Ubuntu/Fedora/Arch), Windows (PowerShell 5.1 + 7+) addressed concretely
- [ ] Mermaid diagrams render without syntax errors
- [ ] License + copyright section present (Apache 2.0, © Simtabi LLC)
- [ ] No "TBD" anywhere
- [ ] No filler — every paragraph decides, surveys, or warns
- [ ] Every external claim has a citation with URL and access date
- [ ] Document length of the **deliverable** (`../sange-architecture.md`) targets **~80k words**. Shorter = under-specified for the agency-workbook use case; longer = padded. The prompt itself (`../sange-architecture-prompt.md`) sits at ~45k words and is the spec; the deliverable is the narrative + the generator stubs filled in (v4.3).
- [ ] Audit-vs-redesign clearly marked for every component carried over from v1/v2

---

*Source of truth: §19 of `../sange-architecture-prompt.md`.*
