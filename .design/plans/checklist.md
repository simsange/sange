# Master checklist

Single canonical list, dependency-aware. Mirrors §18 of `../sange-architecture-prompt.md`. Each task: ID, one-sentence description, dependencies, primary phase.

## Phase 0 — Foundation (v0.1)

- [ ] **T-001** Repository scaffolding (`pyproject.toml`, ruff, mypy, pytest, pre-commit) — deps: none
- [ ] **T-002** `SangeConfig` Pydantic v2 model with TOML + JSON merge — deps: T-001
- [ ] **T-003** `VCSDriver` Protocol — deps: T-001
- [ ] **T-004** Git adapter — read operations — deps: T-003
- [ ] **T-005** Git adapter — write operations — deps: T-004
- [ ] **T-006** Commit JSON schema + storage (`.sange/commits/`) — deps: T-002
- [ ] **T-007** Commit lifecycle state machine — deps: T-006
- [ ] **T-008** Counter durability + crash recovery — deps: T-006
- [ ] **T-009** AI provider abstraction (`AIProvider` Protocol) — deps: T-001
- [ ] **T-010** Prompt Enhancer core (§6.7.1) — deps: T-009
- [ ] **T-011** Commit-message enhancement template — deps: T-010
- [ ] **T-012** Modular Makefile generator (Category convention §10.4) — deps: T-002
- [ ] **T-013** Doctor check: Makefile-tracked detection — deps: T-012
- [ ] **T-014** Local telemetry collector — deps: T-002
- [ ] **T-015** `tools/generators/_lib/{output,manpage,markdown,fingerprint}.py` shared helpers (§16.4) — deps: T-001
- [ ] **T-016** `tools/generators/verify_generated.py` integrity check — deps: T-015
- [ ] **T-017** `tools/generators/all.py` orchestrator + dependency graph — deps: T-015

## Phase 0a — Generators (Generate-first / fine-tune-second, ADR-023; run before any catalog drafting)

