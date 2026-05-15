# Commit lifecycle walkthrough

The `sange commits` sub-app turns every commit you make through Sange
into a durable, reviewable, auditable record under
`<repo>/.sange/commits/`. Each commit moves through a small state
machine; each transition has a CLI verb; every operation is
plain-text + `--json` friendly.

This walkthrough covers the v0.1 surface end-to-end. For the
generated, exhaustive reference (every flag, every default) see
[`../../reference/cli-reference.md`](../../reference/cli-reference.md).

## The state machine

Eight states, six forward transitions, one backward transition.

```
                ┌──────────────┐
                │   DRAFT      │◀────────┐
                └──────┬───────┘         │
              submit   │                 │
                       ▼                 │ reopen
              ┌────────────────┐         │ (any → DRAFT)
              │ PENDING_REVIEW │─reject─▶│
              └──────┬─────────┘   ┌─────┴─────┐
              approve│             │ REJECTED  │
                     ▼             └───────────┘
              ┌────────────────┐
              │   APPROVED     │
              └──────┬─────────┘
              commit │
                     ▼
              ┌────────────────┐
              │   COMMITTED    │
              └──────┬─────────┘
              push   │
                     ▼
              ┌────────────────┐
              │     PUSHED     │──(future: archive)──▶ ARCHIVED
              └────────────────┘
```

| State | Meaning |
| :--- | :--- |
| `DRAFT` | A commit message has been written but not yet submitted for review. |
| `PENDING_REVIEW` | Submitted; waiting for an approver. (`approve` auto-submits DRAFT in the solo-dev path.) |
| `APPROVED` | An approver has signed off; ready for `git commit`. |
| `REJECTED` | Terminal state. The recorded reason is the audit trail; reopen if needed. |
| `COMMITTED` | `git commit` has landed; the local SHA is recorded but nothing has been pushed. |
| `PUSHED` | `git push` to a remote has landed; the remote name + ref is recorded. |
| `ARCHIVED` | Historical. Reserved for the v0.5+ archive flow. |
| `DISCARDED` | Soft-deleted DRAFT. The JSON file is preserved for audit. |

## The CLI verbs

| Verb | Transition | Notes |
| :--- | :--- | :--- |
| `sange commits new TYPE SUBJECT` | (creates DRAFT) | Manual draft — you supply type/subject/body. |
| `sange commits ai` | (creates DRAFT) | AI-driven draft — you supply the diff; the prompt enhancer fills the rest. |
| `sange commits list` | (read-only) | Show the queue. Filter by `--status`, include archived with `--include-archived`. |
| `sange commits reopen ID` | any non-DRAFT → DRAFT | **The only backward transition.** Clears `committed_sha` + `pushed_remote`. A DRAFT input is a no-op. |
| `sange commits submit ID` | DRAFT → PENDING_REVIEW | Explicit submit. Skipped automatically by `approve`/`reject` in solo-dev mode. |
| `sange commits approve ID` | PENDING_REVIEW → APPROVED | Auto-submits DRAFT first. Records the approver + surface. |
| `sange commits reject ID --reason "..."` | PENDING_REVIEW → REJECTED | Auto-submits DRAFT first. Records the rejection reason + surface. |
| `sange commits commit ID` | APPROVED → COMMITTED | Runs `git commit`. No push. |
| `sange commits push ID` | APPROVED → COMMITTED → PUSHED | Runs `git commit` + `git push` in one step. |

Top-level convenience:

| Verb | What it does |
| :--- | :--- |
| `sange commit` | The happy-path alias for `sange commits ai` — reads a diff, calls AI, saves DRAFT. Output is the rendered Conventional Commits message; downstream verbs operate on the saved row. |

## End-to-end: manual flow

Use this when you don't want AI in the loop. Type, scope, subject,
and body are all supplied by you.

```bash
# 1. Stage some changes.
git add src/auth/login.py

# 2. Write a manual draft. `feat` is the type; the rest is options.
sange commits new feat "add login flow" \
    --scope auth \
    --body "Wires up the new auth handler." \
    --reference "#42"
# drafted #0001: feat(auth): add login flow
# saved to .sange/commits/0001-feat-auth-add-login-flow.json

# 3. Approve it. DRAFT auto-submits to PENDING_REVIEW first.
sange commits approve 1 --actor alice

# 4. Run `git commit`, mark COMMITTED locally.
sange commits commit 1
# committed #0001 as 7c1d8a3 (local only — run `sange commits push` to publish)

# 5. Push to origin.
sange commits push 1
# pushed to origin
```

After step 5, `.sange/commits/0001-feat-auth-add-login-flow.json`
contains the full provenance: the original draft, the approver,
the timestamps, the committed SHA, the push remote, the full
rendered commit message.

## End-to-end: AI flow

Use this when you want the prompt enhancer to author the message
from the staged diff.

```bash
# 1. Stage changes.
git add src/auth/

# 2. Generate a draft via AI. Reads the diff from stdin.
git diff --cached | sange commits ai \
    --provider anthropic --model claude-sonnet-4-6
# feat(auth): add login flow
#
# Wires up the new auth handler and the JWT round-trip; the
# token cache is now per-user instead of per-session.
# saved DRAFT #0002 to .sange/commits/0002-feat-auth-add-login-flow.json

# 3. Review the rendered draft, then approve.
sange commits approve 2 --actor alice

# 4. Commit + push in one step.
sange commits push 2
```

