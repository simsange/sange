# Architecture (reader's guide)

This is the contributor-friendly map of Sange's architecture. For
the locked, canonical, every-decision-spelled-out version, read
[`.design/sange-architecture.md`](../.design/sange-architecture.md)
(v4.4, ~1500 lines). For the per-decision rationale, read
[`.design/plans/decisions-log.md`](../.design/plans/decisions-log.md)
(33 ADRs). This file gives you the **mental model** and tells you
where to drill down.

## The mental model

Sange is **three executables, one daemon, one wire protocol**.

```
                    ┌─────────────────────────────────────┐
                    │            User surfaces            │
                    ├──────────┬──────────┬───────────────┤
                    │   CLI    │   TUI    │   Web UI      │
                    │ (typer)  │(textual) │ (Laravel 13)  │
                    └────┬─────┴────┬─────┴──────┬────────┘
                         │          │            │
                         └──────────┴────────────┘
                                    │  JSON-RPC 2.0
                                    │  (loopback HMAC / mTLS remote)
                                    ▼
                    ┌─────────────────────────────────────┐
                    │      Python core daemon `sanged`    │
                    │                                     │
                    │  Core layer       (domain models,   │
                    │                   state machines,   │
                    │                   pure logic)       │
                    │                                     │
                    │  Enhancer layer   (T-030 redaction, │
                    │                   PromptEnhancer,   │
                    │                   AI provider)      │
                    │                                     │
                    │  Adapter layer    (VCS drivers:     │
                    │                   git/svn/hg/...    │
                    │                   AI providers,     │
                    │                   storage backends) │
                    └────┬────────────────────────────────┘
                         │
                         ▼
                ┌──────────────────────────┐
                │   Repo working trees     │
                │   <repo>/.sange/         │
                │   <repo>/.git/ or .svn/  │
                └──────────────────────────┘
```

Three boundaries matter:

| Boundary | Why it exists | Tested by |
| :--- | :--- | :--- |
| **Surface ↔ daemon** | The CLI and Web UI have nothing in common except the JSON-RPC schema. Either can be replaced without touching the other. | The v0.1 CLI talks to the in-process daemon directly; v1.0 adds the wire-protocol layer with HMAC + mTLS. |
| **Core ↔ adapters** | The core is a pure-Python state machine that knows nothing about Git or AI providers. Adapters implement Protocols. The core can be tested with no subprocesses, no network. | Adapter-Protocol contracts in `src/sange/adapters/*/_protocol.py`. |
| **Enhancer ↔ providers** | The enhancer never calls a provider directly. It builds a `CompletionRequest`, hands it to the registered provider, validates the response. Provider swap is one config line. | Mock provider in `src/sange/adapters/ai/mock.py` for tests; live providers as optional extras. |

The daemon's name is `sanged` (Python, async). v0.1 ships the
in-process variant — the CLI imports the daemon's modules directly.
v1.0 ships `sanged` as a real systemd / launchd / Windows-Service
unit and the surfaces talk to it over JSON-RPC.

## Subsystems at a glance

These are the major subsystems, in lifecycle order — i.e. roughly
the order a user touches them when running `sange commit` end-to-end.

### 1. Configuration & Secrets (`src/sange/core/config/`)

`SangeConfig` is a Pydantic v2 model that merges from four layers
in precedence order: CLI flags > environment variables > TOML
files (`.sange/config.toml` + ancestor `.sange/config.toml`s) >
defaults. Secret material (API keys, tokens) is loaded from
`pydantic-settings` env-var bindings and never written to the
TOML; the loader also accepts inline secret references like
`api_key = "{env:ANTHROPIC_API_KEY}"`. Canonical: §10 of the
architecture deliverable; reference: [`reference/config-schema.md`](reference/config-schema.md).

### 2. VCS adapters (`src/sange/adapters/vcs/`)

