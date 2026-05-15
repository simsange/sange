---
generated_by: hand-authored (detail file backfilled for an accepted ADR)
generator_version: n/a
generated_at: 2026-05-16T04:45:00Z
manual_edits_allowed: true
---
# ADR-0029: Generators scaffold everything (strengthens ADR-023)

**Status:** Accepted
**Date:** 2026-05-14 (concurrent with the architecture v4.4 lock)

## Context

ADR-023 established the "generate-first then fine-tune" discipline
for catalog content — Appendices D / E / F / G are deterministic
outputs of generators that read live `git help -a` / `svn help` /
the enrichment table / the Conventional Commits spec, not
hand-written prose. Once any catalog is regenerated, CI checks the
`output_sha256` frontmatter against a fresh run; drift is a CI
failure.

The question this ADR addresses: **does that discipline stop at
catalog content, or extend further?**

Looking at the v0.1 deliverables, the candidates for "could be
generated" extend well beyond Appendices D-G:

- `templates/MANIFEST.toml` — the kit-fragment manifest.
- `templates/gitignore-profiles/<category>/<name>.toml` — 35
  profiles from upstream sources.
- `docs/README.md` + `docs/tools/README.md` — docs indexes.
- `docs/reference/cli-reference.md` — typer-app introspection.
- `docs/reference/exit-codes.md` — from the source enum.
- `docs/reference/config-schema.md` — from the `SangeConfig`
  Pydantic v2 model.
- `docs/reference/json-rpc-schema.md` — from the JSON-RPC contract.
- `docs/security/stride.md` — from the §11 threat-table source.
- `docs/CHANGELOG.md` — from `.sange/commits/*.json` PUSHED rows.
- `.github/workflows/*.yml` — from canonical pipeline templates.
- The `Dockerfile` + `docker-compose.yml` — from a single source.

Each of these has a natural single-source-of-truth that a
generator could read. Writing them by hand multiplies the surface
where source-of-truth and copy drift apart.

The discipline question is binary: do we extend generate-first to
everything that has a single source of truth, or do we draw the
line somewhere?

## Decision

**Generators scaffold everything.** The Phase 0 build order is
strictly:

1. **Bootstrap minimum scaffolding** (the irreducible 30
   files that can't be generated because they're the bootstrap
   itself): `pyproject.toml`, `ruff.toml`, `mypy.ini`,
   `.pre-commit-config.yaml`, empty `src/sange/{__init__.py,
   _version.py, py.typed}`, the
   `tools/generators/_lib/{output,manpage,markdown,fingerprint}.py`
   helpers, `tools/generators/verify_generated.py`,
   `tools/generators/all.py`, the required root files (LICENSE,
   NOTICE, .editorconfig, .gitignore, .gitattributes, CHANGELOG,
   CONTRIBUTING, SECURITY, CODE_OF_CONDUCT, AUTHORS, README).
2. **Write generators first.** Every T-G-NNN task in
   [`.design/plans/checklist.md`](../../.design/plans/checklist.md)
   produces a generator script under `tools/generators/`.
3. **Generators emit the kit + scaffolds** —
   `templates/workflows/`, `templates/bundlers/`,
   `templates/push-to-prod/`, `templates/vps-setup/`,
   `.github/workflows/{ci,release,security-scan,sbom,sigstore,docs,codeql}.yml`,
   the `Dockerfile`, the `docker-compose.yml`, the `.sange/`
   template skeleton under `templates/sange-folder/`, all 35
   gitignore profile TOMLs, the per-tool docs index, every
   appendix. All output carries §16.4.1 frontmatter
   (`generated_by` / `generator_version` / `generated_at` /
   `input_sha256` / `output_sha256` / `manual_edits_allowed`).
4. **Humans finesse business logic + prose.** The narrative
   content inside generated frames (per-tool walkthroughs, ADR
   detail files, the canonical architecture deliverable) is
   hand-authored.

The boundary is: **structure is generated; prose inside
generated frames is hand-authored**. A docs-index table is
generated; the per-doc walkthrough is hand-written. A CLI flag
table is generated from typer introspection; the verb's
narrative description is hand-written. The generator emits the
frame; the human fills the body.

CI verifies the discipline three ways:

- `verify_generated.py` — recomputes `output_sha256` for every
  generated file with `manual_edits_allowed: false` in the
  frontmatter. Drift is a CI failure.
- `all.py --check` — every registered generator runs in
  check-mode; any `stale` result fails CI.
- `verify_session_log.py` — enforces the audit-trail discipline
  from ADR-031, including grounding-column completeness.

A fresh clone can run `python tools/generators/all.py --write`
and produce most of the surrounding scaffolding before any
business logic is written. The v0.1 build proved this: the
bootstrap (1) → generators (2) → scaffolding (3) order
produced 14 of 16 generators + every reference doc before
Phase 0b's first business-logic commit.

## Alternatives Rejected

- **Stop at catalogs (ADR-023 boundary).** Rejected because the
  same drift-prevention argument applies to every other
  single-source-of-truth surface. The cli-reference would drift
  from the actual typer app; the config-schema would drift from
  `SangeConfig`; the exit-codes doc would drift from the source
  enum. Catching drift in CI is the entire point.

