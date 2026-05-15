---
generated_by: hand-authored (detail file backfilled for an accepted ADR)
generator_version: n/a
generated_at: 2026-05-16T04:00:00Z
manual_edits_allowed: true
---
# ADR-0007: License — Apache 2.0, © Simtabi LLC

**Status:** Accepted
**Date:** 2026-05-14 (concurrent with the v0.1.0 tag)

## Context

Sange is a polyglot VCS automation toolkit aimed at seven personas
(non-developer founders, CTOs, junior engineers, senior staff engineers,
DevOps/SRE, OSS maintainers, cyber-security reviewers — see §3 of the
canonical architecture deliverable). The licensing choice has to serve
all seven simultaneously:

- **Plugin authors** building on Sange's plugin system (T-200+) need a
  license that lets them ship plugins (commercial or OSS) without
  surprises about patent retaliation.
- **Enterprise adopters** evaluating Sange for a multi-tenant deployment
  need an explicit patent grant — many corporate legal teams won't
  approve a permissive license without one.
- **OSS maintainers** who fork or vendor Sange need to be able to ship
  derivative work without re-licensing.
- **The original copyright holder** (Simtabi LLC) needs to retain the
  ability to dual-license, sub-license, or move to a different model
  in the future without re-collecting CLAs.

The decision sits inside a small set of candidate licenses (MIT,
BSD-2/3, Apache 2.0, MPL 2.0, GPL/AGPL/LGPL family, source-available
like BSL or PolyForm). Once chosen, the choice propagates to every
file in the repo via `LICENSE`, every package metadata file
(`pyproject.toml::project.license`, `package.json::license`,
`composer.json::license`), every signed release artifact, and every
plugin marketplace listing.

## Decision

**Apache License, Version 2.0, with `Copyright (c) 2026 Simtabi LLC`
in the `LICENSE` file at repo root.** SPDX identifier `Apache-2.0` in
all package metadata.

Concretely:

- `LICENSE` at repo root contains the full Apache 2.0 text verbatim
  (downloaded from apache.org; never paraphrased).
- `NOTICE` at repo root identifies Simtabi LLC as the original
  copyright holder.
- `pyproject.toml::project.license = "Apache-2.0"` and
  `[project.classifiers]` includes
  `"License :: OSI Approved :: Apache Software License"`.
- Every source file gets a one-line SPDX header (`# SPDX-License-Identifier: Apache-2.0`)
  where the language convention supports it.

## Alternatives Rejected

- **MIT** — the natural "as permissive as possible" choice and the
  default for many OSS Python projects. Rejected because MIT has no
  explicit patent grant. A patent troll could ship a license-compliant
  fork while reserving the right to sue users for patent infringement
  on the original code. Apache 2.0's §3 ("Grant of Patent License")
  closes that gap explicitly. The bar for inclusion in many corporate
  vendor allowlists is "Apache 2.0 or MIT-with-patent-grant"; Apache
  2.0 wins on legal team approval velocity alone.

- **BSD-2-Clause / BSD-3-Clause** — same gap as MIT (no patent grant).
  Same rejection.

- **MPL 2.0** — file-level copyleft. Attractive because it lets us
  keep proprietary plugins coupled with OSS Sange. Rejected because
  the file-level granularity introduces compliance friction every
  time a contributor merges code across module boundaries. Apache 2.0
  + a separate proprietary plugin SDK achieves the same outcome with
  less day-to-day overhead.

- **GPL v3 / AGPL v3** — strong copyleft. Rejected for two reasons:
  (a) the plugin ecosystem (T-200+ MCP marketplace) requires
  commercial-plugin compatibility; AGPL specifically would force
  every plugin author to AGPL their plugin too, which kills the
  marketplace before it starts. (b) AGPL's network-use clause
  surfaces unpredictable obligations for self-hosters running Sange's
  Web UI behind a reverse proxy (Cloudflare Tunnel, Tailscale, VPS
  topologies). The §8.5 remote-access patterns become "do you have
  to publish your modifications to anonymous internet users who can
  reach the proxy?" — a question Apache 2.0 makes moot.

- **LGPL v3** — weak copyleft on a per-library basis. Rejected because
  Sange isn't designed as a single linkable library; it's a daemon
  (`sanged`), a CLI (`sange`), and a web UI (Laravel) communicating
  over JSON-RPC. LGPL's "use as library without copyleft" semantics
  don't map cleanly onto this shape.

