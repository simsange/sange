# Changelog

All notable changes to Sange are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and Sange adheres to
[Semantic Versioning 2.0.0](https://semver.org/spec/v2.0.0.html).

From v0.1.0 onward the changelog is emitted by `tools/generators/changelog_from_commits.py`
(T-G-013) from the `.sange/commits/*.json` lifecycle records. Hand-edits between
generator runs are allowed, with every edit recorded as a session-log row per
ADR-028 — but the generator is the source of truth, and CI verifies the
`output_sha256` frontmatter of this file against a fresh run.

## [Unreleased]

The current build phase (Phase 0a — generators-scaffold-everything, per ADR-029).
No commits are tagged yet; entries land here as each task in
`.design/plans/checklist.md` flips to `completed`.

### Added

- **T-001** — Repository scaffolding: `pyproject.toml` (hatchling, Python 3.12+,
  ADR-019-pinned deps), `ruff.toml`, `mypy.ini` (`--strict`), `.pre-commit-config.yaml`,
  `src/sange/{__init__,_version,py.typed}`, `tests/__init__.py`, `LICENSE` (Apache 2.0
  per ADR-007), `NOTICE`, `.editorconfig`, `.gitignore`, `.gitattributes`,
  `CHANGELOG.md`, `CONTRIBUTING.md`, `SECURITY.md`, `CODE_OF_CONDUCT.md`,
  `AUTHORS.md`, `README.md`.

### Changed

_None — Phase 0a is greenfield._

### Removed

_None — the held `sange-v1/` and `sange-v2/` trees remain in place per R-017
(`.design/plans/risk-register.md`); they are scheduled for removal at the
v0.1.0 beta gate._

### Security

_See `SECURITY.md` for the disclosure process. v0.1.0 ships with the §11 threat
model fully reified via `docs/security/stride.md` (emitted by T-G-012)._

## Versioning policy

- **MAJOR.MINOR.PATCH** per SemVer 2.0.0.
- **`.devN`** suffixes denote pre-release builds during a Phase (current).
- **`-rcN`** is reserved for release candidates near a tagged version.
- Breaking changes are recorded as superseding ADRs (`.design/plans/decisions-log.md`).

[Unreleased]: https://github.com/sangedev/sange/compare/HEAD...HEAD
