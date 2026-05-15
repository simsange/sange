"""Redaction layer — T-030 mitigation (secret exfiltration via AI provider).

The redaction pipeline scrubs payloads before they leave the machine. Per
§6.7 + threat T-030, the prompt enhancer (not the AI provider) is the
responsibility-bearer for this; providers receive already-clean input.

Three detection layers, composed in order:

  1. **Known-pattern matchers** — regexes for well-formed secrets that
     have predictable structure (AWS access keys, GitHub PATs, OpenAI
     keys, Slack tokens, JWTs, base64-encoded private keys, etc.). The
     pattern list is conservative: false-positives cost user trust
     more than missed-secrets cost (we backstop with layers 2 + 3).

  2. **High-entropy heuristic** — strings of ≥32 chars that look
     base64/hex/random get redacted. The shannon-entropy check is a
     cheap stand-in for "this could be a secret we don't recognize".

  3. **Configurable patterns** — repo-specific regexes from
     `SangeConfig.secrets.custom_patterns`. Lets each team add
     internal-format tokens (internal vault refs, customer IDs, etc.)
     without a code change.

Replacement is deterministic: matches are replaced with `<redacted:
TYPE>` so the prompt remains coherent. The replacement does NOT reveal
the original length (that would leak entropy back to an attacker
through prompt-injection / chain-of-thought).

Redaction is **lossy by design**. A diff that gets aggressively
redacted will produce worse AI output — that is the correct tradeoff.
Users who need maximum AI quality should configure a provider that
runs locally (Ollama) and skip redaction; that decision lives in
`SangeConfig.ai.providers[*].skip_redaction` (default False).
"""

from __future__ import annotations

import math
import re
from collections.abc import Iterable
from dataclasses import dataclass, field

# --------------------------------------------------------------------------- #
# Known secret patterns
# --------------------------------------------------------------------------- #

