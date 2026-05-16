"""Compose a gitignore document from a list of profiles + a stage.

Per §6.5 + ADR-032, the source-set composition follows a documented
priority order. The first slice of T-101 implements the binary
`dev | prod` axis (the older two-stage model from §6.5); the
multi-dimensional variant matrix from ADR-032 layers on top in a
follow-up.

Composition algorithm:

  1. Build the ordered profile chain. For each profile in
     `profiles` (in caller order), resolve its extends chain
     via `ProfileRegistry.resolve_extends_chain` (ancestors
     first). Concatenate the chains in caller order; dedupe
     (first occurrence wins).
  2. For each profile in the resolved chain, emit:
       - `patterns_always` always
       - `patterns_dev` when stage == "dev"
       - `patterns_prod` when stage == "prod"
  3. Deduplicate lines globally (first occurrence wins) while
     preserving order. A line that appears in profile A's
     `always` and in profile B's `dev_only` keeps profile A's
     position.
  4. Emit a header comment with provenance: stage, profiles in
     order, generator marker, generated_at timestamp.

The output is deterministic given the same `(profiles, stage,
clock, registry)` inputs.
"""

from __future__ import annotations

import datetime as _dt
from collections.abc import Sequence

from sange.core.gitignore.profile import Profile
from sange.core.gitignore.registry import ProfileRegistry
from sange.core.gitignore.variant import Variant

VALID_STAGES = ("dev", "prod")


class CompositionError(Exception):
    """Raised when a composition request is invalid (bad stage, etc.)."""


def compose(
    profiles: Sequence[str],
    *,
    stage: str,
    registry: ProfileRegistry,
    clock: _dt.datetime | None = None,
) -> str:
    """Compose the final `.gitignore` text for `profiles` + `stage`.

    Args:
      profiles: profile names in caller order (e.g.
                `["lang/python", "framework/django"]`). Each name is
                resolved through the registry, including its extends
                chain.
      stage:    `"dev"` or `"prod"`.
      registry: the loaded `ProfileRegistry`.
      clock:    deterministic timestamp for the header
                (defaults to `_dt.datetime.now(tz=UTC)`).

    Returns:
      The gitignore text — header comment + de-duplicated lines.
      Trailing newline included.

    Raises:
      CompositionError: invalid stage or empty profile list.
      ProfileError: a referenced profile (including via extends)
                    doesn't exist in the registry, or the chain
                    has a cycle.
    """

    if stage not in VALID_STAGES:
        raise CompositionError(
            f"stage must be one of {VALID_STAGES}, got {stage!r}"
        )
    if not profiles:
        raise CompositionError("compose: profiles list must be non-empty")

    when = clock or _dt.datetime.now(tz=_dt.UTC)

    # Resolve extends chains in order, then dedupe by name (first wins).
    chain: list[Profile] = []
    seen_names: set[str] = set()
    for caller_name in profiles:
        for profile in registry.resolve_extends_chain(caller_name):
            if profile.name in seen_names:
                continue
            chain.append(profile)
            seen_names.add(profile.name)

    # Collect lines from each profile in chain order; dedupe globally.
    seen_lines: set[str] = set()
    body_lines: list[str] = []
    for profile in chain:
        section_lines: list[str] = []
        for line in profile.patterns_for_stage(stage):
            if line in seen_lines:
                continue
            seen_lines.add(line)
            section_lines.append(line)
        if not section_lines:
            continue
        body_lines.append(f"# --- {profile.name} ({profile.display_name}) ---")
        body_lines.extend(section_lines)
        body_lines.append("")  # blank separator between profile blocks

    header = _build_header(profiles, chain, stage, when)
    body = "\n".join(body_lines).rstrip() + "\n"

    return header + body


