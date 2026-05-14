# Positioning, audience, engineering bar

Mirrors §3 of `../sange-architecture-prompt.md` and ADR-022 of `decisions-log.md`. Edit one, mirror the other.

## What Sange is

> **Sange is the local-first developer-experience layer between humans and their version-control systems** — eliminating boilerplate, enforcing safety, embedding AI assistance into every commit, branch, and release, and providing a secure dashboard (local or self-hosted) for fine-grained review, approval, scheduling, and orchestration.

## What Sange is *not*

- Not a replacement for `git`, `svn`, `hg`, or `p4`.
- Not a competing wire protocol.
- Not a repository host.
- Not a forked VCS — it wraps the user's chosen VCS unmodified.

## Audience scope (designed-for personas)

| Persona | What they need |
|---|---|
| Non-developer founder / CEO | Approve a release with one click on the Web UI; see what shipped at a glance; see approval chain; never read raw `git` output. |
| CTO / Head of Engineering | Audit trail, signed-release receipts, SBOM + provenance, compliance reports, dashboard of repo health across the org. |
| Cyber-security reviewer | Hash-chained audit (§7.0.7), prompt-injection defense (§6.7), purge subsystem (§6.11), STRIDE coverage (§11), CIS-aligned VPS kit (§6.12). |
| Junior engineer | Happy path is one verb (`sange commit`, `sange publish`); gates intercept dangerous ops before damage; helpful errors with the precise fix. |
| Senior staff engineer | Granular subcommands (`sange commits <lifecycle>`, `sange purge plan/execute`), scriptable JSON output, plugin extension points, ADR rigor. |
| DevOps / SRE | Premade kit (§6.12), `sange scaffold`, deploy strategies, monitoring integrations, OIDC trusted publishing. |
| OSS maintainer | Default-secure releases (SLSA 3), sigstore, SBOM, §6.8 commit lifecycle for community PR review queues. |

A feature usable only by senior engineers — *with no equivalently safe path for the other audiences* — is a design defect.

## Engineering bar (enforced by §19 quality gates)

1. **SOLID** — Protocol-driven adapters (VCSDriver, AIProvider), open/closed for new providers, no Liskov violations across the VCS abstraction.
2. **DRY** — Zero internal repetition. The §10.4 Category convention forbids duplicated fragment trees; §16.3 forbids the architecture being told twice.
3. **KISS** — Happy paths are one verb. Power surfaces only open when asked. No mandatory configuration to use defaults.
4. **No internal repetition** — Each fact has one canonical home; the rest cross-reference it.
5. **No design flaws** — Each `🔴 Red-Team Pass` is a working defense against its section's failure modes.
6. **Enterprise + military-grade security** — Hash-chained audit, signed plugins, signed kit, CIS-aligned hosts, prompt-injection defense, purge gates. Defaults are secure; toggling off is explicit + audit-logged.
7. **Simple enough to be powerful** — Powerful tools nobody can use are not powerful. The non-engineer must be able to approve a release in the Web UI without reading the architecture document.

## Quality bar checklists

- [ ] Every CLI verb is approachable to the *junior engineer* persona.
- [ ] Every Web UI module is approachable to the *non-developer founder* persona.
- [ ] Every audit log entry is parseable by the *cyber-security reviewer* persona.
- [ ] Every release artifact is verifiable by the *CTO* persona without trusting Sange itself.
- [ ] Every premade kit fragment is auditable by the *DevOps / SRE* persona.
- [ ] No section of the document is gratuitously hostile to a non-engineer reader.

## Two cross-cutting interaction rules

**Generate-first, fine-tune-second (ADR-023).** Token-heavy deliverable sections (catalogs, manifest, docs index, exit codes, CLI reference, JSON-RPC schema, config schema, STRIDE table, CHANGELOG) are produced by **deterministic generator scripts** under `tools/generators/`, not hand-typed. Every generated file carries §16.4.1 frontmatter with an `output_sha256` that `verify_generated.py` checks in CI. Hand-fine-tuning is reserved for prose-bearing additions where determinism cannot apply.

**One question at a time (ADR-024).** When confirmation is needed — by the responding model running this prompt, or by Sange's CLI / TUI / Web UI — questions are sequential, never batched. The operator must be able to stop the sequence at any answer. Multi-field information-entry forms (commit JSON editor, bundle manifest editor) remain allowed because each field carries data, not a confirmation gate.

## When constraints conflict

Surface as a `⚠️ Design Conflict` callout in the architecture prompt and resolve via an ADR row in `decisions-log.md`.

---

*Last reviewed: 2026-05-13. Source of truth: §3 + ADR-022 of `../sange-architecture-prompt.md`.*
