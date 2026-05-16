"""Variant matrix (ADR-032) — multi-dimensional stage x flavor model.

The v0.5-alpha gitignore-swap engine ships the binary `dev | prod`
stage axis. ADR-032 generalizes that to a Cartesian product of:

  * **stages**            — a linear progression of named environments
                            (e.g. `dev` → `staging` → `production`).
                            One stage is active at a time.
  * **flavor dimensions** — zero or more named axes (e.g.
                            `audience: [internal, external, partner]`,
                            `surface: [web, mobile, api]`).
                            Each dimension has its own value list;
                            exactly one value from each dimension is
                            active at a time.

A `Variant` is a concrete tuple of one stage value + one value from
each declared dimension (e.g. `(production, external, web)`). Source
patterns in a profile's `[patterns]` section can be filtered by:

  * **stage**             — `[patterns.stages.<stage>]` block.
                            Contributes when the active variant's
                            stage matches.
  * **dimension flavor**  — `[patterns.flavors.<dim>.<value>]` block.
                            Contributes when the active variant's
                            value for `<dim>` matches.
  * **always**            — `[patterns]::always` contributes for
                            every variant (legacy, unchanged).
  * **dev_only / prod_only** — legacy two-stage shortcuts. Treated
                            as aliases for `[patterns.stages.dev]`
                            and `[patterns.stages.prod]` so existing
                            profiles keep working unchanged.

Composition (the variant-aware extension of `compose.compose`)
applies these filters per profile, with the same global dedup +
section-header semantics as the binary-stage path.

The Cartesian product can be large (3 stages x 3 audiences x 3
surfaces x 3 regions = 81 variants) but Sange treats variants
lazily: the matrix doesn't materialize all combinations on disk
unless the operator asks for it via `sange variants enumerate`.
The runtime cost is in the composition pass for the *currently
active* variant only.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field


class VariantError(Exception):
    """Raised when a variant request is malformed or inconsistent."""


@dataclass(frozen=True)
class VariantStageAxis:
    """A linear sequence of stage names.

    `values` is ordered from earliest to latest (e.g. `["dev",
    "staging", "production"]`). The order matters for some
    operators ("promote to next stage") but the composition layer
    only cares that the active value is in the list.
    """

    name: str = "stage"
    values: tuple[str, ...] = ("dev", "prod")

    def __post_init__(self) -> None:
        if not self.values:
            raise VariantError("VariantStageAxis.values must be non-empty")
        # Stage names must be unique + non-empty.
        seen: set[str] = set()
        for v in self.values:
            if not v:
                raise VariantError("stage values must be non-empty strings")
            if v in seen:
                raise VariantError(f"duplicate stage value {v!r}")
            seen.add(v)

    def is_valid(self, value: str) -> bool:
        return value in self.values

    def index_of(self, value: str) -> int:
        """Return the 0-based position of `value`. Raises if missing."""

        try:
            return self.values.index(value)
        except ValueError as exc:
            raise VariantError(
                f"stage {value!r} not in axis {self.name!r}: "
                f"valid={list(self.values)}"
            ) from exc


@dataclass(frozen=True)
class VariantDimension:
    """A named flavor axis with a list of allowable values.

    Unlike `VariantStageAxis`, dimensions are unordered — the values
    are mutually exclusive but no "promote" semantics apply.
    """

    name: str
    values: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.name:
            raise VariantError("VariantDimension.name must be non-empty")
        if not self.values:
            raise VariantError(
                f"VariantDimension {self.name!r}: values must be non-empty"
            )
        seen: set[str] = set()
        for v in self.values:
            if not v:
                raise VariantError(
                    f"VariantDimension {self.name!r}: values must be non-empty strings"
                )
            if v in seen:
                raise VariantError(
                    f"VariantDimension {self.name!r}: duplicate value {v!r}"
                )
            seen.add(v)

    def is_valid(self, value: str) -> bool:
        return value in self.values


@dataclass(frozen=True)
class VariantConfig:
    """The matrix declaration: stage axis + zero or more dimensions.

    Construction validates internal consistency. Callers should
    construct one `VariantConfig` per repo (from `SangeConfig.variants`
    in the v1.0 wiring) and reuse it across composition calls.
    """

    stage_axis: VariantStageAxis = field(default_factory=VariantStageAxis)
    dimensions: tuple[VariantDimension, ...] = ()

    def __post_init__(self) -> None:
        # Dimension names must be unique + non-empty + cannot collide
        # with the stage axis name.
        names: set[str] = {self.stage_axis.name}
        for d in self.dimensions:
            if d.name in names:
                raise VariantError(
                    f"VariantConfig: dimension name collision {d.name!r}"
                )
            names.add(d.name)

    def dimension_by_name(self, name: str) -> VariantDimension:
        for d in self.dimensions:
            if d.name == name:
                return d
        raise VariantError(
            f"unknown dimension {name!r}: "
            f"known={[d.name for d in self.dimensions]}"
        )

    def make_variant(
        self,
        stage: str,
        **flavors: str,
    ) -> Variant:
        """Build a `Variant` after validating every component.

        Raises `VariantError` if `stage` isn't on the stage axis,
        if any required dimension is missing from `flavors`, or if
        any supplied flavor value isn't in its dimension's value list.
        """

        if not self.stage_axis.is_valid(stage):
            raise VariantError(
                f"stage {stage!r} not in axis {self.stage_axis.name!r}: "
                f"valid={list(self.stage_axis.values)}"
            )
        provided: dict[str, str] = {}
        for d in self.dimensions:
            value = flavors.get(d.name)
            if value is None:
                raise VariantError(
                    f"dimension {d.name!r} requires a value (got {None!r})"
                )
            if not d.is_valid(value):
                raise VariantError(
                    f"dimension {d.name!r}: value {value!r} not valid; "
                    f"valid={list(d.values)}"
                )
            provided[d.name] = value
        # Reject extra flavors not declared in the config.
        extras = set(flavors) - {d.name for d in self.dimensions}
        if extras:
            raise VariantError(
                f"unknown flavor dimensions: {sorted(extras)}"
            )
        return Variant(stage=stage, flavors=tuple(sorted(provided.items())))

    def all_variants(self) -> tuple[Variant, ...]:
        """Enumerate every variant in the Cartesian product.

        Order: stage outermost (in axis order), then dimensions in
        declared order, each iterating in its values' declared order.
        """

        from itertools import product

        if not self.dimensions:
            return tuple(
                Variant(stage=s, flavors=())
                for s in self.stage_axis.values
            )

        dim_names = tuple(d.name for d in self.dimensions)
        dim_value_lists = tuple(d.values for d in self.dimensions)
        out: list[Variant] = []
        for stage in self.stage_axis.values:
            for combo in product(*dim_value_lists):
                flavors = tuple(sorted(zip(dim_names, combo, strict=False)))
                out.append(Variant(stage=stage, flavors=flavors))
        return tuple(out)


@dataclass(frozen=True)
class Variant:
    """A concrete (stage, flavor1, flavor2, …) tuple.

    `flavors` is stored as a sorted tuple of `(dimension_name, value)`
    pairs so equality is canonical regardless of construction order.
    """

    stage: str
    flavors: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        if not self.stage:
            raise VariantError("Variant.stage must be non-empty")
        names = [n for n, _ in self.flavors]
        if len(names) != len(set(names)):
            raise VariantError(
                f"Variant.flavors has duplicate dimension names: {names}"
            )

    @property
    def flavors_dict(self) -> Mapping[str, str]:
        return dict(self.flavors)

    def slug(self) -> str:
        """Filesystem-safe identifier for this variant.

        Example: `production-external-web`. Used by the v1.0
        per-variant artifact paths (`.sange/variants/<slug>/...`).
        """

        parts = [self.stage]
        parts.extend(value for _, value in self.flavors)
        return "-".join(parts)

    def has_flavor(self, dimension: str, value: str) -> bool:
        return self.flavors_dict.get(dimension) == value


__all__ = [
    "Variant",
    "VariantConfig",
    "VariantDimension",
    "VariantError",
    "VariantStageAxis",
]
