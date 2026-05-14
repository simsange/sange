"""`CommitStore` — file-based read/write for commit JSONs.

Per §6.8: each commit JSON lives at
`${repo}/.sange/commits/NNNN-<type>-<scope>-<short-subject>.json`. This
module owns the read/write/list operations + filename slugify rule.

State-transition logic (T-007) builds on this module via `CommitsDirectory`,
the high-level façade that combines `CommitStore` + `CommitCounter`.

Atomic write discipline mirrors `_lib/output.py::_atomic_write` from the
generator pipeline — write to tmp file, fsync, rename, chmod 0644.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
from collections.abc import Iterable
from pathlib import Path

from sange.core.lifecycle.counter import CommitCounter
from sange.core.lifecycle.schema import CommitJSON, CommitStatus


# --------------------------------------------------------------------------- #
# Filename rules
# --------------------------------------------------------------------------- #


_SLUG_NON_ALPHANUM = re.compile(r"[^a-z0-9\-]+")
_SLUG_REPEATED_DASH = re.compile(r"-+")
_MAX_SUBJECT_SLUG_LENGTH = 64
_FILENAME_RE = re.compile(
    r"^(?P<counter>\d{4,})-(?P<type>[a-z]+)(?:-(?P<scope>[a-z0-9\-]+?))?-(?P<subject>[a-z0-9\-]+)\.json$"
)


def slugify_subject(subject: str, *, max_length: int = _MAX_SUBJECT_SLUG_LENGTH) -> str:
    """Convert a commit subject to a filename-safe slug.

    Pure function — same input → same output. Empty / no-alpha input
    yields `"untitled"` so a filename is always producible.
    """

    if not subject:
        return "untitled"
    s = subject.strip().lower()
    s = _SLUG_NON_ALPHANUM.sub("-", s)
    s = _SLUG_REPEATED_DASH.sub("-", s)
    s = s.strip("-")
    if not s:
        return "untitled"
    if len(s) > max_length:
        s = s[:max_length].rstrip("-")
    return s


def filename_for(commit: CommitJSON) -> str:
    """Compute the on-disk filename for a CommitJSON per §6.8.1 spec.

    Format: `NNNN-<type>[-<scope>]-<subject-slug>.json`.
    """

    scope_part = f"-{commit.message.scope}" if commit.message.scope else ""
    subject_slug = slugify_subject(commit.message.subject)
    return f"{commit.counter:04d}-{commit.message.type}{scope_part}-{subject_slug}.json"


# --------------------------------------------------------------------------- #
# CommitStore
# --------------------------------------------------------------------------- #


class CommitStoreError(Exception):
    """Generic failure reading/writing a commit JSON."""


class CommitStore:
    """File-based read/write for the `${repo}/.sange/commits/` directory.

    Stateless — the directory path is supplied on construction; every
    method derives paths from `commits_dir`. Multiple instances over the
    same directory are interchangeable.

    The `archive/` subdirectory is excluded from `list_commits()` by
    default; pass `include_archived=True` to inspect the archive.
    """

    def __init__(self, commits_dir: Path) -> None:
        self.commits_dir = commits_dir

    def write(self, commit: CommitJSON) -> Path:
        """Write `commit` to disk atomically; return the file path."""

        self.commits_dir.mkdir(parents=True, exist_ok=True)
        target = self.commits_dir / filename_for(commit)
        payload = commit.model_dump_json(indent=2) + "\n"
        _atomic_write_text(target, payload)
        return target

    def read(self, path: Path) -> CommitJSON:
        """Read + validate a single commit JSON. Raises on parse failure."""

        if not path.is_file():
            raise CommitStoreError(f"commit JSON not found: {path}")
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise CommitStoreError(f"failed to read {path}: {exc}") from exc
        try:
            return CommitJSON.model_validate(raw)
        except Exception as exc:
            raise CommitStoreError(f"invalid commit JSON at {path}: {exc}") from exc

    def list_commits(
        self,
        *,
        include_archived: bool = False,
        status: CommitStatus | None = None,
    ) -> list[CommitJSON]:
        """Return every parseable commit JSON in the directory.

        Filters:
          * `include_archived` — when True, also descend into `archive/`.
          * `status` — when set, returns only commits in that state.

        Files that fail to parse are silently skipped (the caller's
        `sange doctor` surfaces them separately).
        """

        if not self.commits_dir.is_dir():
            return []
        out: list[CommitJSON] = []
        for entry in sorted(self.commits_dir.iterdir()):
            if entry.is_file() and entry.suffix == ".json":
                if entry.name.startswith("."):
                    continue
                try:
                    out.append(self.read(entry))
                except CommitStoreError:
                    continue
        if include_archived:
            archive_root = self.commits_dir / "archive"
            if archive_root.is_dir():
                for year_month in sorted(archive_root.iterdir()):
                    if not year_month.is_dir():
                        continue
                    for entry in sorted(year_month.iterdir()):
                        if entry.is_file() and entry.suffix == ".json":
                            try:
                                out.append(self.read(entry))
                            except CommitStoreError:
                                continue
        if status is not None:
            out = [c for c in out if c.status is status]
        out.sort(key=lambda c: c.counter)
        return out

    def find_by_counter(self, counter: int) -> CommitJSON | None:
        """Look up a single commit by its counter number."""

        if not self.commits_dir.is_dir():
            return None
        prefix = f"{counter:04d}-"
        for entry in self.commits_dir.iterdir():
            if (
                entry.is_file()
                and entry.suffix == ".json"
                and entry.name.startswith(prefix)
            ):
                return self.read(entry)
        return None

    def find_by_id(self, commit_id: str) -> CommitJSON | None:
        """Look up by the commit's UUID-shaped `id` field. Linear scan."""

        for c in self.list_commits(include_archived=True):
            if c.id == commit_id:
                return c
        return None

    def delete(self, commit: CommitJSON) -> bool:
        """Delete the commit JSON from disk (DISCARDED state cleanup).

        Returns True if a file was removed, False if no matching file
        existed. Raises on I/O failure.
        """

        if not self.commits_dir.is_dir():
            return False
        target = self.commits_dir / filename_for(commit)
        if target.is_file():
            target.unlink()
            return True
        return False


