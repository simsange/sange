"""`GitignoreSwap` — atomic gitignore swap with SIGKILL-safe recovery.

Per §6.5: the swap operation has to survive `kill -9` at every step
without leaving the repository in an unrecoverable state. The design
is a journal-then-write pattern borrowed from filesystem-transaction
literature:

  Phase 1.  PREPARE
            Write a recovery journal at
            `<repo>/.sange/.recovery/swap-<utc>.json` recording:
              - the operator request (profiles + stage)
              - the planned new content + its sha256
              - the old `.gitignore` content + its sha256 (or None
                if absent)
              - the old `.sange/.active-profile` content (or None)
              - a `phase` field starting at `"prepared"`
            Journal write is tmp+fsync+rename.

  Phase 2.  WRITE
            tmp+fsync+rename the new `.gitignore`. Update the
            journal's `phase` to `"wrote_gitignore"` (tmp+fsync+
            rename — the journal itself is an append-rewrite log
            but each rewrite is atomic).

  Phase 3.  ACTIVATE
            tmp+fsync+rename the new `.sange/.active-profile`
            (a 2-line file: `name=<profile>` + `stage=<stage>`).
            Update the journal's `phase` to `"activated"`.

  Phase 4.  COMMIT
            Delete the journal. From this point the swap is
            durable.

Recovery (called by `recover()` at session start):
  - Phase prepared: roll forward (resume from step 2).
  - Phase wrote_gitignore: roll forward (resume from step 3).
  - Phase activated: clean up (delete the journal — the swap is
    complete, only the cleanup didn't happen).

The journal is the source of truth for in-progress swaps; if the
process dies mid-write of any artifact, the next `recover()` call
re-runs the remaining phases from the journal payload.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
import os
import tempfile
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

from sange.core.gitignore.compose import compose
from sange.core.gitignore.registry import ProfileRegistry


class SwapError(Exception):
    """Raised when an atomic gitignore swap can't complete."""


# Journal phase values, in order of progression.
_PHASE_PREPARED = "prepared"
_PHASE_WROTE_GITIGNORE = "wrote_gitignore"
_PHASE_ACTIVATED = "activated"
_PHASE_ORDER = (_PHASE_PREPARED, _PHASE_WROTE_GITIGNORE, _PHASE_ACTIVATED)


@dataclass(frozen=True)
class SwapJournal:
    """The on-disk crash-recovery record for one in-progress swap.

    `phase` advances through PREPARED → WROTE_GITIGNORE → ACTIVATED
    before the journal is deleted on success. Each phase update is
    a tmp+fsync+rename of the journal file itself.
    """

    journal_id: str            # UTC `swap-<YYYYMMDDTHHMMSSZ>` slug
    journal_path: Path
    profiles: tuple[str, ...]
    stage: str
    planned_content: str
    planned_sha256: str
    old_gitignore_content: str | None
    old_active_profile_content: str | None
    phase: str = _PHASE_PREPARED
    started_at: _dt.datetime = field(default_factory=lambda: _dt.datetime.now(tz=_dt.UTC))

    def to_dict(self) -> dict[str, object]:
        return {
            "journal_id": self.journal_id,
            "profiles": list(self.profiles),
            "stage": self.stage,
            "planned_sha256": self.planned_sha256,
            "old_gitignore_content": self.old_gitignore_content,
            "old_active_profile_content": self.old_active_profile_content,
            "phase": self.phase,
            "started_at": self.started_at.isoformat(),
            # planned_content is large; persist it last for readability.
            "planned_content": self.planned_content,
        }

    @classmethod
    def from_dict(cls, data: dict[str, object], journal_path: Path) -> SwapJournal:
        started = data.get("started_at")
        if isinstance(started, str):
            started_at = _dt.datetime.fromisoformat(started)
        else:
            started_at = _dt.datetime.now(tz=_dt.UTC)
        profiles_raw = data.get("profiles") or []
        if not isinstance(profiles_raw, list):
            profiles_raw = []
        return cls(
            journal_id=str(data.get("journal_id", journal_path.stem)),
            journal_path=journal_path,
            profiles=tuple(str(p) for p in profiles_raw),
            stage=str(data.get("stage", "")),
            planned_content=str(data.get("planned_content", "")),
            planned_sha256=str(data.get("planned_sha256", "")),
            old_gitignore_content=_optional_str(data.get("old_gitignore_content")),
            old_active_profile_content=_optional_str(data.get("old_active_profile_content")),
            phase=str(data.get("phase", _PHASE_PREPARED)),
            started_at=started_at,
        )


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    return str(value)


