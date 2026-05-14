# `sange commit`

Generate a Conventional Commits message from a staged diff. Saves a
DRAFT row to `<repo>/.sange/commits/0001-<type>-<scope>-<slug>.json`
unless `--no-save` is passed.

## Synopsis

```bash
git diff --staged | sange commit [OPTIONS]
sange commit --diff <path> [OPTIONS]
```

## Common usage

```bash
# The default flow — read diff from stdin, use mock provider
git diff --staged | sange commit --provider mock

# Real AI provider (requires ANTHROPIC_API_KEY)
git diff --staged | sange commit --provider anthropic

# Read from a file
sange commit --diff /tmp/staged.diff --provider openai

# Skip the DRAFT-row save (one-shot, no lifecycle persistence)
git diff --staged | sange commit --no-save

# Skip telemetry recording for this invocation
git diff --staged | sange commit --no-telemetry

# Suggest a scope to bias the model
git diff --staged | sange commit --scope auth
```

## Key flags

- **`--diff <path>`** — read diff from a file instead of stdin.
- **`--repo <path>`** — repo root (default: cwd). DRAFT rows land in
  `<repo>/.sange/commits/`.
- **`--provider <name>`** — `mock` / `anthropic` / `openai` / `ollama` /
  `gemini` / `bedrock`. Each provider needs the matching SDK extra
  installed (`pip install "sange[ai-anthropic]"`, etc.).
- **`--model <id>`** — model identifier passed to the provider.
- **`--scope <scope>`** — optional scope hint biasing the generated
  message.
- **`--save / --no-save`** — write the DRAFT JSON row (default: save).
- **`--no-telemetry`** — disable local NDJSON telemetry recording for
  this call.
- **`--telemetry-dir <path>`** — override the telemetry directory.

## Output

Plain text mode (default):

```
feat(auth): add passkey support

WebAuthn-backed passkey authentication helpers.

saved DRAFT #0001 to .sange/commits/0001-feat-auth-add-passkey-support.json
recorded to .sange/telemetry/events-2026-W20.ndjson
```

`--json` mode emits:

```json
{
  "type": "feat",
  "scope": "auth",
  "subject": "add passkey support",
  "body": "WebAuthn-backed passkey authentication helpers.",
  "breaking_change": false,
  "audit_id": "commit-message@1.0.0",
  "draft_counter": 1,
  "draft_path": "/path/to/.sange/commits/0001-feat-auth-add-passkey-support.json"
}
```

## Behaviour

1. The diff is **redacted** by the T-030 layer before any payload
   leaves your machine. AWS keys, GitHub PATs, OpenAI/Anthropic
   keys, JWTs, PEM private keys, and high-entropy strings are
   replaced with `<redacted:LABEL>` markers.
2. The redacted diff + repo context (branch, recent commits, files
   changed) is rendered into a provider-appropriate prompt format
   (XML for Anthropic, JSON for OpenAI, markdown for the rest).
3. The provider's response is JSON-schema-validated; one retry on
   failure, then exit 70 if still malformed.
4. The validated `CommitMessageResult` is converted to a DRAFT-status
   `CommitJSON` and saved (counter is monotonic per-repo).
5. An `AiCallEvent` is recorded to the telemetry NDJSON with the
   provider/model/tokens/cost/redaction-count/retries/latency.

## Exit codes

- `0` — success (message printed; DRAFT saved if `--save`).
- `2` — usage error (empty diff, missing file, bad flag).
- `70` — AI provider error (network, schema validation failure).
