# Python projects with Sange

Sange is itself a Python project, so its Python integration is
well-tested by inversion. This doc covers Python-specific
workflows: the gitignore profile, the `sange init` flow on a
Python repo, pre-commit gates, and CI integration.

For non-Python-specific behavior, see
[`../workflow/commit-lifecycle.md`](../workflow/commit-lifecycle.md)
and [`../vcs/git.md`](../vcs/git.md).

## The Python gitignore profile

Sange ships a curated `lang/python` profile in the 35-profile
registry. It's auto-detected when any of the following is at the
repo root:

- `pyproject.toml`
- `setup.py`
- `requirements.txt`
- `Pipfile`

The detector boosts confidence when it also sees `.python-version`,
`uv.lock`, `poetry.lock`, or `Pipfile.lock`. Generated upstream
from
[github/gitignore/Python.gitignore](https://github.com/github/gitignore/blob/main/Python.gitignore)
and re-emitted via T-G-015 (`tools/generators/profile_registry.py`).

To inspect or apply manually:

```bash
sange init --profile lang/python              # scaffold .sange/ with this profile
sange scaffold list | grep python             # list available profiles (v0.5+)
sange scaffold show lang/python               # see the full profile contents (v0.5+)
```

The full profile registry lives at
[`../../reference/profile-registry.md`](../../reference/profile-registry.md);
the on-disk source is `templates/gitignore-profiles/lang/python.toml`.

## Bootstrapping a Python project

The recommended layout matches what Sange itself uses
(`src/<package>/` per PEP 561, hatchling build backend, Python
3.12+ floor):

```
my-python-project/
├── src/
│   └── mypackage/
│       ├── __init__.py
│       └── py.typed
├── tests/
│   └── __init__.py
├── pyproject.toml
├── ruff.toml
├── mypy.ini
├── .pre-commit-config.yaml
├── .gitignore
├── README.md
├── LICENSE
├── CHANGELOG.md
├── CONTRIBUTING.md
├── SECURITY.md
├── CODE_OF_CONDUCT.md
└── .github/
    ├── workflows/
    │   ├── ci.yml
    │   └── release.yml
    ├── ISSUE_TEMPLATE/
    └── PULL_REQUEST_TEMPLATE.md
```

`sange init` lays down `.sange/commits/` + `.sange/telemetry/` +
`.sange/.gitignore` (which gitignores telemetry & private files
inside `.sange/` while keeping the lifecycle records committable).

## A typical Python commit flow

```bash
# 1. Make changes in src/mypackage/...
vim src/mypackage/feature.py

# 2. Stage them.
git add src/mypackage/feature.py tests/unit/test_feature.py

# 3. Generate a commit message via Sange. Mock provider works
#    without API keys; switch to anthropic/openai/etc. for real
#    use.
git diff --cached | sange commit \
    --provider anthropic --model claude-sonnet-4-6

# 4. Review the rendered draft, then approve.
sange commits approve 1

# 5. Land it. Pushes to origin (or use --no-push for local-only).
sange commits push 1
```

For routine commits that don't warrant AI:

```bash
sange commits new feat "add feature X" --scope mypackage \
    --body "Implementation details."
sange commits approve 1
sange commits push 1
```

See [`../workflow/commit-lifecycle.md`](../workflow/commit-lifecycle.md)
for the full state machine.

## Local quality gates

For projects that mirror Sange's discipline (or any modern Python
project), the standard 4-gate trio lives in `pyproject.toml::optional-dependencies::dev`:

```toml
[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
    "pytest-cov>=5.0",
    "hypothesis>=6.100",
    "ruff>=0.5",
    "mypy>=1.10",
    "pre-commit>=4.0",
]
```

Then:

```bash
pip install -e ".[dev]"

pytest -q                                  # tests
ruff check .                               # lint
mypy src                                   # type check
python -m build                            # sdist + wheel
```

For projects that want pre-commit auto-runs:

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.5.0
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.10.0
    hooks:
      - id: mypy
        additional_dependencies: [pydantic, types-PyYAML]
