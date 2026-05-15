# Sange

> Local-first developer-experience layer between humans and their
> version-control systems — eliminating boilerplate, enforcing safety,
> embedding AI assistance into every commit, branch, and release, and
> providing a secure dashboard (local or self-hosted) for fine-grained
> review, approval, scheduling, and orchestration.

[![CI](https://github.com/simsange/sange/actions/workflows/ci.yml/badge.svg)](https://github.com/simsange/sange/actions/workflows/ci.yml)
[![License: Apache-2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](pyproject.toml)
[![OpenSSF Scorecard](https://api.securityscorecards.dev/projects/github.com/simsange/sange/badge)](https://securityscorecards.dev/viewer/?uri=github.com/simsange/sange)

> **Status: pre-alpha.** The architecture is locked
> (`.design/sange-architecture.md`, v4.4). The code is being built — Phase 0a
> (generators-scaffold-everything per ADR-029) is in progress. Track progress
> at `.design/plans/checklist.md`. First tagged release: `v0.1.0` (MVP).

## What Sange is

- A **workflow layer** that wraps your chosen VCS (Git, SVN, Mercurial,
  Perforce) — never a replacement for it.
- A **commit message lifecycle** (`draft → pending_review → approved →
  committed → pushed → archived`) with AI generation, prompt enhancer, and
  ≥50 normalized presets.
- A **release engine** with signed bundles, SBOM, SLSA 3 provenance, and
  6 destinations (GitHub / GitLab / OCI / S3 / generic registry / filesystem).
- A **history-purge subsystem** with 8 pre-flight gates, hash-chained audit
  JSONL, typed-phrase confirmation, and per-VCS executors.
- A **local-first dashboard** (Laravel 13 + Livewire 4 + WebAuthn passkeys)
  approachable to non-developers — accessible at `https://sange.test` by
  default; remote access via Cloudflare Tunnel / Tailscale / WireGuard / VPS.

## What Sange is not

- Not a fork of any VCS.
- Not a competing wire protocol or repository host.
- Not a closed-source SaaS — it's local-first, Apache-2.0, self-hostable.

## Quickstart

> The installer ships at the v0.1 release. Until then, install from source:

```bash
git clone https://github.com/simsange/sange.git
cd sange
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev,tui]"

# Verify install:
python -c "import sange; print(sange.__version__)"
```

When the v0.1 release ships:

```bash
# macOS / Linux:
curl -fsSL https://sange.sh/install.sh | sh   # checksum + sigstore verified

# Windows (PowerShell):
iwr -useb https://sange.sh/install.ps1 | iex
```

## Documentation

All documentation lives under `docs/`. The canonical reference is the
architecture deliverable in `.design/sange-architecture.md`; reader-oriented
manuals are split per-tool, per-topic.

| Topic | Path |
|---|---|
| Installation | [`docs/installation.md`](docs/installation.md) |
| Quickstart | [`docs/quickstart.md`](docs/quickstart.md) |
| Architecture (narrative) | [`docs/architecture.md`](docs/architecture.md) |
| ADR index | [`docs/adr/`](docs/adr/) |
| Audit findings (v1, v2) | [`docs/audit/`](docs/audit/) |
| Commit lifecycle walkthrough | [`docs/tools/workflow/commit-lifecycle.md`](docs/tools/workflow/commit-lifecycle.md) |
| Release bundling | [`docs/tools/release/bundle.md`](docs/tools/release/bundle.md) |
| History purge | [`docs/tools/security/purge.md`](docs/tools/security/purge.md) |
| Remote access | [`docs/tools/ui/remote-access.md`](docs/tools/ui/remote-access.md) |
| Premade ops kit | [`docs/tools/ui/vps-setup.md`](docs/tools/ui/vps-setup.md) |
| Per-VCS reference | [`docs/tools/vcs/`](docs/tools/vcs/) |
| Per-language profiles | [`docs/tools/lang/`](docs/tools/lang/) |
| Git command catalog (Appendix D) | [`docs/reference/git-command-catalog.md`](docs/reference/git-command-catalog.md) |
| SVN command catalog (Appendix E) | [`docs/reference/svn-command-catalog.md`](docs/reference/svn-command-catalog.md) |
| Cross-VCS concept map (Appendix F) | [`docs/reference/cross-vcs-concept-map.md`](docs/reference/cross-vcs-concept-map.md) |
| Commit template library (Appendix G) | [`docs/reference/commit-template-library.md`](docs/reference/commit-template-library.md) |
| Profile registry | [`docs/reference/profile-registry.md`](docs/reference/profile-registry.md) |
| CLI reference | [`docs/reference/cli-reference.md`](docs/reference/cli-reference.md) |
| JSON-RPC schema | [`docs/reference/json-rpc-schema.md`](docs/reference/json-rpc-schema.md) |
| Config schema | [`docs/reference/config-schema.md`](docs/reference/config-schema.md) |
| Exit codes | [`docs/reference/exit-codes.md`](docs/reference/exit-codes.md) |
| Threat model (STRIDE) | [`docs/security/threat-model.md`](docs/security/threat-model.md) |
| Prompt-injection defense | [`docs/security/prompt-injection.md`](docs/security/prompt-injection.md) |
| SLSA + SBOM | [`docs/security/slsa-and-sbom.md`](docs/security/slsa-and-sbom.md) |
| Roadmap (v0.1 → v3.0+) | [`docs/governance/roadmap.md`](docs/governance/roadmap.md) |
| ADR process | [`docs/governance/adr-process.md`](docs/governance/adr-process.md) |
| Operations runbook | [`docs/operations/`](docs/operations/) |

Many of the paths above are populated by Phase 0a generators
(`tools/generators/`); they appear as the relevant `T-G-NNN` tasks land in
`.design/plans/checklist.md`.

## Audience

Sange is designed to be approachable to seven personas — non-developer founders,
CTOs, cyber-security reviewers, junior engineers, senior staff engineers,
DevOps/SRE, and OSS maintainers. A feature usable only by senior engineers, with
no equivalently-safe path for the others, is a design defect. See
[`.design/plans/positioning.md`](.design/plans/positioning.md).

## Etymology

Named after the **sengi** (Swahili for the elephant shrew), stylized as
"Sange" for branding — short, memorable, evocative of the agile, resilient
nature of the animal. See ADR-014 for the framing rationale.

## License

Sange is licensed under the [Apache License 2.0](LICENSE) (ADR-007). The patent
grant matters for the plugin ecosystem and enterprise adoption.

Copyright © 2026 Simtabi LLC.

## Reporting and contact

- **Bugs / feature requests:** <https://github.com/simsange/sange/issues>
- **Security:** `opensource@simtabi.com` — see [`SECURITY.md`](SECURITY.md)
- **General contact (OSS):** `opensource@simtabi.com`
- **Maintainer:** Imani Manyara — `imani@simtabi.com`
- **Product page:** <https://opensource.simtabi.com/products/sange>
