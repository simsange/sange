"""§6.11.4 gate 3 — backup tarball + verification hash.

> "A tarball mirror snapshot is created under
> `.sange/purge/<ts>/backup-<ts>.tar.gz` + a verification hash
> (`sha256` of the tarball + `git fsck --full` against the mirror).
> Sange refuses to proceed if either check fails." — §6.11.4 gate 3

This module ships the tarball part. The `git fsck` part is already
covered by `create_mirror` (T-111b) which runs fsck during the
mirror-create pipeline; the destructive-ops slice (T-203+) will
re-fsck the post-rewrite mirror and compare.

Approach: shell to `tar czf <tarball> -C <mirror.parent> <mirror.name>`
via `run_streamed` so the tar invocation lands one audit chain entry
with a 0600 transcript. After tar exits, compute sha256 of the
tarball ourselves (no subprocess) and write a `<tarball>.sha256`
sidecar so the verification hash is operator-readable without
re-deriving.

The off-host backup destination (S3, age-encrypted file mount, …)
mentioned in §6.11.4 is NOT in this slice — that's a v1.0 concern
when the destructive subsystem actually needs a recoverable backup.
v0.5 ships the local tarball + sha256 sidecar so the operator can
manually copy it off-host if they choose.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
from dataclasses import dataclass
from pathlib import Path

from sange.core.audit import AuditChain, EventKind
from sange.core.purge.plan import PurgePlan
from sange.core.streaming import run_streamed


class BackupError(Exception):
    """Raised when the backup operation can't proceed."""


@dataclass(frozen=True)
class BackupResult:
    """Outcome of `create_backup`.

    Fields:
      * `tarball_path`   — absolute path to the .tar.gz file.
      * `sidecar_path`   — absolute path to the `<tarball>.sha256` sidecar.
      * `sha256_hex`     — 64-char hex digest of the tarball.
      * `size_bytes`     — tarball size on disk.
      * `event_id`       — audit chain event id for the tar subprocess.
    """

    tarball_path: Path
    sidecar_path: Path
    sha256_hex: str
    size_bytes: int
    event_id: str


def create_backup(
    plan: PurgePlan,
    mirror_path: Path,
    *,
    audit_chain: AuditChain,
    actor: str,
    timeout: float = 600.0,
    clock: _dt.datetime | None = None,
) -> BackupResult:
    """Create a verified tarball backup of the mirror.

    Args:
      plan:         the active `PurgePlan` (used for plan_id +
                    destination directory).
      mirror_path:  the bare-repo dir produced by `create_mirror()`.
      audit_chain:  chain to thread the tar event onto.
      actor:        audit-entry actor.
      timeout:      seconds before SIGTERM cascade on the tar subprocess.
      clock:        optional `datetime` for the filename timestamp
                    (test-only override; default is `now-UTC`).

    Raises:
      BackupError: mirror doesn't exist / mirror outside expected
        plan dir / tar exits non-zero / resulting tarball is empty.
    """

    if not mirror_path.is_dir():
        raise BackupError(f"mirror not found: {mirror_path}")

    plan_dir = mirror_path.parent
    if plan_dir.name != plan.plan_id:
        raise BackupError(
            f"mirror_path is not inside the plan dir for {plan.plan_id}: "
            f"{mirror_path} (expected parent basename {plan.plan_id!r}, "
            f"got {plan_dir.name!r})"
        )

    moment = clock or _dt.datetime.now(tz=_dt.UTC)
    stamp = moment.strftime("%Y-%m-%dT%H-%M-%SZ")
    tarball = plan_dir / f"backup-{stamp}.tar.gz"
    if tarball.exists():
        raise BackupError(
            f"backup file already exists: {tarball} "
            f"(remove it manually or wait one second for a fresh timestamp)"
        )

    # `tar -czf <tarball> -C <mirror.parent> <mirror.name>` produces a
    # tarball whose archive root is the mirror dir's basename — that's
    # the convention git users expect (the archive extracts to a sibling
    # directory rather than dumping bare-repo files into cwd).
    tar_result = run_streamed(
        [
            "tar",
            "-czf",
            str(tarball),
            "-C",
            str(mirror_path.parent),
            mirror_path.name,
        ],
        audit_chain=audit_chain,
        actor=actor,
        event_kind=EventKind.GENERIC,
        payload={
            "phase": "backup-tar",
            "plan_id": plan.plan_id,
            "mirror_path": str(mirror_path),
            "tarball": tarball.name,
        },
        timeout=timeout,
    )
    if tar_result.returncode != 0:
        # Best-effort cleanup: the tarball may have been partially
        # written before tar failed. Removing it eliminates the
        # "stale half-tarball mistaken for a good backup" foot-gun.
        if tarball.exists():
            try:
                tarball.unlink()
            except OSError:
                pass
        raise BackupError(
            f"tar exited {tar_result.returncode}; "
            f"see transcript at {tar_result.transcript_path}"
        )

    if not tarball.is_file():
        raise BackupError(
            f"tar reported success but tarball is missing: {tarball}; "
            f"see transcript at {tar_result.transcript_path}"
        )
    size_bytes = tarball.stat().st_size
    if size_bytes == 0:
        try:
            tarball.unlink()
        except OSError:
            pass
        raise BackupError(
            f"tar produced an empty tarball: {tarball}; "
            f"see transcript at {tar_result.transcript_path}"
        )

    sha256_hex = _sha256_file(tarball)
    sidecar = tarball.with_suffix(tarball.suffix + ".sha256")
    sidecar.write_text(f"{sha256_hex}  {tarball.name}\n", encoding="utf-8")

    return BackupResult(
        tarball_path=tarball,
        sidecar_path=sidecar,
        sha256_hex=sha256_hex,
        size_bytes=size_bytes,
        event_id=tar_result.event_id,
    )


def verify_backup(result: BackupResult) -> bool:
    """Re-compute the tarball's sha256 and compare to the recorded digest.

    Returns True iff the on-disk tarball still hashes to `result.sha256_hex`.
    Used by the destructive-ops slice (T-203+) to confirm the backup
    is intact before consuming it for a rollback.
    """

    if not result.tarball_path.is_file():
        return False
    current = _sha256_file(result.tarball_path)
    return current == result.sha256_hex


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _sha256_file(path: Path, *, chunk_size: int = 1024 * 1024) -> str:
    """Stream-hash a file in 1 MiB chunks.

    Bounded memory regardless of file size — critical for tarballs of
    multi-GB mirrors.
    """

    hasher = hashlib.sha256()
    with path.open("rb") as fp:
        while True:
            chunk = fp.read(chunk_size)
            if not chunk:
                break
            hasher.update(chunk)
    return hasher.hexdigest()


__all__ = [
    "BackupError",
    "BackupResult",
    "create_backup",
    "verify_backup",
]