# --------------------------------------------------------------------------- #
# CommitsDirectory — high-level façade
# --------------------------------------------------------------------------- #


class CommitsDirectory:
    """Composes `CommitStore` + `CommitCounter` for high-level use.

    Most callers use `CommitsDirectory` (not `CommitStore` directly)
    because:
      * Creating a new commit needs both a counter allocation + a write.
      * Reading + listing is convenient via the same object.
      * The state-machine layer (T-007) takes a `CommitsDirectory` not
        the raw `CommitStore`.
    """

    def __init__(self, repo_root: Path) -> None:
        self.repo_root = repo_root
        self.commits_dir = repo_root / ".sange" / "commits"
        self.store = CommitStore(self.commits_dir)
        self.counter = CommitCounter(self.commits_dir)

    def allocate_counter(self) -> int:
        """Allocate the next counter without writing a commit yet."""

        return self.counter.next_number()

    def save(self, commit: CommitJSON) -> Path:
        """Save a commit JSON (counter already allocated)."""

        return self.store.write(commit)

    def read(self, path: Path) -> CommitJSON:
        return self.store.read(path)

    def list_all(self, **kwargs: object) -> list[CommitJSON]:  # type: ignore[no-untyped-def]
        return self.store.list_commits(**kwargs)  # type: ignore[arg-type]

    def by_counter(self, counter: int) -> CommitJSON | None:
        return self.store.find_by_counter(counter)

    def by_id(self, commit_id: str) -> CommitJSON | None:
        return self.store.find_by_id(commit_id)


# --------------------------------------------------------------------------- #
# Atomic write helper (mirrors _lib/output.py)
# --------------------------------------------------------------------------- #


def _atomic_write_text(path: Path, content: str) -> None:
    """Write `content` to `path` atomically (tmp + fsync + rename + chmod)."""

    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = content.encode("utf-8")
    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=str(path.parent),
    )
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
        try:
            os.chmod(path, 0o644)
        except OSError:
            pass
    except BaseException:
        try:
            Path(tmp_name).unlink(missing_ok=True)
        except OSError:
            pass
        raise


__all__ = [
    "CommitStore",
    "CommitStoreError",
    "CommitsDirectory",
    "filename_for",
    "slugify_subject",
]
