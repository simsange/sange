"""`sange.core.streaming` — subprocess streaming helper (§7.0.6).

Every external command (`git`, `git-filter-repo`, `bfg.jar`, `svnadmin`,
`hg`, `p4`, `gitleaks`, `trufflehog`, `docker`, …) routes through
`run_streamed()` when its stdout/stderr need to be captured *as it runs*
rather than buffered into a single string return.

Three guarantees per §7.0.6:

  1. **Concurrent reads.** Both pipes drain in parallel (asyncio gather)
     so the streams never race for the subprocess's write buffer.
  2. **Lossless retention.** Every byte of both streams lands in a
     transcript file at
     `<repo>/.sange/audit/transcripts/<event_id>.log` with mode `0600`.
     The transcript_hash (sha256 of stdout-bytes ++ stderr-bytes) goes
     into the audit entry's payload — the small entry references the
     full retention.
  3. **Signal cascade on timeout.** SIGTERM is sent first; after
     `sigterm_grace` seconds (default 5.0) the process is SIGKILL'd.
     The cascade tuple lands in the audit payload + StreamResult.

The helper integrates with the just-shipped `AuditChain` (T-108) so
every streamed invocation produces exactly one chain entry — the
audit chain is the system of record, the transcript file is the
forensic retention.
"""

from __future__ import annotations

from sange.core.streaming.result import StreamResult
from sange.core.streaming.streamer import LineCallback, run_streamed

__all__ = [
    "LineCallback",
    "StreamResult",
    "run_streamed",
]
