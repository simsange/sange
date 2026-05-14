"""Durable monotonic counter for commit-JSON filenames.

Per §6.8.1 every commit JSON gets a four-digit monotonic counter
(`NNNN-<type>-<scope>-<short-subject>.json`). The counter lives at
`${repo}/.sange/commits/.counter` and survives across crashes.

Implementation:

  * `next_number()` atomically: read → increment → write tmp file →
    fsync → rename. The rename is POSIX-atomic on every supported
    filesystem.
  * `current_number()` is read-only and idempotent.
  * On corruption (non-integer content, negative, etc.) the counter
    rolls forward — it re-scans the commits directory for the highest
    `NNNN-` prefix, increments past it, and writes that. Same idea as
    the §6.5 gitignore-swap SIGKILL recovery: the file system is the
    source of truth.

Concurrency: a future-version `sanged` daemon will serialize counter
allocation; until then we rely on the rename's atomicity.
"""

from __future__ import annotations

import os
import re
import tempfile
from pathlib import Path


COUNTER_FILENAME = ".counter"
_JSON_NAME_RE = re.compile(r"^(\d{4,})-")


class CounterError(Exception):
    """Counter file is unreadable / unrecoverable. Rare; usually FS issue."""


class CommitCounter:
    """File-backed monotonic counter for `.sange/commits/`.

    Construct with the directory containing `.counter`. Calling
    `.next_number()` reserves the next integer atomically; reading
    `.current_number()` is non-mutating.
    """

    def __init__(self, commits_dir: Path) -> None:
        self.commits_dir = commits_dir
        self.path = commits_dir / COUNTER_FILENAME

    def current_number(self) -> int:
        """Return the highest counter ever issued, or 0 if untouched.

        Reads the counter file; recovers from a missing or corrupted file
        by re-scanning `commits_dir` for the highest `NNNN-` filename.
        """

        if not self.commits_dir.exists():
            return 0

        if self.path.is_file():
            try:
                raw = self.path.read_text(encoding="utf-8").strip()
                value = int(raw)
                if value < 0:
                    raise ValueError(f"negative counter: {value}")
                return value
            except (ValueError, OSError):
                # Fall through to filesystem-based recovery.
                pass

        return self._recover_from_filesystem()

    def next_number(self) -> int:
        """Allocate and return the next counter, atomically updating disk."""

        self.commits_dir.mkdir(parents=True, exist_ok=True)
        current = self.current_number()
        nxt = current + 1
        self._atomic_write(nxt)
        return nxt

    # ----- internals -------------------------------------------------- #

    def _recover_from_filesystem(self) -> int:
        """Re-derive the counter from existing `NNNN-*.json` filenames.

        Returns the highest `NNNN` ever observed (0 when none exist),
        then bumps the on-disk counter to match so future writes don't
        need to re-scan.
        """

        if not self.commits_dir.is_dir():
            return 0
        highest = 0
        for entry in self.commits_dir.iterdir():
            if entry.is_file() and entry.suffix == ".json":
                m = _JSON_NAME_RE.match(entry.name)
                if m:
                    n = int(m.group(1))
                    if n > highest:
                        highest = n
        # Persist the recovered value so subsequent reads avoid the scan.
        if highest > 0:
            try:
                self._atomic_write(highest)
            except OSError:
                # If we can't write, fall back to the scan-every-time mode.
                # Read-side is still correct.
                pass
        return highest

    def _atomic_write(self, value: int) -> None:
        """Write `value` to the counter file via rename-after-fsync."""

        if value < 0:
            raise CounterError(f"refusing to write negative counter {value}")
        encoded = (str(value) + "\n").encode("utf-8")
        fd, tmp_name = tempfile.mkstemp(
            prefix=f".{COUNTER_FILENAME}.",
            suffix=".tmp",
            dir=str(self.commits_dir),
        )
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(encoded)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp_name, self.path)
            try:
                os.chmod(self.path, 0o644)
            except OSError:
                pass
        except BaseException:
            try:
                Path(tmp_name).unlink(missing_ok=True)
            except OSError:
                pass
            raise


__all__ = ["CommitCounter", "COUNTER_FILENAME", "CounterError"]
