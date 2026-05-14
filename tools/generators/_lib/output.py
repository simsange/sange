"""Generator metadata + frontmatter rendering + atomic write.

Every Sange-generated file opens with a YAML frontmatter block per §16.4.1 of
`.design/sange-architecture-prompt.md`:

    ---
    generated_by: tools/generators/<name>.py
    generator_version: <semver>
    generated_at: <ISO-8601 UTC>
    input_sha256: <hash of input>
    output_sha256: <hash of body>
    manual_edits_allowed: false
    ---

This module renders that block, computes the body sha256, and writes the
resulting file atomically (tmp file → fsync → rename) so a half-written file
never lands on disk.

Two write modes:

  * `WriteMode.WRITE` — render + write, overwriting if present.
  * `WriteMode.CHECK` — render, compare to existing file, exit cleanly on
    match, return mismatch info on diff. Used by CI's `verify_generated.py`
    so generators are runnable in "is the on-disk file in sync?" mode.

Per ADR-023:

  * Timestamps come from the GeneratorMetadata.generated_at field — never
    `datetime.now()` at the call site. The orchestrator (`all.py`) supplies
    a single `--clock` value so the whole pipeline shares one timestamp.
  * No UUIDs. No randomness. The only non-deterministic field is
    `generated_at`, and that's pinned by the orchestrator.
"""

from __future__ import annotations

import datetime as _dt
import enum
import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from . import fingerprint


class WriteMode(str, enum.Enum):
    WRITE = "write"
    CHECK = "check"


class VerificationResult(str, enum.Enum):
    """Outcome of a WriteMode.CHECK run."""

    MATCH = "match"
    MISMATCH = "mismatch"
    MISSING = "missing"


