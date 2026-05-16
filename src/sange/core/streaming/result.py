"""`StreamResult` — outcome of one streamed subprocess invocation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class StreamResult:
    """One subprocess invocation's recorded outcome.

    Fields:
      * `returncode`        — child's exit status; `-9` on SIGKILL,
                              `-15` on SIGTERM-without-handler.
      * `transcript_hash`   — sha256 hex of `stdout_bytes ++ stderr_bytes`.
                              Deterministic re-hash if you replay the
                              two byte sequences in the same order.
      * `transcript_path`   — absolute path to the per-event log file.
                              Mode is `0600` (owner read/write only).
      * `event_id`          — audit chain event id; the transcript
                              file basename is `<event_id>.log`.
      * `duration_ms`       — wall-clock subprocess duration.
      * `timed_out`         — True iff the `timeout` parameter triggered
                              the SIGTERM cascade.
      * `signal_cascade`    — tuple of signal names sent ("SIGTERM",
                              optionally followed by "SIGKILL"). Empty
                              tuple if the process exited cleanly.
      * `stdout_lines`      — newline-delimited line count on stdout.
      * `stderr_lines`      — newline-delimited line count on stderr.
    """

    returncode: int
    transcript_hash: str
    transcript_path: Path
    event_id: str
    duration_ms: int
    timed_out: bool
    signal_cascade: tuple[str, ...]
    stdout_lines: int
    stderr_lines: int

    @property
    def succeeded(self) -> bool:
        """True iff returncode is 0 and the process wasn't killed."""

        return self.returncode == 0 and not self.timed_out


__all__ = ["StreamResult"]
