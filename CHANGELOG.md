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

### Changed

- **Version bumped to `0.1.1.dev0`.** Per `docs/release.md::After
  the release`, the dev suffix returns after every published cut.
  v0.1.0.post1 shipped on 2026-05-16; `_version.py` had been left
  at the release version since. Local builds now produce
  `sange-0.1.1.dev0` wheels until the next tag.

### Added

- **T-107b — `rich.console.Console` factory + status helpers
  (`sange.utils.console`).** The first concrete consumer of
  T-107a's `TerminalProfile`. Wraps `rich` so a single
  `make_console(profile)` call produces a `Console` whose
  color / encoding / width / emoji / force_terminal flags are
  all derived from the cached profile. New module
  `src/sange/utils/console.py`:
  - `make_console(profile, *, stderr=False, file=None)` builds
    a `rich.console.Console`. Color-mode maps:
    `"none"→None / "16"→"standard" / "256"→"256" /
    "truecolor"→"truecolor"`. CI without TTY produces
    `force_terminal=False / force_interactive=False`
    (avoids CR-spam in log aggregators). Width is taken from
    the profile, not rich's own detection (deterministic CI
    column count).
  - `success_text(profile, msg)` / `failure_text(...)` /
    `warning_text(...)` — `rich.text.Text` instances with the
    profile's glyph prefixed. Lighter than a Panel for inline
    use (progress per-task status).
  - `success_panel(...)` / `failure_panel(...)` /
    `warning_panel(...)` — `rich.panel.Panel` with green / red /
    yellow border + the profile's glyph in the body. Default
    titles: `None` / `"Error"` / `"Warning"`. The failure
    panel matches §7.0.8's `Panel(title="Error",
    border_style="red")` convention.
  - Emoji glyph automatically used on UTF-8 TTYs; ASCII
    fallback on legacy Windows. NO_COLOR profiles get Unicode
    glyphs (✓/✗/△) but no ANSI escapes.
  +22 tests in `test_console.py` covering: console type +
  utf8 enables color + NO_COLOR disables color + CI force_terminal
  off + legacy Windows no emoji + width from profile + stderr/file
  kwargs / success/failure/warning Text contains message + uses
  emoji on UTF-8 + uses ASCII on legacy / panel returns Panel +
  green border / red border + default Error title / yellow
  border / custom title / integration smoke: actually renders
  through rich without crash, NO_COLOR omits ANSI escapes.
  Suite 1773 → 1795 passing. ruff 0, mypy 0 (86 → 87 source
  files). **What this unblocks**: T-107c (`rich.tree.Tree` for
  `sange purge preview` / `sange branch list` per §7.0.3),
  `sange.utils.progress` (§7.0.4 ETA helper), and rich-based
  rendering across the existing CLI commands.
- **T-105 — `sange doctor --container` (§6.10.3 audits).**
  Audits the running container for leaked secrets. v0.5 v0.5
  scope: detection-only — flags issues, doesn't auto-remediate.
  New module `src/sange/core/doctor/container.py` with pure
  check functions (no typer/click deps), plus a `--container`
  flag on `sange doctor`:
  - `check_in_container(env, marker_paths)` — verifies we're
    inside a container via any of: `/.dockerenv` (Docker),
    `/run/.containerenv` (Podman), `KUBERNETES_SERVICE_HOST`
    env (in-cluster pod), `container=` env (systemd-nspawn /
    LXC). Fires FIRST; if it fails, the rest of the container
    checks are skipped to avoid noisy host-environment
    findings.
  - `check_non_root(uid_fn)` — §6.10.3 mandates non-root.
    Default uses `os.geteuid()`; skipped on platforms without
    it (Windows).
  - `check_leaky_env_vars(env)` — flags env vars whose names
    match a secret-shaped pattern (`*_TOKEN$`, `*_KEY$`,
    `*_SECRET$`, `*_PASSWORD$`, plus provider-specific
    `GITHUB_TOKEN` / `AWS_SECRET_ACCESS_KEY` / `NPM_TOKEN` /
    etc.) AND have non-empty values. Findings include the
    var NAME + value LENGTH only — **NEVER the value itself**.
    Allowlist skips obviously-safe names like `SSH_KEY_PATH`
    (a path, not a key). Case-insensitive.
  - `check_secret_mount_perms(mount_dir, max_mode)` — scans
    a secret-mount dir (default `/run/secrets/`) for files
    whose mode exceeds the §6.10.3 0400 max. Findings carry
    path + mode + max_allowed; never file content.
  - `check_ssh_key_perms(home, max_mode)` — scans
    `~/.ssh/id_<algo>` for keys whose mode exceeds 0600
    (SSH client itself refuses to use overpermissive keys).
    `.pub` files explicitly excluded (they CAN be
    world-readable). `known_hosts` and other non-id files
    also excluded.
  - `ContainerCheck` frozen dataclass: `name` + `ok` +
    `message` + `findings` (list of dicts). Findings are
    typed per check so JSON consumers can rely on the shape.
  - CLI adapter `_container_check_to_result` converts core
    `ContainerCheck` → CLI `CheckResult` so the core stays
    free of typer/click imports.
  - `--container` flag added to `sange doctor`. Honors `--json`.
    cli-reference regenerated.
  +26 tests in `test_doctor_container.py` covering: in-container
  detection (Docker marker / Kubernetes / systemd-container /
  no-signals-fails); non-root (root fails / non-root passes /
  default uses geteuid); leaky env vars (no-secret / token /
  password / empty-value-not-flagged / **value never in findings**
  exercised with `"this-secret-value-must-not-leak"` and asserted
  absent / allowlist / case-insensitive); secret mount perms
  (missing dir skipped / 0400 passes / 0644 fails / multiple
  bad files); SSH key perms (no ssh dir / 0600 passes / 0644
  fails / .pub not flagged / non-id files ignored); CLI
  integration (default mode excludes container checks /
  `--container` runs in-container check / JSON mode).
  Suite 1747 → 1773 passing. ruff 0, mypy 0 (84 → 86 source
  files). **The v0.5 surface for the §6.10 container story
  is now complete**: T-104 (resolver chain) + T-105 (auditor).
- **T-104 — Secret resolver library (`sange.core.secrets`).**
  Implements the §6.10 runtime-side secret-mount mechanism chain.
  The §6.10 spec enumerates five mechanisms in preference order;
  this v0.5 slice ships four (SSH agent, BuildKit/file, OS
  keyring, env-var dev fallback). The remaining external-manager
  paths (Vault, AWS Secrets Manager, 1Password, age/GPG) land in
  v1.0+ when those integrations exist. New subsystem at
  `src/sange/core/secrets/`:
  - `Secret` frozen dataclass — METADATA only (name + provider
    + lookup_key + description + required). NEVER holds the
    value. `__repr__` redacts `lookup_key` because it sometimes
    carries secret-adjacent context (a Vault path, a keychain
    service identifier). Newlines in name/lookup_key rejected
    (structured-log injection vector). Empty name rejected.
  - `redact(value)` returns the constant `<redacted>` regardless
    of input. Used as a grep-able call-site marker for every
    place a value might otherwise reach a log / error / repr.
  - `Resolver` runtime-checkable Protocol with `.name: str`
    property + `resolve(secret) -> str | None`. Returning None
    means "I can't resolve this; try the next resolver"; raising
    `ResolutionError` means config-time failure (missing
    lookup_key etc.) the caller can fix.
  - `EnvVarResolver` — `provider=="env"` only. Reads
    `os.environ[secret.lookup_key]` (overridable via constructor
    `env=` for tests). Empty env-var values treated as None
    (operators export blank vars by accident; a blank "secret"
    is never the right answer).
  - `FileResolver` — `provider=="file"` only. Reads from a
    mounted path (Docker/BuildKit convention is
    `/run/secrets/<name>`). Refuses to read world- or
    group-writable files (deployment bug, not a secret).
    `strict_ownership=True` (default) refuses files owned by a
    uid other than the running process — defends against a
    sibling-container hijack (§6.10 Red-Team #1). Trailing
    whitespace stripped (BuildKit-mounted files end in `\n`).
  - `SshAgentResolver` — `provider=="ssh-agent"` only. Does NOT
    return key material (that's the SSH client's job); returns
    the socket PATH from `SSH_AUTH_SOCK` after `stat`-checking
    it's actually a socket. Callers forward `SSH_AUTH_SOCK` to
    child processes (git, ssh, scp).
  - `KeyringResolver` — `provider=="keyring"` only. Wraps
    `keyring.get_password(service, secret.lookup_key)`.
    Service defaults to `"sange"`. Returns None if keyring
    import fails (running in a container without a backend
    daemon) or the backend reports the credential missing —
    chain falls through cleanly.
  - `ChainResolver(*resolvers, strict=False)` walks the chain
    in order. Returns the first non-None result OR raises
    `ResolutionError` if `strict=True` OR `secret.required=True`.
    `resolve_detailed(secret)` returns a `ResolutionResult`
    (frozen dataclass with `secret_name` + `value` +
    `resolved_via` + `found`) for audit logging — the audit
    chain records WHICH resolver fired without recording the
    value. `ResolutionResult.__repr__` redacts the value.
  - `ResolutionError` raised on config failures + strict-mode
    misses.
  Production callers compose the chain in §6.10 preference order:
  `ChainResolver(SshAgentResolver(), FileResolver(),
  KeyringResolver(), EnvVarResolver())`. +41 tests in
  `test_secrets.py` covering: Secret model (construct / repr
  redacts / empty rejected / newline rejected x2 / frozen);
  redact (string / bytes / None); EnvVarResolver (present /
  missing returns None / empty treated as None / wrong-provider /
  missing lookup raises / Protocol satisfied); FileResolver
  (reads / strips newline / missing returns None /
  world-writable refused / group-writable refused / wrong-provider
  / missing lookup raises); SshAgentResolver (real Unix socket
  bind / no env var / non-socket path / nonexistent / wrong
  provider — POSIX-only); KeyringResolver (wrong-provider /
  missing lookup / service in name / fake-module credential
  resolved / fake-module credential missing); ChainResolver
  (first wins / falls through / all miss / strict raises /
  required raises / empty chain rejected / resolve_detailed
  records resolver name / not-found shape / result repr does
  NOT contain value — the most important security invariant).
  Suite 1706 → 1747 passing. ruff 0, mypy 0 (81 → 84 source
  files). v1.0+ remainder: Vault / AWS Secrets Manager /
  1Password / age / GPG resolvers + the `sange secrets`
  management CLI surface + `mlock` memory-protection for
  resolved values.
- **T-109 — Typed-phrase confirmation gate (`sange.utils.gate`).**
  Implements §7.0.5 — the destructive-op confirmation gate
  reused by every high-blast operation (`sange purge execute` in
  v1.0+, `sange publish` to prod, `sange release` tag+push,
  `sange recover` history rewrite). New module
  `src/sange/utils/gate.py`:
  - `typed_phrase_confirm(action, *, nonce=True, timeout_s=60,
    batch=False, max_attempts=3, input_fn, output_fn, clock_fn,
    nonce_fn, date_fn)` → `GateResult`. Prompts the operator for
    the canonical phrase, verifies a literal match, enforces a
    deadline across attempts.
  - `render_phrase(action, *, nonce=True, clock=None,
    nonce_fn=None)` produces `<ACTION>_<YYYY-MM-DD>_<8-hex>`
    when `nonce=True`, `<ACTION>_<YYYY-MM-DD>` otherwise. Action
    is upper-cased; only alphanumerics + underscore allowed.
  - `GateResult` frozen dataclass: `passed` + `outcome`
    (`"passed"` / `"failed"` / `"timed_out"` / `"skipped"`) +
    `attempts` + `elapsed_s` + `via` (`"tty"` / `"batch"`) +
    `phrase`. `.as_audit_payload()` returns the
    `{gate_passed, gate_outcome, attempts, elapsed_s, via,
    phrase}` dict per §7.0.5's required audit fields.
  - `GateError` raised on invalid args: `timeout_s` ≤ 0 or
    above 600s cap, `max_attempts` ≤ 0, action with illegal
    chars or empty.
  - Deadline enforcement: `elapsed = clock_fn() - start_ns` is
    checked BEFORE each input call. If past deadline, returns
    `outcome="timed_out"` without burning the attempt. The
    helper does NOT interrupt a blocked `input()` call — the
    operator who walks away is expected to ctrl-c; this is
    explicit in the docstring.
  - Mismatch handling: the operator's typed input is NEVER
    echoed back into the output stream — operators might be
    mid-typing of a secret they confused with the phrase. The
    output only says `✗ phrase mismatch (N attempt(s) left)`.
  - `batch=True` bypasses the prompt entirely, returns
    `passed=True / via=batch / outcome=skipped / attempts=0`.
    CALLERS MUST verify operation-specific precondition flags
    before passing `batch=True` (per §6.11.4 "--batch requires
    four explicit flags" for purge; other ops have their own).
  - Audit-chain integration is the CALLER's responsibility —
    the gate returns the payload shape, the caller threads
    into `chain.append(EventKind.PURGE_EXECUTE, payload=...)`.
    Same separation-of-concerns pattern as T-111a's plan model.
  +26 tests in `test_typed_phrase_gate.py`: render_phrase × 8
  (canonical / no-nonce / action uppercased / action with
  underscore / empty rejected / whitespace rejected / illegal
  chars / 8-hex nonce); happy-path × 2 (first try / second
  try); failures × 2 (max attempts exhausted / EOFError fast
  fail); timeout × 2 (before any attempt / between attempts);
  batch × 2 (skip prompt / still renders phrase for audit);
  validation × 4 (negative/zero/above-max timeout / zero
  max_attempts); audit payload × 3 (passed shape / failed
  shape / batch shape); prompt-output × 2 (phrase appears in
  prompt / mismatch does NOT echo typed input); frozen × 1.
  Suite 1680 → 1706 passing. ruff 0, mypy 0 (80 → 81 source
  files). **Unblocks v1.0+ T-203** (`sange purge execute` —
  the typed-phrase gate fires before the destructive transition;
  pairs with §6.11.2 `previewed → confirmed` state edge).
- **T-107a — `TerminalProfile` detection + glyph helpers (§7.0.2).**
  First slice of T-107. Pure capability detection — no `rich` /
  `textual` / `questionary` integration yet (those layer on top
  when concrete visual primitives need a profile to switch
  glyphs against). New module `src/sange/utils/terminal.py`:
  - `TerminalProfile` frozen dataclass: `is_tty` + `is_ci` +
    `encoding` + `has_utf8` + `is_windows` +
    `is_modern_windows_terminal` + `shell` + `color_mode`
    (Literal `truecolor`/`256`/`16`/`none`) + `use_emoji` +
    `use_unicode_box_chars` + `width`.
  - `detect_profile(*, env=None, stream=None)` implements §7.0.2
    rules in priority order: `NO_COLOR` always wins (explicit
    opt-out) → `FORCE_COLOR` (explicit opt-in over TTY
    heuristics) → `CI=true` (disables emoji, keeps Unicode
    structure) → Windows-no-WT_SESSION + non-UTF-8 (full ASCII
    fallback) → COLORTERM=truecolor → TERM contains 256 →
    TTY → non-TTY. Tests inject `env=` dict + `stream=` mock
    so every rule combination exercises without touching the
    real env.
  - `Glyphs` frozen dataclass: `success` / `failure` / `warning`
    / `in_progress` / `bullet` / `tree_branch` / `tree_last` /
    `tree_vert` / `section_rule`.
  - `glyphs_for(profile)` returns one of three shipped maps:
    `_GLYPHS_EMOJI` (`✅` `❌` `⚠️` `•` `├──`) for modern
    terminals, `_GLYPHS_UNICODE` (`✓` `✗` `△` `•` `├──`) for
    NO_COLOR + UTF-8, `_GLYPHS_ASCII` (`[OK]` `[FAIL]` `[WARN]`
    `*` `+--`) for legacy Windows + non-UTF-8.
  - `truncate_to_width(text, width, *, suffix="…")` uses
    `wcwidth.wcswidth` so CJK / emoji / zero-width-joiner
    sequences truncate correctly. Display width != string
    length — never use `len(s)` for column math.
  - `_detect_shell()` tries `shellingham` first, falls back to
    `SHELL` / `COMSPEC` env-var inspection if shellingham
    import fails or its detection raises. The §7.0.1 library
    pin mandates shellingham; the fallback honors the
    architecture-prompt allowance for graceful degradation.
  +27 tests in `test_terminal_profile.py` covering: every env
  rule (NO_COLOR wins over FORCE_COLOR / CI disables emoji /
  TERM=dumb / COLORTERM=truecolor / 256-color / TTY default
  16-color / piped output none); encoding (UTF-8 → emoji /
  cp1252 → no emoji / StringIO with no encoding falls back);
  Windows (legacy ASCII / modern with WT_SESSION); glyphs
  (emoji / NO_COLOR Unicode / legacy Windows ASCII / frozen);
  truncate (short / ellipsis / zero/negative width / wide
  chars / custom suffix / exact fit); profile frozen; width
  is positive int. Suite 1653 → 1680 passing. ruff 0, mypy 0
  (78 → 80 source files).
- **T-111f — `sange purge` CLI sub-app (8 verbs).** Sixth slice of
  §6.11 — the operator-facing surface for the v0.5 read-only purge
  story. Every v0.5 library capability is now reachable from the
  command line. New module `src/sange/cli/purge.py`:
  - `sange purge plan --path X --glob Y [--vcs git] [--remote URL]
    [--slug s] [--repo PATH] [--dry-run] [--batch]` — creates a
    `PurgePlan`, saves to `.sange/purge/<plan-id>/plan.json`,
    appends one `EventKind.PURGE_PLAN` event with `verb=plan` +
    `target_vcs` + `filter_count`. Prints the plan_id.
  - `sange purge list [--repo PATH]` — enumerates every saved plan
    with id + state, sorted lex (== chrono within a year).
  - `sange purge show PLAN_ID [--repo PATH]` — pretty-prints the
    plan JSON; raw under `--json`.
  - `sange purge mirror PLAN_ID [--source-url URL] [--repo PATH]` —
    runs `create_mirror`, updates `plan.mirror_path`, saves, audits.
  - `sange purge analyze PLAN_ID [--repo PATH]` — runs
    `analyze_mirror`, merges result into `plan.counts`. Refuses if
    `plan.mirror_path` is empty (operator must run `mirror` first).
  - `sange purge backup PLAN_ID [--repo PATH]` — tarball + sha256
    sidecar via `create_backup`, updates `plan.backup_path`.
  - `sange purge scan PLAN_ID [--repo PATH]` — `run_scanners`
    (gitleaks + trufflehog), updates `plan.scanner_results`.
    Gracefully reports "not installed" if a tool is absent rather
    than failing.
  - `sange purge abort PLAN_ID [--reason TEXT] [--repo PATH]` —
    transitions to `aborted` with the reason recorded.
  Every verb honors `--json`. Every state-changing verb pairs the
  library call with a `PURGE_PLAN`-kind audit event carrying the
  `verb` name + operation-specific extras — the library's own
  audit entries (clone, fsck, analyze subprocesses, etc.) thread
  onto the chain as leaf ops between two PURGE_PLAN bookends.
  Actor identity is `<getuser>@<hostname>` (best-effort, falls
  back to `unknown@unknown`). Wired into `main.py` via
  `app.add_typer(purge_app, name="purge", ...)`. cli-reference
  regenerated to include all 8 verbs. +20 tests in
  `test_cli_purge.py` covering: plan creates + JSON mode + no-filter
  rejected + unsupported VCS rejected + paths+globs combined + audit
  event recorded / list empty + lists + JSON mode / show prints +
  missing rejected + JSON / mirror → analyze flow end-to-end with
  source repo + analyze-without-mirror rejected / backup creates
  tarball + without-mirror rejected / scan with empty PATH gracefully
  reports + without-mirror rejected / abort transitions + reason
  recorded + double-abort rejected.
- **T-111e — Scanner library (gitleaks + trufflehog, §6.11.4 gate 8).**
  Fifth slice of §6.11 — pre-rewrite scanner pass against the
  mirror. The "regression detection" half (post-rewrite count
  must be ≤ pre-rewrite) lands in v1.0+ T-203 alongside
  destructive ops; this slice ships the baseline scan only. New
  module `src/sange/core/purge/scanners.py`:
  - `run_gitleaks(plan, mirror_path, *, audit_chain, actor,
    tool_path=None, timeout=300)` → `ScannerResult`. Invocation:
    `gitleaks git <mirror> --no-banner --report-format=json
    --report-path=-`. Parses the JSON-array output via
    `json.loads` and returns `len(array)` as findings_count.
    gitleaks exits 1 when it finds secrets — that's a valid
    "ran cleanly + found stuff" outcome, not a failure.
  - `run_trufflehog(plan, mirror_path, *, audit_chain, actor,
    tool_path=None, timeout=300)` → `ScannerResult`. Invocation:
    `trufflehog git file://<mirror> --json --no-update`. Parses
    NDJSON stdout — one finding per line, skipping malformed
    lines + empty `{}` heartbeats.
  - `run_scanners(...)` runs both sequentially and returns
    `(gitleaks_result, trufflehog_result)`. Sequential, not
    concurrent: doubling disk I/O against the same pack file
    isn't a win.
  - `tool_path: Path | None = None` parameter for testability —
    tests inject fake shell scripts at known paths so they don't
    depend on host gitleaks/trufflehog installation. Production
    callers default to `None` → `shutil.which()`.
  - When a tool is absent, the result has `available=False` /
    `returncode=-1` / `findings_count=0` / `event_id=""` and NO
    audit chain event is appended (the v0.5 scope treats these
    as soft preconditions, not hard fails).
  - `ScannerResult` frozen dataclass: `name` + `available` +
    `returncode` + `findings_count` + `event_id` +
    `transcript_path`. `.succeeded` property is strict
    (`available and returncode == 0`).
  - `ScannerError` raised on missing mirror.
  Output parsing reads from the streaming-helper transcript's
  `[stdout] ` prefix — same pattern as `mirror._capture_refs`
  and `analyzer._stdout_lines`. +12 tests in
  `test_purge_scanners.py` using fake shell scripts that produce
  controlled stdout (gitleaks-style JSON array / trufflehog-style
  NDJSON with heartbeats + malformed lines / various exit codes /
  not-on-PATH path) — fully hermetic, no host scanner dependency.
  One mid-impl bug caught: the initial fake-tool generator used
  `textwrap.dedent` over a heredoc whose embedded payload
  contained an unindented line; `dedent` then couldn't strip the
  common leading whitespace, leaving the shebang `#!/bin/sh`
  with 8 leading spaces — kernel rejected with errno 8 "Exec
  format error". Fixed by writing the script body without
  indentation (`"#!/bin/sh\nprintf '%s' '%s'\nexit %d\n"`).
  Suite 1621 → 1633 → 1653 passing (+12 from T-111e + 20 from T-111f).
