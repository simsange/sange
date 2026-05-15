# Quickstart

Get from zero to your first AI-drafted commit in five minutes.

Once you've finished this guide you'll know how to: install Sange,
verify it works, generate a commit message from a staged diff, and
land it through the lifecycle.

For the deep dives, follow the links to the rest of the docs as
you go.

## 1. Install

Sange targets Python 3.12+. Source-install today; `pip install sange`
lights up once the v0.1.0 PyPI publisher record activates (see
[`release.md`](release.md#step-0--pre-flight-checklist) for the
current gating status).

```bash
git clone https://github.com/simsange/sange.git
cd sange
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
```

If you want the optional dev tooling (pytest / ruff / mypy) for
hacking on Sange itself:

```bash
pip install -e ".[dev]"
```

If you want a specific AI provider's SDK (otherwise the `mock`
provider works without any extras):

```bash
pip install -e ".[ai-anthropic]"      # Anthropic Claude
pip install -e ".[ai-openai]"         # OpenAI
pip install -e ".[ai-ollama]"         # Local Ollama
pip install -e ".[ai-google]"         # Gemini
pip install -e ".[ai-bedrock]"        # AWS Bedrock
pip install -e ".[ai-all]"            # all of the above
```

Once Sange publishes, the equivalent will be:

```bash
pip install sange                     # core
pip install 'sange[ai-anthropic]'     # with one provider
docker pull ghcr.io/simsange/sange:v0.1.0   # multi-arch image
```

## 2. Verify

```bash
sange --version
# sange 0.1.0.dev0   (or 0.1.0 from a release wheel)

sange doctor
# Runs a handful of environment checks. Every line should print 'ok'
# unless your environment is genuinely missing something.

sange --help
# Lists the top-level verbs: doctor / commit / init / ai / commits
```

If `sange doctor` reports a `failed` line, follow the hint inline
or open
[`reference/exit-codes.md`](reference/exit-codes.md) to interpret
the exit code.

## 3. Bootstrap a repo

`sange init` creates the `.sange/` skeleton inside your repo where
the lifecycle state lives.

```bash
cd /path/to/your/git/repo
sange init
# Created .sange/commits/, .sange/telemetry/, .sange/.gitignore.
# Makefile-tracking check: ok (no Makefile / Makefile is gitignored as expected).
```

This is idempotent — re-running it on an already-initialized repo
exits with no changes.

## 4. Generate your first commit message

Stage some changes, then pipe the diff through `sange commit`. It
generates a Conventional Commits message and saves it as a DRAFT
under `.sange/commits/`.

```bash
git add src/foo.py docs/foo.md

# AI-driven (the happy path). Without API keys the `mock` provider
# echoes a placeholder; set --provider to a real one for production.
git diff --cached | sange commit --provider mock --model mock-1
```

Or if you'd rather write the message yourself:

```bash
sange commits new feat "add foo handler" \
    --scope foo \
    --body "Wires up the public foo API and the test stub."
# drafted #0001: feat(foo): add foo handler
```

Either way, `.sange/commits/0001-feat-foo-add-foo-handler.json` now
contains the structured record.

## 5. Land it

Three more verbs:

```bash
# Approve. (DRAFT auto-submits to PENDING_REVIEW first.)
sange commits approve 1

# Run `git commit` + `git push origin` in one step.
sange commits push 1
# pushed to origin
```

`.sange/commits/0001-...json` now records the approver, the
committed SHA, the push remote, and the timestamps for each
transition.

If you only want to land locally without pushing:

```bash
sange commits commit 1                # APPROVED → COMMITTED, no push
# (later)
sange commits push 1                  # COMMITTED → PUSHED
```

## What to read next

- **The full lifecycle reference**:
  [`tools/workflow/commit-lifecycle.md`](tools/workflow/commit-lifecycle.md)
  — every verb, the 8-state machine diagram, the reject + reopen
  flows, `--json` mode, file layout.
- **All CLI flags**:
  [`reference/cli-reference.md`](reference/cli-reference.md) —
  generated, exhaustive.
- **Configuration**:
  [`reference/config-schema.md`](reference/config-schema.md) —
  every `SangeConfig` key with its default + override precedence
  (CLI > env > TOML > defaults).
- **Cutting a release**:
  [`release.md`](release.md) — operator-facing release recipe
  with the v0.1.0 known-issues + Step 0 pre-flight checklist.
- **Architecture rationale**:
  [`.design/sange-architecture.md`](../.design/sange-architecture.md)
  — the locked deliverable, v4.4. Why each subsystem is shaped
  the way it is.

## Common gotchas

- **`sange commit` reports "diff is empty"** — `git add` your
  changes first; `sange commit` reads `git diff --cached` from
  stdin. Use `--diff <path>` to read from a file instead.
- **`mock` provider returns garbage** — the default mock echoes
  its input rather than synthesizing Conventional Commits JSON.
  For real output, pass a real `--provider` and either an env-var
  API key or `--config` pointing at a TOML with the credentials.
  See [`reference/config-schema.md`](reference/config-schema.md).
- **`sange commits push` fails with "no upstream"** — first push
  needs `-u` on the underlying `git push`. Either:
  `git push -u origin main` once manually, or wait for a future
  release where `sange commits push --set-upstream` lands.
- **`sange doctor` reports `makefile-tracked: failed`** — your
  repo has a `Makefile` that's not in `.gitignore`. Per §10.3 the
  Makefile shouldn't be tracked when Sange is managing it
  (regeneration would create churn). Either gitignore it, or run
  `sange init --no-makefile`.

## Need help?

- Issues / feature requests:
  <https://github.com/simsange/sange/issues>
- Security disclosures: `opensource@simtabi.com` (see
  [`../SECURITY.md`](../SECURITY.md))
- General OSS contact: `opensource@simtabi.com`
- Maintainer: Imani Manyara — `imani@simtabi.com`
