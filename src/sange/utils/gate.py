"""`typed_phrase_confirm` — §7.0.5 destructive-op confirmation gate.

> "A reusable helper `sange.utils.gate.typed_phrase_confirm(action,
> *, nonce=True, timeout_s=60)`: renders the phrase with a
> per-session nonce by default (`PURGE_2026-05-13_<8-hex>`) so a
> copy-pasted phrase from yesterday's log is invalid." — §7.0.5

The gate exists for operations whose blast radius warrants more
than a `[y/N]` confirm: `sange purge execute`, `sange publish` to
prod, `sange release` tag-and-push, `sange recover` history
rewrite. Every such operation receives a `GateResult` and threads
it into the audit chain (the gate itself does NOT touch the
chain — the caller wires it, same separation-of-concerns as the
T-111a plan model).

Per the spec:
  * Renders `<ACTION>_<YYYY-MM-DD>_<8-hex>` by default (nonce
    appended). `nonce=False` skips it (for tests / pre-baked
    phrases) but production callers always leave it on.
  * Times out (default 60s, max 600s — capped here in the helper,
    not by convention). Refuses to fall back to "press Y" — the
    operator types the literal phrase or the gate fails.
  * `batch=True` bypasses the gate entirely. CALLERS MUST validate
    operation-specific precondition flags before passing
    `batch=True` (§6.11.4 invariant: `--batch` requires four
    explicit flags for the purge subsystem; other ops have their
    own flag sets).
  * Records outcome / attempts / elapsed_s / via on `GateResult`
    for the caller's audit payload.

Tests inject `input_fn` / `clock_fn` / `nonce_fn` / `output_fn` so
no real stdin / clock / random is consulted. Production callers
let those default to `input` / `time.monotonic` / `secrets.token_hex` /
`typer.echo`.
"""

from __future__ import annotations

import datetime as _dt
import secrets
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

GateOutcome = Literal["passed", "failed", "timed_out", "skipped"]
GateVia = Literal["tty", "batch"]

_MAX_TIMEOUT_S: float = 600.0


class GateError(Exception):
    """Raised when typed_phrase_confirm is called with invalid args."""


@dataclass(frozen=True)
class GateResult:
    """Outcome of one gate invocation.

    Fields:
      * `passed`      — True iff the operator typed the phrase exactly
                        OR `batch=True` was honored.
      * `outcome`     — `"passed"` / `"failed"` / `"timed_out"` /
                        `"skipped"`. `failed` = max_attempts exhausted
                        without a match; `timed_out` = deadline hit;
                        `skipped` = batch mode.
      * `attempts`    — count of operator entries before the outcome
                        was decided (0 for `skipped`).
      * `elapsed_s`   — wall-clock seconds spent in the gate.
      * `via`         — `"tty"` if the operator was prompted, `"batch"`
                        if the gate was bypassed.
      * `phrase`      — the phrase that was expected. Returned so
                        callers can include it in the audit payload
                        for forensic reconstruction.

    `as_audit_payload()` returns the shape §7.0.5 mandates for the
    audit-log entry.
    """

    passed: bool
    outcome: GateOutcome
    attempts: int
    elapsed_s: float
    via: GateVia
    phrase: str

    def as_audit_payload(self) -> dict[str, object]:
        return {
            "gate_passed": self.passed,
            "gate_outcome": self.outcome,
            "attempts": self.attempts,
            "elapsed_s": round(self.elapsed_s, 3),
            "via": self.via,
            # Phrase is included so the audit reader can verify the
            # nonce + date in the rendered prompt; do NOT log the
            # operator's actual typed input (which may have leading
            # / trailing whitespace they corrected).
            "phrase": self.phrase,
        }


def render_phrase(
    action: str,
    *,
    nonce: bool = True,
    clock: _dt.datetime | None = None,
    nonce_fn: Callable[[], str] | None = None,
) -> str:
    """Produce the canonical phrase per §7.0.5.

    Format: `<ACTION>_<YYYY-MM-DD>_<8-hex>` when `nonce=True`,
    `<ACTION>_<YYYY-MM-DD>` otherwise. The date is taken from the
    `clock` parameter (default: now-UTC).

    `action` is upper-cased and whitespace-stripped; leading/trailing
    underscores are removed. `_` is the only non-alpha character
    permitted in the action (e.g. `PURGE`, `PURGE_PUSH`, `RECOVER`).
    """

    normalized = action.strip().upper()
    if not normalized:
        raise GateError("action must be a non-empty alphanumeric token")
    for ch in normalized:
        if not (ch.isalnum() or ch == "_"):
            raise GateError(
                f"action contains illegal character {ch!r}; "
                f"use alphanumerics + underscore only"
            )

    moment = clock or _dt.datetime.now(tz=_dt.UTC)
    date_part = moment.strftime("%Y-%m-%d")

    if not nonce:
        return f"{normalized}_{date_part}"

    nonce_str = nonce_fn() if nonce_fn else secrets.token_hex(4)
    return f"{normalized}_{date_part}_{nonce_str}"


