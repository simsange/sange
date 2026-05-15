# Audit chain

Every Sange operation that touches an AI provider OR mutates the
commit lifecycle is traceable end-to-end. The chain runs:

```
diff (stdin)
  ↓
sange.cli.commit_command
  ↓
CommitMessageRequest (frozen dataclass; validated)
  ↓
generate_commit_message()
  ↓
PromptEnhancer.enhance()
  ↓
  Redactor.scrub()                  ← T-030 mitigation
  ↓
  TemplateRegistry.render()
  ↓
  for_provider(name).format()       ← XML / JSON / Markdown
  ↓
  AIProvider.complete()              ← real provider call
  ↓
  _validate_against_schema()        ← top-level type + required-keys check
  ↓
CommitMessageResult (typed: type, scope, subject, body, breaking_change)
  ↓
AuditRecord (template_id, version, provider, model, redaction_count,
              redaction_labels, usage, retries)
  ↓
CommitJSON (DRAFT status, 8-state machine)
  ↓
CommitsDirectory.save() → .sange/commits/0001-<type>-<scope>-<slug>.json
  ↓
TelemetryCollector.from_audit() → AiCallEvent
  ↓
.sange/telemetry/events-YYYY-Www.ndjson (atomic append, weekly rotation)
```

## Why each link matters

| Link | What it adds |
|---|---|
| `CommitMessageRequest` | Construct-time validation rejects empty diffs + invalid input before any AI call. |
| `Redactor.scrub()` | T-030 mitigation: 13 known-pattern matchers + shannon-entropy heuristic + operator-configurable custom patterns. Fires before any payload leaves your machine. |
| `for_provider().format()` | Provider-appropriate prompt format (Anthropic XML, OpenAI JSON-mode, others markdown) — quality boost without changing the engine. |
| Schema validation | Catches malformed AI responses; one retry, then raises `EnhancerValidationError`. |
| `AuditRecord` | Carries provenance: template+version, provider+model, redaction stats, retry count, token+cost accounting. |
| `CommitJSON` | Persisted source of truth. State transitions go through `LifecycleEngine`; the model has cross-field validators (`committed_sha` populated iff `status ∈ {COMMITTED, PUSHED, ARCHIVED}`, etc.). |
| `AiCallEvent` → NDJSON | Audit feed. Sensitive fields (repo paths, branch names) are hashed before storage. Off-machine send is OFF by default. |

## What the audit trail catches

- **Prompt-injection forensics.** When a generated message references
  something it shouldn't have, `sange ai preview` reproduces the exact
  prompt that was sent (it's deterministic from the inputs).
- **Cost overruns.** `summary_by_provider()` aggregates token + cost
  totals from the NDJSON feed. `sange telemetry view` (v0.5+) builds
  on this.
- **Schema regressions.** Every retry is recorded; a spike in retries
  for a specific template signals the prompt has drifted from what
  the model produces.
- **Redaction misses.** `redaction_labels` in the AuditRecord tells
  you which patterns fired; a zero-label record on a diff that
  contained secrets is a bug to fix in the regex set.

## Off-by-default external send

Per [§12.1](https://github.com/simsange/sange/blob/main/.design/sange-architecture-prompt.md)
and ADR-008, **nothing leaves your machine in v0.1**. The NDJSON
feed is local-only. v2+ may add opt-in aggregated/anonymized send
to a Sange-operated endpoint for product improvement; that lands as
a separate ADR and remains off-by-default.
