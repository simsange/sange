# Changelog

All notable changes to Sange are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and Sange adheres to
[Semantic Versioning 2.0.0](https://semver.org/spec/v2.0.0.html).

From v0.1.0 onward the changelog is emitted by `tools/generators/changelog_from_commits.py`
(T-G-013) from the `.sange/commits/*.json` lifecycle records. Hand-edits between
generator runs are allowed, with every edit recorded as a session-log row per
ADR-028 — but the generator becomes the source of truth once the project
dogfoods its own lifecycle. Until then, this file is maintained by hand.

## [Unreleased]

_No changes queued yet._

## [0.1.0.post1] — 2026-05-16

**The real first published release.** v0.1.0 shipped against
`__version__ = "0.1.0.dev0"` (a wart — the version string wasn't
bumped before tagging). PyPI permanently reserves
`sange==0.1.0.dev0` from that publish; `pip install sange` (no
`--pre`) skipped it. **v0.1.0.post1 is the real `pip install`-able
v0.1**. The v0.1.0 git tag stays at its original commit per
"release-as-immutable"; this `.post1` carries the same code shape
plus everything the [Unreleased] section accumulated:

### Added

- **T-042** — `sange commits new`: manual DRAFT-commit creation, no AI
  involved. Takes `TYPE` + `SUBJECT` positional args plus `--scope`,
  `--body` (or `-` to read from stdin), `--breaking-change`,
  `--co-author`, `--reference`, `--repo`, `--branch`. Validates type
  against the 11-element Conventional Commits set; auto-detects the
  current branch via `GitDriver`. Plain-text + `--json` output.
- **T-043** — `sange commits ai`: AI-driven DRAFT-commit creation,
  registered as a typer alias for the existing `sange commit`
  happy-path. Gives the granular sub-app a complete parallel:
  `commits new` (manual) ↔ `commits ai` (AI).
- **T-044** — Three new lifecycle CLI verbs closing the remaining
  state-machine transitions:
  - `sange commits submit` — DRAFT → PENDING_REVIEW
  - `sange commits reject --reason "<text>"` — PENDING_REVIEW → REJECTED.
    DRAFT auto-submits transparently (solo-dev UX).
  - `sange commits commit` — APPROVED → COMMITTED via `git commit`, no push.
- **`sange commits reopen`** — the only backward transition.
  Brings any non-DRAFT commit back to DRAFT, clearing
  `committed_sha` + `pushed_remote`. The
  `LifecycleEngine.reopen()` method existed since the engine
  was implemented; this commit adds the CLI surface (mirrors
  `submit` in shape). 5 tests in `TestCommitsReopen`.
- **ADR detail files** — three backfills closing part of the
  31-of-33 detail-file gap that `docs/governance/adr-process.md`
  called out:
  - [`docs/adr/0007-license-apache-2.md`](docs/adr/0007-license-apache-2.md)
    — why Apache 2.0 over MIT / BSD / MPL / GPL / AGPL / LGPL /
    BSL / dual-license.
  - [`docs/adr/0029-generate-first-everything.md`](docs/adr/0029-generate-first-everything.md)
    — why generators scaffold every reference doc, not just
    catalogs.
  - [`docs/adr/0031-audit-trail-append-only.md`](docs/adr/0031-audit-trail-append-only.md)
    — why session-log + snapshots + audit-chain are all
    append-only, and the §22 step 11.5 Continuity Check.
- **Docs sprint** — 13 reader-facing docs added under `docs/`,
  closing every `Planned` row in the README that didn't depend on
  v0.5+/v1.0+ feature work:
  - [`docs/installation.md`](docs/installation.md) — install paths
    (source / PyPI / Docker / pipx) × per-platform notes.
  - [`docs/quickstart.md`](docs/quickstart.md) — five-minute
    end-to-end onramp.
  - [`docs/architecture.md`](docs/architecture.md) — reader's
    guide mapping the 1500-line canonical deliverable.
  - [`docs/tools/workflow/commit-lifecycle.md`](docs/tools/workflow/commit-lifecycle.md)
    — the 8-state lifecycle with three worked examples.
  - [`docs/tools/vcs/git.md`](docs/tools/vcs/git.md) — what the
    Git adapter adds over raw `git`.
  - [`docs/tools/vcs/svn.md`](docs/tools/vcs/svn.md) — SVN adapter
    plan + pointer to Appendix E.
  - [`docs/tools/lang/python.md`](docs/tools/lang/python.md) —
    Python workflows.
  - [`docs/tools/lang/node.md`](docs/tools/lang/node.md) — Node.js
    workflows.
  - [`docs/governance/roadmap.md`](docs/governance/roadmap.md) —
    version map v0.1 → v4.0+.
  - [`docs/governance/adr-process.md`](docs/governance/adr-process.md)
    — how Sange records decisions.
  - [`docs/governance/privacy.md`](docs/governance/privacy.md) —
    privacy + telemetry posture.
  - [`docs/security/prompt-injection.md`](docs/security/prompt-injection.md)
    — T-030 redaction layer in one place.
  - [`docs/security/slsa-and-sbom.md`](docs/security/slsa-and-sbom.md)
    — supply-chain integrity claims for every released artifact.

### Changed

- **Docs** — `docs/reference/cli-reference.md` regenerated (T-G-009) to
  reflect the five new verbs in both the top-level command index and
  the `sange commits` sub-command tree.
- **Docs** — `docs/release.md`: added a "Step 0 — Pre-flight checklist"
  subsection plus a "Failure modes seen in production" table folding
  in the v0.1.0 release lessons (PyPI trusted-publisher pending vs
  active, HTTPS-vs-SSH auth mismatch, org-rename tag-annotation drift).
- **CI** — `.github/workflows/ci.yml`: bumped action versions to
  node24-using majors (`actions/checkout@v6`, `actions/setup-python@v6`,
  `actions/upload-artifact@v7`, `actions/download-artifact@v8`,
  `docker/build-push-action@v7`, `docker/login-action@v4`,
  `docker/setup-buildx-action@v4`, `docker/setup-qemu-action@v4`).
  Each version verified via `api.github.com/repos/<action>/releases/latest`
  before pinning.
- **CI** — `generators` job now runs `all.py --check --skip T-G-001 T-G-002`.
  The two skipped generators introspect the installed `git --version` /
  `svn --version` and embed those in their outputs, so CI's toolchain
  version never byte-matches a contributor's local toolchain.
- **URLs** — Migrated from `github.com/sangedev/sange` to
  `github.com/simsange/sange` across 36 files. The GitHub org was
  renamed in-place on 2026-05-15. The `v0.1.0` tag's annotation retains
  the historical `sangedev` URL per the release-as-immutable rule.
- **README** — Documentation table refactored into a two-tier
  "Live now / Planned" structure with explicit gate-conditions on
  every planned row (e.g. "Release bundling: v0.5+ release
  engine"; "JSON-RPC schema: T-162 (v1.0)"). Zero 404-prone links
  in the live table.
- **CONTRIBUTING.md** — Replaced the stale pointer to a
  never-emitted `docs/governance/contributing.md` with a 4-item
  link list into the actually-existing governance + architecture
  docs.

### Fixed

- **Tests** — `tests/unit/test_cli_commits.py:_setup_git_repo`: added
  `-u` flag to the fixture's `git push` so the test repo's `main` has
  upstream tracking. Required by newer git versions when
  `GitDriver.push()` runs bare `git push origin` with no branch
  argument.
- **mypy** — 25 errors → 0 across the source tree. One real bug
  caught (`_gather_repo_context` returned `BranchInfo` where `str`
  was declared); the rest were missing type ignores for optional AI
  extras + `cast(AIProvider, ...)` on three lazy-loaded provider
  constructions.
- **ruff** — 375 errors → 0. Targeted fixes (B904 raise-from, RUF005,
  N806, RUF043, B007, RUF059, F841, SIM110) plus config-level ignores
  (SIM105 / UP042 / B008 / B017 / N818 / RUF001 / RUF012 / SIM102 /
  SIM103 / SIM108). Per-file E501 ignores for generator scripts +
  test fixtures.
- **Docs site** —
  `documentation/docs/architecture/redaction.md`: converted regex-
  bearing markdown table to a fenced code block. Python's HTML parser
  was interpreting `[A-Za-z0-9]{36,}` in table cells as a
  `<![CDATA[...]]>` marked-section, crashing `mkdocs build --strict`.

## [0.1.0] — 2026-05-14

First public release. Functional MVP closing the §14.1 v0.1
exit-criteria: `sange init` → `git diff | sange commit` →
`commits approve` → `commits push`.

### Added

- **Foundation** (Phase 0)
  - `pyproject.toml` with hatchling backend, Python 3.12+ floor,
    pinned deps per ADR-019; `src/sange/{__init__,_version,py.typed}`
    layout (PEP 561).
  - `SangeConfig` Pydantic v2 model with TOML + JSON merge.
  - `VCSDriver` Protocol + 4 capability sub-protocols
    (`SupportsStash`, `SupportsBisect`, `SupportsRebase`,
    `SupportsLFS`).
  - Git adapter: read operations (status, log, diff, branches,
    current_branch, remotes, tags, show_commit) plus 12 write
    operations (add, remove, revert, commit, branch_create/delete,
    switch, fetch, pull, push, tag_create/delete).
  - 8-state `CommitJSON` lifecycle schema + storage
    (`.sange/commits/`) + pure-function `LifecycleEngine` state
    machine + atomic-write counter with filesystem-rescan crash
    recovery.
  - `AIProvider` Protocol + adapters for mock / anthropic / openai
    / ollama / gemini / bedrock (optional extras gated by
    `pip install 'sange[<provider>]'`).
  - PromptEnhancer with T-030 redaction → template render →
    provider completion → schema validate → AuditRecord pipeline.
  - Commit-message enhancement template (Conventional Commits 1.0.0
    output schema).
  - Modular Makefile generator with Category convention (§10.4).
  - Doctor checks including `--makefile-tracked` detection (§10.3).
  - Local NDJSON telemetry collector (opt-in, ISO-week sharded).

- **Generators** (Phase 0a — generate-first per ADR-023 + ADR-029)
  - Shared helpers: `_lib/{output,manpage,markdown,fingerprint}.py`.
  - 14 of 16 generators implemented (T-G-010 + T-G-014 deferred to
    Phase 3 / Phase 4 respectively): git-catalog, svn-catalog,
    cross-vcs-map, commit-templates, kit-manifest, docs-index,
    adr-scaffold, exit-codes, cli-reference, config-schema,
    threat-model-table, changelog-from-commits, profile-registry
    (35 templates), verify-session-log.
  - `tools/generators/all.py` orchestrator with topological
    dependency ordering, shared clock, deterministic `output_sha256`
    frontmatter, and `--write` / `--check` modes.

- **CLI** (Phase 1 — happy path)
  - `sange --version`, `--json` global flag, `--help`.
  - `sange init` — bootstrap `.sange/` skeleton with
    Makefile-tracking detection.
  - `sange commit` — happy-path AI-driven commit message
    generation with optional DRAFT save.
  - `sange commits {list,approve,push}` — initial lifecycle verbs.
    The remaining verbs (`new`, `ai`, `submit`, `reject`,
    `commit`) land in v0.1.0.post1 / v0.1.1.
  - `sange doctor` — environment health checks.
  - `sange ai providers` — list registered providers.

- **Release infrastructure**
  - `.github/workflows/release.yml` — tag-driven pipeline: sdist+wheel
    build, PyPI trusted-publisher OIDC publish, multi-arch Docker
    buildx push to GHCR (linux/amd64 + linux/arm64 per ADR-033) with
    sigstore provenance + SBOM, GitHub Release creation with
    auto-extracted notes from `docs/CHANGELOG.md`.
  - `.github/workflows/ci.yml` — pytest matrix (3.12/3.13 ×
    ubuntu-x64/ubuntu-arm64/macos), ruff, mypy `--strict`, generators
    `--check`, package build, single-arch docker sanity.
  - Multi-stage `Dockerfile` per ADR-033: `python:3.12-slim` base,
    non-root `sange` user (UID 1000), 310 MB final image, doctor
    smoke at container start.

- **Docs**
  - `docs/release.md` — operator-facing release recipe (one-time
    setup + per-release procedure + recovery paths).
  - `docs/CHANGELOG.md` — T-G-013-generated changelog (will populate
    as the project dogfoods `sange commits push`).
  - 33 ADRs in `.design/plans/decisions-log.md` documenting every
    non-trivial design choice.
  - Two sister-repo seeds in this checkout pending bootstrap:
    `documentation/` (MkDocs Material site for
    `simsange/documentation`) and `org-github/` (community-health
    files for `simsange/.github`).

### Known issues at release time

- **PyPI publish blocked**. The v0.1.0 tag push at 2026-05-15
  successfully built sdist+wheel and pushed multi-arch images to
  GHCR, but the `publish to PyPI (OIDC)` job failed with
  `invalid-publisher` — the trusted-publisher record on PyPI was
  filed as "pending" rather than active. Pre-flight checklist now
  in `docs/release.md::Step 0` to prevent this on the next release.
  `pip install sange` will work once the maintainer completes the
  one-time trusted-publisher setup and re-runs the failed `pypi` +
  `release` jobs.
- **GHCR image is private by default**. Anonymous
  `docker pull ghcr.io/simsange/sange:v0.1.0` requires the
  maintainer to flip the package visibility to "Public" at
  `github.com/orgs/simsange/packages`.

## Versioning policy

- **MAJOR.MINOR.PATCH** per SemVer 2.0.0.
- **`.postN`** suffixes for fix-forward releases against an immutable
  tag (per PEP 440; e.g. `v0.1.0.post1` fixes bugs without bumping
  `0.1.0` → `0.1.1`).
- **`-rcN`** for release candidates near a tagged version.
- **`-bN`** / **`-aN`** for betas / alphas.
- Breaking changes are recorded as superseding ADRs in
  `.design/plans/decisions-log.md`.

[Unreleased]: https://github.com/simsange/sange/compare/v0.1.0.post1...HEAD
[0.1.0.post1]: https://github.com/simsange/sange/releases/tag/v0.1.0.post1
[0.1.0]: https://github.com/simsange/sange/releases/tag/v0.1.0
