# `sange commits`

Sub-app for managing the commit lifecycle queue. Three commands:
`list` / `approve` / `push`.

## `sange commits list`

```bash
sange commits list [--repo <path>] [--status <state>] [--include-archived]
```

Walks `<repo>/.sange/commits/` and renders the queue. The breaking-
change marker `!` follows the counter; empty scope renders as `-`.

Filter by lifecycle state:

```bash
sange commits list --status draft
sange commits list --status approved
sange commits list --status pushed
```

Valid states: `draft`, `pending_review`, `approved`, `rejected`,
`committed`, `pushed`, `archived`, `discarded`.

`--json` mode returns:

```json
{
  "count": 2,
  "commits": [
    { "counter": 1, "status": "draft", "type": "feat", ... },
    { "counter": 2, "status": "approved", "type": "fix", ... }
  ]
}
```

## `sange commits approve <counter|id>`

```bash
sange commits approve 1 [--actor <name>] [--via <surface>] [-i]
```

Transitions DRAFT → APPROVED. The state machine actually goes
DRAFT → PENDING_REVIEW → APPROVED, but the CLI bridges through
PENDING_REVIEW transparently for solo-dev UX.

Resolve by counter (`1`, `0001`) or full commit id (uuid4 hex).

`--actor <name>` defaults to `$USER`; `--via <surface>` defaults to
`cli` and records which surface the approval came through.

`-i` / `--interactive` opens a questionary prompt:
- **Approve** — fall through to the normal approve path.
- **Reject** — prompts for a reason via `questionary.text()`; reason
  is recorded in the commit's `rejections[]` array.
- **Skip** — exits without any transition.

```bash
sange commits approve 1 -i --actor alice
```

Exit 2 if the commit is already past the APPROVED state (the engine
refuses with the state-machine's allowed-from set in the message).

## `sange commits push <counter|id>`

```bash
sange commits push 1 [--repo <path>] [--remote origin] [--branch main] \
                     [--push / --no-push] [--author-name N] [--author-email E] [--sign]
```

The **headline command**: takes an APPROVED commit, calls
`GitDriver.commit()` for the real `git commit`, records the SHA via
the lifecycle state machine, optionally pushes to the remote.

- **`--push / --no-push`** (default `--push`) — after the local
  commit lands, also `git push` to the remote.
- **`--remote <name>`** (default `origin`).
- **`--branch <name>`** (default: current).
- **`--author-name` + `--author-email`** — override the author
  identity for this commit (must be both-or-neither, else exit 2).
- **`--sign`** — GPG-sign the commit (`git commit -S`).

Output:

```
committed #0001 as 893a945d50f8 (pushed to origin)
```

`--json` mode emits the full lifecycle metadata + push result
(remote, refs_updated, was_no_op, forced).

Exit codes:

- `0` — success.
- `2` — counter not found, or commit not in APPROVED state.
- `65` — repo is not a git working tree.
- `70` — git commit / push subprocess failed.

## State machine summary

```
DRAFT ──────┬─→ PENDING_REVIEW ──┬─→ APPROVED ──→ COMMITTED ──→ PUSHED ──→ ARCHIVED
            └──────────────────┘ │              │
                       (transparent in CLI)     ├─→ DISCARDED
                                 │              └─→ (back to DRAFT via reopen)
                                 └─→ REJECTED   (terminal)

REJECTED, DISCARDED, ARCHIVED — terminal states.
```

See [Architecture: audit chain](../architecture/audit-chain.md) for
why every transition is persisted to JSON before the next state
fires.
