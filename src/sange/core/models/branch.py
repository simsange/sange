"""`BranchInfo` + `RemoteInfo` — VCS-agnostic branch and remote models."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RemoteInfo:
    """A named remote endpoint.

    For Git: `origin`, `upstream`, etc. For SVN: the canonical repository
    URL (SVN has one root — `name` is conventionally `"origin"`). For Hg:
    the `default` or `default-push` paths.

    Fields:
      * `name` — short label (`"origin"`).
      * `url`  — canonical URL (HTTPS / SSH / svn+ssh / etc.).
    """

    name: str
    url: str

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("RemoteInfo.name must be non-empty")
        if not self.url:
            raise ValueError("RemoteInfo.url must be non-empty")


@dataclass(frozen=True)
class BranchInfo:
    """A branch reference, abstracted across VCS kinds.

    For SVN where "branches" are URL paths under `branches/`, the Adapter
    translates URL conventions into BranchInfo so the rest of Sange treats
    SVN branches as first-class names.

    Fields:
      * `name`         — branch name (`"main"`, `"feature/oauth"`).
      * `tip_sha`      — SHA of the branch tip commit (or revision number
                          rendered as a string for SVN).
      * `tracking`     — upstream tracking name (e.g. `"origin/main"`)
                          or None for branches without an upstream.
      * `ahead`/`behind` — commits ahead-of / behind-of tracking, or None
                            when not tracked.
      * `is_current`   — is this the active branch in the working copy?
    """

    name: str
    tip_sha: str
    tracking: str | None = None
    ahead: int | None = None
    behind: int | None = None
    is_current: bool = False

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("BranchInfo.name must be non-empty")
        if not self.tip_sha:
            raise ValueError("BranchInfo.tip_sha must be non-empty")
        # Slash in `name` is fine (Git supports `feature/foo`); newlines
        # are not.
        if "\n" in self.name or "\r" in self.name:
            raise ValueError(f"BranchInfo.name must be a single line; got {self.name!r}")
        if (self.ahead is None) != (self.behind is None):
            raise ValueError(
                "BranchInfo.ahead and .behind must both be set or both be None"
            )
        if self.ahead is not None and self.ahead < 0:
            raise ValueError(f"BranchInfo.ahead must be ≥ 0; got {self.ahead}")
        if self.behind is not None and self.behind < 0:
            raise ValueError(f"BranchInfo.behind must be ≥ 0; got {self.behind}")

    @property
    def is_tracking(self) -> bool:
        return self.tracking is not None

    @property
    def is_up_to_date(self) -> bool:
        return self.is_tracking and self.ahead == 0 and self.behind == 0


__all__ = ["BranchInfo", "RemoteInfo"]
