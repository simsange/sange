# Roadmap

Where Sange is going, organized by release. This document is the
reader-friendly synthesis of the canonical phased plan in
[`.design/plans/implementation-plan.md`](../../.design/plans/implementation-plan.md)
and the master task list in
[`.design/plans/checklist.md`](../../.design/plans/checklist.md).

## At a glance

| Version | Target | Status | Headline |
| :--- | :--- | :--- | :--- |
| **v0.1.0** | MVP | **Tagged 2026-05-14** — PyPI publish pending | Git happy-path: init → AI commit → approve → push |
| **v0.1.0.post1 / v0.1.1** | Fix-forward | In progress on `main` | Phase 1 CLI surface complete (`commits new/ai/submit/reject/commit/push`) + release-pipeline lessons folded back into docs |
| **v0.5** | Beta | Not started | SVN adapter, secret scanning, history purge (read-only), TUI conventions, Operations Kit (read-only) |
| **v1.0** | GA | Not started | Local-first Web UI, bundling to 6 destinations, MCP server + client, History Purge (destructive), full kit surface |
| **v2.0** | Multi-VCS | Not started | Mercurial / Fossil / Pijul adapters, workflow builder, opt-in external telemetry |
| **v3.0** | Enterprise | Not started | Perforce / Plastic / Sapling adapters, SAML/OIDC SSO, SIEM forwarding, optional Sange Cloud |
| **v4.0+** | Speculative | Not started | IDE integrations, federation across instances, on-device fine-tuning |

**Status legend.** _Tagged_ means a git tag exists at the
specified release. _In progress_ means active work on `main`
between two tagged releases. _Not started_ means the design is
locked but no code has shipped against the milestone yet.

## v0.1.0 — MVP (Phase 0)

**Tagged at commit `b947a2e9` on 2026-05-14.** Cross-platform install,
the Git happy-path end-to-end, the generator pipeline producing
every reference doc.

What it ships:

- The `sange` Python package + multi-arch Docker image at
  `ghcr.io/simsange/sange:v0.1.0`.
- Foundation: `SangeConfig` (Pydantic v2 + TOML/JSON merge),
  `VCSDriver` Protocol + 4 capability sub-protocols, Git adapter
  (read + 12 write operations), 8-state `CommitJSON` lifecycle
  schema + storage with crash-safe counter, `AIProvider` Protocol
  + adapters for mock / anthropic / openai / ollama / gemini /
  bedrock, PromptEnhancer with T-030 redaction, Conventional Commits
  message template.
- CLI happy path: `sange init`, `sange commit`, `sange doctor`,
  `sange ai providers`, `sange commits {list, approve, push}`.
- 14 of 16 generators implemented (T-G-010 + T-G-014 deferred to
  Phase 3 / Phase 4 respectively): every doc under
  `docs/reference/` is deterministically produced.
- Release infrastructure: tag-driven `release.yml` with OIDC
  trusted-publisher PyPI publish + multi-arch buildx → GHCR with
  sigstore provenance + SBOM.

What it doesn't yet ship: SVN write operations, gitignore-swap,
hooks, secret scanning, container modes, TUI, Web UI, purge,
release bundling.

