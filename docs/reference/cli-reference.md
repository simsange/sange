---
generated_by: tools/generators/cli_reference.py
generator_version: 1.0.0
generated_at: 2026-05-15T15:34:28Z
input_sha256: f84331228926701d822d4454b2f4ce7748aa5bf57f8c5138d2083a5ff044b322
output_sha256: d4917ddf5f71767f248dde3765e9901dfa45add257b41595619a21c18910a240
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
| `sange commits` | Manage the commit lifecycle queue. |
| `sange commits ai` | Generate a commit message via AI and save as DRAFT. |
| `sange commits approve` | Approve a commit (DRAFT → APPROVED). |
| `sange commits commit` | Land an APPROVED commit locally (git commit, no push). |
| `sange commits list` | Show the commit queue. |
| `sange commits new` | Write a manual DRAFT commit to the queue (no AI involved). |
| `sange commits push` | Land an APPROVED commit (git commit + optionally git push). |
| `sange commits reject` | Reject a PENDING_REVIEW commit (PENDING_REVIEW → REJECTED). |
| `sange commits submit` | Submit a DRAFT for review (DRAFT → PENDING_REVIEW). |
| `sange doctor` | Environment health checks. |
| `sange init` | Bootstrap .sange/ skeleton in the target repo. |


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
| `sange commits` | Manage the commit lifecycle queue. |
| `sange doctor` | Environment health checks. |
| `sange init` | Bootstrap .sange/ skeleton in the target repo. |


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


### `sange commits`


Manage the commit lifecycle queue.

**Sub-commands:**

| Sub-command | Description |
| :--- | :--- |
| `sange commits ai` | Generate a commit message via AI and save as DRAFT. |
| `sange commits approve` | Approve a commit (DRAFT → APPROVED). |
| `sange commits commit` | Land an APPROVED commit locally (git commit, no push). |
| `sange commits list` | Show the commit queue. |
| `sange commits new` | Write a manual DRAFT commit to the queue (no AI involved). |
| `sange commits push` | Land an APPROVED commit (git commit + optionally git push). |
| `sange commits reject` | Reject a PENDING_REVIEW commit (PENDING_REVIEW → REJECTED). |
| `sange commits submit` | Submit a DRAFT for review (DRAFT → PENDING_REVIEW). |


### `sange commits ai`


Generate a commit message via AI and save as DRAFT.

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


### `sange commits approve`


Approve a commit (DRAFT → APPROVED).

**Arguments:**

| Name | Status |
| :--- | :--- |
| `target` | required |


**Options:**

| Flag | Kind | Default | Description |
| :--- | :--- | :--- | :--- |
| `--actor` | value |  | Approver name. Default: $USER environment variable. |
| `--interactive`, `--no-interactive`, `-i` | flag | false | Show the rendered message + prompt approve / reject / skip. Default: non-interactive (approve immediately). |
| `--repo` | value | `.` | Repo root (the parent of .sange/commits/). Default: cwd. |
| `--via` | value | `cli` | Surface the approval came through (cli / tui / web / mcp). |


### `sange commits commit`


Land an APPROVED commit locally (git commit, no push).

**Arguments:**

| Name | Status |
| :--- | :--- |
| `target` | required |


**Options:**

| Flag | Kind | Default | Description |
| :--- | :--- | :--- | :--- |
| `--author-email` | value |  | Override the author email (otherwise git config user.email). |
| `--author-name` | value |  | Override the author name (otherwise git config user.name). |
| `--repo` | value | `.` | Repo root (must be a working git checkout). Default: cwd. |
| `--sign` | flag | false | GPG-sign the commit (`git commit -S`). |


### `sange commits list`


Show the commit queue.

**Options:**

| Flag | Kind | Default | Description |
| :--- | :--- | :--- | :--- |
| `--include-archived` | flag | false | Include rows in .sange/commits/archive/. |
| `--repo` | value | `.` | Repo root (the parent of .sange/commits/). Default: cwd. |
| `--status` | value |  | Filter by status (draft / pending_review / approved / committed / pushed / archived / rejected / discarded). Empty = all. |


### `sange commits new`


Write a manual DRAFT commit to the queue (no AI involved).

**Arguments:**

| Name | Status |
| :--- | :--- |
| `subject` | required |
| `type_` | required |


**Options:**

| Flag | Kind | Default | Description |
| :--- | :--- | :--- | :--- |
| `--body` | value |  | Commit body. Pass `-` to read from stdin. |
| `--branch` | value |  | Branch override. Default: auto-detect via GitDriver (falls back to empty string if not in a git repo). |
| `--breaking-change` | flag | false | Mark this commit as introducing a BREAKING CHANGE. |
| `--co-author` | value |  | Co-author (repeatable). Format: `Name <email>`. |
| `--reference` | value |  | Issue / ticket reference (repeatable). Format: `#123` or `JIRA-42`. |
| `--repo` | value | `.` | Repo root (the parent of .sange/commits/). Default: cwd. |
| `--scope` | value |  | Optional scope (lowercase letters/digits/hyphens). |


### `sange commits push`


Land an APPROVED commit (git commit + optionally git push).

**Arguments:**

| Name | Status |
| :--- | :--- |
| `target` | required |


**Options:**

| Flag | Kind | Default | Description |
| :--- | :--- | :--- | :--- |
| `--author-email` | value |  | Override the author email (otherwise git config user.email). |
| `--author-name` | value |  | Override the author name (otherwise git config user.name). |
| `--branch` | value |  | Branch to push. Default: current branch. |
| `--no-push`, `--push` | flag | true | After the local commit lands, also `git push` to the remote. |
| `--remote` | value | `origin` | Remote name when --push is on. Default: origin. |
| `--repo` | value | `.` | Repo root (must be a working git checkout). Default: cwd. |
| `--sign` | flag | false | GPG-sign the commit (`git commit -S`). |


### `sange commits reject`


Reject a PENDING_REVIEW commit (PENDING_REVIEW → REJECTED).

**Arguments:**

| Name | Status |
| :--- | :--- |
| `target` | required |


**Options:**

| Flag | Kind | Default | Description |
| :--- | :--- | :--- | :--- |
| `--actor` | value |  | Rejector name. Default: $USER environment variable. |
| `--reason` | value |  | Non-empty rejection reason (≤480 chars). |
| `--repo` | value | `.` | Repo root (the parent of .sange/commits/). Default: cwd. |
| `--via` | value | `cli` | Surface the rejection came through (cli / tui / web / mcp). |


### `sange commits submit`


Submit a DRAFT for review (DRAFT → PENDING_REVIEW).

**Arguments:**

| Name | Status |
| :--- | :--- |
| `target` | required |


**Options:**

| Flag | Kind | Default | Description |
| :--- | :--- | :--- | :--- |
| `--repo` | value | `.` | Repo root (the parent of .sange/commits/). Default: cwd. |


### `sange doctor`


Environment health checks.

### `sange init`


Bootstrap .sange/ skeleton in the target repo.

**Options:**

| Flag | Kind | Default | Description |
| :--- | :--- | :--- | :--- |
| `--force` | flag | false | Overwrite existing files. Default: keep existing untouched. |
| `--gitignore`, `--no-gitignore` | flag | true | Append /Makefile + /.sange/ entries to .gitignore. |
| `--makefile`, `--no-makefile` | flag | true | Install the top-level Makefile + .sange/makefiles/ tree. |
| `--repo` | value | `.` | Target repo root. Default: the current directory. |


## Exit codes


See [`docs/reference/exit-codes.md`](exit-codes.md) for the canonical mapping. CLI commands return the codes documented there; `sange doctor` returns non-zero when any check fails.
