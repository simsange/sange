---
generated_by: tools/generators/adr_scaffold.py
generator_version: 1.0.0
generated_at: 2026-05-14T10:42:52Z
input_sha256: 16af59c9d4877e46d0030636a6f233400ba4fd4ed520e7d38ec21a6935dda88d
output_sha256: ac9f0489d3517e1e8ffc06dcc1ba5d522870afa402eb8bc923e3ca391a5f25ed
manual_edits_allowed: true
---
# ADR-0032: Multi-dimensional variant matrix for gitignore-swap (Android-Studio-inspired)

**Status:** Accepted
**Date:** 2026-05-14

## Context

Sange's original §6.5 design (the "gitignore-swap") models the development-vs-publish
boundary as a **single binary axis**: a repo has at most two profiles, `dev.gitignore`
and `prod.gitignore`, switched transactionally during `sange publish`. The §6.5.1 Profile
Registry composes per-language / per-framework / per-editor / per-OS profile fragments via
an `extends` chain, but the swap engine still sees only two states.

In practice, real-world projects ship along **multiple orthogonal axes** at once:

  * **Stage** — `dev`, `staging`, `pilot`, `production`. Each has different secret stores,
    different AI providers, different audit verbosities, different signing keys.
  * **Audience** — `internal`, `pilot-user`, `public`, `customer-x`. Same code, different
    feature flags, different bundle metadata, different telemetry endpoints.
  * **Surface** — `cli`, `web`, `mobile`, `embedded`. Same domain logic, different
    distribution artifacts.
  * **Region** — `us`, `eu`, `apac`. Same product, different compliance-driven resource
    overrides (e.g. GDPR-only files in `eu`).

Compressing this to `dev | prod` is the foot-gun pattern: a developer publishes the wrong
stage's `.env`, a region-specific resource leaks across regions, an internal build ships
to public users.

**Prior art — Android Studio's build-variant model.** The Android Gradle Plugin solves
the same problem by composing variants along three orthogonal axes:

  1. **Build types** (`debug`, `release`, plus custom like `staging`) — control packaging,
     minification, signing, debuggability.
  2. **Product flavors** grouped into **flavor dimensions** (e.g. `mode: demo|full` ×
     `api: minApi23|minApi24`) — control features and content.
  3. **Build variants** = the Cartesian product. The full variant name is
     `<flavorDim1><flavorDim2>...<BuildType>` (e.g. `minApi24DemoRelease`).

**Source sets** live per-variant under `src/`:

  * `src/main/` — shared across every variant
  * `src/<buildType>/` — per build type (e.g. `src/debug/`)
  * `src/<flavor>/` — per flavor (e.g. `src/demo/`)
  * `src/<flavor><BuildType>/` — per variant (e.g. `src/demoDebug/`)

**Merge priority (highest wins):**

  1. `src/<variant>/`           (most specific)
  2. `src/<buildType>/`
  3. `src/<flavor>/` (per dimension)
  4. `src/main/`                (least specific)

**Safety mechanisms** that prevent dev code leaking to release:

  * **Separate source sets** — `src/debug/java/Foo.java` *physically cannot* end up in a
    release build; it's a different directory the release variant never reads.
  * **`applicationIdSuffix`** — `debug` builds get a `.debug` suffix appended to the app
    ID, so dev and prod can coexist on the same device with no collision.
  * **`versionNameSuffix`** — `-demo` / `-staging` suffixes propagate into human-readable
    version strings, preventing confused-deputy "which build is this?" incidents.
  * **`signingConfigs`** — release builds *must* declare a signing config; debug uses an
    auto-generated keystore. The build system refuses to ship an unsigned release.
  * **Variant filters** — explicit `beforeVariants { … enable = false }` block excludes
    impossible combinations (e.g. `minApi21 + demo`) at the IDE level.

These ideas map cleanly to Sange's gitignore-swap, audit, secrets, AI provider selection,
bundle naming, and release engineering.

## Decision