**Known issues at release time** ([`CHANGELOG.md`](../../CHANGELOG.md#010--2026-05-14)):

- PyPI publish blocked on operator's one-time trusted-publisher
  configuration. `pip install sange` will work once that completes.
- GHCR image is private by default; anonymous `docker pull`
  requires the maintainer to flip the package visibility.

## v0.1.0.post1 / v0.1.1 — fix-forward (current)

Post-tag work on `main`. Whether the next cut becomes
`v0.1.0.post1` (bug-fixes only, per PEP 440) or `v0.1.1`
(new functionality) depends on what lands.

What's already on `main`:

- **Phase 1 CLI surface complete.** `sange commits` now exposes
  the full granular set: `new` (manual draft), `ai` (AI draft),
  `submit`, `reject --reason`, `commit` (local only), `push`,
  plus the existing `list` / `approve`.
- **CI hardening.** GitHub Actions bumped to node24-using majors;
  generators step skips T-G-001 + T-G-002 in CI (they introspect
  toolchain versions that differ between runners and contributors);
  test fixtures fixed for newer git.
- **First post-release docs.** `docs/release.md` gained a Step 0
  pre-flight checklist + "Failure modes seen in production" table
  capturing the v0.1.0 release lessons.
- **README + CHANGELOG** brought to current accuracy.
- **First per-tool walkthrough**: `docs/tools/workflow/commit-lifecycle.md`.

What's queued: per-tool / per-topic doc sprints, the install-time
docs once PyPI publishes, the bundling docs alongside the v0.5
release engine.

## v0.5 — Beta (Phase 1)

**Goal**: feature-complete for solo developers.

**Adds:**

- **SVN adapter** as a Tier-1 VCS alongside Git.
- **Gitignore-swap engine** (§6.5) with `kill -9` recovery —
  swap the active gitignore for a scratch profile without losing
  in-flight work.
- **Hooks engine** (§7.4) + secret-scanning rules library wrapping
  `gitleaks` + `trufflehog`.
- **Container modes**: Docker packaging with container-secret
  management (§6.10); `sange doctor --container` for host vs
  container parity checks.
- **`sange bootstrap`** — orchestrate brew / scoop / apt / mise
  to bring a dev environment up to spec.
- **Expanded commit template library** — 50+ normalized presets
  in [Appendix G](../reference/appendix-g-commit-templates.md).
- **VCS History Purge (read-only)**: `sange purge plan / mirror /
  scan / analyze / preview / notify`. Destructive ops stubbed
  (land in v1.0).
- **CLI/TUI presentation conventions** (§7.0) become mandatory
  from v0.5 on: TerminalProfile detection, rich + textual +
  questionary adoption, hash-chained audit JSONL, typed-phrase
  confirmation gates.
- **Operations Kit (read-only)**: `sange scaffold list / show`.

**Exit criteria**: ≥ 50 external testers; zero critical security
findings.

## v1.0 — GA (Phase 2)

**Goal**: production-grade tool for teams of any size.

**Adds:**

- **Web UI** — Laravel 13 + Livewire 4 + `laravel/passkeys`. All
  21 modules from §8.2. Accessible at `https://sange.test` by
  default (mkcert-provisioned TLS), or via remote-access wizards
  for shared use.
- **Remote access** — `sange web remote setup` wizards for
  Cloudflare Tunnel / Tailscale / WireGuard / reverse-proxy on a
  VPS, with `sange web remote audit` validating the configuration.
- **Release engineering**: bundling (§6.9) for 6 destinations —
  GitHub Releases, GitLab Releases, OCI artifact, S3, generic
  registry, filesystem.
- **CI/CD companion** (§7.5): provider lint + `act`-based local
  exec + simulated end-to-end runs.
- **Plugin system** (§7.9) with a signed marketplace.
- **MCP client + MCP server** (§6.7) so Sange itself becomes
  callable as a tool from other AI agents and vice versa.
- **Full documentation site** at `sange.sh`.
- **History Purge destructive ops** for Git: `sange purge execute /
  push / rollback` with the 8 pre-flight gates from §6.11.4.
- **Full kit surface**: `sange scaffold add / diff / update /
  remove / verify`.
- **`sange vps scaffold <provider>`** covering Hetzner / DO /
  Linode / Vultr / OVH / Scaleway / AWS / GCP / Azure.

**Exit criteria**: stable API; semver guarantees; SLSA 3 releases;
OpenSSF Scorecard ≥ 8.0; ≥ 3 third-party plugins.

## v2.0 — Multi-VCS & Workflow (Phase 3)

**Goal**: cross-VCS parity + power workflows.

**Adds:**

- **Mercurial adapter** (read + write; including `hg convert
  --filemap` for purge).
- **Fossil adapter**.
- **Pijul adapter**.
- **Workflow builder UI** (§8.2.18).
- **Opt-in external telemetry pipeline** (§12.2).
- **Cloudflare Workers edge auth gateway** (§8.5).
- **Purge executors**: SVN (`svnadmin dump → svndumpfilter
  exclude → swap`) + Mercurial (`hg convert --filemap` + `hg
  strip`).

**Exit criteria**: cross-VCS concept map
([Appendix F](../reference/appendix-f-cross-vcs.md)) fully
implemented; workflow library with 20+ presets.

## v3.0 — Enterprise & Team (Phase 4)

**Goal**: org-scale deployment.

**Adds:**

- **Perforce adapter** + `p4 obliterate` purge executor
  (admin-role-gated).
- **Plastic SCM adapter**.
- **Sapling adapter**.
- **SAML / OIDC SSO**.
- **SIEM audit-log forwarding** — forward the hash-chained
  audit JSONL with verified integrity to Splunk / Datadog /
  Sumo / etc.
- **Self-hosted sync server** (opt-in).
- **Sange Cloud** — optional, self-hostable.

**Exit criteria**: SOC 2 readiness checklist; one Fortune 500
design-partner deployment.

## v4.0+ — Speculative (Phase 5)

Held loose because the v0.1..v3.0 backlog has years of work
already. Candidates:

- **IDE deep integration** — VS Code / IntelliJ / vim / emacs
  plugins driving the Web UI's API.
- **Federation across Sange instances** — cross-org commit-state
  exchange with end-to-end integrity proofs.
- **On-device fine-tuning per repo style** — local distillation
  of repo-specific commit conventions onto a small model.

## What's NOT on the roadmap

Honest about what Sange will not become:

- **A VCS replacement.** Sange is a layer on top of Git / SVN /
  Hg / Pijul / Fossil / P4 / Plastic / Sapling — never a fork or
  a competing wire protocol.
- **A SaaS-first product.** Local-first, Apache-2.0,
  self-hostable from day one. Sange Cloud (v3.0+) is optional
  and self-hostable.
- **A code-review tool.** Sange manages the *commit* lifecycle.
  Review tooling — diff annotation, line-by-line discussion,
  PR-style review threads — stays with GitHub / GitLab / Gitea
  etc. The Web UI shows the audit trail, not the line discussion.
- **An LLM provider.** Sange is provider-agnostic; we route to
  Anthropic / OpenAI / Ollama / Gemini / Bedrock and never ship
  a hosted model.

## Cross-phase invariants

These hold across every release:

- Every phase passes the §19 quality gates in scope at that
  phase's exit.
- Every phase ships an updated
  [`content-audit.md`](../../.design/plans/content-audit.md)
  showing requirement → section mapping.
- Every release tag is immutable per CLAUDE.md "release-as-immutable":
  fix-forwards ship as `.postN` or the next semver bump, never as
  retags.
- ADR-031 audit-trail discipline: every change is recorded in
  `.design/plans/session-log.md` as it happens.

## How to track progress

| Surface | Purpose |
| :--- | :--- |
| [`CHANGELOG.md`](../../CHANGELOG.md) | What shipped in each release. Hand-edited between generator runs (per the preamble), generated by T-G-013 once the project dogfoods its own lifecycle. |
| [`.design/plans/checklist.md`](../../.design/plans/checklist.md) | Master task list. Each task is `T-NNN` and links to its phase. |
| [`.design/plans/session-log.md`](../../.design/plans/session-log.md) | Append-only audit trail of every change. The reader-facing "why did this land" record. |
| [`.design/plans/decisions-log.md`](../../.design/plans/decisions-log.md) | 33 ADRs documenting every non-trivial design choice. |
| [`.design/plans/snapshots/`](../../.design/plans/snapshots/) | Cold-resume snapshots at phase boundaries (ADR-031). |
| GitHub Releases | Each tag's release notes, drawn from `docs/CHANGELOG.md`. |

For a question about a specific decision, start at the ADR
([`decisions-log.md`](../../.design/plans/decisions-log.md)). For
a question about where the project is going, start here.
