"""Every third-party module `src/` imports must be a declared dependency.

This exists because the opposite went unnoticed for the life of the package.
`click` was imported by ten modules under `src/sange/cli/` and declared nowhere:
it arrived transitively through `typer`, which depended on it. When typer 0.26.0
dropped click, `pip install -e .` stopped installing it and the suite failed at
collection with `ModuleNotFoundError: No module named 'click'` -- in a repository
whose own tests, ruff and mypy had all been green the day before.

Nothing could have caught that, because no test compared what the code imports
against what the project declares. A green suite proves the installed environment
happens to satisfy the imports; it says nothing about whether the manifest asked
for them. This test asks.

Two details are load-bearing:

* **Function-local imports count.** All ten click imports sat inside function
  bodies, so a scan of module headers -- or a grep for `^import` -- finds none of
  them. The walk is over the full AST.
* **The counts are asserted.** A walk whose glob stops matching reports a clean
  tree rather than a broken search, so both the number of files parsed and the
  number of third-party modules found have floors. Zero is the answer a broken
  scan gives, and it must not be the answer that passes.
"""

from __future__ import annotations

import ast
import re
import sys
import tomllib
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_PYPROJECT = _REPO_ROOT / "pyproject.toml"
_SRC = _REPO_ROOT / "src"

# A walk that silently matches less than this has broken, not improved. Both
# floors sit meaningfully below the measured values (87 files, 6 modules on
# 2026-10-05) so ordinary growth or a removed module does not trip them.
_MIN_FILES = 60
_MIN_THIRD_PARTY = 5

# Import name -> distribution name, for the cases where they differ. Only needed
# when a package's import name is not its PyPI name; anything absent is compared
# under its own normalised name.
_IMPORT_TO_DIST = {
    "magic": "python-magic",
    "yaml": "pyyaml",
    "dateutil": "python-dateutil",
    "pkg_resources": "setuptools",
}

_FIRST_PARTY = {"sange"}
_NOT_A_PACKAGE = {"__future__"}


def _normalise(name: str) -> str:
    """PEP 503 normalisation, so `tomli_w`, `tomli-w` and `Tomli.W` compare equal."""
    return re.sub(r"[-_.]+", "-", name).lower()


def _declared() -> tuple[set[str], set[str]]:
    """(runtime, runtime + every optional group), both PEP 503 normalised."""
    data = tomllib.loads(_PYPROJECT.read_text(encoding="utf-8"))
    project = data["project"]

    def names(specs: list[str]) -> set[str]:
        out = set()
        for spec in specs:
            # Strip extras, markers and version constraints: `foo[bar]>=1 ; python<"4"`
            head = spec.split(";")[0].strip()
            head = re.split(r"[\[<>=!~ ]", head, maxsplit=1)[0]
            if head:
                out.add(_normalise(head))
        return out

    runtime = names(project.get("dependencies", []))
    optional = set(runtime)
    for group in (project.get("optional-dependencies") or {}).values():
        optional |= names(group)
    return runtime, optional


def _optional_import_nodes(tree: ast.AST) -> set[ast.AST]:
    """Import nodes inside a `try:` whose handler catches an import failure.

    An optional dependency is imported defensively and degrades at runtime, so it
    belongs in an extra rather than in `dependencies`. Treating those as hard
    requirements would force every extra into the base install.
    """
    guarded: set[ast.AST] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Try):
            continue
        caught: set[str] = set()
        for handler in node.handlers:
            if isinstance(handler.type, ast.Name):
                caught.add(handler.type.id)
            elif isinstance(handler.type, ast.Tuple):
                caught |= {e.id for e in handler.type.elts if isinstance(e, ast.Name)}
        if caught & {"ImportError", "ModuleNotFoundError"}:
            for stmt in node.body:
                for sub in ast.walk(stmt):
                    guarded.add(sub)
    return guarded