`VCSDriver` is a Protocol; concrete drivers (Git, SVN, eventually
Hg / Fossil / Pijul / P4 / Plastic / Sapling) implement it. Four
optional sub-Protocols (`SupportsStash`, `SupportsBisect`,
`SupportsRebase`, `SupportsLFS`) gate features that not every VCS
supports. The Git driver wraps a `subprocess.run(['git', ...])`
call with environment discipline (`LC_ALL=C`, `GIT_PAGER=cat`,
`GIT_TERMINAL_PROMPT=0`) and parses output via the pure-function
parsers in `parsers.py`. v0.1 ships Git read+write; SVN is read-only
stubbed; the rest land per [`governance/roadmap.md`](governance/roadmap.md).
Canonical: §7 + §9 + Appendix F.

### 3. AI providers (`src/sange/adapters/ai/`)

`AIProvider` is a Protocol. Concrete providers (`mock`, `anthropic`,
`openai`, `ollama`, `gemini`, `bedrock`) implement it. Each
provider is gated by an optional extra (`pip install
'sange[ai-anthropic]'` etc.) so the base install stays light.
The `mock` provider supports canned responses for deterministic
tests. The contract: `provider.complete(CompletionRequest) →
CompletionResponse`, with `temperature=0` honored for
determinism. Canonical: §11.

### 4. Prompt enhancer (`src/sange/core/enhancer/`)

The §6.7.1 chokepoint: every prompt to every AI provider flows
through `PromptEnhancer.enhance()`. Six stages, strict order:
redact → render → format → call → validate → audit. The redaction
layer (T-030 mitigation) gets its own doc:
[`security/prompt-injection.md`](security/prompt-injection.md).
Provider-specific delimiters (XML for Claude, JSON for OpenAI,
markdown for the rest) are applied by the `formatting.py` module
based on a small lookup table. Canonical: §12 + Appendix G.

### 5. Commit lifecycle (`src/sange/core/lifecycle/`)

`CommitJSON` is a Pydantic v2 model recording one commit in
8 possible states (DRAFT → PENDING_REVIEW → APPROVED → COMMITTED
→ PUSHED, with REJECTED/ARCHIVED/DISCARDED terminal branches).
`LifecycleEngine` is pure — every transition is a function that
takes a `CommitJSON` and returns a new one; the engine itself is
stateless. Storage is one JSON file per commit in
`<repo>/.sange/commits/<NNNN>-<slug>.json`, atomically written
via tmp + fsync + rename. The counter is monotonic + crash-safe
via filesystem rescan. Canonical: §16 + reader-friendly walkthrough:
[`tools/workflow/commit-lifecycle.md`](tools/workflow/commit-lifecycle.md).

### 6. Hooks & policy (`src/sange/core/hooks/` — v0.5+)

`HookEngine` runs configurable pre-commit / pre-push / pre-purge
hooks. The hooks library is a registry of named gates (e.g.
`gitleaks` / `trufflehog` / `make test` / `make lint`). Each hook
returns a `HookResult` (pass / warn / fail / skip). The hook
contract is intentionally simple — anything that exits 0 passes;
anything else fails — so plugins can add hooks in any language.
Canonical: §24.

### 7. Release engineering (`src/sange/core/release/` — v1.0+)

`sange release` orchestrates bundling, signing, and shipping to
six destinations (GitHub Releases / GitLab Releases / OCI artifact
registries / S3 / generic package registries / filesystem). Every
release produces a SLSA-3 provenance attestation + sigstore
signature + CycloneDX SBOM. The v0.1 release pipeline (the
GitHub Actions workflow at `.github/workflows/release.yml`)
implements a subset of this — the `sange release` CLI proper
lands in v0.5+. Canonical: §17 + §26 + [`security/slsa-and-sbom.md`](security/slsa-and-sbom.md).

### 8. Purge subsystem (`src/sange/core/purge/` — v0.5 read-only, v1.0 destructive)

`sange purge` is the controlled-destruction surface — rewriting
history to remove leaked secrets, accidental committed binaries,
PII. Eight pre-flight gates (per §6.11.4) including typed-phrase
confirmation, force-with-lease semantics, hash-chained audit
record. Per-VCS executors: Git via `git filter-repo` + BFG; SVN
via `svnadmin dump → svndumpfilter exclude → swap`; Mercurial via
`hg convert --filemap` + `hg strip`. Canonical: §19.

### 9. Web UI (`web/` — v1.0+)