# Each entry is (label, compiled_regex). Order matters — earlier entries
# win when ranges overlap.
_KNOWN_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("aws-access-key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("aws-secret-key", re.compile(r"\b(?<![A-Za-z0-9/+=])[A-Za-z0-9/+=]{40}(?![A-Za-z0-9/+=])\b")),
    ("github-pat", re.compile(r"\bghp_[A-Za-z0-9]{36,}\b")),
    ("github-oauth", re.compile(r"\bgho_[A-Za-z0-9]{36,}\b")),
    ("github-app", re.compile(r"\b(?:ghs|ghu)_[A-Za-z0-9]{36,}\b")),
    ("github-refresh", re.compile(r"\bghr_[A-Za-z0-9]{76,}\b")),
    ("anthropic-key", re.compile(r"\bsk-ant-[A-Za-z0-9_-]{20,}\b")),
    ("openai-key", re.compile(r"\bsk-(?!ant-)[A-Za-z0-9_-]{20,}\b")),
    ("slack-token", re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}\b")),
    ("stripe-key", re.compile(r"\b(?:sk|pk|rk)_(?:live|test)_[A-Za-z0-9]{24,}\b")),
    ("google-api-key", re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b")),
    ("jwt", re.compile(r"\beyJ[A-Za-z0-9_=-]+\.eyJ[A-Za-z0-9_=-]+\.[A-Za-z0-9_=.+/-]+\b")),
    (
        "private-key-pem",
        re.compile(
            r"-----BEGIN (?:RSA |EC |DSA |OPENSSH |ENCRYPTED |PGP )?PRIVATE KEY"
            r"(?: BLOCK)?-----[\s\S]+?-----END (?:RSA |EC |DSA |OPENSSH |ENCRYPTED |PGP )?"
            r"PRIVATE KEY(?: BLOCK)?-----",
        ),
    ),
)


# --------------------------------------------------------------------------- #
# RedactionPolicy
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class RedactionPolicy:
    """Knobs the operator can turn.

    Fields:
      * `enabled`              — master switch. When `False` the
                                  redactor returns input unchanged.
      * `entropy_min_length`   — minimum string length to consider for
                                  the entropy heuristic. Lower bound
                                  catches more, costs more false-positives.
      * `entropy_threshold`    — shannon entropy (bits) above which a
                                  long string is treated as a secret.
                                  3.5 bits/char is roughly the
                                  boundary between English prose and
                                  random/base64.
      * `custom_patterns`      — additional (label, regex) pairs.
                                  Compiled once at policy-construction.
      * `redaction_token`      — the replacement string. The `{label}`
                                  placeholder is filled with the matched
                                  pattern's label.
    """

    enabled: bool = True
    entropy_min_length: int = 32
    entropy_threshold: float = 4.0
    custom_patterns: tuple[tuple[str, str], ...] = field(default_factory=tuple)
    redaction_token: str = "<redacted:{label}>"

    def __post_init__(self) -> None:
        if self.entropy_min_length < 8:
            raise ValueError(
                "RedactionPolicy.entropy_min_length must be >= 8; "
                f"got {self.entropy_min_length}"
            )
        if not 0.0 <= self.entropy_threshold <= 8.0:
            raise ValueError(
                "RedactionPolicy.entropy_threshold must be 0..8 bits/char; "
                f"got {self.entropy_threshold}"
            )
        if "{label}" not in self.redaction_token:
            raise ValueError(
                "RedactionPolicy.redaction_token must include `{label}` placeholder"
            )
        for label, pattern in self.custom_patterns:
            if not label:
                raise ValueError("custom_patterns: label must be non-empty")
            # Compile-test the regex now so failure surfaces at policy
            # construction, not at first scrub.
            re.compile(pattern)


# --------------------------------------------------------------------------- #
# Entropy helper
# --------------------------------------------------------------------------- #


def shannon_entropy(s: str) -> float:
    """Shannon entropy (bits/char) of `s`. Empty string returns 0.0."""

    if not s:
        return 0.0
    counts: dict[str, int] = {}
    for ch in s:
        counts[ch] = counts.get(ch, 0) + 1
    total = len(s)
    entropy = 0.0
    for c in counts.values():
        p = c / total
        entropy -= p * math.log2(p)
    return entropy


# --------------------------------------------------------------------------- #
# Redactor
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class RedactionResult:
    """Output of `Redactor.scrub()`.

    Fields:
      * `text`            — the scrubbed payload.
      * `redactions`      — count of replacements made.
      * `labels_applied`  — labels that fired at least once
                             (e.g. `{"aws-access-key", "high-entropy"}`).
    """

    text: str
    redactions: int = 0
    labels_applied: frozenset[str] = field(default_factory=frozenset)


# Heuristic candidate matcher for the entropy pass: contiguous runs of
# chars that *could* be a secret (letters/digits/typical secret-set
# punctuation). Excludes whitespace + most punctuation that wouldn't
# appear inside a secret.
_ENTROPY_CANDIDATE = re.compile(r"[A-Za-z0-9+/=_-]{8,}")


class Redactor:
    """Compose-able redactor — call `scrub(text)` to redact in place."""

    def __init__(self, policy: RedactionPolicy | None = None) -> None:
        self._policy = policy or RedactionPolicy()
        # Pre-compile custom patterns once.
        self._custom: tuple[tuple[str, re.Pattern[str]], ...] = tuple(
            (label, re.compile(pat)) for label, pat in self._policy.custom_patterns
        )

    # ----- public API ----------------------------------------------- #

    def scrub(self, text: str) -> RedactionResult:
        if not self._policy.enabled or not text:
            return RedactionResult(text=text)

        labels: set[str] = set()
        count = 0
        out = text

        # Pass 1 — known patterns (highest specificity).
        for label, pattern in _KNOWN_PATTERNS:
            replacement = self._policy.redaction_token.format(label=label)
            out, n = pattern.subn(replacement, out)
            if n:
                labels.add(label)
                count += n

        # Pass 2 — custom patterns (repo-specific).
        for label, pattern in self._custom:
            replacement = self._policy.redaction_token.format(label=label)
            out, n = pattern.subn(replacement, out)
            if n:
                labels.add(label)
                count += n

        # Pass 3 — high-entropy heuristic.
        ent_replacement = self._policy.redaction_token.format(label="high-entropy")

        def _maybe_redact_entropy(match: re.Match[str]) -> str:
            nonlocal count
            candidate = match.group(0)
            if len(candidate) < self._policy.entropy_min_length:
                return candidate
            if shannon_entropy(candidate) < self._policy.entropy_threshold:
                return candidate
            # Don't re-redact something the previous passes already wrapped.
            if candidate.startswith("redacted") or "redacted:" in candidate:
                return candidate
            labels.add("high-entropy")
            count += 1
            return ent_replacement

        out = _ENTROPY_CANDIDATE.sub(_maybe_redact_entropy, out)

        return RedactionResult(
            text=out,
            redactions=count,
            labels_applied=frozenset(labels),
        )

    def scrub_many(self, texts: Iterable[str]) -> list[RedactionResult]:
        return [self.scrub(t) for t in texts]

    # ----- introspection -------------------------------------------- #

    @property
    def policy(self) -> RedactionPolicy:
        return self._policy


__all__ = [
    "RedactionPolicy",
    "RedactionResult",
    "Redactor",
    "shannon_entropy",
]
