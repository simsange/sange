# Risk register

Open risks the implementation team should watch. Add a row as risks are discovered; mark `Closed` with the date + the resolution mechanism (ADR / mitigation / acceptance).

| # | Risk | Likelihood | Impact | Owner | Mitigation | Status |
|---|---|---|---|---|---|---|
| R-001 | Final v3 codebase path ambiguity: user said `/Users/imanimanyara/Artisan/projects/sange/`; actual is `/Users/imanimanyara/Artisan/projects/opensource/sange/` | High | Medium | architect | **CLOSED 2026-05-13** — user confirmed in-place at `/Users/imanimanyara/Artisan/projects/opensource/sange/`. Recorded as ADR-027 in `decisions-log.md`; resolved in §16.2 of the prompt. | Closed |
| R-002 | `laravel/passkeys` package is new (released 2026-05-12); ecosystem stability not yet proven | Medium | Medium | web-ui | Pin by exact version; weekly Dependabot update PR; fall back to PIN + password if package has a critical regression | Open |
| R-003 | Livewire 4 (released 2026-01-15) is recent; some Laravel 13 packages may not yet support it | Medium | Low | web-ui | Track upstream package compatibility matrix; document any temporary v3 fallback per-feature | Open |
| R-004 | Etymology re-framing ("named after the *sengi*") may still draw critique from native Swahili speakers | Low | Low | docs | Cite Wikipedia + Kingdon 1997; offer brand rename via ADR if challenged | Open |
| R-005 | Premade kit fragments (CIS-baseline, Caddy templates, etc.) age faster than the Sange release cadence | High | Medium | kit-maintainer | Weekly integration matrix CI (T-212); `kit_status: needs_attention` surface; documented kit update path via `sange update-kit` | Open |
| R-006 | Purge subsystem's `--batch` flag is socially normalized (engineers default to it for routine purges) | Medium | High | security | Rate-limit per operator per month; elevated-severity audit; automatic notify to security inbox; quarterly review | Open |
| R-007 | Web UI's Cloudflare Tunnel mode leaks tunnel token via misconfigured CI | Low | High | security | Tunnel tokens in OS keychain; rotation supported; tunnel bound to a single Sange instance | Open |
| R-008 | `sange purge execute` runs against a stale mirror because upstream moved | Medium | High | security | Mid-execution upstream-HEAD check; abort + re-`--analyze` + re-confirm; ADR-018 invariant | Open |
| R-009 | TUI rendering breaks on a terminal Sange's TerminalProfile heuristics don't recognize | Medium | Low | dx | `sange doctor` reports detected profile + emits ASCII fallback hint; user can override via `--no-emoji` | Open |
| R-010 | `git-filter-repo` major-version upgrade breaks Sange's wrapper | Medium | Medium | wrap-maintainer | `sange doctor` checks installed version; pin minimum in `pyproject.toml`; release notes flag wrapped-tool upgrades | Open |
| R-011 | Non-developer persona finds the Web UI too dense after v1.0 feature growth | Medium | Medium | design | "Approvals" and "Releases" are first-tier nav; "Engineering" is second-tier; periodic UX review against the 10-minute non-engineer skim target | Open |
| R-012 | Audit-chain integrity broken by file-system mtime adjustments on macOS Time Machine restore | Low | Medium | observability | `sange audit verify` warns on shifted mtime even when hash chain is intact; documented in `docs/operations/recovery.md` | Open |
| R-013 | OIDC trusted publishing flow for PyPI / npm / GHCR is misconfigured per-provider | Medium | Medium | release | `templates/workflows/<provider>/` ships verified-good config; release CI smoke-tests OIDC on every minor version | Open |
| R-014 | Plugin author bypasses signature requirement via a build-time injection | Low | High | security | Signature check at *install time* (not just download time); plugin sandbox + capability declarations; runtime check on every invocation | Open |
| R-015 | A `--batch` waiver in CI silently masks a `secrets-rotated` gate failure | Low | Critical | security | The `--batch` audit entry is severity=elevated; security inbox receives notification; quarterly review of all `--batch` invocations | Open |
| R-016 | `sange.sh` domain registered (status confirmed by user 2026-05-13) — verify registration ownership + TLS / nameservers / mail policy / WHOIS privacy posture before any public release | Low | Medium | ops | User confirmed registered (no `whois sange.sh` lookup performed). Action: validate ownership; configure Cloudflare DNS + redirect to `opensource.simtabi.com/products/sange`; configure SPF/DKIM/DMARC if email enabled; set WHOIS privacy. | Open |
| R-017 | `sange-v1/` and `sange-v2/` directories not deleted until v0.1.0 reaches beta (per user direction 2026-05-13) — risk of stale paths or accidental imports during Phase 0 development | Low | Low | architect | Hold-until-beta is intentional (preserves v1 audit-source-of-truth until generators have ingested it); `sange doctor` flags any code/config referencing `../sange-v1/` or `../sange-v2/` paths; final deletion is gated by §19 quality-gate "v1/v2 audit findings fully captured in `docs/audit/`" | Open |
| R-018 | Generator drift across the v0.5→v1.0 development window — generators emit different output as their Python deps update, breaking the `output_sha256` chain | Medium | Medium | dev | Generators pin their own dependencies in `tools/generators/_requirements.txt` separate from the main `pyproject.toml`; CI verifies the pinned versions match; ADR-023 strengthened to require dep-pin discipline | Open |

## Closed risks

- **R-001** — Codebase target path (closed 2026-05-13). User confirmed in-place at `/Users/imanimanyara/Artisan/projects/opensource/sange/`. Recorded as ADR-027.

---

*Reviewed: 2026-05-13.*