Laravel 13 + Livewire 4 + `laravel/passkeys`. 21 modules per §28.
Local-first at `https://sange.test` (mkcert-provisioned TLS) by
default. Remote-access wizards (Cloudflare Tunnel / Tailscale /
WireGuard / VPS) per §30. Talks to the daemon via JSON-RPC 2.0
over loopback (HMAC) or mTLS (remote). Canonical: §27 - §30.

### 10. Operations Kit (`templates/` + `src/sange/core/scaffold/` — v0.5 read-only, v1.0 add/diff/update)

`sange scaffold` materializes premade fragments — `.github/`
workflows, Dockerfiles, vps-setup recipes for 9 providers,
push-to-prod strategies, language-specific gitignore profiles
(35 of them in `templates/gitignore-profiles/`). Every fragment
is signed in `templates/MANIFEST.toml` and verified at materialize
time. Canonical: §20 + reference: [`reference/kit-manifest.md`](reference/kit-manifest.md).

## Cross-cutting concerns

These thread through every subsystem above.

| Concern | What it is | Where it lives |
| :--- | :--- | :--- |
| **Audit chain** | Hash-chained JSONL append-only log of every state-changing operation. Tamper-evident: rewriting any record invalidates all later hashes. | `.sange/audit/<ISO-week>.jsonl` (per-repo); `sange audit verify` (v0.5+) checks integrity. |
| **Generators** | 14 of 16 deterministic generators emit every reference doc, every appendix, the CLI reference, the threat model table, the changelog, the kit manifest. CI re-runs them in `--check` mode on every PR. Per ADR-023 + ADR-029. | `tools/generators/`. Output frontmatter carries `input_sha256` + `output_sha256` per §16.4.1. |
| **Telemetry** | NDJSON, ISO-week sharded, opt-in (default off in v0.1, default off for the foreseeable future). Lives in `.sange/telemetry/`. External send is opt-in in v2.0 only. | `src/sange/core/telemetry/`. |
| **Secrets** | Two-pass redaction (known patterns + Shannon-entropy heuristic) on every variable into every AI prompt. Trusted-vars escape hatch is explicit. Per-provider `skip_redaction` for local providers only. | `src/sange/core/enhancer/redaction.py`. Full doc: [`security/prompt-injection.md`](security/prompt-injection.md). |
| **TerminalProfile** (v0.5+) | Adaptive output: rich tables when stdout is a TTY, plain text when piped, NDJSON when `--json`. Width detection, color depth, unicode support all detected once and passed to every surface. | `src/sange/cli/term/`. Canonical: §21. |
| **Category convention** | Every fragment tree (gitignore profiles, kit fragments, makefile modules, commit templates) follows the same `<category>/<topic>` layout. Predictable navigation; per-category indexes. | Canonical: §22 + §23. |

## Key invariants

These hold across every subsystem and every release:

1. **Local-first.** Sange runs on the developer's machine. No
   cloud dependency. Even the Web UI is a local Laravel app at
   `https://sange.test`. External services (AI providers, sigstore,
   GitHub) are opt-in integrations, never required for the core
   loop.

2. **Polyglot.** Sange wraps every supported VCS through the same
   `VCSDriver` Protocol. The CLI's user surface is identical across
   VCS — `sange commit` works on a git repo, an svn repo, an hg
   repo, etc.

3. **Generate-first** (ADR-029). Every doc, every catalog, every
   reference table is emitted by a deterministic generator that
   CI verifies on every PR. Hand-edits to generated files are not
   allowed (the file frontmatter says so).

4. **Audit everything** (ADR-031). Every state-changing operation
   appends a hash-chained record to the audit log. The session
   log captures every notable design decision. Snapshots capture
   phase boundaries. The audit trail is append-only and never
   mutates.

5. **Release-as-immutable** (CLAUDE.md global rule + ADR-018).
   A pushed tag is forever. Fix-forwards ship as `.postN` or as
   the next semver bump, never as retags.

6. **Verification before pinning** (CLAUDE.md global rule). Every
   external reference — a SHA, a release tag, a URL, an API
   endpoint — gets `curl`'d / `gh api`'d before it's committed.