def typed_phrase_confirm(
    action: str,
    *,
    nonce: bool = True,
    timeout_s: float = 60.0,
    batch: bool = False,
    max_attempts: int = 3,
    input_fn: Callable[[str], str] | None = None,
    output_fn: Callable[[str], None] | None = None,
    clock_fn: Callable[[], float] | None = None,
    nonce_fn: Callable[[], str] | None = None,
    date_fn: Callable[[], _dt.datetime] | None = None,
) -> GateResult:
    """Prompt the operator for the typed phrase + verify it back.

    Returns a `GateResult`. Callers must thread the result's
    `as_audit_payload()` into their PURGE_PLAN / PURGE_EXECUTE
    (or analogous) audit chain entry — the gate itself does NOT
    touch the chain.

    Args:
      action:       short uppercase action token (`PURGE`, `PUBLISH`,
                    `RELEASE`, `RECOVER`).
      nonce:        when True (default), append a per-invocation
                    8-hex nonce so prior log lines don't replay.
      timeout_s:    total wall-clock seconds for ALL attempts; max
                    600 (anything higher raises GateError).
      batch:        when True, skip the prompt entirely and return
                    `passed=True / via=batch / outcome=skipped`.
                    CALLERS MUST verify operation-specific
                    precondition flags before passing `batch=True`.
      max_attempts: maximum operator entries before failure (default 3).
      input_fn:     test-only — replace `input(prompt)`. Defaults to
                    builtins.input.
      output_fn:    test-only — replace `typer.echo`. Defaults to
                    `print` (so the module has no typer dep at the
                    function level).
      clock_fn:     test-only — replace `time.monotonic`. Defaults
                    to `time.monotonic`.
      nonce_fn:     test-only — replace `secrets.token_hex(4)`.
      date_fn:      test-only — replace `datetime.now(UTC)` for the
                    date portion of the phrase.
    """

    if timeout_s <= 0:
        raise GateError(f"timeout_s must be positive (got {timeout_s!r})")
    if timeout_s > _MAX_TIMEOUT_S:
        raise GateError(
            f"timeout_s exceeds max {_MAX_TIMEOUT_S}s (got {timeout_s!r})"
        )
    if max_attempts <= 0:
        raise GateError(
            f"max_attempts must be positive (got {max_attempts!r})"
        )

    phrase = render_phrase(
        action,
        nonce=nonce,
        clock=date_fn() if date_fn else None,
        nonce_fn=nonce_fn,
    )

    if batch:
        return GateResult(
            passed=True,
            outcome="skipped",
            attempts=0,
            elapsed_s=0.0,
            via="batch",
            phrase=phrase,
        )

    _clock = clock_fn or time.monotonic
    _input = input_fn or input
    _output = output_fn or print

    start_ns = _clock()
    prompt = f"Type {phrase!r} to confirm: "

    _output("⚠  This action requires a typed-phrase confirmation.")
    _output(f"   Expected phrase: {phrase}")
    _output(f"   Deadline: {timeout_s:.0f} seconds. Max attempts: {max_attempts}.")

    attempts = 0
    while attempts < max_attempts:
        elapsed = _clock() - start_ns
        if elapsed >= timeout_s:
            return GateResult(
                passed=False,
                outcome="timed_out",
                attempts=attempts,
                elapsed_s=elapsed,
                via="tty",
                phrase=phrase,
            )

        try:
            entered = _input(prompt)
        except EOFError:
            # stdin closed mid-prompt — treated as a failed attempt,
            # but immediately surface "failed" rather than burning more
            # attempts on a stream that won't yield further input.
            return GateResult(
                passed=False,
                outcome="failed",
                attempts=attempts + 1,
                elapsed_s=_clock() - start_ns,
                via="tty",
                phrase=phrase,
            )

        attempts += 1
        if entered == phrase:
            return GateResult(
                passed=True,
                outcome="passed",
                attempts=attempts,
                elapsed_s=_clock() - start_ns,
                via="tty",
                phrase=phrase,
            )

        # Wrong phrase — surface the mismatch but don't echo the
        # operator's input back (avoids the "muscle-memory typing
        # something secret" foot-gun).
        _output(f"   ✗ phrase mismatch ({max_attempts - attempts} attempt(s) left)")

    return GateResult(
        passed=False,
        outcome="failed",
        attempts=attempts,
        elapsed_s=_clock() - start_ns,
        via="tty",
        phrase=phrase,
    )


__all__ = [
    "GateError",
    "GateOutcome",
    "GateResult",
    "GateVia",
    "render_phrase",
    "typed_phrase_confirm",
]
