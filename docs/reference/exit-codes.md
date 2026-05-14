---
generated_by: tools/generators/exit_codes.py
generator_version: 1.0.0
generated_at: 2026-05-14T20:00:00Z
input_sha256: b988cd862be46984d327dc9b466962e0d92f78d4c1268f968eae20ba8df3aad8
output_sha256: 1eb540553029da512da2d995a9a0cc6479885fdb9a8c6b84126f79b135915db6
manual_edits_allowed: false
---
# Sange exit codes

> Generated from `src/sange/exit_codes.py` by `tools/generators/exit_codes.py` (T-G-008). Source-of-truth: §7.0.8 of `.design/sange-architecture-prompt.md`.

Every Sange CLI / TUI / daemon process exits with one of the values in the table below. Adding a new value is a SemVer-minor change; removing or repurposing one is a SemVer-major change.

## Reference

| Code | Constant | Category | Meaning |
| ---: | :--- | :--- | :--- |
| 0 | `OK` | Unix | Success — the command completed as expected. |
| 1 | `GENERIC_FAILURE` | Unix | Catch-all failure. Prefer a more specific code where one applies. |
| 2 | `INVALID_ARGUMENT` | Unix | Caller passed a bad CLI argument: unknown flag, malformed value, or missing required positional. |
| 64 | `PRECONDITION_FAILED` | Cross-cutting | A pre-flight gate refused the operation. Examples: a `sange purge` §6.11.4 gate returned red; a `sange publish` saw a concurrent VCS operation; `sange scaffold add` saw the target path already exists without `--force`. |
| 65 | `USER_ABORTED` | Cross-cutting | User cancelled the operation. Typed-phrase mismatch on a destructive gate (§7.0.5), explicit decline at a `questionary` prompt, or Ctrl-C during execution. |
| 66 | `VERIFICATION_FAILED` | Cross-cutting | Post-operation verification failed. Examples: `sange purge` §6.11.5 post-rewrite checks returned red; a release bundle's remote signature did not match (sigstore / cosign); a generator's `output_sha256` did not match the on-disk body (`tools/generators/verify_generated.py`). |
| 67 | `ROLLBACK_FAILED` | Cross-cutting | An attempted rollback could not complete cleanly — partial state may remain on disk. The audit log records the rollback attempt and the resulting state for hand-recovery. |
| 68 | `AUDIT_WRITE_REFUSED` | Cross-cutting | The audit log refused the write: no writable destination, destination is read-only, or the operator tried to redirect the global audit-log sink to `/dev/null` (refused per §6.11.6). |
| 69 | `SIGNATURE_VERIFICATION_FAILED` | Cross-cutting | A signed artifact failed signature verification. Examples: the `templates/MANIFEST.toml.sig` did not match the installed kit (ADR-020); a plugin manifest's sigstore signature was invalid; a release bundle's GPG signature did not verify. |
| 70 | `KIT_VERSION_DRIFT` | Subsystem | A materialized premade-kit fragment drifted from its registered version (`sange scaffold verify`, §7.11). Re-materialize the fragment or accept the drift with an explicit acknowledgement. |


## Programmatic access

```python
from sange.exit_codes import ExitCode, describe

raise SystemExit(ExitCode.USER_ABORTED)

# Or look up the description:
describe(ExitCode.VERIFICATION_FAILED)
```

## Cross-references

- Typed-phrase confirmation gate: `.design/sange-architecture-prompt.md` §7.0.5.
- Hash-chained audit JSONL: `.design/sange-architecture-prompt.md` §7.0.7.
- Purge subsystem pre-flight gates: `.design/sange-architecture-prompt.md` §6.11.4.
- Purge subsystem verification: `.design/sange-architecture-prompt.md` §6.11.5.
- Premade Operations Kit policy: `.design/sange-architecture-prompt.md` §6.12 (ADR-020).
- Generator integrity discipline: ADR-023 + ADR-029; verifier `tools/generators/verify_generated.py`.