The `--provider` and `--model` flags accept any registered AI
adapter — `mock` / `anthropic` / `openai` / `ollama` / `gemini` /
`bedrock`. The optional extras (`pip install 'sange[anthropic]'`,
`pip install 'sange[openai]'`, etc.) wire the per-provider SDKs.

The happy-path alias `sange commit` does the same thing as
`sange commits ai`; pick whichever surface fits your muscle memory.

## Reject flow

```bash
# Draft something you don't actually want to ship.
sange commits new fix "patch the wrong thing" --scope cli

# Reject with a non-empty reason. DRAFT auto-submits to
# PENDING_REVIEW first; the rejection records who said no
# and why.
sange commits reject 3 \
    --reason "wrong fix — root cause is in the caller, not here" \
    --actor alice

# Status check.
sange commits list
#     #  STATUS         TYPE      SCOPE          SUBJECT
# -----  -------------- --------- -------------- ----------------------------------------
#    3   rejected       fix       cli            patch the wrong thing
```

`REJECTED` is terminal in the forward direction, but **`reopen`
can bring it back to DRAFT**:

```bash
sange commits reopen 3
# reopened #0003: rejected → draft

# Now the draft is editable again. Update it manually:
# (rewrite the body / scope / subject via your editor, or just
# delete + re-create with `sange commits new`).
sange commits approve 3
sange commits push 3
```

`reopen` works from any state — `PENDING_REVIEW`, `APPROVED`,
`REJECTED`, `COMMITTED`, `PUSHED`. When called on a `COMMITTED`
or `PUSHED` record, the engine clears `committed_sha` +
`pushed_remote` so the next forward path starts fresh; the
cross-field invariants in the schema enforce that.

## JSON mode

Every verb honors the global `--json` flag.

```bash
sange --json commits new feat "add login" --scope auth
```

Emits something like:

```json
{
  "counter": 1,
  "id": "d435386b14534316a4c400c845e575ca",
  "status": "draft",
  "path": "/path/to/repo/.sange/commits/0001-feat-auth-add-login.json",
  "type": "feat",
  "scope": "auth",
  "subject": "add login",
  "branch": "main",
  "breaking_change": false
}
```

The JSON shape is stable across verbs in the sense that every
payload includes `counter` / `id` / `status` / `path`; per-verb
fields layer on top. The full schema lives at
[`../../reference/cli-reference.md`](../../reference/cli-reference.md).

## File layout

Each commit is one JSON file under `<repo>/.sange/commits/`:

```
<repo>/
├── .sange/
│   └── commits/
│       ├── 0001-feat-auth-add-login.json
│       ├── 0002-fix-core-tighten.json
│       ├── 0003-docs-update-readme.json
│       └── .counter                  ← monotonic counter (crash-safe)
└── ...
```

Filenames follow `<counter>-<type>-<scope>-<slugified-subject>.json`.
The counter is allocated atomically and survives `kill -9` mid-write
via a filesystem-rescan fallback (see ADR-024). The file content is
written via tmp + fsync + rename so a partial write is never visible.

Once a commit reaches `PUSHED`, the changelog generator
([T-G-013](../../reference/cli-reference.md)) picks it up on the
next run and appends it to `docs/CHANGELOG.md` under the next
release header.

## Solo-dev shortcuts

The CLI is granular by design, but the common path is short:

```bash
# Generate + approve + push in three commands.
git diff --cached | sange commits ai
sange commits approve 1
sange commits push 1
```

Or even shorter using the top-level alias:

```bash
git diff --cached | sange commit          # generates DRAFT #N
sange commits approve N
sange commits push N
```

Multi-user workflows use the full sequence — `new`/`ai` → `submit`
→ separate reviewer runs `approve`/`reject` → author runs
`commit`/`push`.

## What's not in v0.1

These ship in later releases:

- **Interactive TUI** for browsing the queue (v0.5+).
- **Archive verb** + automatic archival policy (v0.5+). The
  `LifecycleEngine.archive()` method exists; the CLI surface lands
  with the §6.8.5 archive policy.
- **`sange commits regenerate <id>`** to re-run AI on an existing
  draft with a different provider/model (v0.5+).
- **Web UI** lifecycle view at `https://sange.test` (v1.0).
- **Multi-user approver workflows** with role checks (v0.5+ via the
  `--actor` field; full RBAC at v1.0).

## Related references

- [`../../reference/cli-reference.md`](../../reference/cli-reference.md)
  — generated, exhaustive flag/option reference for every verb.
- [`../../reference/config-schema.md`](../../reference/config-schema.md)
  — `SangeConfig` keys, including the `[commits]` section.
- [`../../reference/exit-codes.md`](../../reference/exit-codes.md)
  — exit-code dictionary for the CLI.
- [`../../reference/appendix-g-commit-templates.md`](../../reference/appendix-g-commit-templates.md)
  — the 50+ commit-message presets the enhancer draws on.
- [`../../release.md`](../../release.md) — release pipeline; cuts
  read `docs/CHANGELOG.md` which the lifecycle feeds.
- [`.design/sange-architecture.md`](../../../.design/sange-architecture.md)
  — §6.8 (canonical lifecycle definition).
