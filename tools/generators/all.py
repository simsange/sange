"""Run every deterministic generator in dependency order.

Two modes:

    python tools/generators/all.py --write   # regenerate every file on disk
    python tools/generators/all.py --check   # exit non-zero if any file is stale

The orchestrator owns:

  * The registry of T-G-001 .. T-G-016 entry points (below).
  * Topological dependency ordering via `graphlib.TopologicalSorter`.
  * A single shared clock (the `--clock` flag, defaulting to now-UTC) so every
    generator stamps the same `generated_at` and downstream byte-diffs are
    only ever about content, never about timestamps.
  * "Not implemented" reporting — Phase 0a stubs each generator until the
    real entry-point ships. Missing modules report cleanly rather than crash.

Exit codes (per `.design/sange-architecture-prompt.md` §7.0.8):

    0   All requested generators ran successfully (or skipped cleanly).
    2   Bad argument.
    65  User aborted (e.g. ^C).
    66  At least one generator failed integrity verification.
    67  At least one generator crashed.

Per ADR-023 / ADR-029 every generator is **deterministic** and **pure-stdlib**
where possible. The orchestrator itself never imports a non-stdlib library.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import importlib
import importlib.util
import sys
import traceback
from dataclasses import dataclass, field
from graphlib import CycleError, TopologicalSorter
from pathlib import Path

# Add the generators directory to the import path so `_lib.*` resolves both
# when running this file directly (`python tools/generators/all.py`) and when
# generators import each other.
_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from _lib.output import WriteMode  # noqa: E402  (after path bootstrap)

REPO_ROOT = _HERE.parent.parent

EXIT_OK = 0
EXIT_BAD_ARG = 2
EXIT_USER_ABORTED = 65
EXIT_VERIFY_FAILED = 66
EXIT_GENERATOR_CRASH = 67


# --------------------------------------------------------------------------- #
# Registry
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Generator:
    """A registered T-G-NNN entry-point.

    `module` names a Python module (relative to this directory). The
    orchestrator imports it lazily and calls `run(mode, clock)`. If the
    import fails the generator is reported as "not implemented" — a clean
    state, not a crash.
    """

    task_id: str
    module: str
    description: str
    output_paths: tuple[str, ...] = field(default_factory=tuple)
    dependencies: tuple[str, ...] = field(default_factory=tuple)


# Order in this list is informational only — actual run order is the
# topological sort over `dependencies`. Every T-G-NNN that lives in
# `.design/plans/checklist.md` Phase 0a is registered here.
REGISTRY: tuple[Generator, ...] = (
    Generator(
        task_id="T-G-001",
        module="git_catalog",
        description="Appendix D — Git command catalog.",
        output_paths=("docs/reference/appendix-d-git-catalog.md",),
        dependencies=(),
    ),
    Generator(
        task_id="T-G-002",
        module="svn_catalog",
        description="Appendix E — SVN command catalog.",
        output_paths=("docs/reference/appendix-e-svn-catalog.md",),
        dependencies=(),
    ),
    Generator(
        task_id="T-G-003",
        module="cross_vcs_map",
        description="Appendix F — cross-VCS concept map.",
        output_paths=("docs/reference/appendix-f-cross-vcs.md",),
        dependencies=("T-G-001", "T-G-002"),
    ),
    Generator(
        task_id="T-G-004",
        module="commit_templates",
        description="Appendix G — curated commit-message template library "
        "(folds v1's 104 strings + Conventional Commits 1.0.0).",
        output_paths=(
            "docs/reference/appendix-g-commit-templates.md",
            "templates/commit-templates/default.toml",
        ),
        dependencies=(),
    ),
    Generator(
        task_id="T-G-005",
        module="kit_manifest",
        description="templates/MANIFEST.toml (CI cosign-signs the output).",
        output_paths=("templates/MANIFEST.toml",),
        dependencies=(),
    ),
    Generator(
        task_id="T-G-006",
        module="docs_index",
        description="docs/README.md + docs/tools/README.md (the docs index "
        "tables both root README.md and the manual link into).",
        output_paths=("docs/README.md", "docs/tools/README.md"),
        dependencies=(
            "T-G-001",
            "T-G-002",
            "T-G-003",
            "T-G-004",
            "T-G-008",
            "T-G-009",
            "T-G-010",
            "T-G-011",
            "T-G-012",
            "T-G-015",
        ),
    ),
    Generator(
        task_id="T-G-007",
        module="adr_scaffold",
        description="On-demand ADR scaffolder (`docs/adr/NNNN-<slug>.md`).",
        output_paths=(),  # produces files on demand, not as part of `--write`
        dependencies=(),
    ),
    Generator(
        task_id="T-G-008",
        module="exit_codes",
        description="docs/reference/exit-codes.md from src/sange/exit_codes.py.",
        output_paths=("docs/reference/exit-codes.md",),
        dependencies=(),
    ),
    Generator(
        task_id="T-G-009",
        module="cli_reference",
        description="docs/reference/cli-reference.md (introspects the typer app).",
        output_paths=("docs/reference/cli-reference.md",),
        dependencies=(),
    ),
    Generator(
        task_id="T-G-010",
        module="jsonrpc_schema",
        description="docs/reference/json-rpc-schema.md.",
        output_paths=("docs/reference/json-rpc-schema.md",),
        dependencies=(),
    ),
    Generator(
        task_id="T-G-011",
        module="config_schema",
        description="docs/reference/config-schema.md (introspects SangeConfig).",
        output_paths=("docs/reference/config-schema.md",),
        dependencies=(),
    ),
    Generator(
        task_id="T-G-012",
        module="threat_model_table",
        description="docs/security/stride.md.",
        output_paths=("docs/security/stride.md",),
        dependencies=(),
    ),
    Generator(
        task_id="T-G-013",
        module="changelog_from_commits",
        description="docs/CHANGELOG.md from .sange/commits/*.json.",
        output_paths=("docs/CHANGELOG.md",),
        dependencies=(),
    ),
    Generator(
        task_id="T-G-014",
        module="hg_p4_catalogs",
        description="Mercurial + Perforce catalogs (v2.0 / v3.0 respectively).",
        output_paths=(
            "docs/reference/appendix-h-hg-catalog.md",
            "docs/reference/appendix-i-p4-catalog.md",
        ),
        dependencies=(),
    ),
    Generator(
        task_id="T-G-015",
        module="profile_registry",
        description="35 templates/gitignore-profiles/<category>/<name>.toml "
        "files + docs/reference/profile-registry.md (per §6.5.1).",
        output_paths=(
            "docs/reference/profile-registry.md",
            "templates/gitignore-profiles/",
        ),
        dependencies=(),
    ),
    Generator(
        task_id="T-G-016",
        module="verify_session_log",
        description="CI check that walks .design/plans/session-log.md and "
        "verifies cross-references + the `grounding` column (ADR-030 + ADR-031).",
        output_paths=(),  # produces a pass/fail report, not a file
        dependencies=(),
    ),
)

REGISTRY_BY_ID: dict[str, Generator] = {g.task_id: g for g in REGISTRY}


# --------------------------------------------------------------------------- #
# Execution
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class RunResult:
    task_id: str
    status: str  # "ok" | "not_implemented" | "skipped" | "crashed" | "stale"
    detail: str = ""


def _topo_order(ids: list[str]) -> list[str]:
    """Topological sort over the registry's dependencies, restricted to `ids`."""

    selected = {i for i in ids if i in REGISTRY_BY_ID}
    sorter: TopologicalSorter[str] = TopologicalSorter()
    for gid in selected:
        gen = REGISTRY_BY_ID[gid]
        deps = [d for d in gen.dependencies if d in selected]
        sorter.add(gid, *deps)
    try:
        return list(sorter.static_order())
    except CycleError as exc:
        raise SystemExit(f"dependency cycle in registry: {exc}") from exc


