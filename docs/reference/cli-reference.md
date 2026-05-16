---
generated_by: tools/generators/cli_reference.py
generator_version: 1.0.0
generated_at: 2026-05-16T08:47:10Z
input_sha256: c77ddb2c9e1c5431e87697edbfbbaaafafa38d975f428a7e7d416acda118e2f3
output_sha256: 268018083aec20574e4608b171f02cb716b137bdf4d224cea258d161102ecc32
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
| `sange audit` | Inspect + verify the hash-chained audit JSONL (T-108). |
| `sange audit append` | Append a record (mainly for plugins + manual testing). |
| `sange audit list` | List audit records (every shard, or filtered). |
| `sange audit tail` | Print the most recent N audit records. |
| `sange audit verify` | Walk the chain + recompute every hash. Exit 0 clean / 1 tampered. |
| `sange commit` | Generate a commit message from a diff. |
| `sange commits` | Manage the commit lifecycle queue. |
| `sange commits ai` | Generate a commit message via AI and save as DRAFT. |
| `sange commits approve` | Approve a commit (DRAFT → APPROVED). |
| `sange commits commit` | Land an APPROVED commit locally (git commit, no push). |
| `sange commits list` | Show the commit queue. |
| `sange commits new` | Write a manual DRAFT commit to the queue (no AI involved). |
| `sange commits push` | Land an APPROVED commit (git commit + optionally git push). |
| `sange commits reject` | Reject a PENDING_REVIEW commit (PENDING_REVIEW → REJECTED). |
| `sange commits reopen` | Re-open a non-DRAFT commit back to DRAFT (the only backward transition). |
| `sange commits submit` | Submit a DRAFT for review (DRAFT → PENDING_REVIEW). |
| `sange doctor` | Environment health checks. |
| `sange gitignore` | Manage the active gitignore profile (T-101). |
| `sange gitignore current` | Show the currently active gitignore profile. |
| `sange gitignore detect` | Auto-detect profile candidates for the repo. |
| `sange gitignore list` | List discoverable gitignore profiles. |
| `sange gitignore recover` | Roll forward any crashed-in-progress swap journals. |
| `sange gitignore swap` | Atomic swap to a new gitignore composition. |
| `sange hooks` | Manage pre-commit / pre-push / etc. hooks (T-102). |
| `sange hooks add` | Install a named gate's scripts into .sange/hooks/. |
| `sange hooks gates` | List available named gates (gitleaks / trufflehog / make-test / etc.). |
| `sange hooks install` | Write .git/hooks/<event> shims that delegate to `sange hooks run`. |
| `sange hooks list` | Show discovered hooks (every event, or a specific one). |
| `sange hooks remove` | Remove a named gate's scripts from .sange/hooks/. |
| `sange hooks run` | Run every hook for EVENT in priority order. |
| `sange hooks status` | Per-event summary: hook count + shim install state. |
| `sange hooks uninstall` | Remove Sange-managed .git/hooks/<event> shims (foreign hooks untouched). |
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
| `sange audit` | Inspect + verify the hash-chained audit JSONL (T-108). |
| `sange commit` | Generate a commit message from a diff. |
| `sange commits` | Manage the commit lifecycle queue. |
| `sange doctor` | Environment health checks. |
| `sange gitignore` | Manage the active gitignore profile (T-101). |
| `sange hooks` | Manage pre-commit / pre-push / etc. hooks (T-102). |
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

### `sange audit`


Inspect + verify the hash-chained audit JSONL (T-108).

**Sub-commands:**

| Sub-command | Description |
| :--- | :--- |
| `sange audit append` | Append a record (mainly for plugins + manual testing). |
| `sange audit list` | List audit records (every shard, or filtered). |
| `sange audit tail` | Print the most recent N audit records. |
| `sange audit verify` | Walk the chain + recompute every hash. Exit 0 clean / 1 tampered. |


### `sange audit append`


Append a record (mainly for plugins + manual testing).

**Arguments:**

| Name | Status |
| :--- | :--- |
| `kind` | required |


**Options:**

| Flag | Kind | Default | Description |
| :--- | :--- | :--- | :--- |
| `--actor` | value |  | Identifier for the actor responsible. Required. |
| `--payload` | value |  | JSON-encoded payload dict. Default: empty `{}`. |
| `--repo` | value | `.` | Repo root. Default: cwd. |