- **BSL (Business Source License) / PolyForm** — source-available with
  delayed open-sourcing (BSL converts to GPL/MIT after N years).
  Rejected because Sange's funding model doesn't depend on the
  source-available restriction; Simtabi LLC's value capture is around
  hosting, support, and the Sange Cloud variant (v3.0+), all of which
  work fine under a permissive license.

- **Custom dual-license** (Apache 2.0 + commercial) — viable, and
  many infra projects do this. Rejected for v0.1 because dual-licensing
  requires CLA infrastructure (Contributor License Agreements) which
  is a significant onboarding-friction surface. The architecture
  doesn't preclude moving to a dual-license later: every contributor's
  copyright assignment can be re-collected if the project value
  becomes large enough to warrant the friction.

## Consequences

### Positive

- **Patent grant** in §3 protects users + downstream forks from patent
  retaliation by upstream contributors.
- **Enterprise legal teams** can approve Apache 2.0 without escalation
  (most maintain a "pre-approved" list; Apache 2.0 is always on it).
- **Plugin ecosystem** (T-200+) can host commercial plugins alongside
  OSS plugins without sub-license friction.
- **OpenSSF Scorecard** (the v1.0 ≥ 8.0 exit-criterion in
  [`../governance/roadmap.md`](../governance/roadmap.md)) rewards
  Apache 2.0 over the no-patent-grant permissive licenses.
- **Forks for downstream commercial deployment** are unrestricted —
  Simtabi LLC reserves nothing operationally important via license.

### Negative

- **No copyleft means proprietary forks are allowed.** A vendor can
  take Sange, rebrand it, and ship a closed-source competitor. This is
  a deliberate trade-off; the moat is Simtabi LLC's velocity + the
  ecosystem around the original, not the license.
- **Apache 2.0's notice requirement** (every distribution must include
  the LICENSE + NOTICE files) is more administrative overhead than MIT.
  The SPDX header convention + the existing `NOTICE` file at repo
  root mitigate this.
- **`Apache-2.0` is not GPL-compatible.** A future need to integrate
  GPL-licensed code (e.g. wrapping a GPL'd VCS adapter via in-process
  linking rather than subprocess) would require an exception or a
  re-license. Subprocess boundaries (which is how Sange wraps `git` /
  `svn` / etc.) are unaffected.

### Neutral

- **The patent grant is automatically revoked** for parties that sue
  upstream contributors for patent infringement on the code. This is
  not a problem in practice but worth knowing if litigation ever
  arises.
- **Copyright assignment** stays with each contributor (no CLA in
  v0.1). If Simtabi LLC ever wants to dual-license or change license,
  it needs every contributor's individual sign-off. The implementation
  plan's open-questions log (`risk-register.md`) tracks this as an
  acceptable v0.1 posture.

## Lens Notes

- **Security**: Apache 2.0's patent-retaliation clause is part of the
  threat-model surface — it materially affects supply-chain risk for
  enterprise adopters. The §11 STRIDE model assumes Apache 2.0 in
  every "Repudiation" + "Tampering" row.
- **Maintainability**: SPDX headers + `NOTICE` files require minor
  ongoing maintenance (one line per new source file). Mitigated by
  the per-tool docs sprint having added the SPDX convention to the
  language profile docs (e.g.
  [`../tools/lang/python.md`](../tools/lang/python.md)).
- **DX**: contributors don't need to sign anything to PR. Removing the
  CLA friction is worth more than the dual-license flexibility for
  v0.1's external-tester recruitment goal.
- **Operability**: zero. Apache 2.0 has no runtime implication.
- **Cost**: zero. License files + NOTICE files are tiny.

## Cross-references

- [`LICENSE`](../../LICENSE) — the full Apache 2.0 text at repo root.
- [`NOTICE`](../../NOTICE) — copyright holder + attribution.
- [`../governance/adr-process.md`](../governance/adr-process.md) — how
  ADRs are recorded; this file is the second-oldest detail file in
  `docs/adr/` (the first detail file written backwards from an
  already-accepted ADR; the two newer ones, ADR-032 + ADR-033, were
  written forward at their decision moment).
- [`../governance/roadmap.md`](../governance/roadmap.md) — OpenSSF
  Scorecard ≥ 8.0 is a v1.0 exit-criterion that depends on the
  license-choice line.
- [`../../.design/plans/decisions-log.md`](../../.design/plans/decisions-log.md)
  — the master index where ADR-007 is recorded.
- [Apache License, Version 2.0](https://www.apache.org/licenses/LICENSE-2.0)
  — the canonical license text.
- [SPDX License List](https://spdx.org/licenses/Apache-2.0.html) —
  the canonical SPDX identifier.
