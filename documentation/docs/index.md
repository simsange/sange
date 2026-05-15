# Sange

> Local-first developer-experience layer between humans and their
> version-control systems — eliminating boilerplate, enforcing safety,
> embedding AI assistance into every commit, branch, and release.

Sange is a polyglot VCS automation toolkit (Git working today;
SVN / Mercurial / Perforce coming) that lifts the everyday plumbing
out of your way:

- **AI-generated commit messages** — Conventional Commits, derived
  from your staged diff, with secret redaction before any payload
  leaves your machine.
- **Lifecycle-tracked commits** — every message goes through
  DRAFT → APPROVED → COMMITTED → PUSHED, persisted as JSON in
  `.sange/commits/`. No more `git commit -m` ambiguity.
- **Modular Makefile system** — one auto-generated top-level
  Makefile + a fragment library at `.sange/makefiles/`. Self-help
  built in (`make help`).
- **Provider-agnostic AI** — Anthropic, OpenAI, Ollama, Gemini,
  Bedrock, Azure OpenAI, MCP. Switch providers per-invocation; the
  redaction layer is the same for all of them.
- **Local-only telemetry** — NDJSON in `.sange/telemetry/`, off by
  default for external send, on by default for local
  cost/latency/retry tracking.

## Quick install

=== "pip"

    ```bash
    pip install sange
    sange --version
    ```

=== "Docker"

    ```bash
    docker pull ghcr.io/simsange/sange:latest
    docker run --rm -v "$PWD":/repo ghcr.io/simsange/sange --version
    ```

=== "From source"

    ```bash
    git clone https://github.com/simsange/sange.git
    cd sange
    pip install -e ".[dev]"
    ```

## The five-step golden path

```bash
sange init                              # bootstrap .sange/ in this repo
git add <files>                          # stage your changes as usual
git diff --staged | sange commit         # generate the commit message
sange commits approve 1 -i               # review + approve (interactive)
sange commits push 1                     # git commit + git push
```

That's it. Each step is auditable, each step is reversible until the
final push, and the AI provider's payload is scrubbed of secrets
before transmission.

## Where to go from here

- [Getting started](getting-started.md) — install + your first commit
  end-to-end.
- [CLI commands](cli/index.md) — every subcommand explained.
- [Architecture](architecture/index.md) — how the pieces fit together.
- [GitHub repo →](https://github.com/simsange/sange)
- [Full CLI reference →](https://github.com/simsange/sange/blob/main/docs/reference/cli-reference.md)
  (auto-generated from the typer app)

## License + maintainer

Apache License 2.0, © [Simtabi LLC](https://simtabi.com).
Maintained by [Imani Manyara](mailto:imani@simtabi.com).
Community contact: [opensource@simtabi.com](mailto:opensource@simtabi.com).