def _import_module(gen: Generator) -> object | None:
    """Try to import the generator's module. Return None on ModuleNotFoundError."""

    full = gen.module  # the module lives alongside `all.py` (sys.path was tweaked at module top)
    try:
        return importlib.import_module(full)
    except ModuleNotFoundError:
        return None


def _run_one(gen: Generator, mode: WriteMode, clock: _dt.datetime) -> RunResult:
    module = _import_module(gen)
    if module is None:
        return RunResult(
            task_id=gen.task_id,
            status="not_implemented",
            detail=f"module 'tools/generators/{gen.module}.py' does not exist yet",
        )
    runner = getattr(module, "run", None)
    if not callable(runner):
        return RunResult(
            task_id=gen.task_id,
            status="crashed",
            detail=f"module '{gen.module}' has no callable `run(mode, clock)`",
        )
    try:
        outcomes = runner(mode=mode, clock=clock)
    except Exception as exc:
        return RunResult(
            task_id=gen.task_id,
            status="crashed",
            detail=f"{exc.__class__.__name__}: {exc}\n{traceback.format_exc()}",
        )

    if mode is WriteMode.CHECK:
        stale = [o for o in (outcomes or ()) if getattr(o, "result", None) and o.result.value != "match"]
        if stale:
            paths = ", ".join(str(o.path) for o in stale)
            return RunResult(task_id=gen.task_id, status="stale", detail=f"out-of-date: {paths}")

    return RunResult(task_id=gen.task_id, status="ok", detail=f"{len(outcomes or ())} file(s)")


