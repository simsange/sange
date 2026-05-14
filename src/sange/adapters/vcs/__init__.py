"""VCSDriver Protocol + per-VCS adapter implementations.

Per §6.2 the `VCSDriver` Protocol is the contract every VCS adapter
implements. Application + Domain code depends on the Protocol, never on a
concrete `GitDriver` / `SvnDriver` / etc.

Public surface:

  * `VCSDriver`         — core Protocol (status / add / commit / log /
                          diff / branch / push / pull / fetch / tag).
  * `SupportsStash`     — optional sub-Protocol (Git stash, Hg shelve).
  * `SupportsBisect`    — optional sub-Protocol (Git, Hg, Fossil).
  * `SupportsRebase`    — optional sub-Protocol (Git, Hg — local history rewrite).
  * `SupportsLFS`       — optional sub-Protocol (Git LFS, Hg largefiles).
  * `DriverError`       — base exception for adapter-side failures.
  * `DriverCapabilities` — declarative capability descriptor each adapter
                            exposes for introspection.

Concrete adapter modules (`git`, `svn`, `hg`, `p4`) land per the §14
roadmap as their tier of VCS support unlocks.
"""

from __future__ import annotations

from sange.adapters.vcs._protocol import (
    DriverCapabilities,
    DriverError,
    PushResult,
    SupportsBisect,
    SupportsLFS,
    SupportsRebase,
    SupportsStash,
    TagInfo,
    VCSDriver,
)

__all__ = [
    "DriverCapabilities",
    "DriverError",
    "PushResult",
    "SupportsBisect",
    "SupportsLFS",
    "SupportsRebase",
    "SupportsStash",
    "TagInfo",
    "VCSDriver",
]
