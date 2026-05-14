# Sange v3 — Architecture

**Version:** v3.0 (architecture document, derived from `sange-architecture-prompt.md` v4.0)
**Copyright:** © 2026 Simtabi LLC. Licensed under Apache License 2.0.
**Status:** Draft pending §22 execution steps 5–12 (the §16.4 generators, the consistency pass, and the §19 quality-gate review).

> This file is **item §17.1 through §17.17** of the architecture-prompt outline filled in. Items §17.18 through §17.50 are produced by the responding model via the §2.4 Generate-first / fine-tune-second discipline (CLI catalog, threat model, ADR index, references, appendices). When reading: items 1–6 are leadership-facing; 7–13 are engineering-facing; 14–17 are operational.

---

## Table of contents

1. [Executive Summary](#1-executive-summary)
2. [Vision & Positioning](#2-vision--positioning)
3. [Etymology & Naming](#3-etymology--naming)
4. [Competitive Landscape](#4-competitive-landscape)
5. [Codebase Audit Findings (v1, v2)](#5-codebase-audit-findings-v1-v2)
6. [Glossary](#6-glossary)
7. [System Architecture](#7-system-architecture)
8. [Domain Model](#8-domain-model)
9. [Adapter Specifications](#9-adapter-specifications)
10. [Configuration & Secrets](#10-configuration--secrets)
11. [AI Subsystem & Prompt Library](#11-ai-subsystem--prompt-library)
12. [Prompt Enhancer](#12-prompt-enhancer)
13. [MCP Integration](#13-mcp-integration)
14. [.sange/ Repo Folder Specification](#14-sange-repo-folder-specification)
15. [Gitignore Profile System](#15-gitignore-profile-system)
16. [Commit Message Lifecycle](#16-commit-message-lifecycle)
17. [Release Bundling](#17-release-bundling)

---

## 1. Executive Summary

Sange is the **local-first developer-experience layer between humans and their version-control systems**. It does not replace `git`, `svn`, `hg`, or `p4` — it wraps them with safety nets, AI assistance, auditability, and a CLI/TUI/Web surface so that the *workflow around* the VCS is predictable, reviewable, and approachable to people who are not seasoned engineers.

The headline capabilities at v1.0:

- **AI-assisted commit messages** with a JSON-file lifecycle (draft → pending_review → approved → committed → pushed) — every message is editable, reviewable, audit-tracked, and provenance-tagged.
- **Gitignore-swap** at publish time so dev artifacts never reach production remotes.
- **History purge** wrapping `git filter-repo`, BFG, `svnadmin dump | svndumpfilter`, `hg convert`, and `p4 obliterate` behind eight pre-flight gates, eight verification checks, a typed-phrase confirmation, and a hash-chained audit log.
- **Release bundling** producing SLSA-3 attested, sigstore-signed, SBOM-attached artifacts shippable to six destinations (GitHub Releases, GitLab Releases, OCI artifact registry, S3, generic package registries, filesystem for air-gapped).
- **Web UI** (Laravel 13 + Livewire 4 + first-party `laravel/passkeys`) with twenty-one modules covering every CLI capability plus approval queues, scheduler, secrets management, audit timeline, and a kit scaffolder.
- **Premade Operations Kit** ready to materialize: CI workflows for nine providers, release bundlers for eight tools, push-to-prod strategies for nine deployment patterns, VPS provisioning aligned to CIS benchmarks.

Built for seven personas (non-developer founder/CEO, CTO, cyber-security reviewer, junior engineer, senior staff engineer, DevOps/SRE, open-source maintainer). The happy path is one verb. The power surface opens when asked.

License Apache 2.0, © Simtabi LLC. Source at `github.com/simtabi/sange`. Marketing at `sange.sh` (when acquired) redirecting to the canonical `opensource.simtabi.com/products/sange`.

---

## 2. Vision & Positioning

### 2.1 What Sange is

> *Sange is the local-first developer-experience layer between humans and their version-control systems — eliminating boilerplate, enforcing safety, embedding AI assistance into every commit, branch, and release, and providing a secure dashboard (local or self-hosted) for fine-grained review, approval, scheduling, and orchestration.*

### 2.2 What Sange is not

- Not a replacement for `git`, `svn`, `hg`, or `p4`. It wraps them unmodified.
- Not a competing wire protocol. Pushes go through the underlying VCS to the same remotes.
- Not a repository host. GitHub, GitLab, Bitbucket, Gitea, and Forgejo remain authoritative.
- Not a fork. The on-disk repository remains valid for any `git` command run without Sange.

### 2.3 Designed-for personas

| Persona | What they get |
|---|---|
| Non-developer founder / CEO | One-click release approval in the Web UI; legible audit trail of who shipped what; never reads raw `git` output. |
| CTO / Head of Engineering | Signed-release receipts, SBOM + provenance, compliance dashboards, cross-repo health view. |
| Cyber-security reviewer | Hash-chained audit, prompt-injection defense, purge subsystem, CIS-aligned VPS kit, STRIDE threat model. |
| Junior engineer | Happy path is one verb (`sange commit`, `sange publish`); gates intercept dangerous ops before damage; errors include the precise fix. |
| Senior staff engineer | Granular subcommands, scriptable JSON output, plugin extension points, ADR-grade rigor. |
| DevOps / SRE | Premade operations kit, `sange scaffold`, deploy strategies, monitoring integrations, OIDC trusted publishing. |
| Open-source maintainer | Default-secure releases (SLSA 3), sigstore, SBOM, the commit lifecycle for community PR review queues. |

A feature usable only by the senior engineer persona — *without an equivalently safe path for the others* — is a design defect, not a power feature.

### 2.4 Engineering bar

SOLID. DRY. KISS. Zero internal repetition. No design flaws. Enterprise + military-grade security defaults. Simple enough to be powerful — powerful tools that nobody can use are not powerful.

### 2.5 What it replaces in practice

Sange does not deprecate any tool. It absorbs the *workflow glue* that engineers currently write in shell scripts, Makefiles, blog-post snippets, and tribal knowledge — and turns that glue into versioned, signed, auditable building blocks.

---

## 3. Etymology & Naming

The name *Sange* is **stylized branding** for the **sengi** — the Swahili word for the elephant shrew, popularized in conservation biology by Jonathan Kingdon (1997). The sengi is small, fast, alert, and resilient: a fitting symbol for a tool that wraps massive, complex VCSes with a light, decisive surface.

**Honest claim:** *sange* is not a headword in *Kamusi ya Kiswahili Sanifu* (TATAKI/OUP) or other authoritative Swahili dictionaries. It appears only as a peripheral Glosbe entry mapping `sange → elephant shrew`. The accepted Swahili term is **sengi**. We brand the tool *Sange* — a memorable stylization — and frame the etymology honestly. The v1 README's claim *"Sange is the Swahili name for the Elephant Shrew"* is corrected here: it is named *after* the sengi, not as a literal Swahili word.

**Sources** (accessed 2026-05-13):

- Wikipedia, *Elephant shrew*. <https://en.wikipedia.org/wiki/Elephant_shrew>
- sengis.org, *Synopsis*. <https://www.sengis.org/synopsis.php>
- California Academy of Sciences, *Evolution of Sengis*. <https://www.calacademy.org/scientists/projects/evolution-of-sengis-elephant-shrews>
- Glosbe, `sange → elephant shrew`. <https://glosbe.com/sw/en/sange>

**Naming property:**

- **GitHub repo:** `github.com/simtabi/sange` (the v1 repo's existing origin)
- **Marketing domain:** `sange.sh` (to be acquired; `.sh` ccTLD is open registration; pre-acquisition `whois sange.sh`)
- **Canonical product URL:** `https://opensource.simtabi.com/products/sange`
- **Canonical docs URL:** `https://opensource.simtabi.com/documentation/sange`
- **Marketing redirect:** `sange.sh` → `opensource.simtabi.com/products/sange`

---

## 4. Competitive Landscape

A narrative selection. The full feature-comparison matrix (≥ 15 tools) is in **Appendix H** of the prompt-bundle and is regenerated by `tools/generators/landscape.py` (deferred to a later generator pass — the matrix is hand-curated until then).

### 4.1 Commit assistants

`aicommits`, `opencommit`, `gptcommit`, `commitizen`, `czg`, GitHub Copilot CLI's commit feature. All four free / open. **The gap:** none of them ship a *commit lifecycle* — they generate a message and move on. Sange wraps the message in a JSON file with eight states, approval chain, integrity hash, and AI provenance. None offer prompt-injection defense layered into a prompt enhancer.

### 4.2 Git TUIs

`lazygit`, `gitui`, `tig`, `magit`, Sourcetree, GitKraken, Tower. Strong at *navigation*. **The gap:** none integrate the *destructive operations* (history purge, force-push, gitignore-swap) behind safety gates; none surface AI-assisted review.

### 4.3 Hook / policy

`pre-commit`, `husky`, `lefthook`, `gitleaks`, `trufflehog`, `git-secrets`, `talisman`. Each does one thing well. **The gap:** none unify hook installation, secret scanning, history purge, and the kit scaffolder under a single tool — they require multiple installs and YAML files. Sange ships them as a coordinated set.

### 4.4 Release engineering

`semantic-release`, `release-please`, `goreleaser`, `git-cliff`, `changesets`, `release-it`, `auto`. Each strong in its language ecosystem. **The gap:** none provide cross-language coverage with the same primitives. Sange's release-bundling subsystem is the abstraction layer that wraps these tools through a uniform interface.

### 4.5 AI in IDE / CLI

GitHub Copilot CLI, `aider`, `gemini-cli`, Cursor, Continue.dev. Excellent code-generation tools. **The gap:** they don't gate AI output through an editable JSON lifecycle, don't redact secrets before egress, don't carry MCP-server capabilities for their own surfaces. Sange does all three.

### 4.6 Web-based DevEx dashboards

GitButler, Graphite, Linear's git integration, Backstage, Coder, Gitpod. **The gap:** all are SaaS or require a heavyweight self-hosted infrastructure. Sange's web UI is a thin Laravel app over a local daemon, secure-by-default loopback, with optional remote-access topologies (Cloudflare Tunnel, Tailscale, WireGuard, VPS).

### 4.7 Premade operations kits

`devbox`, `chezmoi`, `nix`, `mise`, `asdf`, `dotbot`. **The gap:** these are toolchain managers. They don't ship CI scaffolds, release bundlers, push-to-prod strategies, or VPS provisioning. Sange's kit (§6.12 of the prompt) covers nine CI providers, eight release bundlers, nine deploy strategies, nine VPS providers.

### 4.8 History purge

`git-filter-repo`, BFG Repo-Cleaner, `svndumpfilter`, `hg convert`, `p4 obliterate`. The *correct* tools — Sange wraps them. **The gap:** none of them ship an integrated workflow (pre-flight rotation check, fresh-mirror enforcement, audit-chain, post-rewrite verification, collaborator-notification template, server-side housekeeping ticket payload). Sange's purge subsystem ties them into a single safe verb.

---

## 5. Codebase Audit Findings (v1, v2)

The full inventory + defect log lives in `docs/audit/v1.md`, `docs/audit/v2.md`, `docs/audit/divergence.md`. Summary:

### 5.1 v1 — `/Users/imanimanyara/Artisan/projects/opensource/sange/sange-v1`

- **6,427 lines of Bash** across 12 `.sh` files; 9 Makefile fragments + top-level Makefile.
- **0 lines of Python; 0 of PHP** (the `composer.json` is vestigial — `require: {}`).
- **Asset to preserve:** `configs/config.sh:25–128` defines `DEFAULT_GIT_COMMIT_MESSAGES`, a 104-entry emoji-prefixed array. The legacy strings carry forward into v3 via the `aliases` field on the curated ≥50-preset commit-template library (Appendix G).
- **Asset to preserve:** `helpers/scripts/error_handler.sh` — comprehensive trap-based error workflow. Its *intent* is re-implemented as `src/sange/utils/errors.py` in v3.
- **Asset to preserve:** `helpers/scripts/colors.sh` — re-implemented via `rich` theming (§7.0.1 of the prompt).
- **40+ git workflow functions** in `src/scripts/git.sh` — informed the §7.2 CLI mapping and §9.0.1 Top-25 coverage. The shell implementations are *not* ported; the *function signatures* are.

### 5.2 v2 — `/Users/imanimanyara/Artisan/projects/opensource/sange/sange-v2`

- **4,469 lines of Bash** (30 % regression vs v1).
- v2 is **a silent regression of v1**: it deleted `configs/config.sh`, `helpers/scripts/colors.sh`, `helpers/scripts/error_handler.sh`, `.github/`, and `.sange/.state` with no replacement. The deletions don't simplify; they remove safety nets.
- **Verdict:** v3 baselines on **v1**; v2 is preserved only as a cautionary diff in `docs/audit/divergence.md`.

### 5.3 Defects (severity-tagged, selected)

| Severity | Defect | File | Remediation in v3 |
|---|---|---|---|
| Medium | `eval` on dynamic uppercased variable name (`eval "${up}_ROOT=…"`) | v1 `src/scripts/git.sh:81` | Replace with Python `dataclasses` |
| Medium | No `.git` validation in some git-call sites | v1 `src/scripts/git.sh:916, 941` | `VCSDriver.git` adapter pre-checks |
| Medium | Stale absolute path in `.sange/.state` (was `/Users/imanimanyara/Artisan/projects/simtabi/opensource/automation/sange` — directory no longer exists) | v1 `.sange/.state` | v3 uses relative paths + audit chain |
| Medium | Race in `git_add` between user confirmation and stage | v1 `src/scripts/git.sh:1140` | Re-validate file existence pre-stage in `core/lifecycle/` |
| Low | Hardcoded `46`, `100` terminal widths | v1 `src/scripts/git.sh` multiple | `shutil.get_terminal_size()` via TerminalProfile (§7.0.2) |
| Low | Color codes redefined in every function (~200 redundant lines) | v1 `src/scripts/*.sh` | `rich` theming, once |
| Low | Mixed concerns in `git_add` (167 lines, four responsibilities) | v1 `src/scripts/git.sh:1035+` | Split into `_gather / _confirm / _execute / _report` |

### 5.4 Anti-patterns the v3 design avoids

- Per-package Makefile copied into every repo (drift). **v3:** auto-generated Makefile shim, fragments in `.sange/makefiles/<category>/` (§10).
- No audit trail. **v3:** hash-chained JSONL (§7.0.7).
- Inline error trap losing context. **v3:** `structlog` + `transcript_hash`.
- No `--dry-run` discipline. **v3:** `--dry-run` is the default for destructive verbs.

### 5.5 The "default commit messages array"

Captured verbatim in `docs/audit/v1.md` and condensed in Appendix G with a v1→v3 migration map. Curation rules in §6.8.5 of the prompt: dedupe (multiple cosmetic-emoji variations collapse), filter (non-commit operational nouns removed — e.g. `📤 cron: send report` is not a commit message), re-taxonomize under Conventional Commits 1.0.0, structure (`id, category, type, scope, template, description, applies_to, requires_body, breaking_change, tags, aliases`).

---

## 6. Glossary

| Term | Meaning |
|---|---|
| **`.sange/`** | Per-repo metadata folder Sange manages (config, profiles, makefiles, prompts, commits, bundles, audit, telemetry, purge plans). |
| **ADR** | Architecture Decision Record. One per non-trivial decision; numbered ADR-001 onward; indexed in §41 of the architecture deliverable. |
| **Audit chain** | Hash-chained JSONL log; each entry's `entry_hash` covers the canonical JSON of the entry minus the hash field, plus the previous entry's `entry_hash`. Tampering is detectable. |
| **BYOK** | Bring Your Own Key. Sange does not host AI keys — users supply their own provider tokens. |
| **Category convention** | The subgrouped directory convention (§10.4 of the prompt): `_core/`, `_local/`, plus purpose-named sub-directories (`vcs/`, `lang/`, `framework/`, `infra/`, `cloud/`, `ci/`, `release/`, `security/`, `ai/`, `db/`, `editor/`, `os/`, `domain/`, `type/`, `workflow/`). |
| **Chainable / fluent API** | The idiomatic Python surface for Sange domain objects (§6.13 of the prompt): every chain method returns `self`; terminal verbs trigger side effects. |
| **Commit lifecycle** | The 8-state machine the JSON commit file traverses (`draft → pending_review → approved → committed → pushed → archived`, plus `rejected` and `discarded`, plus the `reopen` reverse edge). |
| **Generate-first** | The §2.4 discipline: token-heavy deliverable content is produced by deterministic generator scripts under `tools/generators/`; the model fine-tunes prose, not catalog tables. |
| **MCP** | Model Context Protocol. Sange is both an MCP **server** (exposing capabilities) and an MCP **client** (consuming external MCP servers). It is **not** an MCP host (that's the LLM application, e.g. Claude Desktop). |
| **Plan / Bundle / Purge / Commit JSON** | The four object types Sange tracks lifecycles for. Each has an explicit state machine and a JSON schema. |
| **Prompt Enhancer** | The §6.7.1 subsystem that transforms raw user input into structured prompts before any AI call. Single ingress point. |
| **`sanged`** | The Python daemon (long-running process; per-OS supervisor). The CLI / TUI / Web UI all talk to it via JSON-RPC. |
| **Sengi** | The Swahili word for the elephant shrew. The animal whose attributes (small, fast, resilient) the brand evokes; *sange* is a stylization. |
| **TerminalProfile** | The §7.0.2 dataclass computed at process start: `(is_tty, is_ci, encoding, has_utf8, is_windows, is_modern_windows_terminal, shell, color_mode, use_emoji, use_unicode_box_chars, width)`. Every visual primitive accepts it. |
| **Typed-phrase gate** | The §7.0.5 confirmation pattern: the user types a phrase with a per-session nonce before destructive operations proceed. |

The expanded glossary is regenerated as `docs/reference/glossary.md` by `tools/generators/glossary.py` (a future generator); the table above is the v1.0 stable subset.

---

## 7. System Architecture

### 7.1 Layered diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│  Presentation                                                           │
│  ─────────────                                                          │
│  CLI (typer + rich)   TUI (textual)   Web UI (Laravel 13 + Livewire 4) │
│  JSON-RPC client      JSON-RPC client  JSON-RPC client                  │
│  MCP server (stdio / HTTP+SSE / streamable HTTP)                        │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │  JSON-RPC 2.0 (HMAC local / mTLS remote)
┌────────────────────────────────────▼────────────────────────────────────┐
│  sanged daemon                                                          │
│  ──────────────                                                         │
│  Health endpoint   IPC server   Scheduler   MCP client+server runtime   │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │
┌────────────────────────────────────▼────────────────────────────────────┐
│  Application                                                            │
│  ─────────────                                                          │
│  Commit lifecycle   Bundle lifecycle   Purge lifecycle   Hook engine    │
│  Prompt enhancer    Workflow runner    Scheduler         Policy engine  │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │
┌────────────────────────────────────▼────────────────────────────────────┐
│  Domain                                                                 │
│  ───────                                                                │
│  Repo  Commit  Branch  Release  Bundle  Approval  AuditEntry  PurgePlan │
│  CommitTemplate  GitignoreProfile  ScaffoldFragment  TerminalProfile    │
│  (VCS-agnostic; no driver imports allowed)                              │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │
┌────────────────────────────────────▼────────────────────────────────────┐
│  Adapters                                                               │
│  ─────────                                                              │
│  VCSDriver Protocol → git.py, svn.py, hg.py (v2), p4.py (v3)            │
│  AIProvider Protocol → anthropic, openai, ollama, gemini, bedrock, …    │
│  Secrets → keyring, vault, 1password, age, gpg                          │
│  Containers → docker, podman                                            │
│  MCP transports → stdio, http_sse, streamable_http                      │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │
┌────────────────────────────────────▼────────────────────────────────────┐
│  Infrastructure                                                         │
│  ──────────────                                                         │
│  Filesystem  Network  OS keychain  Edge tunnels  External AI providers  │
└─────────────────────────────────────────────────────────────────────────┘
```

**Invariants:**

1. **Domain knows nothing about VCS.** A `Commit` doesn't know whether its source is Git or SVN. The Adapter layer is the only path to the underlying tool.
2. **Web UI cannot bypass Application.** The Laravel app is a JSON-RPC client. It cannot import the Python `core/` directly; it cannot reach Adapters at all.
3. **Application is async-aware** (`asyncio` throughout). Long-running operations stream progress per §7.0.4.
4. **New Adapter = zero core changes.** Adding Mercurial in v2.0 = implementing `VCSDriver` in `adapters/vcs/hg.py`; nothing in Application or Domain changes.
5. **New Presentation surface = zero Application changes.** A future `editor-plugin/` directory implementing JSON-RPC on a different transport requires no Application rework.

### 7.2 Sequence diagrams — top 10 flows

Rendered as Mermaid `.mmd` files under `diagrams/`:

1. `sange commit` happy path: stage → AI-generate → approve → commit → push
2. `sange purge execute`: pre-flight gates → mirror → analyze → preview → typed-phrase → execute → verify → push → housekeeping
3. `sange publish`: gitignore-swap → push → restore → audit
4. `sange bundle build → sign → publish`
5. Daemon health probe + IPC handshake (HMAC local / mTLS remote)
6. MCP server tool call from Claude Desktop → daemon → adapter → response
7. Prompt enhancer dataflow: user input → enhancer → provider → validator → response
8. Web UI passkey login → daemon authorization → session
9. Scheduler firing a release → daemon checks lifecycle → typed-phrase relay to CLI if destructive
10. `sange recover` after a crashed publish: read recovery file → restore gitignore → audit

Each diagram lives at `diagrams/<flow>.mmd` and is rendered as SVG by the docs CI workflow.

### 7.3 Component diagram

```
        ┌───────────────┐    ┌───────────────┐    ┌───────────────┐
        │   CLI         │    │     TUI       │    │   Web UI      │
        │  (typer)      │    │  (textual)    │    │ (Laravel 13)  │
        └───────┬───────┘    └───────┬───────┘    └───────┬───────┘
                │                    │                    │
                └────────────┬───────┴────────────────────┘
                             │
                  ┌──────────▼──────────┐
                  │    sanged daemon    │
                  │  (Python 3.12+)     │
                  └──────────┬──────────┘
                             │
        ┌────────────────────┼────────────────────┐
        │                    │                    │
   ┌────▼────┐         ┌─────▼─────┐         ┌────▼────┐
   │ Domain  │         │Application│         │   AI    │
   │  Layer  │◄────────┤   Layer   ├────────►│Provider │
   └─────────┘         └─────┬─────┘         └─────────┘
                             │
                       ┌─────▼─────┐
                       │ Adapters  │
                       │ (VCS, …)  │
                       └───────────┘
```

### 7.4 Deployment diagrams (local, LAN, remote)

**Local-only (default):**

```
[user laptop]
    sanged ←→ CLI/TUI                127.0.0.1
    sanged ←→ Laravel app ←→ browser https://sange.test
                                     (mkcert TLS, HMAC-signed IPC)
```

**LAN:**

```
[user laptop]                       [other LAN device]
    sanged ←─ IPC ─→ CLI/TUI/Laravel  ─── HTTPS ─→ browser
                                                   (LAN IP, mkcert intermediate)
```

**Remote (any of four topologies):**

```
[user laptop / VPS]              [Cloudflare edge / Tailscale tailnet / WG peer / VPS direct]
    sanged ←─ IPC (mTLS) ─→ Laravel ←─ HTTPS+mTLS+MFA+IP-allowlist ─→ remote browser
                                  (cloudflared / tailscaled / wg-quick / Caddy)
```

The remote mode enforces three controls *simultaneously*: mTLS daemon-to-Laravel, MFA on at least one user role, IP allowlist for direct VPS exposure. `sange web remote audit` refuses to start if any control is missing.

---

## 8. Domain Model

The Domain is pure data + behavior, VCS-agnostic. Every class is a `dataclass` (or Pydantic v2 model when validation matters) plus a chainable façade (§6.13).

### 8.1 Core entities

```python
@dataclass(frozen=True)
class Repo:
    path: Path
    vcs: Literal["git", "svn", "hg", "p4"]
    remote: str | None
    default_branch: str
    detected_at: datetime

@dataclass
class Commit:
    id: str                       # ULID (the lifecycle file's id field)
    counter: int                  # monotonic per repo
    status: CommitStatus          # the 8-state enum
    repo: Repo
    message: CommitMessage
    diff: CommitDiff
    ai: AIProvenance | None
    approvals: list[Approval]
    rejections: list[Rejection]
    created_at: datetime
    updated_at: datetime
    schema_version: int

@dataclass
class Branch:
    name: str
    repo: Repo
    ahead: int
    behind: int
    last_activity: datetime
    owner: str | None
    age_days: int

@dataclass(frozen=True)
class Release:
    version: SemVer
    repo: Repo
    channel: Literal["stable", "beta", "nightly"] | str
    bundles: list[Bundle]
    signed_tag: bool
    published_at: datetime | None

@dataclass
class Bundle:
    name: str
    version: SemVer
    visibility: Literal["public", "private"]
    destinations: list[BundleDestination]
    manifest_path: Path
    artifacts: list[BundleArtifact]
    state: BundleState
    sbom_path: Path | None
    signatures: list[Signature]

@dataclass
class PurgePlan:
    plan_id: str                  # purge-<utc-iso>-<nonce>
    state: PurgeState             # 10-state machine
    vcs: Literal["git", "svn", "hg", "p4"]
    repo: Repo
    filters: PurgeFilters
    gates: list[GateCheck]
    counts: PurgeCounts | None
    backup_path: Path | None
    mirror_path: Path | None
    audit_chain_position: str     # last entry hash on creation

@dataclass(frozen=True)
class Approval:
    actor: str                    # "user@host"
    at: datetime
    via: Literal["cli", "tui", "web", "mcp"]
    typed_phrase: str | None      # for destructive ops

@dataclass(frozen=True)
class AuditEntry:
    event_id: str
    timestamp: datetime
    operator: str
    operation: str
    state_from: str | None
    state_to: str | None
    payload: dict
    prev_hash: str
    entry_hash: str
    schema_version: int
```

### 8.2 Domain enums

- `CommitStatus`: `draft`, `pending_review`, `approved`, `rejected`, `committed`, `pushed`, `archived`, `discarded`
- `PurgeState`: `planned`, `preflight_passed`, `analyzed`, `previewed`, `confirmed`, `executing`, `verified`, `completed`, `aborted`, `rolled_back`
- `BundleState`: `plan`, `build`, `sign`, `verify`, `publish`, `verify-published`, `released`, `held`

### 8.3 Domain invariants

1. Every state transition produces an `AuditEntry`.
2. State transitions are forward-only; backward transitions are explicit (`reopen`, `rollback`) and themselves audited.
3. Domain objects are JSON-serializable round-trip (`to_dict` / `from_dict`).
4. Domain objects never import from `adapters/`; they import only from `domain/` and stdlib.

---

## 9. Adapter Specifications

### 9.1 `VCSDriver` Protocol (v1.0 — Git + SVN)

```python
class VCSDriver(Protocol):
    """The VCS-agnostic surface. Every concrete VCS adapter implements this."""

    name: ClassVar[Literal["git", "svn", "hg", "p4"]]

    def detect(self, path: Path) -> bool: ...
    def info(self, repo: Repo) -> RepoInfo: ...
    def status(self, repo: Repo) -> WorkingTreeState: ...
    def add(self, repo: Repo, paths: list[Path]) -> None: ...
    def commit(self, repo: Repo, message: str, *, author: str | None = None) -> Commit: ...
    def push(self, repo: Repo, *, remote: str = "origin", force: bool = False) -> PushResult: ...
    def fetch(self, repo: Repo, *, remote: str = "origin") -> FetchResult: ...
    def pull(self, repo: Repo, *, remote: str = "origin", strategy: PullStrategy = "rebase") -> PullResult: ...
    def branch(self, repo: Repo) -> list[Branch]: ...
    def checkout(self, repo: Repo, ref: str) -> None: ...
    def log(self, repo: Repo, *, limit: int = 100) -> list[Commit]: ...
    def diff(self, repo: Repo, *, staged: bool = False) -> Diff: ...
    def tag(self, repo: Repo, name: str, *, message: str | None = None, sign: bool = False) -> Tag: ...
    def stash(self, repo: Repo, *, message: str | None = None) -> StashRef: ...
    def reset(self, repo: Repo, *, mode: ResetMode, ref: str) -> None: ...
    def revert(self, repo: Repo, ref: str) -> Commit: ...
    def reflog(self, repo: Repo) -> list[ReflogEntry]: ...
    def gc(self, repo: Repo, *, aggressive: bool = False, prune_now: bool = False) -> None: ...
    def fsck(self, repo: Repo) -> FsckReport: ...
    # … and the purge-relevant primitives for §6.11:
    def mirror_clone(self, remote: str, dest: Path) -> Repo: ...
    def analyze_history(self, repo: Repo) -> HistoryAnalysis: ...
    def rewrite_history(self, repo: Repo, plan: PurgePlan) -> RewriteResult: ...
    def force_push_mirror(self, repo: Repo, remote: str) -> PushResult: ...
```

### 9.2 Git adapter (v1.0)

Implementation backed by `subprocess` against the `git` CLI (no `pygit2` / `dulwich` — keeps the dependency surface minimal). Uses `asyncio.create_subprocess_exec` per §7.0.6. Supports `git filter-repo` + BFG via `core/purge/executor.py`.

### 9.3 SVN adapter (v0.5)

Implementation backed by `subprocess` against `svn`, `svnadmin`, `svnlook`, `svndumpfilter`. Read operations land in v0.5; destructive operations + purge land in v2.0 with the branch/tag copy-graph handling.

### 9.4 Mercurial / Fossil / Pijul adapters (v2.0 stubs)

The Protocol shape is fixed at v1.0. v2.0 implements:

- `adapters/vcs/hg.py` — `hg` CLI + `hg convert --filemap` for purge
- `adapters/vcs/fossil.py` — `fossil` CLI
- `adapters/vcs/pijul.py` — `pijul` CLI

### 9.5 Perforce adapter (v3.0 stub)

`adapters/vcs/p4.py` — `p4` CLI; admin-role-gated for `p4 obliterate`; spec-file scrubbing reminders per §6.11.

### 9.6 `AIProvider` Protocol

```python
class AIProvider(Protocol):
    """Provider-agnostic AI surface. Every implementation wraps a single vendor."""

    name: ClassVar[str]

    def list_models(self) -> list[ModelInfo]: ...
    async def complete(self, prompt: EnhancedPrompt, *, model: str, max_tokens: int) -> Completion: ...
    async def stream(self, prompt: EnhancedPrompt, *, model: str) -> AsyncIterator[CompletionChunk]: ...
    def cost_estimate(self, prompt: EnhancedPrompt, *, model: str) -> CostEstimate: ...
    def tos_url(self) -> str: ...
```

Implementations (v1.0): `anthropic`, `openai`, `ollama`, `gemini`, `bedrock`, `azure_openai`, `mcp_routed` (delegates to a configured MCP server).

---

## 10. Configuration & Secrets

### 10.1 Precedence (rightmost wins)

```
built-in defaults  ←  /etc/sange/*  ←  ~/.sange/*  ←  ${repo}/.sange/*  ←  ENV  ←  CLI flags
```

### 10.2 File formats

- **TOML** for human-edited (`config.toml`, `commit-templates/*.toml`)
- **JSON** for machine-generated (`.sange/commits/*.json`, `.sange/audit/*.jsonl`, IPC payloads)
- Detection by extension. If both `config.toml` and `config.json` exist in the same directory, JSON wins (machine-authoritative) and a warning is logged. Both parse into the same Pydantic v2 model.

### 10.3 `SangeConfig` (the single Pydantic model)

```python
class SangeConfig(BaseModel):
    schema_version: int = 1
    ai: AIConfig                    # providers, BYOK, redaction policy
    commit: CommitConfig            # template paths, default-status
    gitignore: GitignoreConfig      # active profile name + composition
    bundle: BundleConfig            # destinations, default channel
    purge: PurgeConfig              # ref-budget, batch policy
    secrets: SecretsConfig          # backend choice
    telemetry: TelemetryConfig      # local-only in v1
    web: WebConfig                  # mode (local/lan/remote), auth methods
    mcp: MCPConfig                  # client servers + server-export toggles
    scaffold: ScaffoldConfig        # kit version pin
```

### 10.4 Secrets

**Never in TOML or JSON.** Always via:

1. **OS keychain** (default) via the `keyring` library
2. **External secret managers** (AWS Secrets Manager, HashiCorp Vault, 1Password CLI, Bitwarden CLI)
3. **Encrypted files** (`age`, GPG)
4. **`.env` files with `0600` perms** (fallback)

The secrets sub-system reports values *only* via the `core/secrets/resolver` which never logs the resolved value; metadata (provider, last-rotated, scope) is the only thing rendered.

---

## 11. AI Subsystem & Prompt Library

### 11.1 Provider Protocol

See §9.6.

### 11.2 Stream-first

Every prompt is streamed when the provider supports it. The TUI / CLI / Web UI render tokens as they arrive. Streamed content is captured for the audit chain (the transcript hash covers the joined stream).

### 11.3 Untrusted input handling

All AI-bound text from outside the user's direct typed input — diffs, foreign commit messages, file contents, MCP-server responses — is **wrapped in `<untrusted_input>` delimiters** with an explicit system-prompt instruction to treat them as data, not instructions. The wrapping is performed by the Prompt Enhancer (§12), so no caller bypasses it.

### 11.4 Content firewall

Sange runs every LLM input and output through:

- **Pattern scanner** detecting known prompt-injection markers (`Ignore previous instructions`, `</user_input>` mid-content, base64-encoded instruction blocks, etc.)
- **Output validator** that rejects responses asking Sange to skip its own gates
- **Redaction layer** scrubbing high-entropy strings, configured secret patterns, and configurable PII patterns *before egress*

### 11.5 Confirmation discipline

Output that would modify the repo requires **explicit user confirmation** (typed-phrase if destructive, Y/n if reversible). AI does not silently commit.

### 11.6 BYOK + provider transparency

All keys are user-supplied; Sange never hosts them. `sange ai providers` lists every configured provider with: model list, ToS URL, current month spend, approximate per-call cost, key source (which keychain entry).

---

## 12. Prompt Enhancer

The only path by which raw user input reaches an AI provider.

### 12.1 Flow

```
User input → Enhancer → Provider → Response → Validator → User
              ↑                                  ↓
       Prompt templates                    Schema enforcement
       Repo context                        Pattern firewall
       Few-shot examples                   Redaction (output)
       Model-specific tuning               Audit chain entry
       Output schema
```

### 12.2 Properties

- **Model-agnostic** — Claude prefers XML delimiters, GPT JSON, local models markdown; per-model adapters select the format.
- **Versioned** — every template carries `prompt_version`; every AI call records the version used.
- **Auditable** — `sange ai preview --task commit` shows the exact prompt that would be sent without sending it.
- **Configurable** — users override templates per-project via `.sange/prompts/`.
- **Composable** — templates can include other templates; circular includes refuse.
- **Schema-enforcing** — JSON-output tasks attach a schema; failed validation retries once then surfaces.
- **Plugin point** — third-party plugins register task templates and model adapters.

### 12.3 Task templates (v1.0)

`commit-msg`, `pr-description`, `changelog`, `code-review`, `diff-summary`, `branch-name`, `release-notes`, `commit-message-explanation`, `breaking-change-detection`, `secret-pattern-match`.

---

## 13. MCP Integration

Sange uses the Model Context Protocol in two roles:

### 13.1 As MCP client

Sange connects to user-configured MCP servers (Jira, Linear, GitHub MCP, internal docs) for additional context. Servers are allowlisted, capability-reviewed at install, and revocable per-project. Transports supported: `stdio`, `http_sse`, `streamable_http`.

```toml
# .sange/config.toml
[mcp.servers.jira]
transport = "http_sse"
url = "http://localhost:7831/mcp"
allowed_tools = ["search_issues", "get_issue"]
allowed_resources = ["jira://project/PROJ"]
```

### 13.2 As MCP server

Sange exposes its capabilities so MCP hosts (Claude Desktop, Claude Code, Cursor, Continue.dev) can drive Sange operations with full audit + gate enforcement.

Exposed tools (v1.0):

- `commit_generate` / `commit_submit` / `commit_approve` / `commit_commit` / `commit_push`
- `branch_list` / `branch_create` / `branch_delete`
- `bundle_plan` / `bundle_build` / `bundle_publish` (build-only; publish requires terminal-side typed-phrase relay)
- `purge_plan` / `purge_preview` (read-only; execute requires terminal-side typed-phrase per ADR-018)
- `scaffold_list` / `scaffold_show` / `scaffold_add`

Configuration in `.sange/config.toml`:

```toml
[mcp.server]
enabled = true
bind = "stdio"                  # or "127.0.0.1:7820" for http_sse
auth = "shared-secret"          # token from OS keychain
allowed_tools = ["commit_generate", "commit_submit", "scaffold_list"]
rate_limit_per_minute = 60
```

### 13.3 Sange is not an MCP host

Per the spec terminology, *host* = the LLM application. Sange is a developer tool. We are both a **server** (exposing capabilities) and a **client** (consuming external context). The v3.1 / v3.2 corrections to earlier drafts that called Sange an "MCP host" stand.

---

## 14. .sange/ Repo Folder Specification

The subgrouped layout per the §10.4 Category convention. Full tree:

```
.sange/
├── config.toml                      # repo policy
├── .counter                         # durable monotonic commit counter
├── gitignore/                       # gitignore-swap engine (§15)
│   ├── dev.gitignore                # active during development
│   ├── prod.gitignore               # active during publish
│   └── profiles/
│       ├── _core/                   # secrets.gitignore, editor-noise.gitignore
│       ├── lang/                    # python, node, php, go, rust, ruby, java
│       ├── framework/               # laravel, django, rails, nextjs, nuxt, symfony
│       ├── infra/                   # docker, kubernetes, terraform
│       ├── editor/                  # jetbrains, vscode, vim, emacs, claude
│       └── os/                      # macos, windows, linux
├── makefiles/                       # modular Makefile fragments — §10 + §10.4
│   ├── _core/                       # help.mk, colors.mk, env.mk
│   ├── vcs/                         # git.mk, svn.mk, hg.mk, p4.mk
│   ├── lang/                        # python.mk, node.mk, php.mk, …
│   ├── framework/                   # laravel.mk, django.mk, …
│   ├── infra/                       # docker.mk, compose.mk, k8s.mk
│   ├── ci/                          # github.mk, gitlab.mk, azure.mk, …
│   ├── release/                     # semver.mk, changelog.mk, bundle.mk, sign.mk
│   ├── security/                    # scan.mk, purge.mk
│   ├── ai/                          # providers.mk, mcp.mk
│   ├── db/                          # postgres.mk, mysql.mk, sqlite.mk
│   └── _local/                      # user customizations, gitignored
├── commits/                         # JSON commit lifecycle (§16)
│   ├── NNNN-feat-auth.json
│   └── archive/
│       └── YYYY-MM/
├── commit-templates/                # message presets
│   ├── default.toml                 # curated ≥50 presets — Appendix G
│   ├── _core/                       # conventional.tmpl, header-footer.tmpl
│   ├── type/                        # feat, fix, docs, …
│   ├── workflow/                    # release, hotfix, cherry-pick, merge, …
│   ├── domain/                      # security, deps, license
│   └── user/                        # user-authored overrides
├── bundles/                         # release bundling (§17)
│   ├── manifests/
│   └── artifacts/<name>-<version>/
├── hooks/                           # source-controlled hooks
│   ├── pre-commit/
│   ├── prepare-commit-msg/
│   ├── commit-msg/
│   ├── pre-push/
│   ├── post-merge/
│   └── _core/
├── workflows/                       # CI workflow definitions
│   ├── _core/
│   ├── github/
│   ├── gitlab/
│   ├── azure/
│   ├── bitbucket/
│   ├── gitea/
│   ├── forgejo/
│   ├── circleci/
│   └── jenkins/
├── prompts/                         # AI prompt templates
│   ├── _core/
│   ├── commit/
│   ├── pr/
│   ├── changelog/
│   ├── review/
│   ├── explain/
│   ├── branch/
│   └── release-notes/
├── secrets/                         # encrypted secrets, gitignored
│   ├── _local/                      # age- or GPG-encrypted files
│   └── refs/                        # references to external secret managers
├── purge/                           # history purge plans + audits
│   └── <utc-ts>-<nonce>/
│       ├── plan.json
│       ├── analysis.json
│       ├── backup-<ts>.tar.gz
│       └── audit/
├── audit/                           # global hash-chained JSONL
│   ├── *.jsonl
│   └── transcripts/                 # subprocess transcripts (referenced by hash)
├── telemetry/                       # local-only NDJSON, weekly rotation
│   └── YYYY-WW.ndjson
└── web/                             # web UI per-repo overrides
    ├── theme/
    └── dashboards/
```

Per the §10.4 Category convention: every sub-tree uses `_core/`, `_local/`, plus purpose-named categories from the canonical list. Flat fragments (e.g. `gitignore/profiles/python.gitignore` directly under `profiles/`) are forbidden — `sange doctor` flags them and offers `sange fix --reorganize`.

---

## 15. Gitignore Profile System

### 15.1 The swap

A repo holds two active files:

- `.sange/gitignore/dev.gitignore` — active during development; ignores `node_modules/`, `vendor/`, `.idea/`, `.claude/`, `.phpunit.cache`, etc.
- `.sange/gitignore/prod.gitignore` — active during `sange publish`; ignores in addition all dev-only files that must not reach production remotes (e.g. fixtures, design assets, contract drafts).

Both files are *composed* from named profiles under `.sange/gitignore/profiles/<category>/<name>.gitignore`:

```toml
# .sange/config.toml
[gitignore.dev]
extends = ["lang/python", "framework/laravel", "editor/jetbrains", "os/macos"]

[gitignore.prod]
extends = ["lang/python", "framework/laravel", "os/macos"]
exclude_additional = ["docs/internal/**", "**/fixtures/**"]
```

### 15.2 Transactional swap

`sange publish` performs:

1. File lock on `.gitignore` and a `.sange/.recovery` sentinel
2. Atomic rename: current `.gitignore` → `.sange/.tmp/.gitignore.dev`; `prod.gitignore` → `.gitignore`
3. `git push`
4. Atomic rename back
5. Remove the recovery sentinel

On any failure path (SIGKILL, crash, network drop):

- The `.sange/.recovery` file persists on disk
- `sange recover` reads it on next invocation and restores the dev profile
- The recovery operation is audit-logged

Refuses to run if:

- Another `git` operation is in progress (detected via `.git/index.lock`)
- Working tree is dirty (must commit or stash first)
- Recovery file from a prior crash exists (must `sange recover` first)

### 15.3 Composition rules

- `extends` order matters — later entries override earlier ones
- `_core/secrets.gitignore` (always-on safety net for `*.pem`, `*.key`, `.env`, etc.) is included automatically; can only be disabled with `gitignore.policy.allow_safety_off = true` in `config.toml` (audit-logged)
- `_core/license.gitignore` safety profile is auto-loaded for every repo; it *blocks* any profile (including plugin-provided) from excluding `LICENSE*`, `COPYING`, `NOTICE`, `README*`
- Globs use git's `.gitignore` syntax exactly; no Sange-specific extensions

### 15.4 Profile Registry (the supported-set)

The registry is **the** source of truth for which languages, frameworks, infrastructure tools, editors, and operating systems Sange knows about. **v1.0 ships 35 profiles**, each declaring:

1. **Auto-detection signals** — file-presence triggers that put the profile in the suggestion list (`pyproject.toml` → `lang/python`; `composer.json` containing `laravel/framework` → `framework/laravel`).
2. **Pattern scope per file class** — `always` (ignored both in dev and prod), `dev_only` (ignored in development tree but **also** in publish — these never ship), `prod_only` (ignored only when publishing — useful for fixtures, test data, dev-only credentials examples).
3. **Composition via `extends`** — `framework/laravel` extends `lang/php`; `framework/django` extends `lang/python`; etc.
4. **Versioning + maintainer** — semver; renames forbidden in minor releases; major releases ship a migration map.

#### 15.4.1 The v1.0 supported set

| Category | Profile | Auto-detect signal | Key patterns |
|---|---|---|---|
| `_core` | `_core/secrets` | (always-on) | `*.pem`, `*.key`, `*.p12`, `id_rsa*`, `.env`, `.env.*`, `credentials*`, `secrets*` |
| `_core` | `_core/editor-noise` | (always-on) | `.DS_Store`, `Thumbs.db`, `desktop.ini`, `*.swp`, `*~` |
| `_core` | `_core/license` | (always-on, *safety*) | Refuses to exclude `LICENSE*`, `COPYING`, `NOTICE`, `README*` from any composition |
| `lang` | `lang/python` | `pyproject.toml`, `setup.py`, `requirements.txt`, `Pipfile` | `__pycache__/`, `.venv/`, `*.pyc`, `.ruff_cache/`, `.mypy_cache/`, `.pytest_cache/`, `dist/`, `build/`, `*.egg-info/` |
| `lang` | `lang/node` | `package.json`, `package-lock.json`, `yarn.lock`, `pnpm-lock.yaml`, `bun.lockb` | `node_modules/`, `.npm/`, `.yarn/`, `.pnp.*`, `dist/`, `coverage/`, `.next/`, `.nuxt/` |
| `lang` | `lang/php` | `composer.json`, `composer.lock` | `vendor/`, `composer.phar`, `.phpunit.cache`, `.phpunit.result.cache` |
| `lang` | `lang/go` | `go.mod`, `go.sum` | `bin/`, `pkg/`, `*.exe`, `*.test`, `vendor/` (when `go.mod` lacks `vendor` directive) |
| `lang` | `lang/rust` | `Cargo.toml`, `Cargo.lock` | `target/`, `**/*.rs.bk` |
| `lang` | `lang/ruby` | `Gemfile`, `Gemfile.lock`, `*.gemspec` | `.bundle/`, `vendor/bundle/`, `*.gem`, `.byebug_history`, `.rspec_status`, `coverage/` |
| `lang` | `lang/java` | `pom.xml`, `build.gradle`, `build.gradle.kts`, `gradlew` | `target/`, `build/`, `*.class`, `*.jar`, `*.war`, `.gradle/` |
| `lang` | `lang/dotnet` | `*.csproj`, `*.fsproj`, `*.sln`, `global.json` | `bin/`, `obj/`, `*.user`, `*.suo`, `packages/` |
| `lang` | `lang/elixir` | `mix.exs`, `mix.lock` | `_build/`, `deps/`, `*.beam`, `.elixir_ls/` |
| `lang` | `lang/swift` | `Package.swift`, `*.xcodeproj/`, `*.xcworkspace/` | `.build/`, `DerivedData/`, `Pods/`, `Carthage/` |
| `lang` | `lang/kotlin` | `build.gradle.kts`, `settings.gradle.kts` | (composes `lang/java` + `editor/jetbrains`) |
| `lang` | `lang/dart` | `pubspec.yaml`, `pubspec.lock` | `.dart_tool/`, `build/`, `.packages` |
| `framework` | `framework/laravel` | `artisan` + `composer.json` declares `laravel/framework` | `bootstrap/cache/`, `storage/logs/`, `storage/framework/`, `Homestead.*` (extends `lang/php`) |
| `framework` | `framework/django` | `manage.py` + `requirements.txt` declares `Django` | `*.log`, `db.sqlite3*`, `staticfiles/`, `media/` (extends `lang/python`) |
| `framework` | `framework/rails` | `bin/rails` + `Gemfile` declares `rails` | `tmp/`, `log/`, `*.rbc`, `storage/`, `config/master.key` (extends `lang/ruby`) |
| `framework` | `framework/nextjs` | `next.config.js`, `next.config.mjs`, `next.config.ts` | `.next/`, `out/`, `next-env.d.ts` (extends `lang/node`) |
| `framework` | `framework/nuxt` | `nuxt.config.js`, `nuxt.config.ts` | `.nuxt/`, `.output/`, `dist/` (extends `lang/node`) |
| `framework` | `framework/symfony` | `bin/console` + composer declares `symfony/symfony` | `var/`, `public/bundles/` (extends `lang/php`) |
| `framework` | `framework/astro` | `astro.config.mjs`, `astro.config.ts` | `dist/`, `.astro/` (extends `lang/node`) |
| `framework` | `framework/sveltekit` | `svelte.config.js`, `svelte.config.ts` | `.svelte-kit/`, `build/` (extends `lang/node`) |
| `framework` | `framework/flutter` | `pubspec.yaml` declares `flutter:` | `.flutter-plugins`, `build/`, `*.iml` (extends `lang/dart`) |
| `infra` | `infra/docker` | `Dockerfile`, `compose.yml`, `docker-compose.yml` | `*.local`, plus a separate `.dockerignore` materialized for build context |
| `infra` | `infra/kubernetes` | `kustomization.yaml`, `helm/Chart.yaml`, `*.k8s.yaml` | `charts/*.tgz`, `kubeconfig*` (always — secret-class) |
| `infra` | `infra/terraform` | `*.tf`, `*.tfvars` | `.terraform/`, `*.tfstate`, `*.tfstate.backup`, `*.tfplan`, `.terraform.lock.hcl` (tracked or not per team policy) |
| `infra` | `infra/ansible` | `ansible.cfg`, `inventory.yml`, `playbook.yml` | `*.retry`, `roles/*.tar.gz`, `ansible.log` |
| `infra` | `infra/pulumi` | `Pulumi.yaml`, `Pulumi.*.yaml` | `Pulumi.*.yaml.bak`, language-specific deps |
| `editor` | `editor/jetbrains` | `.idea/` exists | `.idea/`, `*.iml`, `*.iws`, `out/`, `.idea_modules/` |
| `editor` | `editor/vscode` | `.vscode/` exists | `.vscode/`, `.history/`, `*.vsix` |
| `editor` | `editor/vim` | `.vim/` exists or `~/.vimrc` references | `*.swp`, `*~`, `Session.vim`, `.netrwhist` |
| `editor` | `editor/emacs` | `*.el` files or `.emacs.d/` exists | `*~`, `\#*\#`, `auto-save-list`, `tramp` |
| `editor` | `editor/claude` | `.claude/` exists | `.claude/`, `CLAUDE.local.md` |
| `os` | `os/macos` | (host detected) | `.DS_Store`, `.AppleDouble`, `.LSOverride`, `._*`, `.Spotlight-V100`, `.Trashes` |
| `os` | `os/windows` | (host detected) | `Thumbs.db`, `Desktop.ini`, `$RECYCLE.BIN/`, `*.lnk`, `*.cab`, `*.msi` |
| `os` | `os/linux` | (host detected) | `*~`, `.fuse_hidden*`, `.directory`, `.Trash-*`, `.nfs*` |

#### 15.4.2 Per-project activation

```toml
# .sange/config.toml
[gitignore.dev]
profiles = [
  "_core/secrets", "_core/editor-noise", "_core/license",
  "lang/python", "framework/django",
  "infra/docker",
  "editor/vscode",
  "os/macos",
]

[gitignore.prod]
profiles = [
  "_core/secrets", "_core/license",
  "lang/python", "framework/django",
  "infra/docker",
  # editor/* and os/* drop out — host-side noise must not appear in published tree
]

[gitignore.policy]
allow_safety_off = false     # cannot disable _core/secrets except via audit override
detect_on_init = true        # auto-suggest profiles in `sange init`
override_extends = []        # ordered patterns that win over profile compositions
```

#### 15.4.3 CLI surface

```
sange profile list                    # all registered profiles
sange profile show <name>             # patterns + auto-detect + scope
sange profile detect [--apply]        # suggest profiles from file-presence signals
sange profile use <name> [--scope dev|prod|both]
sange profile remove <name> [--scope dev|prod|both]
sange profile diff                    # what dev.gitignore vs prod.gitignore ignore
sange profile validate                # all extends resolve; rename safety check
sange profile materialize [--scope dev|prod]  # write composed .gitignore
```

Per ADR-024 (one question at a time), the `sange init` auto-detect flow asks **one profile suggestion at a time** — accept/reject sequentially.

#### 15.4.4 Plugin extensions

Signed plugins (§9.5.13 of the prompt) may ship additional profiles under `templates/gitignore-profiles/<category>/<plugin-name>.toml`. Plugin profiles must:

- Use the canonical §10.4 category set (no novel categories without an ADR)
- Be signed in the plugin manifest
- Be tagged `provenance: plugin (<name>)` in `sange profile list`
- Pass the `_core/license` safety check (cannot exclude license/readme/notice files)

The kit's weekly integration matrix detects when the upstream `github/gitignore` repository adds a new template and surfaces it as a `profile-suggestion: new` audit entry; agency PRs add the corresponding registry row.

### 15.6 Variant Matrix (multi-dimensional profile composition — ADR-032)

The Profile Registry above handles **which** patterns belong to which language/framework. The **Variant Matrix** (per §6.5.2 of the prompt + ADR-032) handles **which combination** of stages and flavor dimensions is active at any given moment — replacing the binary `dev | prod` axis with a Cartesian product over user-declared axes.

**Pattern (after Android Studio's Build Variants):**

  * **Stage** — linear axis: `dev`, `staging`, `production` (default trio; extensible). Sange's publish step targets a single stage.
  * **Flavor dimensions** — zero or more orthogonal axes: `audience: {internal, public}`, `surface: {cli, web, mobile}`, `region: {us, eu, apac}`, `tenant: {customer-a, customer-b, ...}` for SaaS.
  * **Variant** = `(stage, *flavors)` — a specific point in the Cartesian product.
  * **Variant filters** — `[[variants.filter]]` blocks exclude impossible combinations.
  * **Source-set composition** under `.sange/variants/<axis>/<value>/` with merge priority `matrix > stage > dimension > _core > profile-registry`.

**Key safety mechanisms (Android-inspired):**

  * **Bundle suffix derivation** — `sange-0.1.0-staging.zip` ≠ `sange-0.1.0.zip` (the production-public-cli artifact is the only suffix-less form). Dev artifacts cannot be confused with production artifacts.
  * **Stage-locked operations** — `sange publish`, `sange bundle publish --channel stable`, `sange purge execute` refuse when the active variant doesn't match the operation's required stage.
  * **Intelligent auto-detection** — CLI flag → env var → `.sange/.active-variant` → branch-map (configurable; default `main`→`production`, `develop`→`dev`, etc.) → heuristic (CI vars, Docker tags, `.env.*` presence) → defaults. Every resolution step is recorded in the audit log.
  * **Variant-aware subsystems** — secret resolver, AI provider, audit verbosity, commit-template visibility, hook policy, and bundle channel are all variant-driven from a single declarative config.
  * **Doctor pollution check** — `sange doctor --variant` flags files that belong to one variant tree appearing in another; suffix-collision detection; branch ↔ variant drift warnings.
  * **Ambient awareness** — every CLI prompt, TUI status line, Web UI header, and audit-log entry shows the active variant.

**Default minimal config** — a project that omits the `[variants]` block entirely gets `stages = ["dev", "production"]` and zero flavor dimensions, behaviourally identical to the v0.5 binary axis. **No migration required** for existing repos; they get the new machinery without configuration cost.

**Kit examples** (`templates/variants/_core/`): `binary`, `three-stage`, `mobile-2x3`, `saas-multi-tenant`, `regulated-rollout` — see §6.12 + the prompt's §6.5.2.12 table.

**CLI surface** (§7.6.1 of the prompt): `sange variant list/show/use/unset/resolve/detect/diff/verify/filters/scaffold/materialize`.

**Plugin extension** — third-party signed plugins (ADR-020) may declare additional flavor dimensions (e.g. `compliance: {hipaa, pci-dss, soc2}`); built-in axis names are reserved.

This expands §6.5's binary swap into a SOLID/DRY-compliant matrix that prevents accidental cross-variant pollution while keeping the simple case simple — the foot-gun Android Studio's build-variant system solves for mobile applies equally to any polyglot project Sange wraps.

---

## 16. Commit Message Lifecycle

### 16.1 The 8-state machine

```
                         ┌──── reopen ────┐
                         ▼                │
   [draft] ── submit ──→ [pending_review] ── approve ──→ [approved]
      │                       │                              │
      │                  reject│                       commit│
      ▼                       ▼                              ▼
   [discarded]            [rejected]                     [committed]
                                                              │
                                                         push │
                                                              ▼
                                                          [pushed]
                                                              │
                                                      archive │
                                                              ▼
                                                         [archived]
```

### 16.2 File location and naming

```
.sange/commits/
├── 0001-feat-auth-add-passkey.json
├── 0002-fix-race-gitignore-swap.json
├── 0003-chore-bump-deps.json
└── archive/
    └── 2026-05/
        └── 0000-*.json
```

- File name: `NNNN-<type>-<scope>-<short-subject>.json` (slugified, ≤ 80 chars)
- `NNNN` is a per-repo zero-padded monotonic counter, durable across crashes (`.sange/.counter`)
- Archived after a configurable retention window (default 90 days)

### 16.3 JSON schema

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

### 16.4 CLI

`sange commit` is the happy-path alias for `stage → ai → approve → commit → push` with confirmation gates between each (sequential, per ADR-024).

Granular: `sange commits list / show / new / ai / edit / submit / approve / reject / commit / push / archive / reopen`.

### 16.5 Default templates

The curated ≥ 50 normalized presets in `.sange/commit-templates/default.toml` are derived from v1's 104-entry array (Appendix G includes the migration `aliases` map). Generated by `tools/generators/commit_templates.py`.

### 16.6 Storage policy

Default: commit JSON files are **gitignored** (workflow artifact, not source). Teams who want shared review queues opt-in via `track_commits = true` in `.sange/config.toml`. When tracked, sensitive fields (AI cost, model name, internal `references`) are redacted via `.sange/commits/.public-schema.json` before commit.

---

## 17. Release Bundling

### 17.1 Lifecycle

```
[plan] → [build] → [sign] → [verify] → [publish] → [verify-published] → [released]
                                            │
                                            └──→ [held] (manual review gate)
```

### 17.2 What's in a bundle

- Source tree at the bundle commit (filtered by `prod.gitignore` semantics)
- Pre-built artifacts (binaries, container images, docs)
- SBOM (CycloneDX or SPDX)
- Provenance attestation (SLSA Level 3)
- Signatures (sigstore + optional GPG)
- Changelog entry for this release
- AI-assisted release notes (human-approved per ADR-024)
- `verify.sh` / `verify.ps1` verification script

### 17.3 Destinations (v1.0)

1. **GitHub Releases** — public + private
2. **GitLab Releases** — public + private
3. **Generic Package Registries** — GitHub Packages, GitLab Generic
4. **S3-compatible object storage** — private, server-side encryption
5. **OCI artifact registries** — any OCI-compliant registry via `oras`
6. **Filesystem** — air-gapped workflows

### 17.4 Public vs private

| Visibility | Treatment |
|---|---|
| **Public** | SBOM + signatures + provenance published alongside; consumers verify with `sange bundle verify-remote <url>`. |
| **Private** | Encrypted-at-rest with per-recipient keys (age or recipient-pinned cosign keyref). ACL enforced at the registry. Access events audit-logged. |

### 17.5 Channels

`stable`, `beta`, `nightly`, plus arbitrary user-named channels. Channel monotonicity is enforced: `sange bundle promote --from beta --to stable` refuses if the target stable is newer than the source beta (prevents downgrade attacks).

### 17.6 CLI

```
sange bundle plan <name>        # dry-run, show what would be included
sange bundle build <name>       # produce artifacts in .sange/bundles/artifacts/
sange bundle sign <name>        # sigstore / cosign / GPG
sange bundle verify <name>      # re-verify before publish
sange bundle publish <name> [--channel beta]
sange bundle promote <name> --from beta --to stable
sange bundle rollback <name>    # only for channels that support it
sange bundle verify-remote <url>  # consumer-side verification
```

### 17.7 Scaffolds

The §6.12 Premade Operations Kit ships eight ready bundlers (`goreleaser`, `semantic-release`, `release-please`, `git-cliff`, `changesets`, `pyinstaller`, `electron-builder`, `docker-oci`) materialized via `sange bundle scaffold <tool>`.

---

## 18. Container VCS Secret Management

See `.design/sange-architecture-prompt.md` §6.10 for the full spec. Summary: when Sange runs inside its Docker container (CI runners, sandboxed dev environments, ephemeral devboxes), it accesses VCS credentials via one of five mechanisms ranked by preference — (1) SSH agent forwarding (host `SSH_AUTH_SOCK` mounted in, the default for local dev), (2) Docker / BuildKit secrets mounted as tmpfs, (3) OS keychain pass-through via a daemon helper over a Unix socket, (4) external secret manager (Vault / AWS Secrets Manager / 1Password Connect) read at startup, (5) age- or GPG-encrypted file mount with a short-lived decryption key. Controls: container is non-root, secret mount paths are `0400`, no environment variables containing secret values past startup (early-zeroed), `sange doctor --container` audits the running container for leaks. ADR-012.

## 19. VCS History Purge Subsystem

See `.design/sange-architecture-prompt.md` §6.11 for the full spec. Summary: a first-class capability wrapping `git filter-repo` + BFG (Git), `svnadmin dump | svndumpfilter` (SVN), `hg convert --filemap` + `hg strip` (Mercurial), and `p4 obliterate` (Perforce). Detection via `gitleaks` + `trufflehog`. **Ten-state lifecycle:** `planned → preflight_passed → analyzed → previewed → confirmed → executing → verified → completed` with `aborted` and `rolled_back` off-ramps. **Eight pre-flight gates** (secrets-rotated, fresh mirror, backup verified, branch-protection inventory, CI pause, collaborator notification, ref-budget, scanner regression). **Eight post-rewrite verification checks** (path-present, string-present, scanner regression, packfile shrinkage, fsck, LFS pointer integrity, tag signature inventory, `--analyze` diff). Hash-chained audit JSONL (per-repo + global). Synchronous, interactive, CLI/TUI-only — never async, never scheduled, never partial-rollout (ADR-018). `--batch` mode requires four explicit precondition flags + per-operator rate-limit. Web UI cannot execute the destructive transition. The user-supplied playbook (`docs/tools/security/purge.md`) is the procedural source; the responding model refactors it into Sange-native commands per §6.11.8.

## 20. Premade Operations Kit

See `.design/sange-architecture-prompt.md` §6.12 for the full spec. Summary: a curated, signed, versioned kit of operational scaffolds — **9 CI providers** (GitHub Actions, GitLab CI, Azure Pipelines, Bitbucket Pipelines, Gitea Actions, Forgejo Actions, CircleCI, Jenkins, plus `_core/` provider-agnostic stages), **8 release bundlers** (goreleaser, semantic-release, release-please, git-cliff, changesets, pyinstaller, electron-builder, OCI artifact), **9 push-to-prod strategies** (rolling, blue-green, canary, SSH-atomic-symlink, compose, k8s, nomad, ECS, Cloud Run), and **VPS provisioning** (cloud-init for 9 providers, Ansible roles, Terraform modules, Caddyfile/nginx templates, Prometheus+Grafana+Loki monitoring) aligned to CIS benchmarks. Each fragment carries front-matter declaring its variables; `sange scaffold` (§7.11) materializes with substitution and provenance tracking; `templates/MANIFEST.toml.sig` gates the lookup (ADR-020). Weekly kit-integration CI surfaces `kit_status: needs_attention` in `sange doctor`.

## 21. CLI / TUI Presentation Conventions

See `.design/sange-architecture-prompt.md` §7.0 for the full spec. Summary: every Sange visual surface follows nine sub-conventions — (1) pinned library stack (`typer` + `rich` + `questionary` + `textual` for TUI mode only + `structlog` + `wcwidth` + `shellingham` + `python-magic` + stdlib `asyncio`/`subprocess`; explicit disallow list includes `tqdm`, `colorama`, `inquirer`, `loguru`, `plumbum`/`sh`, `click`), (2) `TerminalProfile` auto-detection at startup (Windows `cmd.exe` / `cp1252` / MSYS2 / `LC_ALL=C` SSH fall back to ASCII), (3) `rich.tree.Tree` for file-tree rendering, (4) `rich.progress` with the exact column composition `SpinnerColumn + TextColumn + BarColumn + TaskProgressColumn + TimeElapsedColumn + TimeRemainingColumn + TransferSpeedColumn`, (5) typed-phrase confirmation with per-session nonce, (6) subprocess stream-and-retain with transcript hashing, (7) hash-chained audit JSONL, (8) panel-rendered error messages with documented exit codes, (9) one-question-at-a-time interaction rule (ADR-024). ADR-019.

## 22. Modular Makefile System

See `.design/sange-architecture-prompt.md` §10 for the full spec. Summary: zero per-package Makefile in git. A `Makefile` is generated on-demand as a thin compatibility shim containing only `include` statements for fragments under `.sange/makefiles/<category>/*.mk`. `_core/` (framework essentials), `vcs/`, `lang/`, `framework/`, `infra/`, `ci/`, `release/`, `security/`, `ai/`, `db/`, `_local/` (user customizations, gitignored). Fragments hash-verified against signed Sange manifest. Pre-commit hook + `sange doctor` block accidental commit of the generated Makefile. `sange fix-makefile-tracked` is the recovery for the foot-gun case.

## 23. Category Convention (canonical for every fragment tree)

See `.design/sange-architecture-prompt.md` §10.4 for the full spec. Summary: the subgrouped layout in §22 is not Makefile-specific — it is the canonical layout for **every** Sange file-fragment tree: `.sange/makefiles/`, `.sange/gitignore/profiles/`, `.sange/prompts/`, `.sange/workflows/`, `.sange/commit-templates/`, `.sange/hooks/`, `src/sange/templates/`, and `docs/tools/`. Canonical categories: `_core/`, `_local/`, `vcs/`, `lang/`, `framework/`, `infra/`, `cloud/`, `ci/`, `release/`, `security/`, `ai/`, `db/`, `editor/`, `os/`, `domain/`, `type/`, `workflow/`. Two-level cap; one file per tool / topic; namespace mirrors path; `_core/` is sacred; renames are forbidden in minor releases; `sange doctor` enforces the layout. ADR-021.

## 24. Hook & Policy Engine

See `.design/sange-architecture-prompt.md` §7.4 for the surface. Summary: managed `pre-commit`-compatible hooks under `.sange/hooks/<stage>/` (`pre-commit/`, `prepare-commit-msg/`, `commit-msg/`, `pre-push/`, `post-merge/`); secret scanning blocking on staged content (gitleaks + trufflehog patterns from §6.11.4 gate-8); Conventional Commits 1.0.0 validator; large-file warner with LFS suggestion; license-header enforcement (REUSE / SPDX); per-repo and per-user policy via `.sange/config.toml::[policy]`. `sange hooks install` writes a `.pre-commit-config.yaml` referencing Sange's managed hooks; `sange hooks list` shows what runs at each stage.

## 25. CI/CD Companion

See `.design/sange-architecture-prompt.md` §7.5 for the surface + §6.12.1 for the kit scaffolds. Summary: provider-matrix linting (`sange ci lint <file>`), local execution wrapping `act` and equivalents (`sange ci run`), simulated end-to-end pipeline (`sange ci sim`) including release stages, support across GitHub.com / GitHub Enterprise (Server + Cloud) / GitLab.com / GitLab Self-Managed / Bitbucket Cloud / Bitbucket DC / Azure DevOps Services + Server / Gitea / Forgejo. The kit (§20) ships ready-to-materialize scaffolds for each provider — every CI workflow ships with pinned-by-SHA action versions, OIDC trusted publishing where applicable, and `step-security/harden-runner` enabled.

## 26. Release Engineering

See `.design/sange-architecture-prompt.md` §7.3 + §6.9 for the full spec. Summary: semver bumping, changelog (Keep a Changelog format) generation, signed-tag creation, Before/During/After phase hooks, monorepo release coordination via §6.9.1 sub-project bundles. `sange release` is the surface; `sange release schedule` queues a release in the §32 scheduler; `sange release rollback` reverses (where the channel supports it). All releases produce SLSA-3 attestation + sigstore signatures + SBOM (CycloneDX) per ADR-011.

## 27. Web UI Architecture

See `.design/sange-architecture-prompt.md` §8.1 + ADR-002 for the stack. Laravel 13 + Livewire 4 + first-party `laravel/passkeys` (released 2026-05-12 as separate Composer + npm packages, *not* in L13 core), PHP 8.3 floor / 8.4 recommended. SQLite default at `~/.sange/web.db`; PostgreSQL, MySQL/MariaDB, SQL Server via Laravel's database abstraction. WebAuthn passkey primary; PIN fallback; password alternative (Argon2id + HIBP k-anonymity). Local domain `sange.test` via `mkcert`-issued local CA (HSTS, TLS 1.3 minimum). IPC to Python core: JSON-RPC 2.0 over loopback with HMAC-signed requests; mTLS for remote-daemon access. The Laravel app cannot import the Python `core/` — it is a thick UI client over the same JSON-RPC surface the CLI uses.

## 28. Web UI Feature Catalog

See `.design/sange-architecture-prompt.md` §8.2 for all 21 modules. Summary: §8.2.1 Project & Repo Management, §8.2.2 Commit Management (lifecycle inbox), §8.2.3 Branch Management, §8.2.4 Push & Publish Approval, §8.2.5 Release Management, §8.2.6 Release Bundling, §8.2.7 Rollback & Recovery, §8.2.8 Scheduler, §8.2.9 CI/CD Monitoring, §8.2.10 Hook & Policy Management, §8.2.11 Secret & Token Management, §8.2.12 AI Configuration & Cost (with MCP server management), §8.2.13 Audit Log, §8.2.14 Local Tools & Portals Hub, §8.2.15 Gitignore Profile Management, §8.2.16 Plugin Management, §8.2.17 Telemetry & Local Analytics, §8.2.18 Workflow Builder (v2+), §8.2.19 Settings, §8.2.20 Help & Documentation, §8.2.21 Purge & History Surgery. Every module has CLI parity (no Web UI feature exists without a CLI equivalent). §8.2.21 cannot trigger the destructive purge transition per ADR-018.

## 29. Web UI Security Model

See `.design/sange-architecture-prompt.md` §8.3 + §8.5 for the full matrix. Summary: bind to `127.0.0.1` by default; WebAuthn primary auth with PIN + password alternatives; CSRF via Laravel's middleware; CORS disabled (same-origin only); strict Origin/Referer validation; HMAC-signed JSON-RPC for local daemon IPC; mTLS for remote-mode daemon IPC; rate limiting per-route per-IP with abuse lockout; CSP with nonce-gated `unsafe-inline`; HSTS; Subresource Integrity for third-party assets; host-header allowlist (defends DNS rebinding); explicit `serializable_classes` allowlist (default-deny deserialization). All UI actions audit-logged with actor / IP / user-agent / timestamp.

## 30. Remote Access Topologies

See `.design/sange-architecture-prompt.md` §8.5 for the full spec. Supported from v1.0. Four topologies — (1) **Cloudflare Tunnel** (recommended, outbound-only `cloudflared`, Cloudflare Access for policy, optional Cloudflare Workers for edge auth), (2) **Tailscale / Tailscale Funnel** (zero-config mesh + MagicDNS + ACLs), (3) **WireGuard** (expert-only; `sange wg generate` for the config), (4) **Direct reverse-proxy on VPS** (Caddy preferred for automatic TLS; nginx alternate; cloud-init / Terraform / Ansible scaffolds via §20 kit). Each ships a setup wizard. mTLS daemon-to-Laravel + MFA + IP allowlist are **mandatory** in remote mode; `sange web remote audit` refuses to start when any control is missing.

## 31. Local Tools & Portals Hub

See `.design/sange-architecture-prompt.md` §8.2.14 for the surface. Discover and monitor local dev portals — Laravel Herd, Laravel Valet, Docker Desktop, Local by Flywheel, Lando, DDEV, Mailpit. Per-portal health status, quick-launch buttons, aggregate notifications. This module is a **monitoring / launcher view, not a replacement** — it observes what's already running.

## 32. Scheduler & Background Jobs

See `.design/sange-architecture-prompt.md` §8.2.8 for the surface. A local cron-equivalent inside the `sanged` daemon. All scheduled jobs visible, editable, cancelable from CLI and Web. Missed-run handling: `skip` (default), `catch-up` (run once on resume), `fail-loud` (alert on miss). **Purge is excluded by design** (ADR-018: synchronous CLI-only — no scheduled history rewrites). Releases *can* be scheduled (`sange release schedule`); confirmation gates still apply at execution time.

## 33. Plugin Architecture

See `.design/sange-architecture-prompt.md` §7.9 for the surface. Entry-point-based discovery via Python `entry_points` for Python plugins; signed-manifest dispatch for cross-language plugins. Sandboxed execution; capability declarations (network, filesystem scope, secrets access) reviewed at install. `sange plugins list / install / remove / inspect`. Plugins may extend the §15.4 Profile Registry (with `provenance: plugin (<name>)` tagging), the §20 kit (signed manifest required), the §11 AI provider list, and the §32 scheduler job types — but cannot bypass §11 redaction, §6.11 purge gates, or §29 web UI auth.

## 34. CLI Reference

The full CLI reference is **generator output** per §16.4 / T-G-009. `tools/generators/cli_reference.py` introspects the `typer` app at build time and emits `docs/reference/cli-reference.md` with every command, every flag, every help string, every exit code. The frontmatter records `generator_version`, `input_sha256` (the typer app's command tree hash), and `output_sha256`. CI's `verify_generated.py` re-runs the generator and fails on mismatch.

## 35. Command Coverage Floor

See `.design/sange-architecture-prompt.md` §9.0 for the floor. The §9.0.1 Top-25 Git anchor (from the user-supplied reference image), §9.0.2 under-used power commands (bisect, worktree, rerere, maintenance, sparse-checkout, replace, notes, reflog, restore, range-diff, cherry-pick, blame, grep, submodule, lfs, clean, describe, archive, gc, fsck, apply/am, format-patch, send-email, shortlog, verify-commit/-tag, update-index, for-each-ref, switch -c --track, absorb, autostash, commit-graph, fsmonitor), §9.0.3 SVN floor (~45 commands), §9.0.4 Mercurial floor (~35), §9.0.5 Perforce floor (~30), §9.0.6 cross-cutting third-party tools Sange wraps (git-filter-repo, BFG, gitleaks, trufflehog, git-secrets, pre-commit, detect-secrets, act, mkcert, cloudflared, tailscale, wg, cosign, sigstore, syft, cyclonedx-cli). The §9.4 wrapping discipline forbids thin facades — every wrapper does at least one of seven augmentations.

## 36. Innovation Surface

See `.design/sange-architecture-prompt.md` §9.5 for what Sange engineers *on top of* the underlying VCS. Fifteen subsections naming the primitive added per VCS operation, plus the eight new primitives Sange invents (the `.sange/` folder convention, Commit JSON file, PurgePlan JSON, Bundle Manifest, TerminalProfile, Prompt Enhancer template, Sange audit chain, MCP capability allowlist).

## 37. Installer & Distribution

See `.design/sange-architecture-prompt.md` §7.1 for the surface + §6.12 kit for the scaffolds. One-liner installer per OS — `curl -sSL https://sange.sh/install.sh | sh` for Unix, `iwr https://sange.sh/install.ps1 | iex` for Windows PowerShell. Security: checksums + sigstore signatures verified before execution; no auto-elevation; refuses on untrusted-shell heuristics. Distribution channels: PyPI (Python package), Homebrew tap (`simtabi/sange`), Docker image (`ghcr.io/simtabi/sange:<version>`), GitHub Releases binaries (built via PyInstaller per §20 kit), Linux distro packages (deb/rpm via the bundle pipeline). The Python core ships independently of the Laravel web UI — CLI users never need PHP installed.

## 38. Container & Daemon Lifecycle

See `.design/sange-architecture-prompt.md` §6.6 for the container + §6.1 ADR-013 for the daemon. Multi-stage Dockerfile, `python:3.12-slim` base pinned by digest, non-root user, baked health-check, `docker-compose.yml` for local dev with SSH-agent socket forwarding. `sanged` daemon supervision: `launchd` user agent on macOS, `systemd --user` on Linux, Windows Service via `pywin32` (preferred) with NSSM/WinSW fallback. The daemon never runs as root/admin; capabilities dropped post-start. `sange daemon {start|stop|status|restart|logs|reload}` is the surface; `sange doctor --daemon` checks health and supervisor-state.

## 39. Threat Model (STRIDE)

See `.design/sange-architecture-prompt.md` §11 for the full table. STRIDE coverage:

- **Spoofing** — Web UI auth (passkey + PIN + password); MCP server allowlist; signed plugin manifests; signed kit manifest; Cloudflare Tunnel token in OS keychain.
- **Tampering** — Hash-chained audit JSONL (§7.0.7); commit JSON integrity sidecar; signed releases (sigstore + GPG dual); signed plugin manifest; `templates/MANIFEST.toml.sig` for the kit.
- **Repudiation** — Append-only audit log; mandatory operator field per entry; typed-phrase confirmation records actor + nonce; web session audit-log entries carry IP + user-agent.
- **Information Disclosure** — Secrets in OS keychain or external secret manager (never plaintext config); redaction layer scrubs AI-bound diffs; `mlock` on secret-handling subprocesses; `RLIMIT_CORE=0` to forbid core dumps containing secrets.
- **Denial of Service** — Rate limiting per-route per-IP for web UI; `--batch` rate-limiting for purge; subprocess timeout + signal cascade; daemon health-check.
- **Elevation of Privilege** — Daemon as user (no setuid); capability dropping; container non-root; plugin sandbox; web UI cannot execute destructive purge (ADR-018); MCP server's exposed tools cannot bypass typed-phrase gates.

The full per-attacker walkthrough (insider, fork-owner, compromised CI, malicious MCP server, malicious plugin, hostile network, hostile AI provider, hostile commit content) is produced by `tools/generators/threat_model_table.py` (T-G-012).

## 40. Privacy, Local Telemetry, and Opt-in External Send

See `.design/sange-architecture-prompt.md` §12 for the full spec. **v1.0: local telemetry only.** Operation counts, latencies, error rates, AI cost trends stored in `.sange/telemetry/` (per-repo) and `~/.sange/telemetry/` (global) as NDJSON, append-only, weekly rotation. Sensitive fields (paths, branch names, commit messages) are hashed before storage by default; opt-in plaintext for richer local analytics. **v2.0: opt-in external send.** A future feature lets users send aggregated, anonymized telemetry to a Sange-operated endpoint (or self-hosted endpoint, or none). Off by default. Preview pane shows exact payload before send; anonymization is mandatory; aggregation window minimum 24 hours; opt-out is one toggle and effective immediately.

## 41. ADR Index

The full ADR Index is **generator output**, populated by `tools/generators/adr_index.py` (folded into T-G-007 `adr_scaffold.py` as a sub-mode) which walks `docs/adr/` and emits the index table. v1.0 ships with **ADR-001 through ADR-031** (per `.design/plans/decisions-log.md`); subsequent ADRs append at ADR-032+.

## 42. Observability

See `.design/sange-architecture-prompt.md` §13 for the full spec. Structured logging via `structlog` (JSON Lines by default; pretty mode for TTY). Log levels: `trace`, `debug`, `info`, `warn`, `error`, `fatal`. Per-component levels. Sensitive values auto-redacted via the same patterns used by the §11 redaction layer. Optional OpenTelemetry export to a local collector. Metrics: command latency, AI token usage, error rates, queue depths, IPC round-trip times. Daemon health endpoint `/healthz` for web UI polling. Crash dumps respect `RLIMIT_CORE=0` where secrets may be in memory.

---

## 43. Testing Strategy

The test suite is the gate between design and ship. Every quality gate in §19 of the prompt that says "X is verified" terminates in a test under one of the directories below.

### 43.1 Test pyramid

The pyramid is intentional: cheaper tests run first and gate the more expensive ones.

| Layer | Where | Count target (v1.0) | Latency budget | When it runs |
|---|---|---|---|---|
| **Unit** | `tests/unit/` | ~1,200 tests | < 60 s total wall-clock | Every commit (pre-commit + CI) |
| **Property** | `tests/unit/property/` | ~50 properties via Hypothesis | < 30 s total | Every commit |
| **Integration** | `tests/integration/` | ~250 tests | < 180 s total | Every commit (CI) + pre-push |
| **End-to-end (CLI)** | `tests/e2e/` | ~80 tests | < 300 s total | Every PR + main-branch nightly |
| **End-to-end (Web)** | `web/tests/` (Pest 3 + Laravel Dusk) | ~120 tests | < 600 s total | Every PR touching `web/` + main-branch nightly |
| **Security** | `tests/security/` | ~40 + prompt-injection corpus + 500-iteration fuzz | < 600 s for the non-fuzz part; fuzz runs separately on a 30-min budget | Every PR + scheduled weekly deep-fuzz |
| **Performance** | `tests/perf/` | ~25 benchmark tests with thresholds | < 600 s total | Every PR + main-branch nightly with trend tracking |
| **Kit integration** | `tests/kit/` | ~80 fragment integration tests (one per shipped scaffold) | < 1800 s (spins up ephemeral VMs for VPS fragments) | Weekly cron + manual via `sange doctor --kit` |

**Coverage targets for v1.0:**

- **Statement coverage** ≥ 80 % (Python core), ≥ 70 % (Laravel web layer)
- **Branch coverage** ≥ 60 %
- **Mutation score** ≥ 65 % via `mutmut` for the `core/lifecycle/` and `core/purge/` modules (the highest-risk surfaces)
- **No untested error path** in `core/purge/gates.py` — each gate has at least one red-path test
- **No untested state transition** in the commit / bundle / purge lifecycle state machines — Hypothesis properties cover the full transition graph

### 43.2 Toolchain

- **Test runner**: `pytest` + `pytest-asyncio` (for the asyncio surfaces in §7.0.6 and `core/daemon/`) + `pytest-rich` for output rendering consistent with §7.0.
- **Property-based**: `hypothesis` — strategies live in `tests/unit/property/strategies.py` and are reused across unit + property tests.
- **Snapshot**: `syrupy` for generator output (catalogs, commit JSONs, prompt-enhancer prompts) and `pytest-asyncio` for IPC payload golden tests.
- **Mocking**: stdlib `unittest.mock` for unit tests. **Integration tests use real subprocesses** (real `git` in a tmpdir) — never `mock_open()` on `subprocess.Popen` (mock-vs-prod divergence is a known failure mode per the user's prior history-purge brief).
- **Coverage**: `coverage.py` with branch coverage enabled.
- **Mutation**: `mutmut` for the lifecycle + purge modules.
- **Web tests**: `Pest 3` (the Laravel 13-era release) for PHP unit / feature tests; `Laravel Dusk` for browser e2e against the local dev server with `mkcert` TLS.
- **Security**: `bandit` for Python SAST; `gitleaks` + `trufflehog` against the test repo itself; `pip-audit` + `composer audit` + `npm audit` for dependencies.
- **Performance**: `pytest-benchmark` for micro-benchmarks; `hyperfine` invoked from `tests/perf/conftest.py` for whole-CLI invocations; trend-tracking via `gh-action-benchmark` posting to GitHub Pages.
- **Fuzz**: `atheris` (libFuzzer for Python) targeting the commit JSON parser, the prompt-enhancer template loader, the `.gitignore` profile composer, the JSON-RPC IPC unmarshaler.

### 43.3 Fixtures pattern

Test fixtures live in `tests/fixtures/` and follow the §10.4 Category convention:

```
tests/fixtures/
├── _core/                  # framework-level: temp-dir helpers, TerminalProfile mocks, audit-log helpers
├── vcs/
│   ├── git/                # `tmp_git_repo` factory: pristine, dirty, with-history, with-secrets, with-conflicts, …
│   ├── svn/                # `tmp_svn_repo` factory
│   └── hg/                 # (v2.0)
├── ai/                     # FakeAIProvider that replays canned responses; PromptInjectionCorpus
├── commits/                # commit JSON examples (one per status × type combination)
├── bundles/                # bundle manifest examples; pre-signed artifact fixtures
├── purge/                  # purge plan examples; pre-corrupted backup tarballs for verifier tests
└── profiles/               # gitignore profile examples for the §15.4 composer
```

**`tmp_git_repo`** is the workhorse — a `pytest` fixture factory that produces a real `git` repo in a `tmpdir`, configured with the SHAs and refs the test needs. It is **not** a mock; subprocess `git` runs against it. This is how Sange catches the class of bugs that mock-based tests miss.

**`FakeAIProvider`** implements `AIProvider` and returns canned responses indexed by `(prompt_template_id, input_hash)`. Real AI providers are exercised only in the nightly e2e job that uses BYOK env vars.

### 43.4 Prompt-injection corpus

Stored at `tests/security/prompt_injection_corpus/` as one `.txt` file per attack class:

- `direct-instruction-override.txt` — "Ignore previous instructions" variants
- `delimiter-escape.txt` — `</user_input>` and friends mid-content
- `base64-instruction.txt` — encoded instruction blocks
- `multilingual-instruction.txt` — non-English instruction-override attempts
- `tool-call-spoofing.txt` — fake MCP tool-call payloads embedded in commit messages or diffs
- `homoglyph-attack.txt` — Cyrillic-look-alike characters in supposedly-redacted content
- `nested-untrusted-block.txt` — attempts to break out of `<untrusted_input>` framing

Every test in `tests/security/test_prompt_injection.py` is parameterized over the corpus; every entry must pass through the §11 content firewall + redaction layer without triggering an instruction-override. The corpus is append-only; new attack patterns observed in the wild get added with a PR + ADR.

### 43.5 CI invocation order

The exact order each PR's CI runs:

```
1.  pre-commit: ruff format, ruff check, mypy --strict, gitleaks, shellcheck, hadolint, prettier
2.  python-unit: pytest tests/unit
3.  python-property: pytest tests/unit/property --hypothesis-seed=<fixed-per-pr>
4.  python-integration: pytest tests/integration
5.  python-security: bandit + gitleaks + trufflehog --results=verified + pip-audit
6.  generator-verify: python tools/generators/verify_generated.py --check (every output_sha256 matches)
7.  web-unit: cd web && composer install && vendor/bin/pest --filter=Unit
8.  web-feature: cd web && vendor/bin/pest --filter=Feature
9.  web-dusk: cd web && php artisan dusk (against local sanged + mkcert TLS)
10. e2e-cli: pytest tests/e2e
11. perf-bench: pytest tests/perf --benchmark-compare-fail=mean:5% (regress >5% vs main = fail)
12. sbom: syft scan + cyclonedx-py + cyclonedx-cli convert
13. slsa-attest: slsa-verifier verify-artifact (release builds only)
14. kit-smoke: a 5-minute subset of tests/kit (the full kit-integration runs weekly)
```

Steps 1-6 must pass for any PR to merge. Steps 7-9 must pass for any PR touching `web/`. Step 10 must pass for any PR touching `src/sange/cli/`. Step 11 publishes its trend even on pass; a fail blocks main-branch merges. Steps 12-13 run on release-tag pushes only.

### 43.6 What gets fuzzed nightly

- The commit JSON parser (against malformed JSON + schema violations + hash mismatches)
- The `.gitignore` profile composer (against pathological `extends:` graphs — cycles, depth bombs, conflicting `prod_only`/`dev_only` declarations)
- The prompt-enhancer template loader (template includes — circular, depth-bombing, escape attempts)
- The JSON-RPC IPC unmarshaler (against §29 deserialization attacks)
- The purge plan parser (against state-machine bypass attempts)

Each fuzzer runs for 30 minutes nightly; any crash gets filed as a P0 bug; any newly-found bypass triggers an ADR.

### 43.7 Test-data hygiene

Test repos created via `tmp_git_repo` are **never** committed to `tests/fixtures/` as `.git/` directories — they are constructed in the test setup. Commit `.git/`-as-fixture is forbidden because the SHAs would freeze; instead fixtures are *recipes* (a sequence of operations the factory replays).

Real-looking secrets in test fixtures use the `AKIA*EXAMPLE` and `xoxb-EXAMPLE` patterns from AWS / Slack docs respectively, which the major scanners deliberately allowlist as obvious-test-values. No real secret has ever shipped in `tests/fixtures/` and CI's gitleaks step is the guardrail.

### 43.8 Release-gating tests

A release tag may not be cut unless:

- All 14 CI steps above passed on the tagged commit
- Mutation score thresholds met
- Performance benchmarks within budget (§44)
- The kit-integration weekly job was green within the last 7 days
- `sange purge` red-path tests + `sange publish` recovery tests pass on Linux, macOS, and Windows runners

`tools/generators/release_readiness.py` (deferred — likely T-G-016) emits a single `release-readiness.json` summarizing all of the above; the release workflow refuses to proceed if any field is red.

---

## 44. Performance Budgets & Non-Functional Requirements

Numbers below are **budgets** — the maximum allowed at the named percentile on the named hardware. Real measurements arrive during Phase 0 implementation; budgets are revisited at each phase boundary.

### 44.1 Reference hardware

- **Developer baseline:** Apple M2 (16 GB RAM, NVMe SSD, macOS 14+); equivalent Linux x86_64 (16 GB, NVMe, glibc 2.35+); Windows 11 on Surface-class hardware (16 GB, NVMe).
- **CI runner baseline:** GitHub-hosted `ubuntu-latest` (2 vCPU, 7 GB RAM, SSD).
- **Production daemon host:** any of the above; the daemon doesn't need more than 512 MB RAM at steady state.

### 44.2 Latency budgets — CLI

| Operation | p50 | p99 | Notes |
|---|---|---|---|
| `sange --version` (cold) | < 80 ms | < 200 ms | Python startup + version read |
| `sange status` (warm repo, daemon running) | < 150 ms | < 400 ms | Includes one IPC round-trip + one `git status` |
| `sange commit` happy-path (no AI, 5-file diff) | < 600 ms | < 1500 ms | Excludes the AI call |
| `sange commits ai` (Anthropic / Claude, 5-file diff) | < 5 s | < 12 s | Network + provider-dependent; budget set by reasonable network |
| `sange publish` (gitignore-swap + push, 5-file commit) | < 2 s | < 6 s | Excludes network push time |
| `sange purge analyze` (10k-commit repo) | < 30 s | < 90 s | Wall-clock of `git filter-repo --analyze` |
| `sange purge execute` (10k-commit repo, 1 path) | < 120 s | < 600 s | Wall-clock of the rewrite; very dataset-dependent |
| `sange bundle build` (50 MB source tree) | < 20 s | < 60 s | Includes SBOM + sigstore signing |

### 44.3 Latency budgets — Daemon

| Operation | p50 | p99 | Notes |
|---|---|---|---|
| `sanged` cold start (launchd / systemd / pywin32) | < 1.5 s | < 4 s | Time until `/healthz` returns 200 |
| IPC round-trip (loopback HMAC, trivial method) | < 5 ms | < 20 ms | Baseline for routing-only overhead |
| IPC round-trip (remote mTLS, trivial method) | < 50 ms | < 200 ms | Depends on tunnel topology |
| MCP tool invocation (commit_generate end-to-end) | < 6 s | < 15 s | AI-call-dominated |

### 44.4 Latency budgets — Web UI

| Surface | LCP target | INP target | CLS target | Notes |
|---|---|---|---|---|
| Login (passkey path) | < 1.5 s | < 100 ms | < 0.05 | First page; mkcert TLS handshake included |
| Project list (≤ 50 repos) | < 1.0 s | < 100 ms | < 0.05 | After login |
| Commit lifecycle inbox (≤ 200 commits) | < 1.5 s | < 150 ms | < 0.05 | Largest single-page Livewire view |
| Purge plan editor | < 2.0 s | < 200 ms | < 0.10 | Tree-view of paths to remove |
| Audit timeline (last 24 h) | < 1.5 s | < 100 ms | < 0.05 | Server-streamed updates via Livewire's polling |
| Web Vitals (mobile via remote-mode) | LCP < 2.5 s, INP < 200 ms, CLS < 0.10 | | | Per Google Core Web Vitals targets |

### 44.5 Resource budgets

| Resource | Idle | Active (e.g. mid-purge) | Hard cap |
|---|---|---|---|
| `sanged` RSS | < 80 MB | < 400 MB | OOM-kill at 1 GB; daemon restarts |
| Laravel app RSS (per-request) | < 60 MB | < 200 MB | Per-request via Octane / per-worker via PHP-FPM |
| `.sange/audit/` disk | < 1 MB/day at typical usage | up to 50 MB/day at heavy CI | Rotated weekly; archived at 90 days; total ≤ 500 MB |
| `.sange/telemetry/` disk | < 100 KB/day | < 5 MB/day | Same rotation policy |
| `.sange/purge/<plan>/backup-*.tar.gz` | n/a | size-of-repo | Auto-deleted 14 days after `completed`; never deleted on `rolled_back` |
| CPU at idle | < 0.5 % single-core | depends on operation | No spinning loops; daemon uses `epoll`/`kqueue` |

### 44.6 Generator-script budgets (per §16.4)

| Generator | Wall-clock budget | Output size budget |
|---|---|---|
| `git_catalog.py` | < 5 s | < 200 KB |
| `svn_catalog.py` | < 3 s | < 150 KB |
| `cross_vcs_map.py` | < 1 s | < 50 KB |
| `commit_templates.py` | < 2 s | < 100 KB |
| `kit_manifest.py` | < 3 s | size of `templates/` |
| `docs_index.py` | < 1 s | < 30 KB |
| `cli_reference.py` | < 3 s | < 200 KB |
| `jsonrpc_schema.py` | < 1 s | < 100 KB |
| `config_schema.py` | < 1 s | < 50 KB |
| `threat_model_table.py` | < 1 s | < 50 KB |
| `profile_registry.py` | < 2 s | < 150 KB |
| `all.py` (orchestrator) | < 30 s | sum of above |

Any generator exceeding its budget is a CI failure. Generators that legitimately grow (e.g. when SVN adds new commands) bump the budget via an ADR before the merge.

### 44.7 Error budgets and availability

- **Daemon uptime** target: 99.9% on the local box (excludes user-initiated reboots). Crashes count against the budget; clean restarts via `sange daemon restart` do not.
- **Web UI 5xx rate** target: < 0.5 % of requests over a 7-day window.
- **AI provider call failure rate** target: < 5 % including network errors. Sange retries once on transient failures (5xx, timeout); persistent failures surface to the user.
- **Purge `verified → rolled_back` transition rate** target: < 1 % across the install base (a high rate indicates verification false positives — investigate).

### 44.8 Scalability targets — v1.0

- Repositories per user: up to **5,000** (audit chain and telemetry indexed by `repo_slug`; no global lock)
- Commits per repo in lifecycle: up to **50,000** (counter is `u32`-equivalent; archive after 90 days keeps the active set small)
- Concurrent daemon clients: **8** (CLI + TUI + Web UI + MCP server connections + plugins). Hard limit configurable via `daemon.max_concurrent`.
- Web UI concurrent sessions: **16** per daemon. Beyond that, login is rate-limited.

### 44.9 What's deliberately *not* a budget

- Network bandwidth — Sange is a local-first tool; remote-mode bandwidth is the user's network.
- AI provider cost — surfaced via `sange ai cost` (§7.7) but not budgeted; users bring their own keys (BYOK) and own the cost decision.
- Disk usage of `node_modules/` and friends — Sange does not manage them; the §15.4 profiles just ignore them.

### 44.10 How budgets are enforced

- **CI step 11** (`perf-bench`) runs `tests/perf/` with `--benchmark-compare-fail=mean:5%`. Any > 5 % regression vs `main` fails the PR.
- **`sange doctor --perf`** emits a one-shot snapshot of latency on the developer's host with budget comparisons.
- **The `sanged` daemon exposes `/metrics`** (Prometheus format, opt-in) so the §20 monitoring kit (Prometheus + Grafana + Loki) can alert on budget breaches.
- **Quarterly budget review** — every quarter, the implementation team revisits the budgets above against real telemetry; budget bumps require an ADR.

---

## 45. Roadmap

See `.design/sange-architecture-prompt.md` §14 + `.design/plans/implementation-plan.md` for the full phased plan.

- **v0.1 (MVP)** — Git-only, CLI-only, AI commit messages with full lifecycle, `.sange/` skeleton, modular Makefiles, basic hooks, local telemetry. Cross-platform install.
- **v0.5 (Beta)** — SVN adapter, gitignore-swap, hooks engine, secret scanning, Docker packaging, container secret management, `sange doctor`, `sange bootstrap`, prompt enhancer, expanded commit template library, history-purge read-only paths, CLI/TUI presentation conventions, premade-kit `_core/` content. **Target: feature-complete for solo developers + 50 external testers + zero critical security findings.**
- **v1.0 (GA)** — Web UI (all 21 modules), remote access (4 topologies), release engineering with bundling, CI/CD companion, plugin system with signed marketplace, command catalogs, MCP client + server, full docs site, history-purge destructive operations for Git, `sange scaffold` full surface. **Target: SLSA 3 releases, OpenSSF Scorecard ≥ 8.0, ≥ 3 third-party plugins.**
- **v2.0** — Mercurial, Fossil, Pijul adapters; workflow builder UI; opt-in external telemetry; Cloudflare Workers edge auth gateway; SVN + Hg purge executors.
- **v3.0** — Perforce, Plastic SCM, Sapling; SAML / OIDC SSO; SIEM audit forwarding; self-hosted sync server.

## 46. Open Questions & Risks

See `.design/plans/risk-register.md` for the live list. As of v4.3: **R-001 closed** (codebase path confirmed in-place); R-002 through R-015 remain open; new R-016 tracks the `sange.sh` domain status (registered).

## 47. Implementation Checklist

See `.design/plans/checklist.md`. As of v4.3: Phase 0 (T-001..T-017), Phase 0a generators (T-G-001..T-G-015), Phase 1 CLI surface (T-040..T-045), Phase 2 Beta (T-100..T-115), Phase 3 Web UI / GA (T-160..T-212), Phase 4 multi-VCS (T-240..T-247), Phase 5 enterprise (T-280..T-286). Phase 0a runs **before** Phase 1 — generators scaffold the source tree per ADR-023.

## 48. License & Copyright

Apache License 2.0. © 2026 Simtabi LLC. SPDX identifier `Apache-2.0`. The `LICENSE` file at the repo root is the canonical text. The `NOTICE` file records third-party attributions. Per ADR-007.

## 49. References

The full numbered reference list (with URLs and access dates) is produced as `docs/reference/references.md` and includes the §6.12.5 best-practice anchors (CIS Benchmarks, GitHub Actions hardening, OpenSSF Scorecard, SLSA, sigstore, OWASP ASVS L2, Caddy auto-HTTPS, Ansible best practices, cloud-init, Mozilla SSL Config Generator, HashiCorp Terraform style, Google SRE Book, Argo Rollouts, Flagger, Goreleaser v2, semantic-release, release-please, git-cliff, changesets) and the inline citations from the §3 etymology section, the §6.11.8 history-purge playbook source, and the §11 threat-modeling references (OWASP Top 10 LLM, Anthropic / OpenAI tool-use safety guidance, MITRE ATT&CK relevant techniques).

## 50. Appendices

- **Appendix A** — Command Vocabulary (Mukora Makefiles)
- **Appendix B** — v1/v2 codebase audit + defect log + Divergence
- **Appendix C** — Sample configurations
- **Appendix D** — Comprehensive Git Command Catalog (generator output, T-G-001)
- **Appendix E** — Comprehensive SVN Command Catalog (generator output, T-G-002)
- **Appendix F** — Cross-VCS Concept Map (generator output, T-G-003)
- **Appendix G** — Commit Template Library, ≥ 50 normalized presets + v1→v3 migration map (generator output, T-G-004)
- **Appendix H** — References (generator output)
- **Appendix I** — Glossary (extends §6)
- **Appendix J** — ADR Index (auto-emitted)

---

## Provenance

Items §1–§17 and §43–§44 were **hand-authored**. Items §18–§42, §45–§50 were **hand-stubbed** as design summaries pointing to the prompt's §-anchors where the full spec lives — these stubs are replaced by generator output during the §22 execution-order step 5–6 pass.

Generator-produced sections (Appendices D/E/F/G/H/J, `docs/reference/*`, `docs/security/stride.md`, `docs/CHANGELOG.md`, `docs/tools/README.md`, the `templates/MANIFEST.toml`) carry their own frontmatter + integrity hashes per §16.4.1.

**Hand-author signature:** Simtabi LLC, 2026-05-13. Architecture-prompt-driven. Last revision: v4.3.

---

*See `.design/plans/` for the implementation plan, content audit, decisions log, quality gates, risk register, and traceability matrix.*
