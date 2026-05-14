---
generated_by: tools/generators/cli_reference.py
generator_version: 1.0.0
generated_at: 2026-05-14T19:20:02Z
input_sha256: f6019b9d4f28b45745ed28581770da78737f9937f8d001a9f07e65df096ea257
output_sha256: b64fb5725a56a4abdbd31736bd830d2a5dd2fdc606ab11030c7185ee4603c653
manual_edits_allowed: false
---
# Sange CLI reference


> Generated from the live `sange.cli:app` (typer) by `tools/generators/cli_reference.py` (T-G-009). Source-of-truth for command behaviour: the Python decorators on each command function in `src/sange/cli/`. Update the code; this file regenerates from CI.

Every entry below is auto-introspected from the live click command tree, so flag ordering, help text, and defaults stay in lock-step with the implementation. Manual edits to this file are rejected by `verify_generated.py`.

## Command index


| Command | Summary |
| :--- | :--- |
| `sange` | Polyglot VCS automation toolkit (Git/SVN/Hg/P4). |
| `sange ai` | AI provider preview + introspection. |
| `sange ai preview` | Render the prompt for a task without sending. |
| `sange ai providers` | List registered AI providers + capabilities. |
| `sange commit` | Generate a commit message from a diff. |
| `sange doctor` | Environment health checks. |


## Commands


### `sange`


Polyglot VCS automation toolkit (Git/SVN/Hg/P4).

**Options:**

| Flag | Kind | Default | Description |
| :--- | :--- | :--- | :--- |
| `--json` | flag | false | Emit machine-readable JSON output where supported. |
| `--version` | flag | false | Show version and exit. |


**Sub-commands:**

| Sub-command | Description |
| :--- | :--- |
| `sange ai` | AI provider preview + introspection. |
| `sange commit` | Generate a commit message from a diff. |
| `sange doctor` | Environment health checks. |


### `sange ai`


AI provider preview + introspection.

**Sub-commands:**

| Sub-command | Description |
| :--- | :--- |
| `sange ai preview` | Render the prompt for a task without sending. |
| `sange ai providers` | List registered AI providers + capabilities. |


### `sange ai preview`


Render the prompt for a task without sending.

**Options:**

| Flag | Kind | Default | Description |
| :--- | :--- | :--- | :--- |
| `--branch` | value |  | Current branch name. |
| `--diff` | value |  | Path to a file containing the staged diff. When omitted, reads from stdin. |
| `--file` | value |  | Files changed by the diff. Repeat for multiple. (`--file a.py --file b.py`) |
| `--provider` | value | `mock` | Provider whose formatting to preview (anthropic / openai / mock / ...). |
| `--task` | value | `commit-msg` | Task to preview. v0.1 supports: commit-msg. |


### `sange ai providers`


List registered AI providers + capabilities.

### `sange commit`


Generate a commit message from a diff.

**Options:**

| Flag | Kind | Default | Description |
| :--- | :--- | :--- | :--- |
| `--diff` | value |  | Path to a file containing the staged diff. When omitted, reads from stdin. |
| `--model` | value | `mock-1` | Model identifier passed to the provider. |
| `--no-save`, `--save` | flag | true | Save the generated commit as a DRAFT in <repo>/.sange/commits/. Disable for ephemeral one-shot use. |
| `--no-telemetry` | flag | false | Disable local telemetry recording for this invocation. |
| `--provider` | value | `mock` | AI provider to call (mock / anthropic / openai / ollama / ...). |
| `--repo` | value |  | Repo root for context lookup (branch + recent commits). When omitted, the prompt receives empty repo context. |
| `--scope` | value |  | Optional scope hint biasing the generated message. |
| `--telemetry-dir` | value | `.sange/telemetry` | Where to write the NDJSON telemetry file. Default: .sange/telemetry in the current directory. |


### `sange doctor`


Environment health checks.

## Exit codes


See [`docs/reference/exit-codes.md`](exit-codes.md) for the canonical mapping. CLI commands return the codes documented there; `sange doctor` returns non-zero when any check fails.
