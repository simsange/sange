# Contributing to Sange

Thanks for taking the time. Sange is the local-first developer-experience
layer between humans and their VCS — and the audience scope (§3 of
`.design/sange-architecture-prompt.md`) is deliberately broad: contributions
from non-developer founders, CTOs, junior engineers, senior staff engineers,
DevOps/SRE, OSS maintainers, and cyber-security reviewers are all welcome.

This file is the lightweight summary. The full process lives in
[`docs/governance/contributing.md`](docs/governance/contributing.md) once the
generators emit it (T-G-006).

## The short version

1. **Open an issue first** for anything more than a typo fix. We want to align
   on scope before you spend time.
2. **Run the gates** locally: `ruff`, `mypy --strict`, `pytest`, `pre-commit run --all-files`.
3. **Sign your commits** if your environment supports it (`git commit -S`).
4. **Conventional Commits 1.0.0** for commit messages. The §6.8 commit
   lifecycle enforces this; the AI commit-message helper can generate them.
5. **One PR per concern.** Refactors and feature work do not share a PR.

## Setup

```bash
git clone https://github.com/simsange/sange.git
cd sange

# Per-repo identity (do NOT set this globally — see ~/.claude/CLAUDE.md):
git config user.email "19682005+imanimanyara@users.noreply.github.com"
git config user.name  "Imani Manyara"
# (External contributors: use your own GitHub noreply address.)

# Python 3.12+ required (see pyproject.toml::requires-python).
python -m venv .venv
source .venv/bin/activate

pip install -e ".[dev]"
pre-commit install
```

## Quality gates (run before every commit)

```bash
ruff check .
ruff format --check .
mypy
pytest
pre-commit run --all-files
```

CI runs the same set; please don't push until they're green locally.

## ADRs

Sange records every non-trivial architectural decision as an
**Architecture Decision Record** under `docs/adr/NNNN-<slug>.md`. The current
canonical list is `.design/plans/decisions-log.md`. If your PR changes the
architecture in any way, include an ADR.

Scaffold a new ADR with `python tools/generators/adr_scaffold.py <title>`
(landing as part of T-G-007).

## Sange-specific conventions

- **No flat fragment trees** — every fragment lives under one of the canonical
  category sub-directories (`_core/`, `vcs/`, `lang/`, `framework/`, `infra/`,
  `cloud/`, `ci/`, `release/`, `security/`, `ai/`, `db/`, `editor/`, `os/`,
  `domain/`, `type/`, `workflow/`). See §10.4 of the architecture prompt.
- **No commits of the auto-generated `Makefile`** — `sange doctor` blocks this.
- **No `--no-verify`** to skip hooks. Fix the hook failure instead.
- **No invented IDs.** Per ADR-030, every `ADR-NNN`, `T-NNN`, `R-NNN`, `S-NNN`
  reference must resolve to a real entry. The model that drafts your PR (if
  you use one) is expected to follow the same rule.

## Code of conduct

By participating, you agree to abide by the
[Code of Conduct](CODE_OF_CONDUCT.md). Enforcement inbox:
`opensource@simtabi.com`.

## Security

See [`SECURITY.md`](SECURITY.md) for the disclosure process.

## Licensing

Sange is Apache-2.0 (per ADR-007). Your contributions land under the same
license. By submitting a contribution you affirm you have the right to do so
under those terms.

## Asking for help

- **Bugs / feature requests:** GitHub Issues at
  <https://github.com/simsange/sange/issues>.
- **Security:** `opensource@simtabi.com`.
- **General questions:** GitHub Discussions (enabled on the repo).
- **Architectural debates:** open a PR with a draft ADR rather than a thread.

Welcome aboard.
