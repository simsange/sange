"""`run_streamed` — async-cored, sync-facing subprocess streaming helper.

Surface (sync, for use from typer commands + ordinary Python):

    result = run_streamed(
        ["git", "fetch", "origin"],
        audit_chain=chain,
        event_kind=EventKind.GENERIC,
        actor="alice@cli",
        timeout=30.0,
    )

The function spawns the subprocess via `asyncio.create_subprocess_exec`,
runs concurrent readers over both pipes, writes every byte to a
transcript file (mode 0600) under `<repo>/.sange/audit/transcripts/`,
and appends one `AuditEvent` to the chain referencing the
transcript_hash + relative path. On `timeout` the function sends
SIGTERM, waits `sigterm_grace`, then SIGKILL.

The async core is internal — callers always use the sync wrapper
because (a) typer commands are sync, (b) Sange has no async
event-loop yet, and (c) the spec doesn't motivate async fan-out
(we run one subprocess at a time per gate).
"""

from __future__ import annotations

import asyncio
import hashlib
import os
import time
import uuid
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

from sange.core.audit import AuditChain, EventKind
from sange.core.streaming.result import StreamResult

# Callback signature: (stream_name, line) — `stream_name` is "stdout"
# or "stderr"; `line` is the decoded line with its trailing newline
# already stripped.
LineCallback = Callable[[str, str], None]


class StreamingError(Exception):
    """Raised when the streamer itself (not the child) can't proceed."""


def run_streamed(
    argv: Sequence[str],
    *,
    audit_chain: AuditChain,
    actor: str,
    event_kind: EventKind | str = EventKind.GENERIC,
    payload: dict[str, Any] | None = None,
    cwd: Path | None = None,
    env: Mapping[str, str] | None = None,
    timeout: float | None = None,
    sigterm_grace: float = 5.0,
    line_callback: LineCallback | None = None,
) -> StreamResult:
    """Run `argv` to completion, streaming both pipes + writing a transcript.

    Args:
      argv:           subprocess argument vector. argv[0] must be on PATH
                      (or be an absolute path).
      audit_chain:    `AuditChain` instance used to (a) discover the
                      transcripts dir, (b) append the resulting event.
      actor:          audit-entry actor identifier.
      event_kind:     audit-entry `EventKind` (default GENERIC).
      payload:        additional payload fields merged into the audit
                      entry. The streamer overwrites the keys
                      `argv` / `returncode` / `duration_ms` /
                      `transcript_hash` / `transcript_path` /
                      `stdout_lines` / `stderr_lines` / `timed_out` /
                      `signal_cascade` if the caller passes them
                      (those describe what the streamer just did).
      cwd:            subprocess cwd; defaults to caller's cwd.
      env:            extra env vars merged on top of the streamer's
                      base (PATH + HOME from the parent). Pass `{}` to
                      keep only the base. Pass `None` to inherit.
      timeout:        seconds before the SIGTERM cascade fires; `None`
                      means wait forever (caller is responsible for
                      child progress).
      sigterm_grace:  seconds between SIGTERM and SIGKILL (default 5.0).
      line_callback:  optional per-line hook. Called synchronously from
                      the reader task — do not block.
    """

    return asyncio.run(
        _run_streamed_async(
            argv=tuple(argv),
            audit_chain=audit_chain,
            actor=actor,
            event_kind=event_kind,
            payload=payload,
            cwd=cwd,
            env=env,
            timeout=timeout,
            sigterm_grace=sigterm_grace,
            line_callback=line_callback,
        )
    )