- [ ] **T-G-001** `tools/generators/git_catalog.py` → Appendix D — deps: T-015
- [ ] **T-G-002** `tools/generators/svn_catalog.py` → Appendix E — deps: T-015
- [ ] **T-G-003** `tools/generators/cross_vcs_map.py` → Appendix F (v1 columns; Hg added in v2.0; P4 in v3.0) — deps: T-015
- [ ] **T-G-004** `tools/generators/commit_templates.py` → Appendix G (folds v1's 104 strings + Conventional Commits 1.0.0 into ≥50 normalized presets with `aliases`) — deps: T-015
- [ ] **T-G-005** `tools/generators/kit_manifest.py` → `templates/MANIFEST.toml` (CI cosign-signs the output) — deps: T-015
- [ ] **T-G-006** `tools/generators/docs_index.py` → `docs/README.md` + `docs/tools/README.md` — deps: T-015
- [ ] **T-G-007** `tools/generators/adr_scaffold.py` — deps: T-015
- [ ] **T-G-008** `tools/generators/exit_codes.py` → `docs/reference/exit-codes.md` — deps: T-015
- [ ] **T-G-009** `tools/generators/cli_reference.py` → `docs/reference/cli-reference.md` — deps: T-015, T-040
- [ ] **T-G-010** `tools/generators/jsonrpc_schema.py` → `docs/reference/json-rpc-schema.md` — deps: T-015, T-162
- [ ] **T-G-011** `tools/generators/config_schema.py` → `docs/reference/config-schema.md` — deps: T-015, T-002
- [ ] **T-G-012** `tools/generators/threat_model_table.py` → `docs/security/stride.md` — deps: T-015
- [ ] **T-G-013** `tools/generators/changelog_from_commits.py` → `docs/CHANGELOG.md` from `.sange/commits/*.json` — deps: T-015, T-006
- [ ] **T-G-014** `tools/generators/hg_catalog.py` (v2.0) and `p4_catalog.py` (v3.0) — deps: T-015
- [ ] **T-G-015** `tools/generators/profile_registry.py` → `docs/reference/profile-registry.md` + 35 `templates/gitignore-profiles/<category>/<name>.toml` files per §6.5.1 — deps: T-015
- [ ] **T-G-016** `tools/generators/verify_session_log.py` — CI check that walks `.design/plans/session-log.md` and verifies (a) every `linked` cross-reference (ADR-NNN / T-NNN / R-NNN / S-NNN) resolves to a real entry, (b) the `grounding` column is non-empty for every row from S-001-T-20 onward, (c) every `files_touched` entry appears in `git log` within the row's `timestamp` window. Per ADR-030 + ADR-031. — deps: T-015

## Phase 1 — CLI surface (v0.1)

- [ ] **T-040** Typer skeleton, global flags — deps: T-001
- [ ] **T-041** `sange init` — deps: T-012, T-002
- [ ] **T-042** `sange commits new` (manual) — deps: T-007
- [ ] **T-043** `sange commits ai` — deps: T-010, T-011
- [ ] **T-044** `sange commits submit/approve/reject/commit/push` — deps: T-007, T-005
- [ ] **T-045** `sange commit` happy-path alias — deps: T-043, T-044

## Phase 2 — Beta features (v0.5)

- [ ] **T-100** SVN adapter — read operations — deps: T-003
- [ ] **T-101** Gitignore-swap engine with SIGKILL recovery (§6.5) — deps: T-002
- [ ] **T-102** Pre-commit hooks framework — deps: T-001
- [ ] **T-103** Secret scanning rules library (`gitleaks` + `trufflehog`) — deps: T-102
- [ ] **T-104** Container build + secret-mount mechanisms (§6.10) — deps: T-002
- [ ] **T-105** `sange doctor --container` — deps: T-104
- [ ] **T-106** Expanded commit template library (50+ presets — Appendix G) — deps: T-007
- [ ] **T-107** TerminalProfile detection + `rich`/`textual`/`questionary` adoption (§7.0.1, §7.0.2) — deps: T-040
- [ ] **T-108** Hash-chained audit JSONL writer + `sange audit verify` (§7.0.7) — deps: T-002
- [ ] **T-109** Typed-phrase confirmation gate (`sange.utils.gate.typed_phrase_confirm`) (§7.0.5) — deps: T-107
- [ ] **T-110** Subprocess streaming helper with stdout/stderr async capture + transcript hashing (§7.0.6) — deps: T-108
- [ ] **T-111** Purge subsystem core (read-only paths) — `core/purge/{plan,gates,mirror,analyzer}.py` (§6.11) — deps: T-108, T-110
- [ ] **T-112** `sange purge plan / mirror / analyze / preview / scan / notify` (no destructive ops) — deps: T-111
- [ ] **T-113** Scanner integration: `gitleaks` + `trufflehog` wrappers (shared §7.4 + §6.11.4 gate-8) — deps: T-103
- [ ] **T-114** PurgePlan JSON schema + per-repo `.sange/purge/<utc>/` layout — deps: T-111
- [ ] **T-115** Premade Operations Kit scaffolds — `_core/` content for `workflows/`, `bundlers/`, `push-to-prod/`, `vps-setup/`, `scripts/` (§6.12) — deps: T-001

## Phase 3 — Web UI (v1.0)

- [ ] **T-160** Laravel 13 scaffolding (PHP 8.4 recommended / 8.3 floor; Livewire 4) — deps: T-001
- [ ] **T-161** `sanged` daemon (launchd / systemd --user / Windows Service via pywin32) — deps: T-002
- [ ] **T-162** JSON-RPC schema core ↔ Laravel (versioned, HMAC-signed local; mTLS remote) — deps: T-161
- [ ] **T-163** Passkey integration via `laravel/passkeys` + `@laravel/passkeys` — deps: T-160
- [ ] **T-164** PIN fallback + rate limit — deps: T-160
- [ ] **T-165** Password alternative (Argon2id + HIBP k-anonymity) — deps: T-160
- [ ] **T-166** `mkcert` TLS provisioning — deps: T-160
- [ ] **T-167** `sange.test` resolver setup per OS — deps: T-160
- [ ] **T-168** Multi-DB driver test matrix (SQLite default; PostgreSQL, MySQL/MariaDB, SQL Server) — deps: T-160
- [ ] **T-169 .. T-186** Web UI modules §8.2.1 — §8.2.20 — deps: T-162
- [ ] **T-187..T-192** Remote-access setup wizards (Cloudflare Tunnel / Tailscale / WireGuard / VPS) + `sange web remote audit` — deps: T-160
- [ ] **T-193..T-199** Release bundle destinations (GitHub / GitLab / OCI / S3 / generic / sigstore / SBOM / SLSA provenance) — deps: T-002
- [ ] **T-200** MCP server implementation — deps: T-009, T-162
- [ ] **T-201** MCP client implementation — deps: T-009
- [ ] **T-202** Documentation site at sange.sh — deps: T-162
- [ ] **T-203** Purge destructive ops: `sange purge execute` (Git: filter-repo + BFG) with §6.11.4 gates and §6.11.5 verification — deps: T-111, T-112
- [ ] **T-204** `sange purge push` with second typed-phrase gate + platform-support ticket payload generator — deps: T-203
- [ ] **T-205** `sange purge rollback` from backup mirror — deps: T-203
- [ ] **T-206** `sange purge notify` collaborator-notification templates + Slack/webhook delivery with HMAC + idempotency key — deps: T-112
- [ ] **T-207** Web UI module §8.2.21 Purge & History Surgery (plan editor, gates, preview, hand-off) — deps: T-203
- [ ] **T-208** `docs/tools/security/purge.md` produced from user-supplied playbook (refactored per §6.11.8); 19 sections + 20 gotchas preserved — deps: T-202
- [ ] **T-209** `sange scaffold add / diff / update / remove / verify` (§7.11 — the full kit surface) — deps: T-115
- [ ] **T-210** `sange vps scaffold` covering 9 providers (Hetzner / DO / Linode / Vultr / OVH / Scaleway / AWS / GCP / Azure) — deps: T-209
- [ ] **T-211** `templates/MANIFEST.toml.sig` signing pipeline (ADR-020) — deps: T-209
- [ ] **T-212** Weekly kit integration matrix CI workflow surfacing `kit_status: needs_attention` in `sange doctor` — deps: T-209

## Phase 4 — Multi-VCS (v2.0)

- [ ] **T-240** Mercurial adapter — deps: T-003
- [ ] **T-241** Fossil adapter — deps: T-003
- [ ] **T-242** Pijul adapter — deps: T-003
- [ ] **T-243** Workflow builder UI — deps: T-160
- [ ] **T-244** Opt-in external telemetry pipeline — deps: T-014
- [ ] **T-245** Cloudflare Workers edge auth gateway — deps: T-191
- [ ] **T-246** Purge: SVN executor (`svnadmin dump → svndumpfilter exclude → swap`) — deps: T-203, T-100
- [ ] **T-247** Purge: Mercurial executor (`hg convert --filemap` + `hg strip`) — deps: T-203, T-240

## Phase 5 — Enterprise (v3.0)

- [ ] **T-280** Perforce adapter — deps: T-003
- [ ] **T-281** Plastic SCM adapter — deps: T-003
- [ ] **T-282** Sapling adapter — deps: T-003
- [ ] **T-283** SAML/OIDC SSO — deps: T-160
- [ ] **T-284** SIEM audit-log forwarding (forward purge audit chain with verified integrity) — deps: T-108
- [ ] **T-285** Self-hosted sync server (opt-in) — deps: T-161
- [ ] **T-286** Purge: Perforce executor (`p4 obliterate -y`, admin-role-gated) — deps: T-280, T-203

## Notes

- Tasks T-115 to T-212 are net-new in the v3.4 / v3.5 prompt updates and supersede the placeholders in the earlier version of §18.
- Granular task expansion (target ~350 tasks per the §19 quality gate) happens during Phase 0 sprint planning.
- Critical dependency: **T-107 (TerminalProfile) blocks every command that produces user output.** Build it first.

---

*Source of truth: §18 of `../sange-architecture-prompt.md`.*