- **Generate selectively, case-by-case.** Rejected because it
  recreates the friction the discipline is meant to remove —
  every new doc surface becomes an ad-hoc "should this be
  generated?" debate. The blanket rule (anything with a single
  source of truth) is simpler.

- **Use templating + hand-write the result.** Rejected because
  templating without verification is just hand-writing with
  syntax sugar — the source-of-truth drift problem returns the
  first time a contributor edits the rendered file directly.
  The `manual_edits_allowed: false` frontmatter + `output_sha256`
  check is what makes the discipline enforceable.

- **Write generators in any language.** Rejected — the
  generators are pure-Python stdlib only (ADR-023 + this ADR's
  implementation). The orchestrator (`all.py`) never imports a
  non-stdlib library; the helpers in `_lib/` are stdlib-only.
  This keeps the bootstrap minimal (no compile chain) and
  cross-platform-portable.

- **Generators ship as a separate `pip install` dependency.**
  Rejected because then the project depends on itself for
  bootstrap. The generators ship in the repo at
  `tools/generators/`, importable as `python tools/generators/...`,
  zero install required.

## Consequences

### Positive

- **Drift between source-of-truth and rendered file is a CI
  failure.** Nobody can ship a stale doc by accident.
- **Cold-clone reproducibility.** A fresh checkout can run
  `python tools/generators/all.py --write` and reproduce every
  generated file byte-for-byte (modulo the
  `generated_at` timestamp, which is overridable via `--clock`
  for deterministic CI).
- **New surfaces become generator tasks.** Adding a new doc
  reference is a one-line registry entry + a new generator
  module; the conventions take care of the rest.
- **The `templates/MANIFEST.toml` signing pattern** (cosign
  in v0.5+ CI) is enforceable because the manifest is generated;
  if a fragment were added by hand, the signature would invalidate.

### Negative

- **Generator authoring has overhead.** Each T-G-NNN takes
  ~100-500 lines of pure-stdlib code. Mitigated by the
  shared `_lib/` helpers (markdown tables, frontmatter, hashing,
  manpage parsing).
- **Drift from upstream sources** (the gitignore profile registry
  reads `github/github/gitignore`; the git-catalog reads
  `git help -a`) means generators must be re-run when upstream
  changes. Mitigated by Dependabot-style scheduled regeneration
  and by CI's check-mode (which surfaces drift).
- **Two generators are version-bound** (T-G-001 git-catalog,
  T-G-002 svn-catalog) because they embed `git --version` /
  `svn --version` in the canonical input payload. The CI skip
  for these two is documented in `.github/workflows/ci.yml::generators`.

### Neutral

- **`manual_edits_allowed: true` files exist** for a small set of
  generator outputs that intentionally allow hand-tuning between
  regenerations (e.g. the operator-facing release recipe). These
  carry the frontmatter for discoverability but don't fail CI on
  drift.
- **Generator outputs are part of the repo**, not produced at
  install time. Trade-off: bigger repo vs faster install + the
  property that GitHub's web UI shows the same content the
  generated reader sees.

## Lens Notes

- **Security**: generated files with `manual_edits_allowed:
  false` + `output_sha256` are tamper-evident. A malicious PR that
  modifies `MANIFEST.toml` directly fails CI's `verify_generated.py`
  check. The cosign signature on the manifest (v0.5+) is the
  second layer.
- **Maintainability**: high — single source of truth for every
  generated surface. The CI catches drift before merge.
- **DX**: contributor experience is "edit the source, regenerate,
  verify". For surface-level changes (typo fixes in prose) the
  generator may need to extract more inputs (a `description.md`
  alongside the data file); discipline favors the longer path over
  the drift-prone shortcut.
- **Operability**: generator runs are fast (~5-30 seconds for all
  16 in `all.py --write`); easy to integrate into pre-commit and
  CI.
- **Cost**: zero — generators are pure-stdlib Python.

## Cross-references

- [`tools/generators/`](../../tools/generators/) — every
  T-G-NNN generator module.
- [`tools/generators/all.py`](../../tools/generators/all.py) —
  the orchestrator with topological dependency ordering.
- [`tools/generators/verify_generated.py`](../../tools/generators/verify_generated.py)
  — CI integrity check.
- [`tools/generators/_lib/`](../../tools/generators/_lib/) —
  shared helpers (frontmatter, hashing, markdown, manpage
  parsing). Pure-stdlib.
- ADR-023 (generate-first for catalogs) — the predecessor this
  ADR strengthens.
- [`./0007-license-apache-2.md`](./0007-license-apache-2.md) — the
  detail-file pattern this file follows.
- [`./0031-audit-trail-append-only.md`](./0031-audit-trail-append-only.md)
  — `verify_session_log.py` is the third CI integrity surface
  alongside `verify_generated.py` + `all.py --check`.
- [`../governance/adr-process.md`](../governance/adr-process.md)
  — how ADRs are recorded; the §16.4.1 frontmatter convention
  this ADR depends on is documented there.
- [`../../.design/plans/decisions-log.md`](../../.design/plans/decisions-log.md)
  row 37 — the master-log row this detail expands.
- §16.4.1 of the canonical architecture deliverable — the
  frontmatter schema (`generated_by`, `output_sha256`, etc.).
