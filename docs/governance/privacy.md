# Privacy & telemetry

Sange is **local-first by design**. Every byte of telemetry stays
on the developer's machine unless the operator explicitly enables
an external pipeline (v2.0+). This doc explains what Sange records,
what it deliberately doesn't, and the operator's controls.

For the canonical specification, see §40 of
[`.design/sange-architecture.md`](../../.design/sange-architecture.md).
For the related supply-chain integrity posture, see
[`../security/slsa-and-sbom.md`](../security/slsa-and-sbom.md);
for prompt-side data flows, see
[`../security/prompt-injection.md`](../security/prompt-injection.md).

## TL;DR

| Question | Answer |
| :--- | :--- |
| Does Sange send data to a server? | **No.** Not in v0.1, not in v1.0, not unless you flip a config flag in v2.0+. |
| Does Sange call AI providers? | Yes, when you ask it to (`sange commit`, `sange commits ai`). The provider you configured sees the (redacted) diff. The redaction layer is documented in [`../security/prompt-injection.md`](../security/prompt-injection.md). |
| Where do telemetry files live? | `<repo>/.sange/telemetry/events-<ISO-year>-W<NN>.ndjson`. Local files, per-repo, ISO-week sharded. |
| Can I disable telemetry entirely? | Yes — `--no-telemetry` on any CLI verb that records, or `[telemetry] enabled = false` in `.sange/config.toml`. |
| Is the local telemetry hashed? | Yes by default — `hash_sensitive_fields = true` redacts paths and identifiers before they hit disk. |

## What gets recorded

`TelemetryCollector` writes three event kinds to NDJSON files:

| Event | When | Fields recorded |
| :--- | :--- | :--- |
| `AiCallEvent` | After every `provider.complete()` round-trip in the prompt enhancer | template id + version, provider name, model name, tokens in/out, latency, finish reason, cost estimate (USD), redaction-match count by label. **No prompt text. No response text.** |
| `CommandEvent` | At the start + end of every `sange` CLI verb | command name, argv hash (not raw argv), repo-path hash (not raw path), exit code, duration. |
| `ErrorEvent` | On any unhandled exception caught by the CLI's error envelope | exception class name, stack-trace hash, exit code. **No exception message** — those can contain user data. |

The fields are deliberately narrow. Sange tracks **what kinds of
things you did**, not **what you said or wrote**.

## What's deliberately NOT recorded

These never appear in telemetry files, by design:

- **The diff text** that flows into `sange commit`. (Goes to the
  AI provider after redaction; never to disk telemetry.)
- **The commit message** the AI returned. (Lives in
  `.sange/commits/*.json` as part of the lifecycle record, not in
  telemetry.)
- **File paths in the working tree.** Hashed via SHA-256 truncated
  to 16 hex chars when `hash_sensitive_fields = true`.
- **Repo paths.** Same treatment — hashed.
- **Environment variables.**
- **API keys, tokens, secrets.** Caught by the
  [redaction layer](../security/prompt-injection.md) before any
  prompt + by the audit-chain disclosure rules before any audit
  record.
- **User identity.** No GitHub username, no email, no machine
  hostname. The `actor` field on `Approval` and `Rejection`
  records in the lifecycle is taken from `$USER` only — never
  expanded with system metadata.
- **IP addresses.** Sange never inspects networking state for
  metadata purposes.

The `hash_sensitive_fields = false` operator escape hatch turns
hashing OFF — useful for richer local analytics — but the field
inventory above doesn't change. The hash-vs-clear choice is only
about how things like file paths are represented, not about which
events fire.

## Operator controls

In `.sange/config.toml`:

```toml
[telemetry]
enabled = true                              # default in v0.1; flip false to disable
log_dir = ".sange/telemetry"                # where the NDJSON files land
hash_sensitive_fields = true                # default; richer local view with false
rotation = "weekly"                         # only "weekly" supported in v0.1
```

CLI overrides take precedence:

```bash
sange commit --no-telemetry                 # one-off opt-out
sange --json commits list                   # global flag; doesn't disable telemetry
```

Environment-variable form (per `pydantic-settings`):

```bash
SANGE_TELEMETRY__ENABLED=false sange commit
```

The double-underscore convention nests into the `telemetry`
sub-config. See
[`../reference/config-schema.md`](../reference/config-schema.md)
for every config knob.

## Inspecting your own telemetry

