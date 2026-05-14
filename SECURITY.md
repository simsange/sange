# Security Policy

## Supported versions

| Version | Status | Security fixes |
|---|---|---|
| `0.1.x` (MVP, in progress) | Pre-release | Best effort during build phase |
| `< 0.1` | Unreleased | n/a |

Once `v1.0.0` ships, the support matrix in this section is regenerated from the
release engineering policy in [`docs/release.md`](docs/release.md).

## Reporting a vulnerability

**Email:** `opensource@simtabi.com`

- Encrypt with our PGP key when the vulnerability is exploitable in the wild.
  The current PGP key fingerprint will be published at
  <https://opensource.simtabi.com/security> once the v0.1 release is cut; until
  then, plaintext email to the address above is accepted.
- Include: affected version (or git SHA), reproduction steps, observed impact,
  any proof-of-concept code, and your preferred handle for disclosure credit.
- **Do not open a public GitHub issue** for security reports.

## What we will do

1. Acknowledge receipt within **3 business days**.
2. Confirm or refute the report within **10 business days**, including a CVSS
   score and a remediation plan.
3. Coordinate disclosure with you on a timeline appropriate to severity —
   typically ≤ 90 days for critical issues, longer for low-severity reports
   where users need lead time.
4. Credit the reporter in the security advisory unless anonymity is requested.

## Scope

In scope:

- The `sange` Python package and `sanged` daemon.
- The Laravel web UI under `web/`.
- The CLI / TUI surface and JSON-RPC protocol.
- The premade kit fragments under `templates/` (the signed manifest at
  `templates/MANIFEST.toml.sig` is the trust root).
- The history-purge subsystem (`sange purge`, §6.11 of
  `.design/sange-architecture-prompt.md`).
- Plugin loader and signature verification.

Out of scope:

- Issues in upstream dependencies — please report those upstream and CC us if
  Sange's exposure is the vector.
- Social-engineering attacks against humans operating Sange.
- Denial-of-service via flooding a user's own local daemon — Sange is
  local-first; resource quotas are the operator's responsibility.

## Hash-chained audit and prompt-injection defense

Sange ships defense-in-depth controls documented in §11 of the architecture
prompt:

- Hash-chained `.sange/audit/` JSONL (per-repo + global mirror).
- Prompt-injection defense (delimiter discipline + content firewall + redaction
  layer) on every AI provider call (§6.7).
- Signed plugins (ADR-020) and signed kit manifest verification.
- STRIDE threat model: `docs/security/stride.md` (emitted by T-G-012).

If you find a way around any of these, that's a security report.

## Disclosure policy

We follow coordinated disclosure. Reports that comply with this policy will not
result in legal action under any anti-tampering or anti-hacking statute we have
discretion over. We will not pursue researchers who:

- Make a good-faith effort to avoid privacy violations, destruction of data,
  and interruption of service.
- Provide a reasonable time to remediate before public disclosure.
- Do not exploit the vulnerability beyond what is necessary to confirm it.

---

*Disclosure inbox: `opensource@simtabi.com`. Maintainer: Imani Manyara —
`imani@simtabi.com`. Project: <https://opensource.simtabi.com/products/sange>.*