### `sange audit list`


List audit records (every shard, or filtered).

**Options:**

| Flag | Kind | Default | Description |
| :--- | :--- | :--- | :--- |
| `--kind` | value |  | Filter by event kind (e.g. `commit-push`). |
| `--repo` | value | `.` | Repo root. Default: cwd. |
| `--week` | value |  | ISO week filter `YYYY-WNN` (e.g. 2026-W20). Empty = all. |


### `sange audit tail`


Print the most recent N audit records.

**Options:**

| Flag | Kind | Default | Description |
| :--- | :--- | :--- | :--- |
| `--n` | value | `10` | Number of records to show. Default: 10. |
| `--repo` | value | `.` | Repo root. Default: cwd. |


### `sange audit verify`


Walk the chain + recompute every hash. Exit 0 clean / 1 tampered.

**Options:**

| Flag | Kind | Default | Description |
| :--- | :--- | :--- | :--- |
| `--repo` | value | `.` | Repo root (parent of .sange/). Default: cwd. |


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
| `sange commits reopen` | Re-open a non-DRAFT commit back to DRAFT (the only backward transition). |
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


### `sange commits reopen`


Re-open a non-DRAFT commit back to DRAFT (the only backward transition).

**Arguments:**

| Name | Status |
| :--- | :--- |
| `target` | required |


**Options:**

| Flag | Kind | Default | Description |
| :--- | :--- | :--- | :--- |
| `--repo` | value | `.` | Repo root (the parent of .sange/commits/). Default: cwd. |


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

### `sange gitignore`


Manage the active gitignore profile (T-101).

**Sub-commands:**

| Sub-command | Description |
| :--- | :--- |
| `sange gitignore current` | Show the currently active gitignore profile. |
| `sange gitignore detect` | Auto-detect profile candidates for the repo. |
| `sange gitignore list` | List discoverable gitignore profiles. |
| `sange gitignore recover` | Roll forward any crashed-in-progress swap journals. |
| `sange gitignore swap` | Atomic swap to a new gitignore composition. |


### `sange gitignore current`


Show the currently active gitignore profile.

**Options:**

| Flag | Kind | Default | Description |
| :--- | :--- | :--- | :--- |
| `--repo` | value | `.` | Repo root. Default: cwd. |


### `sange gitignore detect`


Auto-detect profile candidates for the repo.

**Options:**

| Flag | Kind | Default | Description |
| :--- | :--- | :--- | :--- |
| `--depth` | value | `1` | How deep to look for marker files. 0 = root only. |
| `--repo` | value | `.` | Repo root to inspect. Default: cwd. |


### `sange gitignore list`


List discoverable gitignore profiles.

**Options:**

| Flag | Kind | Default | Description |
| :--- | :--- | :--- | :--- |
| `--category` | value |  | Filter by category (lang / framework / infra / editor / os / _core). Empty = all. |
| `--repo` | value | `.` | Repo root for per-repo profile overrides. Default: cwd. |


### `sange gitignore recover`


Roll forward any crashed-in-progress swap journals.

**Options:**

| Flag | Kind | Default | Description |
| :--- | :--- | :--- | :--- |
| `--repo` | value | `.` | Repo root. Default: cwd. |


### `sange gitignore swap`


Atomic swap to a new gitignore composition.

**Arguments:**

| Name | Status |
| :--- | :--- |
| `profiles` | required |


**Options:**

| Flag | Kind | Default | Description |
| :--- | :--- | :--- | :--- |
| `--repo` | value | `.` | Repo root (the parent of .sange/). Default: cwd. |
| `--stage` | value | `dev` | Stage to compose for. One of: dev / prod / (any custom stage your profile declares). |


### `sange hooks`


Manage pre-commit / pre-push / etc. hooks (T-102).

**Sub-commands:**

| Sub-command | Description |
| :--- | :--- |
| `sange hooks add` | Install a named gate's scripts into .sange/hooks/. |
| `sange hooks gates` | List available named gates (gitleaks / trufflehog / make-test / etc.). |
| `sange hooks install` | Write .git/hooks/<event> shims that delegate to `sange hooks run`. |
| `sange hooks list` | Show discovered hooks (every event, or a specific one). |
| `sange hooks remove` | Remove a named gate's scripts from .sange/hooks/. |
| `sange hooks run` | Run every hook for EVENT in priority order. |
| `sange hooks status` | Per-event summary: hook count + shim install state. |
| `sange hooks uninstall` | Remove Sange-managed .git/hooks/<event> shims (foreign hooks untouched). |