- **T-111d — Backup tarball + sha256 sidecar (§6.11.4 gate 3).**
  Fourth slice of §6.11. Closes the "backup mirror" item from the
  §6.11.1 v0.5 scope row. New module
  `src/sange/core/purge/backup.py`:
  - `create_backup(plan, mirror_path, *, audit_chain, actor,
    timeout=600, clock=None)` → `BackupResult`. Pipeline:
    1. Validate mirror exists + is inside the plan dir.
    2. Compute tarball path as
       `<plan_dir>/backup-<YYYY-MM-DDTHH-MM-SSZ>.tar.gz`.
       Refuse to clobber an existing tarball (the operator would
       have to wait one second OR rm manually).
    3. `tar -czf <tarball> -C <mirror.parent> <mirror.name>`
       via `run_streamed` so the tar invocation lands one audit
       chain entry with a 0600 transcript. Archive root is the
       mirror dir's basename (git users' convention — extracts
       to a sibling dir rather than dumping bare-repo files).
    4. On non-zero tar exit, best-effort clean up the partial
       tarball (the "stale half-tarball mistaken for a good
       backup" foot-gun is real). Same cleanup if the tarball
       is empty post-tar.
    5. Stream-hash the tarball in 1 MiB chunks (bounded memory
       for multi-GB mirrors) → 64-char sha256 hex.
    6. Write `<tarball>.sha256` sidecar in `sha256sum`-compatible
       format (`<digest>  <basename>\n`) so the operator can
       `cd <plan_dir> && sha256sum -c <tarball>.sha256`.
  - `verify_backup(result)` → bool. Re-hashes the tarball
    in-place and compares to the recorded `sha256_hex`. Used by
    the destructive-ops slice (T-203+ v1.0) to confirm the
    backup is intact before consuming it for a rollback.
  - `BackupResult` frozen dataclass: `tarball_path` +
    `sidecar_path` + `sha256_hex` + `size_bytes` + `event_id`.
  - `BackupError` raised on every failure mode (missing mirror /
    mirror outside plan dir / tar exit / empty tarball /
    duplicate filename).
  Off-host backup destination (S3, age-encrypted file mount, etc.)
  mentioned in §6.11.4 is NOT in this slice — that's a v1.0
  concern when destructive ops need a recoverable backup.
  v0.5 ships the local tarball + sidecar; the operator can
  manually copy off-host. +14 tests in `test_purge_backup.py`
  covering: tarball written / lives in plan dir / sidecar
  contains hex + filename / sha256 matches independent
  `hashlib.sha256` of tarball bytes / tarball is valid gzip
  (opens with `tarfile.open` and contains the mirror dir name) /
  audit chain has 1 event / clock override pins the timestamp /
  missing mirror raises / mirror-outside-plan-dir rejected /
  duplicate timestamp rejected / verify-unchanged returns True /
  mutated tarball fails verify (append a byte) / missing tarball
  fails verify. Suite 1607 → 1621 passing. POSIX + tar +
  git on PATH gated.
- **T-111c — Mirror analyzer (`sange.core.purge.analyze_mirror`).**
  Third slice of §6.11 — the read-only `--analyze` capability that
  answers "what would happen if we purged these filters?" without
  touching the working repo. Operates against the mirror produced
  by T-111b. New module `src/sange/core/purge/analyzer.py`:
  - `analyze_mirror(plan, mirror_path, *, audit_chain, actor,
    timeout=300.0)` → `AnalysisResult`. Three-step pipeline:
    1. `git rev-list --all --objects` enumerates every reachable
       (sha, path) pair across all refs.
    2. `git cat-file --batch-all-objects
       --batch-check='%(objecttype) %(objectsize) %(objectname)'`
       enumerates every object with its type + size in a single
       subprocess (no stdin feeding needed — `--batch-all-objects`
       does the enumeration). Intersected with the candidate
       shas from step 1 + filtered to blob-typed objects.
    3. `git log --all --pretty=format:%H -- <matched_paths>`
       collects every commit that ever touched a matched path,
       deduped to a count.
  - Filter matching: `plan.filters.paths` (exact set
    intersection) + `plan.filters.globs` (`fnmatch` per glob);
    `replace_text_hashes` is NOT applied at the analyze layer —
    that's a redaction filter consumed by the destructive
    rewrite tool (v1.0).
  - When `matched_paths` is empty, the `git log` step is skipped
    entirely — 2 chain events instead of 3, `affected_commits =
    0`, `log_event_id = ""`. Avoids invoking `git log` with no
    pathspec (which would return every commit and silently lie).
  - `AnalysisResult` frozen dataclass: `affected_commits` +
    `matched_blob_shas` (sorted tuple) + `matched_paths` (sorted
    tuple) + `size_delta_bytes` (negative — reduction) +
    `revlist_event_id` + `catfile_event_id` + `log_event_id`.
    `.deleted_objects` property returns `len(matched_blob_shas)`.
    `.as_counts()` returns the `{affected_commits, deleted_objects,
    size_delta_bytes}` dict ready to merge into `plan.counts`
    per §6.11.6.
  - `AnalysisError` raised on non-git VCS / missing mirror /
    non-zero subprocess exit.
  - `affected_refs` intentionally NOT in this slice — needs
    per-ref reachability (`merge-base --is-ancestor` × refs ×
    affected_commits) and lands in T-111d alongside the preflight
    gates.
  Reads parseable output from the streaming-helper transcripts
  via the `[stdout] ` line prefix — same pattern as T-111b
  (transcript-as-source-of-truth). +15 tests in
  `test_purge_analyzer.py` covering: 2-version exact-path match
  (2 blobs / 2 commits / -32 bytes) / no-match returns zeros +
  empty event id + skips log subprocess / glob `notes/*` / glob
  `*.pem` (fnmatch * matches /) / paths + globs union /
  `as_counts()` shape (no `affected_refs` yet) / chain has 3
  events when matched / chain has 2 events when no match / event
  ids distinct / non-git VCS rejected / missing mirror raises /
  `deleted_objects` property / `matched_blob_shas` is sorted.
  Suite 1592 → 1607 passing. POSIX + `git`-on-PATH gated.
- **T-111b — Mirror clone helper (`sange.core.purge.create_mirror`
  / `verify_mirror`).** Second slice of §6.11 — implements gate 2
  per §6.11.4: "Sange refuses to run against the user's working
  repo. Auto-creates a mirror under `.sange/purge/<ts>/work.git/`
  from the configured remote." Uses T-110's `run_streamed` so the
  clone subprocess's full stdout/stderr lands on the audit chain
  with a 0600 transcript file. New module
  `src/sange/core/purge/mirror.py`:
  - `create_mirror(plan, repo_root, *, audit_chain, actor,
    source_url, clone_timeout, fsck_timeout)` →
    `MirrorResult`. Pipeline: refuse-clobber preflight →
    resolve source URL (override > `plan.target_repo.remote` >
    `file://<repo_root>` fallback) → `git clone --mirror
    <source> <dest>` via `run_streamed` → `git fsck --full
    --strict --no-progress` against the mirror → `git
    for-each-ref --format=%(objectname) %(refname)` baseline
    snapshot. Three audit chain events per call (clone /
    fsck / for-each-ref), each with a `phase` payload key
    and the plan_id. Non-zero clone or fsck exit raises
    `MirrorError` with the transcript path in the message.
  - `verify_mirror(plan, repo_root, *, audit_chain, actor,
    baseline_refs, timeout)` → `MirrorVerification`. Re-snapshots
    refs + diffs against the baseline. Result carries
    `added_refs` + `removed_refs` + `changed_refs` (tuples of
    `(ref, old_sha, new_sha)`) so the §6.11 Red-Team #2 race
    ("concurrent push lands between analyzed and executing")
    is detected at any granularity.
  - `MirrorResult` frozen dataclass — `path` + `source_url` +
    `clone_event_id` + `fsck_event_id` + `fsck_passed` +
    `refs` + `ref_count`.
  - `MirrorVerification` frozen dataclass — `passed` +
    `added_refs` + `removed_refs` + `changed_refs` +
    `current_event_id`.
  - `MirrorError` exception type.
  - Non-git VCS rejected at the entry point (`target_vcs !=
    "git"` raises) — SVN / Hg / P4 mirrors land in v1.0+.
  - Ref parsing reads from the audit transcript's `[stdout] `
    prefix (not from a captured stdout return) because the
    streaming helper owns the byte capture; this keeps the
    helper a single source of truth for what got recorded.
  +14 tests in `test_purge_mirror.py` covering: mirror dir
  created with `HEAD` + bare-repo layout / refs match source
  (3 refs: 2 branches + 1 tag) / fsck passes / audit chain has
  3 events with correct phases + prev_hash linkage / kind is
  GENERIC / clobber refused / non-git rejected / bad source URL
  raises with "exited" in message / plan.target_repo.remote
  fallback / verify-unchanged passes / verify detects removed
  refs (synthetic baseline) / verify detects changed refs /
  verify on missing mirror raises / verify detects injected
  ref (real `git update-ref` against mirror). Suite 1578 →
  1592 passing. POSIX + `git`-on-PATH gated via
  `pytestmark = [skipif win32, skipif no git]`.
- **T-111a — Purge subsystem foundation (PurgePlan + state machine
  + store).** First slice of §6.11 (the headline v0.5 capability).
  Ships data model + state machine + persistence only; no
  destructive paths yet (per §6.11.1 v0.5 = detection / analyze /
  dry-run / backup mirror / audit). New subsystem at
  `src/sange/core/purge/`:
  - `PurgeState` — 10 lifecycle states per §6.11.2
    (planned / preflight_passed / analyzed / previewed / confirmed
    / executing / verified / completed / aborted / rolled_back).
  - `_TRANSITIONS` adjacency map — forward-only graph with one
    re-entry edge (`rolled_back → planned` for retries).
    `TERMINAL_STATES` = `{completed, aborted}`. Pure module —
    no I/O, no audit chain, no plan persistence.
  - `IllegalTransition` exception lists the legal alternatives
    in its message so error rendering is precise (§7.0.8 exit 66).
  - `can_transition()` / `assert_transition()` / `legal_next()`
    helpers.
  - `PurgePlan` Pydantic v2 model with `extra="forbid"`. Fields:
    `schema_version` + `plan_id` (canonical
    `purge-<UTC-ISO>-<8-hex>` format) + `created_at` /
    `updated_at` (ISO 8601 UTC second-precision) + `created_by` +
    `state` + `target_vcs` (Literal git/svn/hg/p4) + `target_repo`
    (RepoMeta: path/remote/slug) + `filters` (paths + globs +
    `replace_text_hashes` — at least one non-empty, enforced by
    `model_validator`) + `counts` + `scanner_results` +
    `preflight_checks` (list of PreflightCheck:
    name+status∈{green,red,yellow,skipped}+detail) +
    `tool` (ToolMeta: name+version, populated when execute
    begins) + `backup_path` + `mirror_path` + `dry_run` + `batch`
    + `aborted_reason` + `rolled_back_reason`.
  - `plan.transition(new_state, *, reason="")` validates via
    `assert_transition` then updates `state` + `updated_at`,
    recording the reason on aborted/rolled_back transitions
    (in-band post-mortem so the audit log is the cross-reference,
    not the only source).
  - `new_plan_id()` generates `purge-<%Y-%m-%dT%H-%M-%SZ>-<8-hex>`
    via `secrets.token_hex(4)` — 32-bit nonce comfortably handles
    the "two purges started in the same second" case.
  - `PurgePlanStore` reads/writes
    `<repo>/.sange/purge/<plan-id>/plan.json` atomically
    (`tempfile.mkstemp` + `fsync` + `os.replace`). `save()` /
    `load()` / `exists()` / `list_plans()` / `plan_dir()` /
    `plan_path()`. `list_plans()` returns canonical-id-sorted
    list (== chronological for same-year plans). Invalid plan-id
    rejected by `plan_dir()` to keep arbitrary paths out of
    `<repo>/.sange/purge/`.
  - `PurgePlanNotFound` raised by `load()` on missing plan.
  Audit-chain integration (`EventKind.PURGE_PLAN`) is
  intentionally NOT here — the CLI layer (later slice) pairs each
  `plan.transition(...)` with `chain.append(...)` so the two
  concerns stay independent and the model is unit-testable
  without a chain dependency. +68 tests across
  `test_purge_state.py` (22 — enum / 14 parametrized legal
  transitions / 9 parametrized illegal / terminal states /
  legal_next / IllegalTransition message format) +
  `test_purge_plan.py` (46 — new_plan_id format & clock-override /
  PurgeFilters empty-rejection & every-combo / construction
  invariants / canonical id regex / updated_at >= created_at /
  extra-fields forbidden / unsupported VCS rejected / full happy-path
  transition chain / aborted+rolled_back reason recording /
  rolled_back→planned re-entry / updated_at advances / JSON
  round-trip / intermediate-state preservation / store save+load
  / atomic-no-tmp-residue / overwrite / list-sorted / skip
  non-plan dirs / skip plan-dir-without-plan.json / invalid id
  rejected). Suite 1510 → 1578 passing. ruff 0, mypy 0
  (70 → 73 source files). Foundation for T-111b (mirror clone),
  T-111c (analyzer), T-111d (preflight gates), T-111e (CLI surface).
- **T-110 — Subprocess streaming helper (`sange.core.streaming.run_streamed`).**
  Closes the §7.0.6 foundation. Every external command (`git`,
  `git-filter-repo`, `svnadmin`, `hg`, `p4`, `gitleaks`,
  `trufflehog`, `docker`, …) routes through this helper when its
  stdout/stderr need live capture rather than buffered string
  return. New subsystem at `src/sange/core/streaming/`:
  - `run_streamed(argv, *, audit_chain, actor, event_kind, payload,
    cwd, env, timeout, sigterm_grace, line_callback)` — sync-facing
    wrapper around an asyncio core. Spawns via
    `asyncio.create_subprocess_exec`, runs concurrent stdout/stderr
    readers via `asyncio.gather`. Single combined `[stream] line`
    write to the transcript per line so the asyncio scheduler
    can't slice the prefix between readers.
  - **Transcript retention**: every byte of both streams lands in
    `<repo>/.sange/audit/transcripts/<event_id>.log` with mode
    `0600` (via `os.open(...O_CREAT|O_EXCL, 0o600)` so umask
    can't downgrade the bits). The small audit-chain entry
    references the file's `transcript_hash`
    (`sha256(stdout_bytes ++ stderr_bytes)`) — chain stays
    compact, full transcript stays retrievable.
  - **Signal cascade** on timeout: SIGTERM first, wait
    `sigterm_grace` (default 5.0s), SIGKILL if the child still
    has a pid. The cascade tuple lands in both the
    `StreamResult` and the audit payload's `signal_cascade`
    field — `()` if clean, `("SIGTERM",)` if grace was enough,
    `("SIGTERM", "SIGKILL")` if escalation was needed.
  - **Audit integration**: one `AuditEvent` per invocation,
    `event_id` shared with the transcript filename. Payload
    carries `argv` + `returncode` + `duration_ms` +
    `transcript_hash` + `transcript_path` + `stdout_lines` +
    `stderr_lines` + `timed_out` + `signal_cascade`; the
    chain's `prev_hash` linkage threads through every
    consecutive call.
  - `StreamResult` frozen dataclass with `.succeeded` property
    (`returncode == 0 and not timed_out`).
  - `_build_proc_env` preserves PATH + HOME from the parent
    (reuses the lesson from `_lib/manpage._run`'s PATH bug).
    Pass `env=None` to inherit the full parent env; `env={}`
    to keep only the PATH+HOME base.
  +26 tests in `test_streaming.py` covering basic stdout/stderr/
  exit-code, transcript file (path / mode 0600 / both streams /
  per-stream marker), hash determinism (sha256 hex shape +
  exact-match against `hashlib.sha256(b"abc\n")` +
  stdout-then-stderr ordering), audit-chain integration
  (one event per invocation, payload metadata, kind override,
  prev_hash linkage), line_callback firing, timeout +
  SIGTERM-alone + SIGKILL escalation (via `trap '' TERM`),
  env-override + cwd + `env=None` inheritance. Suite 1484 →
  1510 passing. POSIX-only — `@pytest.mark.skipif(win32)` at
  module level (shell argv + 0600 + SIGTERM semantics don't
  port).
- **T-108 — Hash-chained audit JSONL (`sange audit`).** Closes the
  §7.0.7 audit-trail foundation that `docs/security/prompt-injection.md`
  references. New subsystem at `src/sange/core/audit/`:
  - `EventKind` enum covering every state-changing operation
    (`ai-call`, `commit-draft/submit/approve/reject/reopen/commit/push`,
    `gitignore-swap`, `hook-run`, `gate-add/remove`,
    `purge-plan/execute`, `generic`).
  - `AuditEvent` (frozen dataclass) — `id` + `kind` + `timestamp` +
    `actor` + `payload` + `prev_hash` + `this_hash`. `compute_hash`
    is deterministic (`sort_keys=True, separators=(",", ":")`) over
    every field except `this_hash`. `make_event()` builds with
    auto-populated `this_hash`. JSON round-trip via `to_json()` /
    `from_json()`.
  - `AuditChain` — per-repo writer over
    `<repo>/.sange/audit/<YYYY>-W<NN>.jsonl` ISO-week shards.
    Atomic append (`os.O_APPEND | os.O_CREAT` + single-syscall
    `os.write` + `os.fsync`) — a single JSONL line is well under
    POSIX `PIPE_BUF`, so the kernel guarantees atomicity. Chain
    head discovered by walking shards in chronological order.
  - `verify_chain(shard, *, starting_prev_hash)` /
    `verify_repo(repo_root)` — chain integrity check. Returns
    `VerificationReport` with `verified` / `records_checked` /
    `shards_checked` / `failure_kind` ∈
    `{malformed, hash-mismatch, chain-break}` / `failure_shard` /
    `failure_index` / `failure_event_id` / `failure_message`.
    Cross-shard verification threads each shard's tail hash as the
    next shard's `starting_prev_hash`.
  - **Four new CLI verbs** on `sange audit`:
    - `sange audit verify [--repo]` — walks the chain end-to-end.
      Exit 0 clean / 1 tampered / 2 usage.
    - `sange audit list [--week YYYY-WNN] [--kind KIND] [--repo]`
      — print + filter rows.
    - `sange audit tail [--n N] [--repo]` — most recent N records.
    - `sange audit append KIND --actor A [--payload JSON] [--repo]`
      — manually append (plugin entry point + manual testing).
    All four honor `--json`.
  Distinct from `sange.core.enhancer.AuditRecord` (single-AI-call
  provenance, fed into an `EventKind.AI_CALL` payload rather than
  the chain itself). +50 tests across `test_audit_event.py` (15) +
  `test_audit_chain.py` (9) + `test_audit_verify.py` (11) +
  `test_cli_audit.py` (15). Suite 1434 → 1484 passing.
  cli-reference regenerated. End-to-end smoke: empty repo verifies
  clean (0 records), 3 appends → verify clean, mid-chain `actor`
  mutation → verify fails with `hash-mismatch` at `failure_index=1`.
- **T-103 — Named-gate library (secret scanning + lint/test gates).**
  Layers four preconfigured hook bundles on top of the T-102 engine.
  - `Gate` / `GateEvent` / `GateRegistry` (`src/sange/core/hooks/gates.py`)
    — typed model loaded from `templates/hooks/<name>/manifest.toml`.
    Three-tier discovery (per-repo > per-user > shipped).
  - `add_gate(repo, gate, events=None)` copies the gate's script(s)
    into `<repo>/.sange/hooks/<event>/<priority>-<name>.<ext>` with
    +x. Idempotent — re-running marks the target `updated`.
  - `remove_gate(repo, gate, events=None)` removes only files this
    gate would have installed; foreign hooks left strictly alone.
  - **Four shipped gates** under `templates/hooks/`:
    - `gitleaks` (pre-commit, priority 05) — staged-diff secret
      scanner via `gitleaks protect --staged --redact`.
    - `trufflehog` (pre-commit, priority 10) — second-opinion
      verified-secret scanner.
    - `make-lint` (pre-commit, priority 20) — runs `make lint`
      after secret scanners.
    - `make-test` (pre-push, priority 50) — runs `make test` at
      push time (slow gates belong on pre-push, not pre-commit).
    Each gate script gracefully exits 64 (Sange SKIPPED) when its
    required tool isn't installed, with an install hint in stderr.
  - **Three new CLI verbs** on `sange hooks`:
    - `sange hooks gates [--repo]` — list every discoverable gate.
    - `sange hooks add GATE [--event ...] [--repo]` — install a
      gate; prints an install hint if the gate calls an external
      tool.
    - `sange hooks remove GATE [--event ...] [--repo]` — remove a
      gate's installed scripts.
  +27 tests in `test_hooks_gates.py` (20) + `test_cli_hooks.py`
  (extension, 7). Suite 1407 → 1434 passing. cli-reference
  regenerated.
- **T-102 slice 2 — `sange hooks` CLI sub-app + `.git/hooks/` shim
  writer.** Closes the foundation of T-102. Adds:
  - `sange.core.hooks.shim` module: `install_git_shims(repo,
    *, events, force)` writes `.git/hooks/<event>` scripts that
    delegate to `sange hooks run <event>`. The shim format
    `#!/usr/bin/env bash` + `SANGE-HOOK-SHIM v1 — managed by …`
    marker comment + `exec sange hooks run <event> "$@"` ensures
    the engine's stdin/stdout/stderr/exit-code passes through
    cleanly. tmp+fsync+rename + chmod-755 is the write pattern.
  - `install_git_shims` is idempotent — re-running it overwrites
    existing Sange-managed shims (marker version bumps stay
    honest) but never touches non-shim hook files unless
    `force=True`.
  - `uninstall_git_shims(repo, *, events)` removes only shims that
    carry the marker; foreign hooks are left untouched.
  - `sange hooks run EVENT [--repo --timeout --no-abort]` — invokes
    `HookEngine.run_event`, formats a table (status/pri/name/ms/
    exit), exits 1 iff any FAILED hook is reported.
  - `sange hooks list [--event EVENT] [--repo]` — discovers across
    every known event or one specified.
  - `sange hooks install [--event ...] [--force] [--repo]` —
    writes shims; surfaces counts of installed/updated/
    skipped-foreign/skipped-no-hooks.
  - `sange hooks uninstall [--event ...] [--repo]` — removes
    Sange shims.
  - `sange hooks status [--repo]` — per-event summary: hook count
    + shim install state (sange / foreign / absent).
  All verbs honor `--json`. End-to-end smoke: bash hooks at
  priorities 05/10/20/30 + one non-executable → `discover()`
  returns 4 (non-exec correctly skipped) → `install` writes one
  shim per event with hooks (18 events known, 2 installed,
  16 skipped-no-hooks) → `run pre-commit` returns table + exit
  code → `uninstall` removes only Sange shims.
  +24 tests across `test_hooks_shim.py` (10) + `test_cli_hooks.py`
  (14). Suite 1383 → 1407 passing. cli-reference regenerated.
  The named-gate library (gitleaks / trufflehog / make-test /
  make-lint shipping as preconfigured hooks) lands in T-103.
- **T-102 — Pre-commit hooks framework (slice 1).** First slice
  of the hooks engine (§7.4). New subsystem at
  `src/sange/core/hooks/`:
  - `HookResult` / `HookStatus` / `HookReport` — typed outcomes
    with exit-code conventions: `0` → PASSED, `128` → WARN,
    `64` → SKIPPED, anything else → FAILED.
  - `HookDescriptor` — one discovered hook with name + event +
    priority + path. Priority is 0-99 (validated).
  - `HookEngine` — discovers hooks at
    `<repo>/.sange/hooks/<event>/<priority>-<name>` (one-level,
    POSIX executable bit required) and runs them in priority
    order. Per-hook subprocess timeout (default 60s); per-event
    `abort_on_failed` (default True — first FAILED stops the
    rest, WARN/SKIPPED do not).
  - Environment discipline: `PATH` + `HOME` + caller-supplied
    `env_extra` + per-run `env` override, plus a
    `SANGE_HOOKS_REPO_ROOT` injected so hooks can locate the
    repo without hardcoding paths.
  - Captures stdout + stderr per hook (truncated to 64 KiB) +
    wall-clock duration.
  +23 tests in `tests/unit/test_hooks_engine.py`. Suite 1360 →
  1383 passing. The named-gate library (gitleaks / trufflehog /
  `make test` / `make lint` shipping as preconfigured hooks)
  lands in T-103 as a layer on top of this engine.
- **T-101d — Variant matrix (ADR-032).** Multi-dimensional
  stage × flavor model replaces the binary `dev | prod` axis as
  the v0.5 default.
  - `VariantStageAxis` — linear sequence of stage names.
  - `VariantDimension` — named flavor axis with value list.
  - `VariantConfig` — matrix declaration (stage axis + N
    dimensions); `make_variant(stage, **flavors)` validates a
    concrete tuple; `all_variants()` enumerates the full
    Cartesian product lazily.
  - `Variant` — `(stage, flavors)` tuple with canonical equality
    (sorted flavors), `slug()` for filesystem-safe identifiers,
    `has_flavor(dim, value)` for predicates.
  - `compose_variant(profiles, variant, registry)` — variant-aware
    composition. New TOML schema sections:
    `[patterns.stages.<name>]` and
    `[patterns.flavors.<dim>.<value>]`. Legacy `dev_only` /
    `prod_only` keys still work (treated as
    `patterns.stages.dev` / `patterns.stages.prod` aliases).
- **T-101e — `sange gitignore` CLI sub-app.** Five verbs wrap
  the engine surface:
    `sange gitignore swap PROFILES… --stage STAGE --repo PATH`
    `sange gitignore list [--category CAT] [--repo PATH]`
    `sange gitignore current [--repo PATH]`
    `sange gitignore detect [--repo PATH] [--depth N]`
    `sange gitignore recover [--repo PATH]`
  Each honors `--json` for machine-readable output. Errors
  surface as exit 2 (validation) or exit 1 (engine failures).
- **T-101f — Profile auto-detection.** `detect_profiles(repo,
  registry, *, walk_depth)` ranks profiles by structural match
  against the repo's top-level files. Required-pattern matches
  score 2× each; boost-pattern matches add +1. Result tuple is
  sorted by confidence desc + profile name. Skip-dirs list
  (`.git`, `node_modules`, `.sange`, `.venv`, …) avoids noise.
  Wired into `sange init --auto-detect-profile`: when exactly
  one top candidate exists, auto-swaps to it at stage=dev;
  multi-tie surfaces both candidates as a `status=tied` action;
  no candidates surfaces as `status=no-candidates`.
- **T-101a/b/c — Gitignore-swap engine (§6.5).** New subsystem
  under `src/sange/core/gitignore/`:
  - `Profile` + `load_profile()` — Pydantic-style dataclass loaded
    from `templates/gitignore-profiles/<category>/<name>.toml`.
    Schema: `[profile]` (name + category + display_name +
    version + maintainer + upstream_source + notes), `[detect]`
    (required_any + boost_any), `[patterns]` (always + dev_only +
    prod_only), `[extends]` (profiles[]).
  - `ProfileRegistry` — three-tier discovery (per-repo > per-user >
    shipped). Bad TOML is recorded in `load_detail.skipped` rather
    than fatal. Extends-chain resolution with cycle detection +
    diamond dedup.
  - `compose(profiles, stage, registry)` — produces the final
    `.gitignore` text. Dedupes globally (first occurrence wins),
    emits a per-profile section header, and a provenance comment
    block. Deterministic given a fixed clock.
  - `GitignoreSwap` — atomic swap with **SIGKILL-safe recovery**.
    Four-phase journal-then-write pattern:
      Phase 1. PREPARE  — tmp+fsync+rename a recovery journal at
                          `.sange/.recovery/swap-<utc>.json`
                          (records old + new content + sha256 +
                          phase).
      Phase 2. WRITE    — tmp+fsync+rename the new `.gitignore`;
                          advance journal phase.
      Phase 3. ACTIVATE — tmp+fsync+rename `.sange/.active-profile`;
                          advance journal phase.
      Phase 4. COMMIT   — delete the journal.
    `recover()` walks `.sange/.recovery/` at session start and
    rolls forward any in-progress journals from their recorded
    phase to completion. A `kill -9` at any byte boundary leaves
    the next session in a state that `recover()` can finish
    cleanly.
  - All 36 shipped profiles under `templates/gitignore-profiles/`
    load + validate; extends chains all resolve.
  +49 tests across `tests/unit/test_gitignore_{profile,registry,
  compose,swap}.py`. Suite 1252 → 1301 passing.
  T-101 is the second v0.5-beta deliverable after T-100 (SVN
  adapter). CLI surface (`sange gitignore swap` / `list` /
  `current`) is the next slice; the engine is API-stable today
  for plugin consumers.
- **T-100c — SVN adapter write methods (T-100 closed).** Twelve
  write methods complete the SVN `VCSDriver` contract:
  - `add` / `remove` / `revert_working_copy` — `svn add --parents`,
    `svn rm [--force]`, `svn revert -R`. Each rejects absolute paths
    per the Protocol's relative-path invariant.
  - `commit(repo, *, message, author_name, author_email, allow_empty,
    sign)` — runs `svn commit -m`. Returns a `CommitRef` with the
    new revision parsed from `svn commit`'s "Committed revision N."
    line. `author_email` rejected as partial-set (SVN has no
    separable email in its auth model); `allow_empty=True` rejected
    (SVN refuses no-op commits); `sign=True` rejected (no per-commit
    GPG signing in SVN).
  - `branch_create(repo, name, *, base="")` / `branch_delete(repo,
    name)` — server-side `svn copy` and `svn rm` against
    `^/branches/<name>`. base defaults to `trunk`. `branch_delete`
    refuses to delete trunk; the `force` flag is accepted for
    Protocol parity but has no SVN-side effect (SVN doesn't track
    merged-vs-unmerged).
  - `switch(repo, branch)` — `svn switch` to the resolved
    `^/branches/<name>` or `^/trunk` URL. Caret-prefixed URLs
    pass through verbatim so callers can target `^/tags/<name>`
    explicitly.
  - `fetch(repo)` — documented no-op. SVN has no fetch-without-apply
    primitive separate from `svn update`.
  - `pull(repo)` — `svn update`. Updates the WC to the latest
    revision.
  - `push(repo, *, force, force_with_lease)` — documented no-op
    returning `PushResult(was_no_op=True)`. SVN commits are
    immediately remote; `force` + `force_with_lease` are rejected
    (their semantics — rewriting remote history — don't exist in
    SVN's commit model).
  - `tag_create(repo, name, *, target_sha, message, sign)` /
    `tag_delete(repo, name)` — `svn copy` and `svn rm` against
    `^/tags/<name>`. `sign=True` rejected.
  - Internal: `_extract_committed_revision()` helper parses the
    "Committed revision N." line; `_branch_url()` resolves branch
    arguments to caret URLs.
  Two real bugs caught mid-implementation: (a) `svn info` on the WC
  root reports the *directory's* last-changed revision (not the
  commit's new revision) — `commit()` now parses `svn commit`'s
  stdout instead; (b) `current_branch()` was reading the cached
  `repo.metadata['relative_url']` which `switch()` couldn't refresh
  (frozen `Repo`) — `current_branch()` now always queries `svn info`.
  +26 tests in `tests/unit/test_svn_driver.py::TestSvnDriverWriteOps`
  (+5 in `TestExtractCommittedRevision`). Suite 1226 → 1252 passing.
- **T-100b — SVN adapter read methods.** Seven `VCSDriver` reads
  now ship for SVN, all gated on a real `svn` binary:
  - `log(repo, *, revision_range, max_count)` — runs
    `svn log --xml`, returns `tuple[CommitRef, ...]` newest-first.
    Revision range maps to SVN's `-r FROM:TO` syntax. `max_count=0`
    short-circuits (SVN rejects `--limit 0`). Empty-message
    commits get the placeholder `"(no commit message)"` so the
    non-empty-subject CommitRef invariant holds.
  - `diff(repo, *, paths, revision_range)` — runs `svn diff` and
    parses the unified-diff payload for `(files, insertions,
    deletions)` via a new `parse_diff_stat()`. Counts `Index:`
    markers for the file tally; falls back to `+++ ` headers when
    `Index:` is absent. `content_hash` = sha256 of the diff text.
  - `branches(repo)` — lists `^/trunk` (when present) + every
    directory under `^/branches/`. Current branch derived from
    `repo.metadata['relative_url']`; sort: current first then
    alphabetical.
  - `current_branch(repo)` — parses the WC's relative-URL
    (`^/trunk` / `^/branches/<name>` / `^/tags/<name>`) via a new
    `extract_branch_from_url()`. Returns `None` for repo-root
    checkouts or tag URLs (tags aren't branches).
  - `remotes(repo)` — SVN has one canonical remote (the
    repository root); returned as `RemoteInfo("origin", url)`.
  - `tags(repo)` — lists `^/tags/` dirs as `TagInfo` records;
    `created_at` carries SVN's commit timestamp.
  - `show_commit(repo, sha)` — single-revision log lookup. `sha`
    accepts numeric revisions and SVN's symbolic keywords
    (`HEAD` / `BASE` / `PREV` / `COMMITTED`).
  New parsers: `parse_log_xml`, `parse_ls_xml` + `SvnLsEntry`,
  `extract_branch_from_url`, `parse_diff_stat`. +36 tests in
  `tests/unit/test_svn_{parsers,driver}.py` (58 SVN tests total).
  T-100c (write methods — add / commit / branch_create / etc.)
  is the remaining slice.
- **T-100a — SVN adapter scaffold + read-only `detect` + `status`.**
  First slice of the Phase 2 (v0.5 beta) work. New module
  `src/sange/adapters/vcs/svn/` mirrors the Git adapter layout:
  - `_subprocess.py` — `run_svn()` with env-discipline (LC_ALL=C
    / LANG=C / LC_MESSAGES=C / PAGER=cat / SVN_EDITOR=true) +
    `SvnNotInstalled` / `SvnCommandFailed` errors.
  - `parsers.py` — pure XML parsers via `xml.etree.ElementTree`:
    `parse_version` (from `svn --version --quiet`),
    `parse_status_xml` (maps SVN's 14-state `item=` attribute
    to `FileState`), `parse_info_xml` (returns `SvnInfo` with
    revision / URL / repo root / UUID / WC root / schedule /
    depth / last-commit fields).
  - `driver.py` — `SvnDriver` class implementing `VCSDriver`'s
    `detect` + `capabilities` + `status`. Detect walks up from
    any starting path looking for `.svn/` (SVN 1.7+ stores
    metadata only at the WC root). Capabilities correctly
    report `supports_{stash,bisect,rebase,lfs}=False`.
    Remaining read + write methods raise `NotImplementedError`
    with `T-100b` / `T-100c` markers pointing at the follow-up.
  - 22 tests in `tests/unit/test_svn_{parsers,driver}.py`. Parser
    tests are pure-fixture (no subprocess); driver tests use real
    `svnadmin create` + `svn checkout` and are
    `@pytest.mark.skipif(_SVN is None)`-guarded.
  - `docs/tools/vcs/svn.md` updated to reflect that read-only
    `detect` + `status` ship today; the "v0.5+ planned" framing
    moved to the still-`NotImplementedError` methods.

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