Sange v3 adopts a **multi-dimensional variant matrix** modeled after Android Studio's
build-variant system, replacing the binary `dev | prod` axis with a configurable
Cartesian product over user-declared dimensions. Concretely:

  1. **Stage** (the build-type analog) — a *linear* axis with user-defined values; the
     default set is `dev / staging / production`, but a project may add more (e.g.
     `internal`, `pilot`, `hotfix`). The publish step targets a single stage.
  2. **Flavor dimensions** (the product-flavor analog) — *zero or more* orthogonal axes
     declared in `.sange/config.toml::[variants.dimensions.<name>]`. Each dimension
     declares its set of flavors. Examples: `audience: {internal, public}`,
     `surface: {cli, web, mobile}`, `region: {us, eu, apac}`.
  3. **The active variant** = `(stage, *flavors)` — a specific selection along every axis.
  4. **Source-set composition** — `.sange/variants/<axis>/<value>/` directories layer
     resources (gitignore patterns, prompts, commit-template visibility filters, secret
     references, AI provider config, audit policy). Merge priority mirrors Android's:
     `matrix > stage > each flavor dimension > _core > profile-registry defaults`.
  5. **Variant filters** in `.sange/config.toml::[[variants.filter]]` exclude impossible
     combinations (e.g. `audience=internal AND stage=production`); filtered variants
     don't appear in `sange variant list`.
  6. **Bundle-name suffix** is computed deterministically from the variant — the §6.9
     Release Bundling engine appends `-<stage>` (and optional flavor suffixes) to the
     artifact name. `sange-0.1.0-dev0.zip` ≠ `sange-0.1.0.zip`; the dev artifact cannot
     be confused with the production artifact even when filenames are merged into one
     destination.
  7. **Stage-locked operations** — sensitive ops refuse to run under the wrong stage:
       * `sange publish` defaults to `--stage production`; refuses if the active variant
         is `dev` unless `--stage dev` is explicit.
       * `sange purge execute` requires the active variant's stage to match the target
         repo's protected branch policy.
       * `sange bundle publish --channel stable` requires `stage=production`.
  8. **Auto-detection** — Sange infers the active variant from (in order):
       a. `SANGE_VARIANT=<stage>[/<dim>=<flavor>...]` environment variable.
       b. Git branch name → mapped to a stage via `.sange/config.toml::[variants.branch_map]`
          (default: `main`/`master` → `production`, `develop` → `dev`, `staging/*` →
          `staging`, `release/*` → `production`).
       c. `.sange/.active-variant` file (gitignored; persists between sessions).
       d. The configured `default_stage` from `.sange/config.toml`.
       e. Pollution scanner pre-publish — `sange doctor --variant` flags files that
          belong to one variant tree appearing in another.
  9. **Ambient awareness in the CLI/TUI** — every command renders the active variant
     in the prompt prefix and the audit-log entry:
       ```
       [sange • production / audience=public / surface=cli] sange commits push
       ```
  10. **Variant-aware secret resolution + AI provider selection** — each variant can
      pin its own secret resolver and AI provider (`dev` → Ollama + local `.env`;
      `production` → AWS Secrets Manager + Claude Opus). Configured under
      `.sange/config.toml::[variants.<axis>.<value>.{secrets,ai}]`.
  11. **Variant-aware audit** — the audit-chain JSONL entries carry the active variant
      tuple as a top-level field, so a query like "every action taken in
      production/audience=public/surface=cli during the merge freeze" is one grep.
  12. **Doctor's variant pollution check** — `sange doctor` walks both directions:
      (a) files in `.sange/variants/<axis>/<value>/` that don't match the current variant
      after composition should not appear in the publish tree, and (b) the *current*
      composed gitignore must shadow every variant-specific path that doesn't belong.
      Mismatches are flagged before publish, not after.

The current binary `dev | prod` design is preserved as the **default minimal
configuration** (a `[variants]` block with only `stages = ["dev", "production"]` and no
flavor dimensions). Existing projects don't need to change anything — they get the new
machinery without configuration cost.

## Alternatives Rejected

  * **Keep the binary `dev | prod` axis only** — rejected because the foot-gun pattern
    documented in §6.5 Red-Team Pass is *already* about variant pollution; the binary
    axis cannot express "internal-prod" vs "public-prod" or "dev-cli" vs "dev-web",
    forcing users to either over-ignore everything in `prod.gitignore` (loses
    information) or build their own variant scheme outside Sange (drift).
  * **Single linear axis with a richer enum (dev / qa / staging / prod / hotfix)** —
    rejected because it cannot model orthogonal concerns: a hotfix can target any
    audience; staging can be internal-only or public-beta. Composing axes is more
    expressive and matches how real release pipelines work.
  * **Folder-based-only (no declared dimensions)** — rejected because the Cartesian
    product without explicit dimension declarations leads to combinatorial explosion
    and silent typos; an explicit `[variants.dimensions]` block makes the surface area
    visible + the `variantFilter` mechanism meaningful.
  * **Adopt the Android Gradle Plugin verbatim** — rejected because AGP's variant
    semantics are Android-specific (Java/Kotlin compilation, manifest merging,
    AndroidManifest.xml, R.java generation). We borrow the *pattern* (axes, source
    sets, merge priority, suffixes, filters, signing-per-build-type) and adapt it to
    Sange's domain (gitignore-swap, secret resolution, AI provider selection, bundle
    suffix, audit metadata).
  * **YAML config DSL with imperative variant transforms (à la `beforeVariants`)** —
    rejected for v1; declarative TOML + filters covers 95% of cases. Imperative
    variant manipulation lands as a plugin extension point in v2 if real demand
    surfaces.