def _build_header(
    requested: Sequence[str],
    resolved: Sequence[Profile],
    stage: str,
    when: _dt.datetime,
) -> str:
    """Build the documentation block prepended to every composed gitignore."""

    iso = when.replace(microsecond=0).isoformat()
    extras = [p.name for p in resolved if p.name not in set(requested)]
    extras_str = (
        f"(plus extends: {', '.join(extras)})" if extras else ""
    )

    lines = [
        "# This file is composed by `sange gitignore swap` per §6.5.",
        "# DO NOT hand-edit between swaps — your changes will be overwritten",
        "# by the next composition. Add overrides to a per-repo profile",
        "# at `<repo>/.sange/profiles/<category>/<name>.toml` instead.",
        "#",
        f"# generated_at:  {iso}",
        f"# stage:         {stage}",
        f"# profiles:      {', '.join(requested)}",
    ]
    if extras_str:
        lines.append(f"# {extras_str}")
    lines.append("")
    lines.append("")
    return "\n".join(lines)


def compose_variant(
    profiles: Sequence[str],
    *,
    variant: Variant,
    registry: ProfileRegistry,
    clock: _dt.datetime | None = None,
) -> str:
    """Compose the final `.gitignore` text for `profiles` + a variant.

    The variant-aware extension of `compose()`. Same chain resolution
    + global dedup semantics, but each profile contributes patterns
    via `patterns_for_variant()` (stage + flavor blocks layered on
    top of `always`).

    Args:
      profiles: profile names in caller order.
      variant:  the concrete `(stage, flavors)` tuple.
      registry: the loaded `ProfileRegistry`.
      clock:    deterministic timestamp for the header.

    Returns:
      The gitignore text — header comment + de-duplicated lines.
    """

    if not profiles:
        raise CompositionError("compose_variant: profiles list must be non-empty")

    when = clock or _dt.datetime.now(tz=_dt.UTC)

    # Resolve extends chains in order, dedupe by profile name.
    chain: list[Profile] = []
    seen_names: set[str] = set()
    for caller_name in profiles:
        for profile in registry.resolve_extends_chain(caller_name):
            if profile.name in seen_names:
                continue
            chain.append(profile)
            seen_names.add(profile.name)

    seen_lines: set[str] = set()
    body_lines: list[str] = []
    for profile in chain:
        section_lines: list[str] = []
        for line in profile.patterns_for_variant(
            stage=variant.stage,
            flavors=variant.flavors,
        ):
            if line in seen_lines:
                continue
            seen_lines.add(line)
            section_lines.append(line)
        if not section_lines:
            continue
        body_lines.append(f"# --- {profile.name} ({profile.display_name}) ---")
        body_lines.extend(section_lines)
        body_lines.append("")

    header = _build_variant_header(profiles, chain, variant, when)
    body = "\n".join(body_lines).rstrip() + "\n"
    return header + body


def _build_variant_header(
    requested: Sequence[str],
    resolved: Sequence[Profile],
    variant: Variant,
    when: _dt.datetime,
) -> str:
    iso = when.replace(microsecond=0).isoformat()
    extras = [p.name for p in resolved if p.name not in set(requested)]
    extras_str = (
        f"(plus extends: {', '.join(extras)})" if extras else ""
    )
    flavors_str = (
        ", ".join(f"{d}={v}" for d, v in variant.flavors) or "(no flavors)"
    )
    lines = [
        "# This file is composed by `sange gitignore swap` per §6.5 + ADR-032.",
        "# DO NOT hand-edit between swaps — your changes will be overwritten",
        "# by the next composition. Add overrides to a per-repo profile",
        "# at `<repo>/.sange/profiles/<category>/<name>.toml` instead.",
        "#",
        f"# generated_at:  {iso}",
        f"# variant:       {variant.slug()}",
        f"# stage:         {variant.stage}",
        f"# flavors:       {flavors_str}",
        f"# profiles:      {', '.join(requested)}",
    ]
    if extras_str:
        lines.append(f"# {extras_str}")
    lines.append("")
    lines.append("")
    return "\n".join(lines)


__all__ = [
    "VALID_STAGES",
    "CompositionError",
    "compose",
    "compose_variant",
]
