# `sange doctor`

Environment health checks. Run after install to confirm the toolchain
is sane.

```bash
sange doctor
sange --json doctor    # machine-readable
```

Five checks today:

| Check | Pass condition |
|---|---|
| `python` | Python ≥ 3.10 |
| `git` | `git --version` runs cleanly |
| `config` | `SangeConfig` default-minimal validates |
| `ai-providers` | `mock` provider installed (always); other providers reported informationally |
| `makefile-tracked` | Per §10.3 — the generated `Makefile` is NOT tracked in git (it must be gitignored) |

## Exit codes

- `0` — all checks passed.
- `1` — one or more checks failed; details on stderr.

## Output

Plain text:

```
[OK]   python: Python 3.12.4
[OK]   git: git version 2.43.0
[OK]   config: SangeConfig default-minimal validates
[OK]   ai-providers: mock=installed, anthropic=missing-sdk (install sange[ai-anthropic]), openai=installed, ollama=missing-sdk (install sange[ai-ollama])
[OK]   makefile-tracked: Makefile present + correctly gitignored

All checks passed.
```

JSON mode emits:

```json
{
  "ok": true,
  "checks": [
    {
      "name": "python",
      "ok": true,
      "message": "Python 3.12.4",
      "details": {"major": 3, "minor": 12, "patch": 4}
    },
    {
      "name": "ai-providers",
      "ok": true,
      "message": "mock=installed, anthropic=missing-sdk ...",
      "details": {
        "mock": "installed",
        "anthropic": "missing-sdk (install sange[ai-anthropic])"
      }
    }
  ],
  "platform": "macOS-14.5-arm64-arm-64bit"
}
```

## When the Makefile-tracked check fires

If your `Makefile` IS tracked in git, doctor refuses to pass and
prints:

```
[FAIL] makefile-tracked: Makefile is tracked in git — per §10.3 the
generated Makefile must be gitignored. Recovery: `sange fix-makefile-
tracked` (or manually: `git rm --cached Makefile && echo '/Makefile'
>> .gitignore`).
```

The fix is to untrack the Makefile and add it to `.gitignore`. The
generated Makefile is meant to be **derived** from the user's
`.sange/makefiles/` configuration (per §10.1), not a hand-edited
artifact under VCS.
