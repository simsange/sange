# CLI commands

Sange's CLI surface is typer-based (per ADR-019). Every command
follows the same conventions:

- `--json` makes the output machine-readable (returns a structured
  payload that downstream tooling can consume).
- `--repo <path>` overrides the default working directory.
- `--help` works on every command and sub-command.

## Top-level commands

| Command | Purpose |
|---|---|
| [`sange init`](init.md)            | Bootstrap `.sange/` skeleton + Makefile shim + .gitignore in a repo. |
| [`sange commit`](commit.md)        | Generate a Conventional Commits message from a staged diff; saves a DRAFT to `.sange/commits/`. |
| [`sange commits`](commits.md)      | Sub-app: manage the lifecycle queue (list / approve / push). |
| [`sange doctor`](doctor.md)        | Environment health checks (Python, git, config, AI providers, §10.3 Makefile-tracked). |
| [`sange ai`](ai.md)                | Provider introspection + prompt preview. |

For the **complete auto-generated reference** (every flag, every
default, every sub-command), see
[`docs/reference/cli-reference.md`](https://github.com/simsange/sange/blob/main/docs/reference/cli-reference.md)
in the main repo. It's regenerated from the live typer app on every
CLI change, so it stays in sync.

## Exit codes

Sange uses a consistent exit-code scheme per `docs/reference/exit-codes.md`:

| Code | Meaning |
|---|---|
| 0 | success |
| 1 | generic failure |
| 2 | usage error (bad args, missing required input) |
| 64 | config invalid |
| 65 | VCS not detected / git not installed |
| 70 | AI provider error |

[Full exit-code reference →](https://github.com/simsange/sange/blob/main/docs/reference/exit-codes.md)

## JSON output mode

```bash
sange --json commits list
```

returns a payload like:

```json
{
  "count": 3,
  "commits": [
    {
      "counter": 1,
      "id": "abc...",
      "status": "draft",
      "type": "feat",
      "scope": "auth",
      "subject": "add passkey support",
      "breaking_change": false,
      "branch": "main",
      "created_at": "2026-05-15T12:00:00+00:00",
      "updated_at": "2026-05-15T12:00:00+00:00",
      "committed_sha": "",
      "pushed_remote": ""
    }
  ]
}
```

Every command that emits structured data supports `--json`.
