"""`Repo` — the VCS-agnostic repository identity."""

from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal


VCSKind = Literal["git", "svn", "hg", "p4", "fossil", "pijul"]


@dataclass(frozen=True)
class Repo:
    """An on-disk repository, abstracted across VCS kinds.

    Constructed by an Adapter (e.g. `GitDriver.detect(path)`); never by
    user code directly.

    Fields:
      * `path`           — repo root on disk (canonical, resolved).
      * `vcs`            — which VCS this is (`"git"`, `"svn"`, ...).
      * `remote`         — canonical remote URL, or None for local-only.
      * `default_branch` — name of the default branch / trunk equivalent.
      * `detected_at`    — when the adapter built this Repo object.
      * `metadata`       — VCS-specific extras (read-only opaque dict).
    """

    path: Path
    vcs: VCSKind
    remote: str | None = None
    default_branch: str = "main"
    detected_at: _dt.datetime = field(
        default_factory=lambda: _dt.datetime.now(tz=_dt.timezone.utc)
    )
    metadata: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        # Frozen dataclass invariants: enforce that path is absolute + the
        # vcs string is one of the recognized kinds. We raise on construct,
        # not on field access, so a bad Repo never reaches the rest of the code.
        if not self.path.is_absolute():
            raise ValueError(
                f"Repo.path must be absolute; got {self.path!r}"
            )
        if self.vcs not in {"git", "svn", "hg", "p4", "fossil", "pijul"}:
            raise ValueError(f"unknown VCSKind {self.vcs!r}")
        if not self.default_branch:
            raise ValueError("Repo.default_branch must be non-empty")

    @property
    def slug(self) -> str:
        """A short, file-safe identifier for the repo (parent-dir basename)."""

        return self.path.name


__all__ = ["Repo", "VCSKind"]