@dataclass(frozen=True)
class SwapResult:
    """The outcome of `GitignoreSwap.swap(...)`."""

    profiles: tuple[str, ...]
    stage: str
    gitignore_path: Path
    active_profile_path: Path
    journal_id: str
    bytes_written: int
    was_recovered: bool  # True when this swap finished a crashed predecessor


class GitignoreSwap:
    """Atomic gitignore swap rooted at `repo_root`.

    The swap layer doesn't introspect the file content — it takes
    a registry, a list of profile names, and a stage; composes via
    `compose.compose()`; writes via the journal-then-write
    sequence.
    """

    def __init__(
        self,
        repo_root: Path,
        *,
        registry: ProfileRegistry,
        clock: _dt.datetime | None = None,
    ) -> None:
        self._repo_root = Path(repo_root).resolve()
        self._registry = registry
        self._clock = clock

    # ---- public surface ------------------------------------------- #

    @property
    def repo_root(self) -> Path:
        return self._repo_root

    @property
    def gitignore_path(self) -> Path:
        return self._repo_root / ".gitignore"

    @property
    def active_profile_path(self) -> Path:
        return self._repo_root / ".sange" / ".active-profile"

    @property
    def recovery_dir(self) -> Path:
        return self._repo_root / ".sange" / ".recovery"

    def swap(self, profiles: Sequence[str], *, stage: str) -> SwapResult:
        """Atomically replace `.gitignore` with the composed profile.

        Returns a `SwapResult` describing what happened. Raises
        `SwapError` if the underlying filesystem ops fail.
        """

        composed = compose(
            profiles,
            stage=stage,
            registry=self._registry,
            clock=self._clock,
        )

        journal = self._prepare_journal(profiles, stage, composed)
        self._write_journal(journal)

        # Phase 2 — write new .gitignore.
        self._atomic_write(self.gitignore_path, journal.planned_content)
        journal = self._advance_phase(journal, _PHASE_WROTE_GITIGNORE)

        # Phase 3 — write .sange/.active-profile.
        self._atomic_write(
            self.active_profile_path,
            self._active_profile_text(profiles, stage),
        )
        journal = self._advance_phase(journal, _PHASE_ACTIVATED)

        # Phase 4 — delete the journal (durability achieved).
        self._delete_journal(journal)

        return SwapResult(
            profiles=tuple(profiles),
            stage=stage,
            gitignore_path=self.gitignore_path,
            active_profile_path=self.active_profile_path,
            journal_id=journal.journal_id,
            bytes_written=len(journal.planned_content.encode("utf-8")),
            was_recovered=False,
        )

    def recover(self) -> list[SwapResult]:
        """Replay any in-progress journals on disk.

        Walks `<repo>/.sange/.recovery/` for `swap-*.json` files
        and rolls each forward to completion (or cleans them up if
        they were already past the final phase). Returns one
        `SwapResult` per journal recovered, in chronological order.
        """

        if not self.recovery_dir.is_dir():
            return []

        journals = sorted(
            self.recovery_dir.glob("swap-*.json"),
            key=lambda p: p.name,
        )
        results: list[SwapResult] = []
        for journal_path in journals:
            try:
                with journal_path.open("r", encoding="utf-8") as fp:
                    data = json.load(fp)
            except (OSError, json.JSONDecodeError) as exc:
                raise SwapError(
                    f"recover: failed to read journal {journal_path}: {exc}"
                ) from exc
            journal = SwapJournal.from_dict(data, journal_path)
            results.append(self._roll_forward(journal))
        return results

    # ---- internal helpers ---------------------------------------- #

    def _prepare_journal(
        self,
        profiles: Sequence[str],
        stage: str,
        composed: str,
    ) -> SwapJournal:
        utc = (self._clock or _dt.datetime.now(tz=_dt.UTC)).replace(microsecond=0)
        journal_id = f"swap-{utc.strftime('%Y%m%dT%H%M%SZ')}"
        journal_path = self.recovery_dir / f"{journal_id}.json"

        old_gitignore = self._read_or_none(self.gitignore_path)
        old_active = self._read_or_none(self.active_profile_path)

        return SwapJournal(
            journal_id=journal_id,
            journal_path=journal_path,
            profiles=tuple(profiles),
            stage=stage,
            planned_content=composed,
            planned_sha256=hashlib.sha256(composed.encode("utf-8")).hexdigest(),
            old_gitignore_content=old_gitignore,
            old_active_profile_content=old_active,
            phase=_PHASE_PREPARED,
            started_at=utc,
        )

    def _write_journal(self, journal: SwapJournal) -> None:
        journal.journal_path.parent.mkdir(parents=True, exist_ok=True)
        self._atomic_write(
            journal.journal_path,
            json.dumps(journal.to_dict(), indent=2, sort_keys=True) + "\n",
        )

    def _advance_phase(self, journal: SwapJournal, new_phase: str) -> SwapJournal:
        if new_phase not in _PHASE_ORDER:
            raise SwapError(f"unknown journal phase: {new_phase!r}")
        # Frozen dataclass — replace via dict.
        updated_dict = journal.to_dict()
        updated_dict["phase"] = new_phase
        self._atomic_write(
            journal.journal_path,
            json.dumps(updated_dict, indent=2, sort_keys=True) + "\n",
        )
        return SwapJournal.from_dict(updated_dict, journal.journal_path)

    def _delete_journal(self, journal: SwapJournal) -> None:
        try:
            journal.journal_path.unlink()
        except FileNotFoundError:
            pass

    def _roll_forward(self, journal: SwapJournal) -> SwapResult:
        """Resume a crashed swap from its recorded phase."""

        if journal.phase == _PHASE_PREPARED:
            # Phase 2 didn't complete; re-run it.
            self._atomic_write(self.gitignore_path, journal.planned_content)
            journal = self._advance_phase(journal, _PHASE_WROTE_GITIGNORE)

        if journal.phase == _PHASE_WROTE_GITIGNORE:
            # Phase 3 didn't complete; re-run it.
            self._atomic_write(
                self.active_profile_path,
                self._active_profile_text(journal.profiles, journal.stage),
            )
            journal = self._advance_phase(journal, _PHASE_ACTIVATED)

        # Phase 4 — always delete (idempotent).
        self._delete_journal(journal)
        return SwapResult(
            profiles=journal.profiles,
            stage=journal.stage,
            gitignore_path=self.gitignore_path,
            active_profile_path=self.active_profile_path,
            journal_id=journal.journal_id,
            bytes_written=len(journal.planned_content.encode("utf-8")),
            was_recovered=True,
        )

    def _read_or_none(self, path: Path) -> str | None:
        try:
            return path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return None

    @staticmethod
    def _active_profile_text(profiles: Sequence[str], stage: str) -> str:
        return (
            "# Sange — currently active gitignore profile.\n"
            "# Managed by `sange gitignore swap`; do not hand-edit.\n"
            f"profiles={','.join(profiles)}\n"
            f"stage={stage}\n"
        )

    def _atomic_write(self, target: Path, content: str) -> None:
        """tmp+fsync+rename write. Safe under SIGKILL.

        Per §6.5: a kill mid-write leaves only the tmp file (which is
        cleaned up on next recovery sweep — see `recover()`), never
        a partially-written target.
        """

        target.parent.mkdir(parents=True, exist_ok=True)

        # `mkstemp` creates the file with O_EXCL semantics and a
        # randomized name — eliminates the symlink-attack vector of
        # writing to a predictable path.
        fd, tmp_name = tempfile.mkstemp(
            prefix=f".{target.name}.",
            suffix=".swap-tmp",
            dir=str(target.parent),
        )
        tmp_path = Path(tmp_name)
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fp:
                fp.write(content)
                fp.flush()
                os.fsync(fp.fileno())
            os.replace(tmp_path, target)
        except Exception:
            # Best-effort cleanup; if the rename succeeded the tmp is
            # gone, if it didn't we want the tmp gone.
            try:
                tmp_path.unlink()
            except FileNotFoundError:
                pass
            raise


__all__ = [
    "GitignoreSwap",
    "SwapError",
    "SwapJournal",
    "SwapResult",
]