```

Then `pre-commit install` once; subsequent `git commit` runs the
hooks. Sange's commit lifecycle is **not** a replacement for
`pre-commit` — it's a complementary lifecycle for the *message
authoring* + *approval* + *audit*. Sange and pre-commit run
side-by-side: pre-commit gates the diff, Sange tracks the
lifecycle.

## CI integration

Sange's own `.github/workflows/ci.yml` is a good template:

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ${{ matrix.os }}
    strategy:
      matrix:
        os: [ubuntu-24.04, ubuntu-24.04-arm, macos-14]
        python: ["3.12", "3.13"]
    steps:
      - uses: actions/checkout@v6
      - uses: actions/setup-python@v6
        with:
          python-version: ${{ matrix.python }}
          cache: pip
      - run: pip install -e ".[dev]"
      - run: pytest -q

  lint:
    runs-on: ubuntu-24.04
    steps:
      - uses: actions/checkout@v6
      - uses: actions/setup-python@v6
        with:
          python-version: "3.12"
      - run: pip install "ruff>=0.5"
      - run: ruff check .

  typecheck:
    runs-on: ubuntu-24.04
    steps:
      - uses: actions/checkout@v6
      - uses: actions/setup-python@v6
        with:
          python-version: "3.12"
      - run: pip install -e ".[dev]"
      - run: mypy src
```

Action versions verified against `api.github.com/repos/<action>/releases/latest`
per CLAUDE.md "Verification before pinning" — re-pin via
Dependabot on every merged dep PR.

## Release pipeline

For releases via the same OIDC trusted-publisher + sigstore +
SBOM posture Sange itself uses, see
[`../../release.md`](../../release.md) for the full recipe and
[`../../security/slsa-and-sbom.md`](../../security/slsa-and-sbom.md)
for the supply-chain claims.

Sange's release workflow (`.github/workflows/release.yml`) is
copy-friendly: replace the `sange` package name + the
`simsange/sange` owner/repo references with yours, configure
the trusted-publisher record on PyPI, and the same pipeline
publishes wheel + sdist + multi-arch image with sigstore + SBOM.

## Python version policy

Sange itself targets Python **3.12 floor / 3.13 ceiling**. Projects
that integrate with Sange should pick a compatible floor:

| Use case | Recommended Python |
| :--- | :--- |
| Sange the dev (hack on Sange) | 3.13 |
| Sange the user (use the CLI) | 3.12+ |
| Library consumer (`import sange`) | 3.12+ |
| CI matrix coverage | 3.12 + 3.13 |

The 3.12 floor is set in `pyproject.toml::requires-python` and
enforced both at install time (pip refuses install on < 3.12)
and at CI matrix time (the test matrix only runs 3.12 + 3.13).

## What's NOT in v0.1

These ship later:

- **`sange scaffold add lang/python`** (v1.0) — the full per-tool
  add/diff/update/remove/verify surface.
- **`sange bootstrap`** (v0.5+) — orchestrate `brew install
  python@3.13` / `apt install python3.12-venv` / `mise use
  python@3.13` cross-platform.
- **`sange lang python`** sub-app (v0.5+) — Python-specific
  shortcuts (publish to PyPI, regenerate `pyproject.toml::dependencies`
  from imports, etc.).
- **Per-framework profiles** (v0.5+) — Django / Flask / FastAPI /
  Pyramid extending `lang/python`.

## Cross-references

- [`../workflow/commit-lifecycle.md`](../workflow/commit-lifecycle.md)
  — end-to-end commit flow.
- [`../vcs/git.md`](../vcs/git.md) — Git adapter details Sange
  layers on top of.
- [`../../reference/profile-registry.md`](../../reference/profile-registry.md)
  — full gitignore profile registry (regenerated by T-G-015).
- [`../../release.md`](../../release.md) — operator release recipe;
  the same workflow shape Sange uses.
- [`../../security/slsa-and-sbom.md`](../../security/slsa-and-sbom.md)
  — what the release pipeline claims about each artifact.
- [`../../installation.md`](../../installation.md) — installing
  Sange itself.
- [`templates/gitignore-profiles/lang/python.toml`](../../../templates/gitignore-profiles/lang/python.toml)
  — the profile source on disk.
