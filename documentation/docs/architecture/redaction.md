# T-030 redaction layer

> **Threat T-030** (per `docs/security/stride.md`): _Secret
> exfiltration via AI provider — diffs containing secrets, API keys,
> or PII are sent to an external AI provider as part of a
> commit-message generation request._
>
> **Blast radius:** Critical.

The `Redactor` class is the Critical-blast-radius mitigation for
this threat. It runs **before** every AI provider call, transforming
the staged diff in-memory so that recognized secret patterns are
replaced with `<redacted:LABEL>` markers before any payload could
leave the machine.

## Three detection layers

The redactor runs three passes in order, accumulating replacements:

### 1. Known-pattern matchers (13 regexes)

```
Label             Pattern (approximate)
----------------  ---------------------------------------------------------
aws-access-key    \bAKIA[0-9A-Z]{16}\b
aws-secret-key    \b(?<![A-Za-z0-9/+=])[A-Za-z0-9/+=]{40}(?![A-Za-z0-9/+=])\b
github-pat        \bghp_[A-Za-z0-9]{36,}\b
github-oauth      \bgho_[A-Za-z0-9]{36,}\b
github-app        \b(?:ghs|ghu)_[A-Za-z0-9]{36,}\b
github-refresh    \bghr_[A-Za-z0-9]{76,}\b
anthropic-key     \bsk-ant-[A-Za-z0-9_-]{20,}\b
openai-key        \bsk-(?!ant-)[A-Za-z0-9_-]{20,}\b      (anthropic-aware)
slack-token       \bxox[abprs]-[A-Za-z0-9-]{10,}\b
stripe-key        \b(?:sk|pk|rk)_(?:live|test)_[A-Za-z0-9]{24,}\b
google-api-key    \bAIza[0-9A-Za-z_-]{35}\b
jwt               \beyJ[A-Za-z0-9_=-]+\.eyJ[A-Za-z0-9_=-]+\.[A-Za-z0-9_=.+/-]+\b
private-key-pem   -----BEGIN ... PRIVATE KEY ... -----END ... PRIVATE KEY-----
```

### 2. High-entropy heuristic

Strings of ≥ 32 characters matching `[A-Za-z0-9+/=_-]` with Shannon
entropy ≥ 4.0 bits/char are redacted as `<redacted:high-entropy>`.

The 4.0-bits/char threshold sits roughly between English prose
(~3.5 bits/char) and random/base64 (~5+ bits/char). The minimum
length (32) closes the false-positive surface for short identifiers
that happen to look random.

### 3. Operator-configurable custom patterns

```python
from sange.core.enhancer import RedactionPolicy, Redactor

policy = RedactionPolicy(
    custom_patterns=(
        ("internal-vault-ref", r"vault://[a-z0-9-]+"),
        ("customer-id",        r"\bCUST-[A-Z0-9]{8,}\b"),
    ),
)
redactor = Redactor(policy)
```

Custom patterns run AFTER the known-pattern pass, so an
`internal-vault-ref` that overlaps with a built-in label keeps the
built-in label (which is more specific).

## Configuration knobs

`RedactionPolicy` (frozen dataclass):

| Field | Default | Description |
|---|---|---|
| `enabled` | `True` | Master switch. `False` → `scrub()` returns input unchanged. |
| `entropy_min_length` | `32` | Min string length for the entropy pass. |
| `entropy_threshold` | `4.0` | Shannon entropy (bits/char) above which a long string is treated as a secret. |
| `custom_patterns` | `()` | Additional `(label, regex)` pairs. |
| `redaction_token` | `"<redacted:{label}>"` | Replacement template. The `{label}` placeholder is filled with the matched pattern's label. |

## What the redactor returns

```python
result = redactor.scrub(diff_text)
result.text             # scrubbed payload
result.redactions       # count of replacements
result.labels_applied   # frozenset of labels that fired
```

The `redaction_count` + `redaction_labels` propagate into the
`AuditRecord` → `AiCallEvent` → telemetry NDJSON, so you can audit
which secret types were present in diffs over time.

## What the redactor does NOT do

- **Does not validate that secrets are real.** A 40-char hex
  string that looks like an AWS secret key is redacted regardless
  of whether it's actually live. False-positives cost an AI
  response, not a leaked credential.
- **Does not redact context.** The diff line `+ password = "..."`
  has the value redacted but the variable name (`password`) stays
  visible to the model. That's intentional — the model needs
  enough context to write a meaningful commit message.
- **Does not redact source files outside the diff.** Only the diff
  text passed to `scrub()` is scrubbed. If your build pipeline
  embeds secrets into compiled artifacts, that's a separate problem
  (probably solved by the §6.10 container secret model).

## Disabling redaction

For local-only providers (Ollama on `localhost`), you can disable
redaction to get higher-quality AI output on sensitive diffs:

```python
from sange.core.enhancer import RedactionPolicy, Redactor

policy = RedactionPolicy(enabled=False)
redactor = Redactor(policy)
```

**Don't disable redaction when the provider is anything other than
a local Ollama / on-prem deployment.** The threat model exists
because external API calls leak data — disabling for cloud providers
is a foot-gun.

## Extending the pattern set

The known-pattern set lives in
[`src/sange/core/enhancer/redaction.py`](https://github.com/sangedev/sange/blob/main/src/sange/core/enhancer/redaction.py).
Pull requests adding new patterns should:

1. Cite a public reference for the pattern (vendor docs, gitleaks/
   trufflehog rule, etc.).
2. Include a unit test in
   [`tests/unit/test_enhancer_redaction.py`](https://github.com/sangedev/sange/blob/main/tests/unit/test_enhancer_redaction.py).
3. Test for false-positive shape too (the pattern shouldn't match
   common non-secrets that look similar).