## Consequences

**Positive:**
  * Eliminates the §6.5 foot-gun for projects with > 2 axes of concern — a multi-tenant
    SaaS, a regulated-region rollout, a beta-vs-public release, a per-customer build.
  * Default-secure: the suffix mechanism prevents merged-filename confusion between
    artifacts.
  * Composable: existing `.sange/gitignore/profiles/` work unchanged; variants layer on
    top via the `extends` chain.
  * Variant-aware audit, secrets, and AI provider selection emerge from the same
    primitive — one design, three subsystems' worth of feature.
  * Familiar mental model for engineers from mobile/desktop backgrounds (Android
    Studio, Xcode schemes/configurations, Visual Studio configurations all share this
    pattern).
  * Auto-detection from git branch makes the variant invisible in the common case
    (`main` ⇒ `production`) and explicit when it matters.

**Negative:**
  * Cognitive load — users who previously thought in `dev | prod` now have to
    understand stages × flavors. Mitigated by the default-minimal configuration
    (binary stages, zero flavor dimensions) and the `sange variant detect` helper.
  * More config surface — `.sange/config.toml` grows. Mitigated by sensible defaults
    and the §10.4 Category convention's hierarchical layout for `.sange/variants/`.
  * Bundle-naming change is a SemVer-minor breaking change for any project that
    depended on the v0.1-vintage suffix-less bundles. The migration path is
    documented in `docs/upgrade/v0.1-to-v0.5.md`.
  * Doctor + variant interaction adds a new pre-publish gate that may surface
    pre-existing pollution in legacy projects (a one-time cleanup cost).

**Neutral:**
  * Existing §6.5.1 Profile Registry is unchanged — variants compose with profiles via
    `extends`, no profile semantics shift.
  * Plugin authors gain a new entry point (variant axes) but no existing plugin
    surface breaks.

## Lens Notes

  * **Security:** Eliminates accidental cross-variant pollution at publish time;
    variant-aware secret resolution prevents prod secrets from loading in dev
    sessions; variant-aware audit makes after-the-fact forensics tractable.
  * **Performance:** No measurable cost — variant resolution is one TOML parse + a
    set-of-strings comparison at startup; the swap engine's transactional rename
    cost is unchanged.
  * **Maintainability:** Replaces a binary footgun with a declarative matrix that's
    grep-able + diff-able. Reduces special-case logic in `sange publish`.
  * **Developer Experience:** Familiar pattern for mobile devs; default-minimal
    config means existing users see no change; ambient variant indicator in the CLI
    prevents "wait, which stage am I on" anxiety.
  * **Operability:** Stage-locked operations + branch-mapped auto-detection make
    production-bound mistakes harder. Variant tuple in every audit entry enables
    high-cardinality forensics.
  * **Cost:** TOML lines (not money). The kit (§6.12) ships a `templates/variants/`
    folder of canonical examples (default 3-stage; mobile 2-stage × 3-flavor; SaaS
    2-stage × 4-tenant); operators pick and adapt.

## References

  * [Android Developers — Configure build variants](https://developer.android.com/build/build-variants) — primary source for the build-type / product-flavor / flavor-dimension / source-set / merge-priority pattern.
  * [Android Developers — Configure your build](https://developer.android.com/build) — overview of the Gradle build system Sange's variant model rhymes with.
  * `.design/sange-architecture-prompt.md` §6.5 (original gitignore-swap) and §6.5.1
    (Profile Registry) — the prior design this ADR supersedes.
  * `.design/sange-architecture-prompt.md` §6.9 (Release Bundling) — consumer of the
    new bundle-name suffix.
  * `.design/sange-architecture-prompt.md` §6.10 (Container VCS Secret Management) —
    consumer of variant-aware secret resolution.
  * `.design/sange-architecture-prompt.md` §6.7 (AI subsystem) — consumer of
    variant-aware provider selection.
  * `.design/plans/decisions-log.md` row ADR-032 — index entry.

---

*Authored by the responding model + reviewer. Added to `.design/plans/decisions-log.md`
as ADR-032 on 2026-05-14.*