@dataclass(frozen=True)
class GeneratorMetadata:
    """The frontmatter inputs each generator declares.

    Fields:

      * `generated_by`   — path of the generator script, relative to repo
                           root (e.g. ``tools/generators/git_catalog.py``).
      * `generator_version` — SemVer for the generator itself. Bump on every
                              behaviour change so old output is identifiable
                              as out-of-date.
      * `input_sha256`   — sha256 of the canonical input (a file, a CLI
                           sub-tree, a config object). Reproducible.
      * `manual_edits_allowed` — true for the few files where humans add
                                  prose after generation. CI verifies the
                                  *input* hash on those, not the body.
      * `generated_at`   — ISO-8601 UTC. Supplied by the orchestrator; the
                           default is a per-call now, useful only for one-off
                           manual runs.
    """

    generated_by: str
    generator_version: str
    input_sha256: str
    manual_edits_allowed: bool = False
    generated_at: _dt.datetime = field(
        default_factory=lambda: _dt.datetime.now(tz=_dt.timezone.utc)
    )

    def iso_timestamp(self) -> str:
        return self.generated_at.astimezone(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def render_frontmatter(meta: GeneratorMetadata, output_sha256: str) -> str:
    """Render the YAML frontmatter block (deterministic ordering)."""

    lines = [
        "---",
        f"generated_by: {meta.generated_by}",
        f"generator_version: {meta.generator_version}",
        f"generated_at: {meta.iso_timestamp()}",
        f"input_sha256: {meta.input_sha256}",
        f"output_sha256: {output_sha256}",
        f"manual_edits_allowed: {str(meta.manual_edits_allowed).lower()}",
        "---",
        "",
    ]
    return "\n".join(lines)


def assemble(meta: GeneratorMetadata, body: str) -> tuple[str, str]:
    """Compute body sha256 + return the full file text (frontmatter + body).

    The body is canonicalized before hashing so the value is stable across
    OS-level line-ending differences. We *also* normalize the trailing newline
    BEFORE computing `output_sha` — otherwise the on-disk body (which always
    ends with `\\n` because POSIX text files do) would not match the sha
    computed from a no-trailing-newline rendered body. The verifier's
    `body_sha256(on_disk_text)` extracts the body via `extract_body`, which
    preserves the trailing newline — so the assembler must do the same to
    keep the contract symmetric.
    """

    canonical = fingerprint.canonical_bytes(body).decode("utf-8")
    if not canonical.endswith("\n"):
        canonical += "\n"
    output_sha = fingerprint.sha256_text(canonical)
    frontmatter = render_frontmatter(meta, output_sha)
    file_text = frontmatter + canonical
    return file_text, output_sha


def _atomic_write(path: Path, content: str) -> None:
    """Write `content` to `path` atomically.

    Strategy: write to a sibling tempfile, fsync, rename. The rename is
    POSIX-atomic; on Windows it's atomic at the directory level since Python
    3.3+ when both paths share a volume (the case here, since tmp lives next
    to the destination).
    """

    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = content.encode(fingerprint.ENCODING)
    tmp_fd, tmp_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=str(path.parent),
    )
    try:
        with os.fdopen(tmp_fd, "wb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
        # tempfile.mkstemp defaults to 0600. For generated docs and code we
        # want world-readable (0644) so CI runners, docs sites, and other
        # tools can read the output. On Windows os.chmod ignores most bits,
        # so this is a no-op there.
        try:
            os.chmod(path, 0o644)
        except OSError:
            # Some filesystems (e.g. read-only mounts unreached above) refuse
            # chmod; the file is still written correctly.
            pass
    except BaseException:
        # Make best-effort cleanup; if the temp survived, leave a trace in
        # the audit log via the caller (we don't have one here).
        try:
            Path(tmp_name).unlink(missing_ok=True)
        except OSError:
            pass
        raise


@dataclass(frozen=True)
class WriteOutcome:
    path: Path
    mode: WriteMode
    output_sha256: str
    result: VerificationResult | None  # populated only in CHECK mode
    diff_summary: str | None = None    # populated only on MISMATCH


def write_generated_file(
    path: Path,
    body: str,
    meta: GeneratorMetadata,
    mode: WriteMode = WriteMode.WRITE,
) -> WriteOutcome:
    """Render + emit a generated file.

    In WRITE mode: assemble the frontmatter + body and atomically write.
    In CHECK mode: assemble, compare to on-disk content, return verdict.

    CHECK mode never touches the filesystem. The caller (the orchestrator
    or the CI verifier) interprets the verdict.
    """

    file_text, output_sha = assemble(meta, body)

    if mode is WriteMode.WRITE:
        _atomic_write(path, file_text)
        return WriteOutcome(path=path, mode=mode, output_sha256=output_sha, result=None)

    # CHECK mode — compare body sha256, NOT full-file equality.
    #
    # The frontmatter's `generated_at` legitimately varies between runs (a
    # generator invoked at noon today vs. noon tomorrow produces different
    # timestamps even though the body is byte-identical). Comparing full-file
    # would flag every re-run as "stale," which defeats the purpose. CI's
    # `verify_generated.py` uses body-sha semantics too — `all.py --check`
    # mirrors that contract. The other meta fields (input_sha256, generator
    # version) are checked indirectly: a body that's still valid after an
    # input change means the generator didn't *use* the changed input, which
    # is itself a defect the body would surface.
    if not path.exists():
        return WriteOutcome(
            path=path,
            mode=mode,
            output_sha256=output_sha,
            result=VerificationResult.MISSING,
            diff_summary=f"file missing: {path}",
        )

    on_disk = path.read_text(encoding=fingerprint.ENCODING)
    on_disk_body_sha = fingerprint.body_sha256(on_disk)
    if on_disk_body_sha == output_sha:
        return WriteOutcome(
            path=path,
            mode=mode,
            output_sha256=output_sha,
            result=VerificationResult.MATCH,
        )

    return WriteOutcome(
        path=path,
        mode=mode,
        output_sha256=output_sha,
        result=VerificationResult.MISMATCH,
        diff_summary=(
            f"body sha256 differs: on-disk={on_disk_body_sha} expected={output_sha}"
        ),
    )


def _summarize_diff(left: str, right: str) -> str:
    """Short diff summary for human-readable output."""

    left_lines = left.splitlines()
    right_lines = right.splitlines()
    return (
        f"line count: on-disk={len(left_lines)} generated={len(right_lines)} "
        f"size: on-disk={len(left.encode('utf-8'))}B "
        f"generated={len(right.encode('utf-8'))}B"
    )
