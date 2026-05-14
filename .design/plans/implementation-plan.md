# Implementation plan (phased)

Single canonical phased plan. Mirrors §14 (roadmap) + §18 (checklist) of `../sange-architecture-prompt.md`. Owners and dates are placeholders until populated by the implementation team.

## Phase 0 — Foundation (target: v0.1, MVP) — *generators scaffold first per ADR-029*

**Goal:** A developer on macOS / Linux / Windows can install Sange, init a repo, generate a commit message, and ride it through draft → approved → committed → pushed. Git only. CLI only.

**Critical path (in strict order — Phase 0a runs *before* Phase 0b):**

### Phase 0a — Scaffolding + Generators (the foundation the generators emit)

1. **Repo scaffolding** — `pyproject.toml` (hatchling, Python 3.12+, deps pinned), `ruff.toml`, `mypy.ini` (`--strict`), `.pre-commit-config.yaml`, empty `src/sange/__init__.py`, `src/sange/py.typed`, `src/sange/_version.py`, `tests/__init__.py`, `LICENSE` (Apache 2.0), `NOTICE`, `.editorconfig`, `.gitignore`, `.gitattributes`, `CHANGELOG.md`, `CONTRIBUTING.md`, `SECURITY.md`, `CODE_OF_CONDUCT.md`, root `README.md` per ADR-017.
2. **`tools/generators/_lib/`** — shared helpers (`output.py` frontmatter + hash, `manpage.py` parser, `markdown.py` table builders, `fingerprint.py` sha256 + provenance).
3. **`tools/generators/verify_generated.py`** — CI integrity check; recomputes `output_sha256` and fails on mismatch.
4. **`tools/generators/all.py`** — orchestrator, dependency-ordered.
5. **Run every generator with `--write`** to populate the deliverable; all output carries §16.4.1 frontmatter and is CI-verified:
   - **T-G-001** `git_catalog.py` → `docs/reference/appendix-d-git-catalog.md`
   - **T-G-002** `svn_catalog.py` → `docs/reference/appendix-e-svn-catalog.md`
   - **T-G-003** `cross_vcs_map.py` → `docs/reference/appendix-f-cross-vcs.md`
   - **T-G-004** `commit_templates.py` → `docs/reference/appendix-g-commit-templates.md` + `.sange/commit-templates/type/*.toml` skeletons
   - **T-G-005** `kit_manifest.py` → `templates/MANIFEST.toml` (CI cosign-signs)
   - **T-G-006** `docs_index.py` → `docs/README.md` + `docs/tools/README.md`
   - **T-G-007** `adr_scaffold.py` → on-demand ADR file scaffolding
   - **T-G-008** `exit_codes.py` → `docs/reference/exit-codes.md`
   - **T-G-009** `cli_reference.py` → `docs/reference/cli-reference.md`
   - **T-G-010** `jsonrpc_schema.py` → `docs/reference/json-rpc-schema.md`
   - **T-G-011** `config_schema.py` → `docs/reference/config-schema.md`
   - **T-G-012** `threat_model_table.py` → `docs/security/stride.md`
   - **T-G-013** `changelog_from_commits.py` → `docs/CHANGELOG.md`
   - **T-G-015** `profile_registry.py` → 35 `templates/gitignore-profiles/<category>/<name>.toml` + `docs/reference/profile-registry.md`
   - **T-G-016** `verify_session_log.py` → CI check for the `.design/plans/session-log.md` cross-reference graph + `grounding` completeness (ADR-030 + ADR-031)
6. **Generators emit kit fragments + scaffolds** — the `templates/workflows/<provider>/`, `templates/bundlers/<tool>/`, `templates/push-to-prod/<strategy>/`, `templates/vps-setup/<topology>/`, `.github/workflows/{ci,release,security-scan,sbom,sigstore,docs,codeql}.yml`, the `Dockerfile`, `docker-compose.yml`, and the `.sange/` template skeleton under `templates/sange-folder/`. All hand-stubbed prose (per-tool `docs/tools/*.md`) gets a generator-emitted header + frontmatter; humans fill the body.

### Phase 0b — Business logic (what humans build, on top of the scaffolded foundation)

7. `SangeConfig` Pydantic v2 model with TOML + JSON merge — once written, **re-run T-G-011** to regenerate `config-schema.md`.
8. `VCSDriver` Protocol — once written, T-G-009 picks it up in the CLI introspection.
9. Git adapter — read + write operations against real subprocess `git`.
10. Commit JSON schema + storage (`.sange/commits/`).
11. Commit lifecycle state machine (8 states).
12. Counter durability + crash recovery.
13. AI provider abstraction (Anthropic + OpenAI + Ollama minimum).
14. Prompt Enhancer core (§6.7.1).
15. Commit-message enhancement template.
16. Modular Makefile generator (§10 + §10.4 Category convention).
17. Doctor check: Makefile-tracked detection.
18. Local telemetry collector.
19. `typer` skeleton + global flags — once written, **re-run T-G-009** to regenerate `cli-reference.md`.
20. `sange init`, `sange commits new/ai/submit/approve/reject/commit/push`.
21. `sange commit` happy-path alias.