NDJSON files are one JSON object per line. To inspect:

```bash
# What events fired today?
cat .sange/telemetry/events-2026-W19.ndjson | jq -r '.kind'

# Which AI provider calls cost the most?
jq -s 'map(select(.kind=="ai_call")) | sort_by(.cost_estimate_usd) | reverse | .[0:10]' \
    .sange/telemetry/events-2026-W19.ndjson

# Token-usage heatmap by template:
jq -r 'select(.kind=="ai_call") | "\(.template_id)\t\(.tokens_in + .tokens_out)"' \
    .sange/telemetry/events-*.ndjson | sort | uniq -c | sort -rn
```

The data is yours. Nobody else has it.

## The audit chain (a separate surface)

Telemetry is the **metrics** surface. The **integrity** surface is
the audit chain: `<repo>/.sange/audit/<ISO-week>.jsonl`. Two
differences:

| | Telemetry | Audit chain |
| :--- | :--- | :--- |
| Purpose | "How is Sange being used?" | "Did this state change actually happen?" |
| Records | Cardinality (`ai_call`, `command`, `error`) | Every state-changing operation. |
| Tamper-evidence | None — telemetry is informational. | Hash-chained; rewriting any record breaks all later hashes. |
| Disable? | Yes (`telemetry.enabled = false`). | Yes (`audit.enabled = false`) but **strongly discouraged** for production. |
| Where? | `.sange/telemetry/` | `.sange/audit/` |

The audit chain is documented inline in
[`../security/prompt-injection.md#audit-trail`](../security/prompt-injection.md#audit-trail);
the `sange audit verify` integrity-check command lands in v0.5+ per
[`./roadmap.md`](./roadmap.md).

## External send (opt-in, v2.0+)

Per the architecture deliverable §40, an **optional** external
telemetry pipeline lands in v2.0 (Phase 3). When it ships, the
contract:

- **Default off.** Every install starts with `telemetry.external.enabled = false`.
- **Opt-in by config flag.** No flipping a default. No
  auto-enrollment.
- **Same redaction** applied to outbound data as the local
  redaction layer applies to AI prompts.
- **Receiver is configurable.** The operator chooses where data
  flows; Sange ships a reference receiver but doesn't require
  using it.
- **What's sent** is a strict subset of what's stored locally —
  the operator's allowlist, not a denylist.
- **Off-by-default in CI.** GitHub Actions runners come up with
  the flag off.

Until v2.0 actually ships this, **no external send happens**. The
config keys exist as `pydantic-settings` placeholders so the
schema is forward-compatible, but flipping them in v0.1 is a no-op.

## Compliance posture

Sange's privacy stance is built around minimization:

- **GDPR / CCPA**: no personal data is processed by Sange itself.
  AI providers you call may be subject to those regimes; that's
  your contract with the provider, not Sange's.
- **HIPAA / PCI-DSS**: Sange is not on-path for protected data
  unless you `git commit` it. The redaction layer reduces risk
  but isn't a substitute for not committing PHI / PAN in the
  first place. Use `gitleaks` / `trufflehog` upstream.
- **SOC 2 readiness**: tracked as a v3.0 exit-criterion per
  [`./roadmap.md`](./roadmap.md). Sange's audit chain is the
  foundation for a SOC 2-aligned audit log.

## Where the canonical surface lives

| Surface | File |
| :--- | :--- |
| Collector + policy | `src/sange/core/telemetry/collector.py` |
| Event schemas | `src/sange/core/telemetry/events.py` |
| Default-disable docs | `docs/release.md::Step 0` checklist (where the operator decides) |
| Canonical spec | §40 of [`../../.design/sange-architecture.md`](../../.design/sange-architecture.md) |
| Config schema | [`../reference/config-schema.md`](../reference/config-schema.md) |

## Cross-references

- [`../security/prompt-injection.md`](../security/prompt-injection.md)
  — the T-030 redaction layer that filters AI-prompt data flows
  (separate from telemetry).
- [`../security/slsa-and-sbom.md`](../security/slsa-and-sbom.md)
  — supply-chain integrity (separate surface).
- [`./roadmap.md`](./roadmap.md) — v2.0 external-telemetry
  milestone, v0.5 `sange audit verify` milestone.
- [`./adr-process.md`](./adr-process.md) — ADR-018 + ADR-031 cover
  the audit-chain + privacy-by-default decisions.
