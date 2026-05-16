"""`sange.core.gitignore` — gitignore-swap subsystem (T-101).

Per §6.5 + ADR-032:

  * `Profile` / `load_profile`           — one profile loaded from TOML.
  * `ProfileRegistry`                    — three-tier discovery
                                           (per-repo > per-user > shipped).
  * `compose(profiles, stage, registry)` — produce a composed gitignore.
  * `GitignoreSwap`                      — atomic swap with crash recovery.

The first T-101 slice (this commit) covers the binary `dev | prod`
stage axis. The multi-dimensional variant matrix from ADR-032
(stages crossed with flavor dimensions) layers on top in a follow-up.
"""

from __future__ import annotations

from sange.core.gitignore.compose import VALID_STAGES, CompositionError, compose
from sange.core.gitignore.profile import Profile, ProfileError, load_profile
from sange.core.gitignore.registry import (
    ProfileRegistry,
    RegistryLoad,
    default_registry_roots,
)
from sange.core.gitignore.swap import (
    GitignoreSwap,
    SwapError,
    SwapJournal,
    SwapResult,
)

__all__ = [
    "VALID_STAGES",
    "CompositionError",
    "GitignoreSwap",
    "Profile",
    "ProfileError",
    "ProfileRegistry",
    "RegistryLoad",
    "SwapError",
    "SwapJournal",
    "SwapResult",
    "compose",
    "default_registry_roots",
    "load_profile",
]