**The discipline:** every time Phase 0b business logic changes a generator's input shape, CI re-runs `python tools/generators/all.py --write` and `verify_generated.py` checks the new `output_sha256`. No manual edits to generator output (ADR-029).

**Exit criteria:** Cross-platform install. Happy path of `sange commit` works end-to-end. No critical security findings in `gitleaks` + `trufflehog` scan of own repo. **Plus:** every generator listed above produces valid output with valid frontmatter and passes `verify_generated.py`.

## Phase 1 — Beta (target: v0.5)

**Goal:** Feature-complete for solo developers.

**Adds:**

- SVN adapter (Tier-1 VCS support)
- Gitignore-swap engine (§6.5) with SIGKILL recovery
- Hooks engine (§7.4) + secret scanning rules library
- Docker packaging with container-secret management (§6.10)
- `sange doctor` (host + container modes)
- `sange bootstrap` (brew/scoop/apt/mise orchestration)
- Expanded commit template library (50+ normalized presets — Appendix G)
- VCS History Purge subsystem (§6.11) **read-only**: `sange purge plan / mirror / scan / analyze / preview / notify`. Destructive subcommands stubbed.
- CLI/TUI presentation conventions (§7.0) mandatory from v0.5 on
- Premade Operations Kit (§6.12) read-only: `sange scaffold list / show`

**Exit criteria:** ≥ 50 external testers; zero critical security findings.

## Phase 2 — General Availability (target: v1.0)

**Goal:** Production-grade tool for teams of any size.

**Adds:**

- Web UI (Laravel 13 + Livewire 4 + `laravel/passkeys`) — all 21 modules from §8.2
- Remote access via Cloudflare Tunnel / Tailscale / WireGuard / reverse-proxy on VPS (§8.5)
- Release engineering with Bundling (§6.9): GitHub Releases, GitLab Releases, OCI artifact, S3, generic registry, filesystem destinations
- CI/CD companion (§7.5): provider lint + local exec via `act` + simulated end-to-end runs
- Plugin system (§7.9) with signed marketplace
- Comprehensive command catalogs (Appendices D, E, F)
- MCP client + MCP server (§6.7)
- Full documentation site at `sange.sh`
- History Purge destructive operations (`sange purge execute / push / rollback`) for Git only
- `sange scaffold add / diff / update / remove / verify` (the full kit surface)
- `sange vps scaffold <provider>` covering Hetzner / DO / Linode / Vultr / OVH / Scaleway / AWS / GCP / Azure

**Exit criteria:** Stable API; semver guarantees; SLSA 3 releases; OpenSSF Scorecard ≥ 8.0; ≥ 3 third-party plugins.

## Phase 3 — Multi-VCS & Workflow (target: v2.0)

**Goal:** Cross-VCS parity + power workflows.

**Adds:**

- Mercurial adapter (read + write; including `hg convert --filemap` for purge)
- Fossil adapter
- Pijul adapter
- Workflow builder UI (§8.2.18)
- Opt-in external telemetry pipeline (§12.2)
- Cloudflare Workers edge auth gateway (§8.5)
- Purge: SVN executor + Mercurial executor

**Exit criteria:** Cross-VCS concept map (Appendix F) fully implemented; workflow library with 20+ presets.

## Phase 4 — Enterprise & Team (target: v3.0)

**Goal:** Org-scale deployment.

**Adds:**

- Perforce adapter + `p4 obliterate` purge executor (admin-gated)
- Plastic SCM adapter
- Sapling adapter
- SAML / OIDC SSO
- SIEM audit-log forwarding (forwards the hash-chained audit JSONL with verified integrity)
- Self-hosted sync server (opt-in)
- Sange Cloud (optional, self-hostable)

**Exit criteria:** SOC 2 readiness checklist; one Fortune 500 design-partner deployment.

## Phase 5 — Speculative (target: v4.0+)

IDE deep integration; federation across Sange instances; on-device fine-tuning per repo style.

## Cross-phase invariants

- Every phase must pass the §19 quality gates that were in scope at that phase's exit.
- Every phase ships an updated `content-audit.md` showing requirement → section mapping.
- Every breaking change is recorded as a superseding ADR.
- Every phase's release is SLSA 3, sigstore-signed, SBOM-attached.

---

*Source of truth: §14 + §18 of `../sange-architecture-prompt.md`.*