## Where to read deeper

The canonical doc is sectioned by topic. The map:

| Topic | Canonical section | Reader-friendly doc |
| :--- | :--- | :--- |
| Vision, positioning, audience | §2, §4 | [`../README.md`](../README.md) intro |
| Glossary | §6 | (in §6 of the canonical doc) |
| Configuration | §10 | [`reference/config-schema.md`](reference/config-schema.md) |
| AI subsystem | §11 - §12 | [`security/prompt-injection.md`](security/prompt-injection.md) |
| `.sange/` folder | §14 | [`tools/workflow/commit-lifecycle.md#file-layout`](tools/workflow/commit-lifecycle.md#file-layout) |
| Commit lifecycle | §16 | [`tools/workflow/commit-lifecycle.md`](tools/workflow/commit-lifecycle.md) |
| Release bundling | §17 + §26 | [`security/slsa-and-sbom.md`](security/slsa-and-sbom.md), [`release.md`](release.md) |
| Container/secret model | §18 | (`docs/tools/security/container-secrets.md`, planned) |
| History purge | §19 | (`docs/tools/security/purge.md`, planned for v1.0) |
| Operations Kit | §20 | [`reference/kit-manifest.md`](reference/kit-manifest.md) |
| CLI/TUI conventions | §21 | [`reference/cli-reference.md`](reference/cli-reference.md) |
| Hooks engine | §24 | (`docs/tools/workflow/hooks.md`, planned for v0.5) |
| Web UI | §27 - §29 | (`docs/tools/ui/`, planned for v1.0) |
| Remote access | §30 | (`docs/tools/ui/remote-access.md`, planned for v1.0) |
| Plugin system | §33 | (`docs/tools/workflow/plugins.md`, planned for v1.0) |
| Innovation surface | §36 | (read §36 directly) |
| Threat model | §39 | [`security/stride.md`](security/stride.md) |
| Privacy / telemetry | §40 | (`docs/governance/privacy.md`, planned) |
| ADR index | §41 | [`adr/`](adr/) + [`.design/plans/decisions-log.md`](../.design/plans/decisions-log.md) |
| Testing strategy | §43 | (in §43 of the canonical doc) |
| Performance budgets | §44 | (in §44) |
| Roadmap | §45 | [`governance/roadmap.md`](governance/roadmap.md) |
| Implementation checklist | §47 | [`../.design/plans/checklist.md`](../.design/plans/checklist.md) |

The canonical doc is locked at v4.4. Changes go through the ADR
process documented in
[`governance/adr-process.md`](governance/adr-process.md): a new
ADR supersedes the old, the architecture deliverable picks up the
ADR's decision at the next revision number.

## What this file is not

- **It's not the spec.** That's `.design/sange-architecture.md`.
  Read it for the contractual definitions; read this file for the
  shape and the navigation.
- **It's not the API reference.** That's
  [`reference/cli-reference.md`](reference/cli-reference.md)
  (generated) + the docstrings in `src/sange/`.
- **It's not the contributor guide.** That's
  [`../CONTRIBUTING.md`](../CONTRIBUTING.md).
- **It's not a changelog.** That's
  [`../CHANGELOG.md`](../CHANGELOG.md).

## Cross-references

- [`.design/sange-architecture.md`](../.design/sange-architecture.md)
  — the canonical v4.4 deliverable, ~1500 lines, 50 sections.
- [`.design/plans/decisions-log.md`](../.design/plans/decisions-log.md)
  — 33 ADRs documenting every non-trivial decision.
- [`.design/plans/implementation-plan.md`](../.design/plans/implementation-plan.md)
  — the phased plan (Phase 0a → Phase 5).
- [`governance/roadmap.md`](governance/roadmap.md) — reader-friendly
  version map (v0.1 → v4.0+).
- [`governance/adr-process.md`](governance/adr-process.md) — how
  to propose a new architectural decision.
- [`quickstart.md`](quickstart.md) — five-minute onramp for users.
- [`tools/workflow/commit-lifecycle.md`](tools/workflow/commit-lifecycle.md)
  — end-to-end walkthrough of the v0.1 product.
