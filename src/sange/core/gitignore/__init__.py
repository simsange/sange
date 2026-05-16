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

from sange.core.gitignore.compose import (
    VALID_STAGES,
    CompositionError,
    compose,
    compose_variant,
)
from sange.core.gitignore.detect import DetectionResult, detect_profiles
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
from sange.core.gitignore.variant import (
    Variant,
    VariantConfig,
    VariantDimension,
    VariantError,
    VariantStageAxis,
)

__all__ = [
    "VALID_STAGES",
    "CompositionError",
    "DetectionResult",
    "GitignoreSwap",
    "Profile",
    "ProfileError",
    "ProfileRegistry",
    "RegistryLoad",
    "SwapError",
    "SwapJournal",
    "SwapResult",
    "Variant",
    "VariantConfig",
    "VariantDimension",
    "VariantError",
    "VariantStageAxis",
    "compose",
    "compose_variant",
    "default_registry_roots",
    "detect_profiles",
    "load_profile",
]