def run(
    *,
    mode: WriteMode,
    only: set[str] | None = None,
    skip: set[str] | None = None,
    clock: _dt.datetime | None = None,
) -> list[RunResult]:
    clock = clock or _dt.datetime.now(tz=_dt.UTC)
    ids = [g.task_id for g in REGISTRY]
    if only:
        ids = [i for i in ids if i in only]
    if skip:
        ids = [i for i in ids if i not in skip]
    order = _topo_order(ids)
    results: list[RunResult] = []
    for gid in order:
        results.append(_run_one(REGISTRY_BY_ID[gid], mode=mode, clock=clock))
    return results


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="generators.all",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    mode_group = p.add_mutually_exclusive_group(required=False)
    mode_group.add_argument(
        "--write",
        action="store_const",
        dest="mode",
        const=WriteMode.WRITE,
        help="Regenerate every selected output (default).",
    )
    mode_group.add_argument(
        "--check",
        action="store_const",
        dest="mode",
        const=WriteMode.CHECK,
        help="Verify every selected output is up-to-date; exit non-zero on drift.",
    )
    p.add_argument(
        "--only",
        nargs="+",
        metavar="ID",
        help="Run only these T-G-NNN IDs (e.g. --only T-G-001 T-G-008).",
    )
    p.add_argument(
        "--skip",
        nargs="+",
        metavar="ID",
        help="Run every generator EXCEPT these IDs.",
    )
    p.add_argument(
        "--clock",
        metavar="ISO8601",
        help="Override the shared generation timestamp (default: now UTC). "
        "Use this in CI to keep outputs byte-stable when re-running.",
    )
    p.add_argument(
        "--list",
        action="store_true",
        help="Print the registry and exit (no work).",
    )
    args = p.parse_args(argv)
    if args.mode is None:
        args.mode = WriteMode.WRITE
    return args


def _format_clock(text: str) -> _dt.datetime:
    # Accept the trailing Z form (UTC) as well as offset-bearing ISO 8601.
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    return _dt.datetime.fromisoformat(text).astimezone(_dt.UTC)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    if args.list:
        for gen in REGISTRY:
            deps = ",".join(gen.dependencies) if gen.dependencies else "—"
            print(f"{gen.task_id:<10} {gen.module:<24} deps={deps}")
            print(f"           {gen.description}")
            if gen.output_paths:
                for path in gen.output_paths:
                    print(f"           → {path}")
            print()
        return EXIT_OK

    only = set(args.only) if args.only else None
    skip = set(args.skip) if args.skip else None
    clock = _format_clock(args.clock) if args.clock else None

    try:
        results = run(mode=args.mode, only=only, skip=skip, clock=clock)
    except KeyboardInterrupt:
        return EXIT_USER_ABORTED

    n_ok = sum(1 for r in results if r.status == "ok")
    n_not_impl = sum(1 for r in results if r.status == "not_implemented")
    n_crashed = sum(1 for r in results if r.status == "crashed")
    n_stale = sum(1 for r in results if r.status == "stale")

    width = max((len(r.task_id) for r in results), default=8)
    for r in results:
        line = f"[{r.status:<16}] {r.task_id:<{width}} {r.detail}"
        out = sys.stderr if r.status in {"crashed", "stale"} else sys.stdout
        print(line, file=out)

    summary = (
        f"\nall.py: mode={args.mode.value} "
        f"ok={n_ok} not_implemented={n_not_impl} stale={n_stale} crashed={n_crashed} "
        f"of {len(results)} registered"
    )
    print(summary, file=sys.stderr if (n_crashed or n_stale) else sys.stdout)

    if n_crashed:
        return EXIT_GENERATOR_CRASH
    if n_stale:
        return EXIT_VERIFY_FAILED
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
