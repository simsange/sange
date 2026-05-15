# Architecture

Sange follows a layered architecture per §6.2 of the design workbook:

```
┌────────────────────────────────────────────────────────────────┐
│ Presentation (sange.cli)                                       │
│   typer app, questionary prompts, JSON output mode             │
└─────────────────┬──────────────────────────────────────────────┘
                  │
┌─────────────────▼──────────────────────────────────────────────┐
│ Application (sange.core)                                       │
│   PromptEnhancer (redaction → render → format → call → validate)│
│   LifecycleEngine (8-state forward-only machine + reopen)      │
│   generate_commit_message() composes them                       │
└─────────────────┬──────────────────────────────────────────────┘
                  │
┌─────────────────▼──────────────────────────────────────────────┐
│ Domain (sange.core.models, sange.core.lifecycle.schema)        │
│   Repo, CommitRef, BranchInfo (frozen dataclasses)             │
│   CommitJSON, CommitMessage (Pydantic v2 with cross-field      │
│   validators — committed_sha iff status >= COMMITTED, etc.)    │
└─────────────────┬──────────────────────────────────────────────┘
                  │
┌─────────────────▼──────────────────────────────────────────────┐
│ Adapters (sange.adapters)                                      │
│   AIProvider Protocol (mock / anthropic / openai / ollama / …) │
│   VCSDriver Protocol (git / svn future)                        │
│   formatting strategies (XML / JSON / markdown per provider)   │
└─────────────────┬──────────────────────────────────────────────┘
                  │
┌─────────────────▼──────────────────────────────────────────────┐
│ Infrastructure (subprocess, filesystem, network)               │
│   GitDriver (real `git` subprocess)                            │
│   TelemetryCollector (NDJSON append-only)                       │
│   CommitsDirectory (.sange/commits/ atomic writes)              │
└────────────────────────────────────────────────────────────────┘
```

The dependency arrows point **down** — Presentation depends on
Application depends on Domain. Adapters and Infrastructure are
behind Protocols, so swapping a provider (or eventually an SVN
adapter for Git) is a single registration call.

## Key concepts

- **[The audit chain](audit-chain.md)** — how every AI call is
  redacted, recorded, and traceable from input diff to pushed commit.
- **[T-030 redaction](redaction.md)** — what gets scrubbed, why,
  how to extend.

## External reading

For the full design workbook (every ADR, every red-team pass, every
generator pipeline), see:

- [`.design/sange-architecture-prompt.md`](https://github.com/simsange/sange/blob/main/.design/sange-architecture-prompt.md)
  — the canonical specification (~45,000 words).
- [`docs/adr/`](https://github.com/simsange/sange/tree/main/docs/adr)
  — accepted ADRs (33 today).
- [`docs/security/stride.md`](https://github.com/simsange/sange/blob/main/docs/security/stride.md)
  — the STRIDE threat model (26 classified threats).
