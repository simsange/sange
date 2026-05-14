# `tools/scaffold/` — content-filter fallback helpers

These are interactive-session helpers used **only** when an AI agent driving
the build phase hits an "Output blocked by content filtering policy" error
emitting a file directly. They are **not** the canonical generators (those
live under `tools/generators/` and follow the §2.4 generate-first / fine-tune-
second discipline).

When a fallback is used, the agent records the use in
`.design/plans/session-log.md` with `🟡 UNVERIFIED` or `❌ Refuted` markers
per ADR-030, and a human reviewer flips the `stub: true` flag in the file's
frontmatter to `false` (or removes the frontmatter entirely if no generator
owns the file).

## Scripts

| Script | Purpose |
|---|---|
| `emit_stub.py` | Write a single stub file with frontmatter + a `TODO: HUMAN REVIEW` marker. |
| `batch_stubs.toml` _(future)_ | Declarative list of files to stub when several are blocked at once. |

## Usage

```bash
python tools/scaffold/emit_stub.py \\
  --path docs/security/threat-model.md \\
  --kind markdown \\
  --topic "STRIDE threat model" \\
  --refers-to ".design/sange-architecture-prompt.md §11" \\
  --body "Stub — see source spec."
```

## Anti-hallucination

The stubs are deliberately empty. The point is to leave a marker the human can
fill in by hand later — not to guess at the content the filter blocked. The
generator pipeline (T-G-001 .. T-G-016) eventually replaces the stub.

When a stub is emitted, do **not** mark its task `completed` in the harness
task list — keep it `in_progress` so the work is visibly outstanding.
