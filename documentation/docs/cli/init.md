# `sange init`

Bootstrap the `.sange/` skeleton + Makefile shim + `.gitignore`
entries in a target repo.

```bash
sange init [--repo <path>] [--force] [--makefile / --no-makefile] [--gitignore / --no-gitignore]
```

## What it creates

1. **`<repo>/.sange/commits/`** — where `sange commit` writes DRAFT
   JSON rows.
2. **`<repo>/.sange/telemetry/`** — where the NDJSON telemetry feed
   lands.
3. **`<repo>/Makefile`** — the generated top-level shim (§10.1).
   `make help` works against it via the bundled fragments.
4. **`<repo>/.sange/makefiles/`** — the modular fragment library.
   v0.1 ships `_core/{help,env,colors}.mk` + `vcs/git.mk` +
   `lang/python.mk`. Future versions add `framework/`, `ci/`,
   `infra/`, etc.
5. **`<repo>/.gitignore`** — appends `/Makefile`, `/.sange/commits/`,
   `/.sange/telemetry/` under a sentinel header `# Sange-managed
   entries (sange init)`.

## Idempotency

Re-running `sange init` is safe. Existing files are left untouched
(action status `skipped`) unless `--force` is passed. Missing
directories are filled in (partial-skeleton repair). `.gitignore`
entries are NOT duplicated on a second run.

```bash
sange init               # first run: all created
sange init               # second run: all skipped / already-present
sange init --force       # rewrites the Makefile + fragments
```

## Output

Plain text (default):

```
initialized .sange at /Users/me/code/my-project
  [+] .sange/commits: created
  [+] .sange/telemetry: created
  [+] Makefile: created
  [+] .sange/makefiles/_core/colors.mk: created
  [+] .sange/makefiles/_core/env.mk: created
  [+] .sange/makefiles/_core/help.mk: created
  [+] .sange/makefiles/lang/python.mk: created
  [+] .sange/makefiles/vcs/git.mk: created
  [+] .gitignore: appended
```

Markers: `[+]` created, `[=]` exists / already-present, `[ ]` skipped,
`[!]` overwritten, `[~]` updated.

JSON mode emits the full action log:

```json
{
  "repo": "/Users/me/code/my-project",
  "actions": [
    {"kind": "mkdir", "path": ".sange/commits", "status": "created"},
    {"kind": "copy",  "path": "Makefile",       "status": "created"},
    {"kind": "gitignore", "path": ".gitignore", "status": "appended",
     "added_lines": ["/Makefile", "/.sange/commits/", "/.sange/telemetry/"]}
  ]
}
```

## Flag opt-outs

- **`--no-makefile`** skips the Makefile + fragments install.
  `.sange/{commits,telemetry}/` + `.gitignore` still happen.
- **`--no-gitignore`** skips the `.gitignore` update. Useful if you
  manage `.gitignore` via another tool.

## Exit codes

- `0` — success.
- `2` — `--repo <path>` is not a directory.
