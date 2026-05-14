"""Canonical Sange exit-code catalog.

Source-of-truth for every value a Sange CLI/TUI/daemon process exits with.
The exit codes are documented in §7.0.8 of `.design/sange-architecture-prompt.md`
and surfaced as `docs/reference/exit-codes.md` by `tools/generators/exit_codes.py`
(T-G-008). Both files are kept in sync via the generator pipeline; this
module is the machine-readable original.

Categories:

  * 0       Success.
  * 1, 2    Common Unix conventions (generic failure, invalid argument).
  * 64-69   Cross-cutting failure modes — apply to many subcommands.
  * 70+     Subsystem-specific failures the cross-cutting block can't express.

Stability:

  * Values are part of Sange's public API surface. Per ADR-026's stability
    discipline, once a value is published in a tagged release it does not
    change semantics.
  * Adding a new value is a minor-version change (SemVer 2.0.0).
  * Removing or repurposing a value is a major-version change.

Usage:

    from sange.exit_codes import ExitCode

    raise SystemExit(ExitCode.USER_ABORTED)
    sys.exit(ExitCode.OK)
    if status != ExitCode.OK: ...
"""

from __future__ import annotations

from enum import IntEnum
from types import MappingProxyType


class ExitCode(IntEnum):
    """Sange exit codes — see module docstring for the §-anchor source."""

    # ----- 0..2: Unix conventions -------------------------------------------
    OK = 0
    GENERIC_FAILURE = 1
    INVALID_ARGUMENT = 2

    # ----- 64..69: Cross-cutting failure modes ------------------------------
    PRECONDITION_FAILED = 64
    USER_ABORTED = 65
    VERIFICATION_FAILED = 66
    ROLLBACK_FAILED = 67
    AUDIT_WRITE_REFUSED = 68
    SIGNATURE_VERIFICATION_FAILED = 69

    # ----- 70+: Subsystem-specific ------------------------------------------
    KIT_VERSION_DRIFT = 70


# Human-readable description for each code. Enum members in Python's stdlib
# don't carry per-member docstrings, so we keep descriptions in a parallel
# mapping that the docs generator (T-G-008) reads. Wrapped in a
# MappingProxyType so callers can't mutate it at runtime.
_DESCRIPTIONS: dict[ExitCode, str] = {
    ExitCode.OK: (
        "Success — the command completed as expected."
    ),
    ExitCode.GENERIC_FAILURE: (
        "Catch-all failure. Prefer a more specific code where one applies."
    ),
    ExitCode.INVALID_ARGUMENT: (
        "Caller passed a bad CLI argument: unknown flag, malformed value, "
        "or missing required positional."
    ),
    ExitCode.PRECONDITION_FAILED: (
        "A pre-flight gate refused the operation. Examples: a `sange purge` "
        "§6.11.4 gate returned red; a `sange publish` saw a concurrent VCS "
        "operation; `sange scaffold add` saw the target path already exists "
        "without `--force`."
    ),
    ExitCode.USER_ABORTED: (
        "User cancelled the operation. Typed-phrase mismatch on a "
        "destructive gate (§7.0.5), explicit decline at a `questionary` "
        "prompt, or Ctrl-C during execution."
    ),
    ExitCode.VERIFICATION_FAILED: (
        "Post-operation verification failed. Examples: `sange purge` "
        "§6.11.5 post-rewrite checks returned red; a release bundle's "
        "remote signature did not match (sigstore / cosign); a generator's "
        "`output_sha256` did not match the on-disk body "
        "(`tools/generators/verify_generated.py`)."
    ),
    ExitCode.ROLLBACK_FAILED: (
        "An attempted rollback could not complete cleanly — partial state "
        "may remain on disk. The audit log records the rollback attempt and "
        "the resulting state for hand-recovery."
    ),
    ExitCode.AUDIT_WRITE_REFUSED: (
        "The audit log refused the write: no writable destination, "
        "destination is read-only, or the operator tried to redirect the "
        "global audit-log sink to `/dev/null` (refused per §6.11.6)."
    ),
    ExitCode.SIGNATURE_VERIFICATION_FAILED: (
        "A signed artifact failed signature verification. Examples: the "
        "`templates/MANIFEST.toml.sig` did not match the installed kit "
        "(ADR-020); a plugin manifest's sigstore signature was invalid; a "
        "release bundle's GPG signature did not verify."
    ),
    ExitCode.KIT_VERSION_DRIFT: (
        "A materialized premade-kit fragment drifted from its registered "
        "version (`sange scaffold verify`, §7.11). Re-materialize the "
        "fragment or accept the drift with an explicit acknowledgement."
    ),
}

DESCRIPTIONS: MappingProxyType[ExitCode, str] = MappingProxyType(_DESCRIPTIONS)


def describe(code: ExitCode) -> str:
    """Look up the human-readable description for a given ExitCode."""

    return DESCRIPTIONS[code]


__all__ = ["DESCRIPTIONS", "ExitCode", "describe"]