def _imports() -> tuple[dict[str, set[str]], dict[str, set[str]], int]:
    """(hard, optional, files_parsed) -- module -> the files importing it."""
    stdlib = set(sys.stdlib_module_names) | _NOT_A_PACKAGE
    hard: dict[str, set[str]] = {}
    optional: dict[str, set[str]] = {}
    files = 0

    for path in sorted(_SRC.rglob("*.py")):
        files += 1
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        guarded = _optional_import_nodes(tree)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules = [alias.name.split(".")[0] for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                modules = [node.module.split(".")[0]]
            else:
                continue
            for module in modules:
                if module in stdlib or module in _FIRST_PARTY:
                    continue
                bucket = optional if node in guarded else hard
                rel = str(path.relative_to(_REPO_ROOT))
                bucket.setdefault(module, set()).add(rel)

    return hard, optional, files


@pytest.fixture(scope="module")
def scan() -> tuple[dict[str, set[str]], dict[str, set[str]], int]:
    return _imports()


class TestScanIsRealistic:
    """Guard the guard: a scan that inspected nothing must not report success."""

    def test_pyproject_exists(self) -> None:
        assert _PYPROJECT.is_file()

    def test_src_tree_exists(self) -> None:
        assert _SRC.is_dir()

    def test_parsed_enough_files(self, scan) -> None:
        _, _, files = scan
        assert files >= _MIN_FILES, (
            f"parsed only {files} files under src/ (floor {_MIN_FILES}); "
            "the glob has stopped matching rather than the tree having shrunk"
        )

    def test_found_third_party_imports(self, scan) -> None:
        hard, _, _ = scan
        assert len(hard) >= _MIN_THIRD_PARTY, (
            f"found only {len(hard)} third-party imports (floor {_MIN_THIRD_PARTY}); "
            "zero is what a broken AST walk reports, so this cannot pass on nothing"
        )

    def test_declared_set_is_not_empty(self) -> None:
        runtime, _ = _declared()
        assert runtime, "parsed no runtime dependencies out of pyproject.toml"


class TestEveryImportIsDeclared:
    def test_hard_imports_are_runtime_dependencies(self, scan) -> None:
        hard, _, _ = scan
        runtime, _ = _declared()
        missing = {
            module: sorted(files)
            for module, files in hard.items()
            if _normalise(_IMPORT_TO_DIST.get(module, module)) not in runtime
        }
        assert not missing, (
            "imported unconditionally by src/ but absent from [project.dependencies] -- "
            "these resolve only while something else happens to pull them in:\n"
            + "\n".join(f"  {m}: {', '.join(f)}" for m, f in sorted(missing.items()))
        )

    def test_optional_imports_are_declared_somewhere(self, scan) -> None:
        _, optional, _ = scan
        _, declared = _declared()
        missing = {
            module: sorted(files)
            for module, files in optional.items()
            if _normalise(_IMPORT_TO_DIST.get(module, module)) not in declared
        }
        assert not missing, (
            "imported behind try/except ImportError but declared in no dependency "
            "group, so no extra installs them:\n"
            + "\n".join(f"  {m}: {', '.join(f)}" for m, f in sorted(missing.items()))
        )


class TestClickIsPinnedToATyperThatProvidesIt:
    """`click.get_current_context()` only works while typer runs on click.

    typer 0.26.0 dropped click, so an uncapped typer satisfies the click import
    while breaking the 32 calls that import exists for -- a green install with a
    runtime failure, which is worse than the build break it replaces.
    """

    def test_click_is_declared(self) -> None:
        runtime, _ = _declared()
        assert "click" in runtime

    def test_typer_is_capped_below_the_click_free_release(self) -> None:
        data = tomllib.loads(_PYPROJECT.read_text(encoding="utf-8"))
        specs = [
            s for s in data["project"]["dependencies"]
            if _normalise(re.split(r"[\[<>=!~ ]", s, maxsplit=1)[0]) == "typer"
        ]
        assert len(specs) == 1, f"expected exactly one typer requirement, got {specs}"
        assert "<0.26" in specs[0].replace(" ", ""), (
            f"typer is declared as {specs[0]!r} with no ceiling below 0.26. "
            "typer 0.26.0 removed click, so src/sange/cli/'s "
            "click.get_current_context() calls would import a click that no longer "
            "drives the CLI. Migrate them to typer.Context before lifting this."
        )