### `sange hooks add`


Install a named gate's scripts into .sange/hooks/.

**Arguments:**

| Name | Status |
| :--- | :--- |
| `gate` | required |


**Options:**

| Flag | Kind | Default | Description |
| :--- | :--- | :--- | :--- |
| `--event` | value |  | Restrict to specific events (repeatable). Default: every event the gate declares. |
| `--repo` | value | `.` | Repo root. Default: cwd. |


### `sange hooks gates`


List available named gates (gitleaks / trufflehog / make-test / etc.).

**Options:**

| Flag | Kind | Default | Description |
| :--- | :--- | :--- | :--- |
| `--repo` | value | `.` | Repo root for per-repo overrides. Default: cwd. |


### `sange hooks install`


Write .git/hooks/<event> shims that delegate to `sange hooks run`.

**Options:**

| Flag | Kind | Default | Description |
| :--- | :--- | :--- | :--- |
| `--event` | value |  | Restrict to these events (repeatable). Default: every known event. |
| `--force` | flag | false | Overwrite pre-existing non-Sange hook files. Use carefully. |
| `--repo` | value | `.` | Repo root (must be a git working tree). Default: cwd. |


### `sange hooks list`


Show discovered hooks (every event, or a specific one).

**Options:**

| Flag | Kind | Default | Description |
| :--- | :--- | :--- | :--- |
| `--event` | value |  | Filter to one event. Empty = list every known event. |
| `--repo` | value | `.` | Repo root. Default: cwd. |


### `sange hooks remove`


Remove a named gate's scripts from .sange/hooks/.

**Arguments:**

| Name | Status |
| :--- | :--- |
| `gate` | required |


**Options:**

| Flag | Kind | Default | Description |
| :--- | :--- | :--- | :--- |
| `--event` | value |  | Restrict to specific events. Default: every event the gate declares. |
| `--repo` | value | `.` | Repo root. Default: cwd. |


### `sange hooks run`


Run every hook for EVENT in priority order.

**Arguments:**

| Name | Status |
| :--- | :--- |
| `event` | required |


**Options:**

| Flag | Kind | Default | Description |
| :--- | :--- | :--- | :--- |
| `--no-abort` | flag | false | Continue after FAILED hooks (collect every result). |
| `--repo` | value | `.` | Repo root (parent of .sange/). Default: cwd. |
| `--timeout` | value | `60.0` | Per-hook subprocess timeout in seconds. |


### `sange hooks status`


Per-event summary: hook count + shim install state.

**Options:**

| Flag | Kind | Default | Description |
| :--- | :--- | :--- | :--- |
| `--repo` | value | `.` | Repo root. Default: cwd. |


### `sange hooks uninstall`


Remove Sange-managed .git/hooks/<event> shims (foreign hooks untouched).

**Options:**

| Flag | Kind | Default | Description |
| :--- | :--- | :--- | :--- |
| `--event` | value |  | Restrict to these events (repeatable). Default: every known event. |
| `--repo` | value | `.` | Repo root. Default: cwd. |


### `sange init`


Bootstrap .sange/ skeleton in the target repo.

**Options:**

| Flag | Kind | Default | Description |
| :--- | :--- | :--- | :--- |
| `--auto-detect-profile` | flag | false | After init, auto-detect a gitignore profile and swap to it. Picks the highest-confidence single candidate; aborts on ties. |
| `--force` | flag | false | Overwrite existing files. Default: keep existing untouched. |
| `--gitignore`, `--no-gitignore` | flag | true | Append /Makefile + /.sange/ entries to .gitignore. |
| `--makefile`, `--no-makefile` | flag | true | Install the top-level Makefile + .sange/makefiles/ tree. |
| `--repo` | value | `.` | Target repo root. Default: the current directory. |


## Exit codes


See [`docs/reference/exit-codes.md`](exit-codes.md) for the canonical mapping. CLI commands return the codes documented there; `sange doctor` returns non-zero when any check fails.