async def _run_streamed_async(
    *,
    argv: tuple[str, ...],
    audit_chain: AuditChain,
    actor: str,
    event_kind: EventKind | str,
    payload: dict[str, Any] | None,
    cwd: Path | None,
    env: Mapping[str, str] | None,
    timeout: float | None,
    sigterm_grace: float,
    line_callback: LineCallback | None,
) -> StreamResult:
    if not argv:
        raise StreamingError("argv must be non-empty")
    if sigterm_grace < 0:
        raise StreamingError("sigterm_grace must be non-negative")

    event_id = str(uuid.uuid4())
    transcripts_dir = audit_chain.audit_dir / "transcripts"
    try:
        transcripts_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise StreamingError(
            f"cannot create transcripts dir {transcripts_dir}: {exc}"
        ) from exc

    transcript_path = transcripts_dir / f"{event_id}.log"

    # Open transcript with mode 0600 via low-level os.open — the umask
    # would otherwise mask the bits down to 0644 on most systems.
    try:
        fd = os.open(
            str(transcript_path),
            os.O_WRONLY | os.O_CREAT | os.O_EXCL,
            0o600,
        )
    except OSError as exc:
        raise StreamingError(
            f"cannot create transcript {transcript_path}: {exc}"
        ) from exc

    stdout_buffer = bytearray()
    stderr_buffer = bytearray()
    signal_cascade: list[str] = []
    timed_out = False

    proc_env = _build_proc_env(env)

    transcript_file = os.fdopen(fd, "wb")
    start_ns = time.monotonic_ns()

    try:
        try:
            proc = await asyncio.create_subprocess_exec(
                *argv,
                cwd=str(cwd) if cwd is not None else None,
                env=proc_env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except FileNotFoundError as exc:
            raise StreamingError(
                f"executable not found: {argv[0]!r} — {exc}"
            ) from exc

        async def reader(
            stream: asyncio.StreamReader | None,
            name: str,
            buffer: bytearray,
        ) -> None:
            if stream is None:
                return
            while True:
                line = await stream.readline()
                if not line:
                    return
                buffer.extend(line)
                # Single combined write so the prefix can't be sliced
                # between the two readers by the asyncio scheduler.
                transcript_file.write(f"[{name}] ".encode("ascii") + line)
                if line_callback is not None:
                    decoded = line.decode("utf-8", errors="replace")
                    line_callback(name, decoded.rstrip("\n"))

        stdout_task = asyncio.create_task(
            reader(proc.stdout, "stdout", stdout_buffer)
        )
        stderr_task = asyncio.create_task(
            reader(proc.stderr, "stderr", stderr_buffer)
        )

        try:
            if timeout is not None:
                await asyncio.wait_for(proc.wait(), timeout=timeout)
            else:
                await proc.wait()
        except TimeoutError:
            timed_out = True
            # SIGTERM first; grace; SIGKILL as fallback.
            try:
                proc.terminate()
                signal_cascade.append("SIGTERM")
            except ProcessLookupError:
                pass
            try:
                await asyncio.wait_for(proc.wait(), timeout=sigterm_grace)
            except TimeoutError:
                try:
                    proc.kill()
                    signal_cascade.append("SIGKILL")
                except ProcessLookupError:
                    pass
                await proc.wait()

        # Drain remaining output. The readers exit naturally on EOF
        # once the pipes are closed (which happens when the child
        # terminates).
        await asyncio.gather(stdout_task, stderr_task, return_exceptions=True)
    finally:
        try:
            transcript_file.flush()
            os.fsync(transcript_file.fileno())
        except OSError:
            pass
        transcript_file.close()

    end_ns = time.monotonic_ns()
    duration_ms = (end_ns - start_ns) // 1_000_000

    # Hash over (stdout || stderr) — deterministic if the two byte
    # sequences are replayed. Matches §7.0.6's "sha256 of the
    # concatenated streams".
    hasher = hashlib.sha256()
    hasher.update(bytes(stdout_buffer))
    hasher.update(bytes(stderr_buffer))
    transcript_hash = hasher.hexdigest()

    # Newline count = LF byte count. Lines without trailing LF aren't
    # counted — that's the conventional shell tally and matches `wc -l`.
    stdout_line_count = bytes(stdout_buffer).count(b"\n")
    stderr_line_count = bytes(stderr_buffer).count(b"\n")

    returncode = proc.returncode if proc.returncode is not None else -1

    payload_dict: dict[str, Any] = dict(payload) if payload else {}
    payload_dict.update(
        {
            "argv": list(argv),
            "returncode": returncode,
            "duration_ms": duration_ms,
            "transcript_hash": transcript_hash,
            "transcript_path": _relative_or_absolute(
                transcript_path, audit_chain.repo_root,
            ),
            "stdout_lines": stdout_line_count,
            "stderr_lines": stderr_line_count,
            "timed_out": timed_out,
            "signal_cascade": list(signal_cascade),
        }
    )

    audit_chain.append(
        event_kind,
        actor=actor,
        payload=payload_dict,
        event_id=event_id,
    )

    return StreamResult(
        returncode=returncode,
        transcript_hash=transcript_hash,
        transcript_path=transcript_path,
        event_id=event_id,
        duration_ms=duration_ms,
        timed_out=timed_out,
        signal_cascade=tuple(signal_cascade),
        stdout_lines=stdout_line_count,
        stderr_lines=stderr_line_count,
    )


def _build_proc_env(extra: Mapping[str, str] | None) -> dict[str, str]:
    """Construct the subprocess env.

    Base preserves PATH + HOME (mirrors the git wrapper's pattern from
    `src/sange/adapters/vcs/git/_subprocess.py` for the PATH-bug
    lesson). Caller-supplied keys layer on top — pass `None` to inherit
    the parent's whole env, `{}` to keep only the PATH+HOME base.
    """

    if extra is None:
        # Inherit full parent env.
        return dict(os.environ)
    base: dict[str, str] = {
        "PATH": os.environ.get("PATH", ""),
        "HOME": os.environ.get("HOME", ""),
    }
    base.update(extra)
    return base


def _relative_or_absolute(path: Path, repo_root: Path) -> str:
    """Repo-relative POSIX string when possible; absolute otherwise."""

    try:
        rel = path.relative_to(repo_root)
        return rel.as_posix()
    except ValueError:
        return str(path)


__all__ = [
    "LineCallback",
    "StreamingError",
    "run_streamed",
]
