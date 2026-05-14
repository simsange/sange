# Getting started

This walkthrough takes you from zero to a pushed Conventional Commits
message in under five minutes. We'll use a tmp directory + a bare
git remote so nothing here touches your real repos.

## Prerequisites

- Python ≥ 3.10 (the project pins ≥ 3.12 long-term; older versions
  work for the runtime).
- `git` on PATH.
- An API key for one of: Anthropic, OpenAI, or a running Ollama daemon.
  (For this walkthrough we'll use the `mock` provider so no key is needed.)

## 1. Install

```bash
pip install sange
sange --version
# expect: sange 0.1.0
```

If you want the dev tooling (pytest, ruff, mypy):

```bash
pip install "sange[dev]"
```

## 2. Set up a test repo

```bash
mkdir /tmp/sange-walkthrough
cd /tmp/sange-walkthrough

# Make it a git repo
git init -q -b main
git config user.email "you@example.com"
git config user.name "Your Name"

# Bootstrap the Sange skeleton
sange init
```

`sange init` creates `.sange/{commits,telemetry}/`, copies the
modular Makefile shim + fragments to `.sange/makefiles/`, and adds
`/Makefile` + `/.sange/commits/` + `/.sange/telemetry/` to your
`.gitignore`.

## 3. Make your first change

```bash
echo "# Walkthrough" > README.md
git add README.md
```

## 4. Generate a commit message

```bash
git diff --staged | sange commit --provider mock
```

You should see something like:

```
docs(readme): add walkthrough header

saved DRAFT #0001 to /tmp/sange-walkthrough/.sange/commits/0001-docs-readme-add-walkthrough-header.json
recorded to /tmp/sange-walkthrough/.sange/telemetry/events-2026-W20.ndjson
```

The DRAFT JSON file is the structured record of this commit:

```bash
cat .sange/commits/0001-*.json | jq .
```

You'll see `status: "draft"`, the parsed Conventional Commits fields,
the AI provenance, and timestamps.

!!! note "Why mock provider?"
    `--provider mock` returns a deterministic stub response — no API
    key, no tokens burned. Once you've confirmed the flow works,
    switch to `--provider anthropic` (with `ANTHROPIC_API_KEY` set)
    or `--provider openai` for a real AI-generated message.

## 5. Review + approve

```bash
sange commits list
```

shows your queue. Now approve:

```bash
sange commits approve 1
# Or interactively:
sange commits approve 1 -i
```

The interactive mode renders the message + prompts approve / reject /
skip. Reject asks for a reason; the reason is stored in the commit
JSON's `rejections[]` array for audit.

## 6. Commit + push

Run the local commit:

```bash
sange commits push 1 --no-push
```

`--no-push` runs `git commit` locally without pushing. The lifecycle
moves DRAFT → APPROVED → COMMITTED. Verify:

```bash
git log --oneline -1
sange commits list
```

The commit's status is now `committed`. To actually push:

```bash
# Add a remote first
git init --bare /tmp/sange-remote.git
git remote add origin /tmp/sange-remote.git
git push -u origin main

# Land the next change with full push
echo "more content" >> README.md
git add README.md
git diff --staged | sange commit --provider mock
sange commits approve 2
sange commits push 2 --remote origin --branch main
```

The lifecycle is now `pushed`; the bare remote has the commit.

## 7. Verify with doctor

```bash
sange doctor
```

You should see all checks passing — Python version, git
availability, config validity, AI provider status, and the §10.3
"Makefile-tracked" check (which passes because `sange init` added
`/Makefile` to your `.gitignore`).

## What just happened

You drove this flow end-to-end:

```
diff → CLI → enhancer (T-030 redaction) → AI provider
     → CommitMessageResult → DRAFT JSON in .sange/commits/
     → approve → APPROVED → push → real git commit + push
     → COMMITTED + PUSHED
     → AuditRecord → telemetry NDJSON
```

Every step persisted to disk; every AI call's provenance is in the
telemetry feed; T-030 redaction ran before any payload could leave
your machine.

## Where next

- [Browse the CLI commands](cli/index.md)
- [How the audit chain works](architecture/audit-chain.md)
- [What the redaction layer scrubs](architecture/redaction.md)
- [GitHub source →](https://github.com/sangedev/sange)
