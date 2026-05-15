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

> **Status: v0.1.0 tagged (2026-05-14)**, Phase 1 CLI surface complete on
> `main`. The architecture is locked (`.design/sange-architecture.md`,
> v4.4). `pip install sange` lights up once the PyPI trusted-publisher
> configuration completes — see `docs/release.md::Step 0` and the
> v0.1.0 known-issues in `CHANGELOG.md`. Multi-arch Docker image
> available at `ghcr.io/simsange/sange:v0.1.0`. Track ongoing
> progress at `.design/plans/checklist.md`.

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

**Live now:**

| Topic | Path |
|---|---|
| Quickstart | [`docs/quickstart.md`](docs/quickstart.md) |
| Commit lifecycle walkthrough | [`docs/tools/workflow/commit-lifecycle.md`](docs/tools/workflow/commit-lifecycle.md) |
| Release procedure | [`docs/release.md`](docs/release.md) |
| Changelog | [`CHANGELOG.md`](CHANGELOG.md) |
| ADR index (33 decisions) | [`docs/adr/`](docs/adr/) and [`.design/plans/decisions-log.md`](.design/plans/decisions-log.md) |
| CLI reference | [`docs/reference/cli-reference.md`](docs/reference/cli-reference.md) |
| Git command catalog (Appendix D) | [`docs/reference/appendix-d-git-catalog.md`](docs/reference/appendix-d-git-catalog.md) |
| SVN command catalog (Appendix E) | [`docs/reference/appendix-e-svn-catalog.md`](docs/reference/appendix-e-svn-catalog.md) |
| Cross-VCS concept map (Appendix F) | [`docs/reference/appendix-f-cross-vcs.md`](docs/reference/appendix-f-cross-vcs.md) |
| Commit template library (Appendix G) | [`docs/reference/appendix-g-commit-templates.md`](docs/reference/appendix-g-commit-templates.md) |
| Profile registry | [`docs/reference/profile-registry.md`](docs/reference/profile-registry.md) |
| Config schema | [`docs/reference/config-schema.md`](docs/reference/config-schema.md) |
| Exit codes | [`docs/reference/exit-codes.md`](docs/reference/exit-codes.md) |
| Operations Kit manifest | [`docs/reference/kit-manifest.md`](docs/reference/kit-manifest.md) |
| Threat model (STRIDE) | [`docs/security/stride.md`](docs/security/stride.md) |
| Architecture deliverable (canonical) | [`.design/sange-architecture.md`](.design/sange-architecture.md) |
| Master checklist | [`.design/plans/checklist.md`](.design/plans/checklist.md) |

**Planned** (each lands as the relevant `T-G-NNN` task in
[`.design/plans/checklist.md`](.design/plans/checklist.md) flips
`completed`):

| Topic | Target | Gates on |
|---|---|---|
| Installation | `docs/installation.md` | v0.1.0 PyPI publish |
| Architecture (reader-oriented) | `docs/architecture.md` | post-v0.1 polish |
| Release bundling | `docs/tools/release/bundle.md` | v0.5+ release engine |
| History purge | `docs/tools/security/purge.md` | v1.0 purge subsystem |
| Remote access | `docs/tools/ui/remote-access.md` | v1.0 Web UI |
| Premade ops kit | `docs/tools/ui/vps-setup.md` | v1.0 kit surface |
| Per-VCS reference | `docs/tools/vcs/` | per-tool docs sprint |
| Per-language profiles | `docs/tools/lang/` | per-tool docs sprint |
| JSON-RPC schema | `docs/reference/json-rpc-schema.md` | T-162 (v1.0) |
| Prompt-injection defense | `docs/security/prompt-injection.md` | per-topic docs sprint |
| SLSA + SBOM | `docs/security/slsa-and-sbom.md` | per-topic docs sprint |
| Roadmap | `docs/governance/roadmap.md` | governance docs sprint |
| ADR process | `docs/governance/adr-process.md` | governance docs sprint |
| Operations runbook | `docs/operations/` | v0.5+ operator-facing |

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
