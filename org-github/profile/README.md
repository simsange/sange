# sangedev — the Sange ecosystem

The home of [Sange](https://github.com/sangedev/sange) and its
companion projects: a local-first developer-experience layer between
humans and their version-control systems.

## What lives here

| Repo | Purpose |
|---|---|
| [`sange`](https://github.com/sangedev/sange) | The main project — polyglot VCS automation toolkit (Git working today; SVN / Mercurial / Perforce coming). |
| [`documentation`](https://github.com/sangedev/documentation) | The public docs site, deployed to <https://opensource.simtabi.com/documentation/sange>. |
| [`.github`](https://github.com/sangedev/.github) | This repo — org-wide community-health files (this README, default issue templates, default PR template, fallback CODE_OF_CONDUCT / SECURITY policies). |

More repos will join the org as the ecosystem grows.

## Get started with Sange

```bash
pip install sange
sange init
git diff --staged | sange commit
sange commits approve 1 -i
sange commits push 1
```

That's the full v0.1 happy path. See
[the Sange docs](https://opensource.simtabi.com/documentation/sange)
for the walkthrough.

## Highlights

- **AI-generated Conventional Commits messages**, derived from your
  staged diff, with **T-030 secret redaction firing before any
  payload leaves your machine**.
- **Lifecycle-tracked commits** persisted to `.sange/commits/` as
  JSON — every state transition (DRAFT → APPROVED → COMMITTED →
  PUSHED) audited.
- **Local-only NDJSON telemetry**. External send is opt-in and
  off-by-default per ADR-008.
- **Multi-arch Docker image** (linux/amd64 + linux/arm64) per
  ADR-033 — runs native on Apple Silicon, AWS Graviton, Hetzner
  Ampere ARM, Raspberry Pi.
- **Modular Makefile system** (§10) — one auto-generated shim +
  a fragment library at `.sange/makefiles/`.
- **Provider-agnostic AI** — Anthropic, OpenAI, Ollama, Gemini,
  Bedrock, Azure OpenAI, MCP.

## Project info

- **License:** Apache License 2.0
- **Maintainer:** [Imani Manyara](mailto:imani@simtabi.com)
- **Owner:** [Simtabi LLC](https://simtabi.com)
- **Community contact:** [opensource@simtabi.com](mailto:opensource@simtabi.com)
- **Security disclosures:** see [SECURITY.md](https://github.com/sangedev/.github/blob/main/SECURITY.md)
- **Code of Conduct:** [Contributor Covenant 2.1](https://github.com/sangedev/.github/blob/main/CODE_OF_CONDUCT.md)

## Contributing

We welcome PRs. See [CONTRIBUTING.md](https://github.com/sangedev/.github/blob/main/CONTRIBUTING.md)
for the org-wide contributor guide; per-product specifics live in
each repo's own `CONTRIBUTING.md`.
