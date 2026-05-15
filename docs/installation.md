# Installation

Pick the install path that matches how you'll use Sange. All
paths land the same `sange` CLI; differences are in how you
update it and whether you pull provider SDKs ahead of time.

> **Status note.** `pip install sange` lights up once the v0.1.0
> PyPI trusted-publisher record activates. Until then, install
> from source (option 1 below) or pull the multi-arch Docker
> image (option 3). Track the gating status in
> [`release.md`](release.md#step-0--pre-flight-checklist) and
> the v0.1.0 known-issues in
> [`../CHANGELOG.md#010--2026-05-14`](../CHANGELOG.md#010--2026-05-14).

## Requirements

| Component | Minimum | Recommended |
| :--- | :--- | :--- |
| Python | 3.12 | 3.13 |
| git | 2.40 | 2.50+ (newer push semantics work cleanly) |
| Disk | 200 MB for the wheel + deps | 1 GB if you build the Docker image locally |
| OS | macOS 13+, Ubuntu 22.04+, Windows 11 (WSL2 or native) | macOS 14+ / Ubuntu 24.04+ |

For container use (option 3), only Docker is required — Python,
git, and the rest ship inside the image.

## Option 1: From source (works today)

The recommended path while the PyPI publisher is still pending.
You get the latest `main`, optional dev tooling, and editable
installs for hacking.

```bash
git clone https://github.com/simsange/sange.git
cd sange
python3 -m venv .venv && source .venv/bin/activate
pip install -e .

# Verify:
sange --version
sange doctor
```

For hacking on Sange itself (tests, lint, type-check, hooks):

```bash
pip install -e ".[dev]"

# Then:
pytest -q                                  # 1163 tests + 1 env-skipped
ruff check .                               # 0 errors
mypy src                                   # 0 issues
python tools/generators/all.py --check     # 12/14 ok, 2 not-implemented
```

The `.venv-smoke` convention used in `release.md` is a fresh
isolated venv for verification; that's separate from your
working `.venv`.

## Option 2: From PyPI (works once the publisher activates)

```bash
pip install sange
```

With one or more provider SDKs:

```bash
pip install 'sange[ai-anthropic]'
pip install 'sange[ai-openai]'
pip install 'sange[ai-ollama]'
pip install 'sange[ai-google]'
pip install 'sange[ai-bedrock]'
pip install 'sange[ai-all]'    # all of the above
```

With the optional TUI:

```bash
pip install 'sange[tui]'
```

Combinations:

```bash
pip install 'sange[ai-anthropic,ai-openai,tui]'
```

The `mock` provider is always available with the base install —
no extras needed for testing or CI scenarios.

## Option 3: Docker

The release pipeline pushes a multi-arch image (linux/amd64 +
linux/arm64) to GHCR per release. Pull, run, mount your repo at
`/repo`:

```bash
docker pull ghcr.io/simsange/sange:v0.1.0          # specific tag
docker pull ghcr.io/simsange/sange:latest          # tracks latest

docker run --rm \
    -v "$PWD:/repo" \
    -w /repo \
    ghcr.io/simsange/sange:v0.1.0 \
    sange doctor
```

> The v0.1.0 image is currently published as a **private** GHCR
> package. Anonymous `docker pull` requires the maintainer to
> flip the package visibility to "Public" at
> `github.com/orgs/simsange/packages`. Until then, authenticate
> with a personal access token before pulling.

For supply-chain verification of the image before deploy, see
[`security/slsa-and-sbom.md`](security/slsa-and-sbom.md).

## Option 4: pipx (isolated install)

Pipx puts Sange in its own venv that doesn't interfere with
project venvs:

```bash
pipx install sange                       # base
pipx install 'sange[ai-anthropic]'       # with one provider
pipx inject sange anthropic              # add a provider later
```

Pipx upgrades cleanly across versions and is the recommended
path for "I want `sange` on my PATH globally without
contaminating any project's venv".

## Per-platform notes

### macOS

```bash
# Homebrew Python (recommended):
brew install python@3.13
python3.13 -m venv .venv && source .venv/bin/activate
pip install -e .

# Apple Silicon: the multi-arch image's linux/arm64 layer runs
# natively under Docker Desktop.
```

### Linux

```bash
# Ubuntu / Debian:
sudo apt install python3.12 python3.12-venv git
python3.12 -m venv .venv && source .venv/bin/activate
pip install -e .

# Fedora / RHEL:
sudo dnf install python3.12 python3.12-pip git
```

ARM64 Linux (Hetzner Ampere, AWS Graviton, Raspberry Pi 4/5)
runs the linux/arm64 image natively per ADR-033.

### Windows

Native Windows (PowerShell):

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .
```

WSL2 (recommended — Sange targets POSIX semantics first):

```bash
# Inside an Ubuntu WSL distro:
sudo apt install python3.12 python3.12-venv git
python3.12 -m venv .venv && source .venv/bin/activate
pip install -e .
```

The `sange` daemon on Windows runs as a Windows Service via
`pywin32` (v1.0+); on macOS / Linux as a launchd or systemd-user
unit.

## Verifying the install

After any of the above:

```bash
sange --version
# Should print something like:  sange 0.1.0.dev0   (or 0.1.0 from a release wheel)

sange doctor
# Runs environment checks. Every line should print 'ok' unless your
# environment is genuinely missing something (e.g. no git on PATH).

sange --help
# Lists the top-level verbs:  doctor / commit / init / ai / commits
```

If `sange doctor` reports a `failed` line, the hint inline tells
you what to do. The exit-code dictionary is in
[`reference/exit-codes.md`](reference/exit-codes.md).

## Upgrading

| Install path | Upgrade command |
| :--- | :--- |
| From source | `git pull && pip install -e .` |
| From PyPI | `pip install -U sange` |
| Docker | `docker pull ghcr.io/simsange/sange:latest` |
| pipx | `pipx upgrade sange` |

For breaking-change releases (v0.5, v1.0, v2.0, v3.0 — see
[`governance/roadmap.md`](governance/roadmap.md)), the
[`../CHANGELOG.md`](../CHANGELOG.md) entry calls out the
migration. Pre-1.0 minor bumps may include breaking changes per
semver; post-1.0 minor bumps are additive-only.

## Uninstalling

| Install path | Uninstall command |
| :--- | :--- |
| From source / PyPI | `pip uninstall sange` |
| Docker | `docker rmi ghcr.io/simsange/sange:v0.1.0` |
| pipx | `pipx uninstall sange` |

The local repo state (`.sange/` in each project) is **not**
touched by uninstall — it's part of the repo, not the install.
To remove it from a specific repo: `rm -rf .sange/`.

## Common install issues

- **`ERROR: Could not find a version that satisfies the requirement sange`** —
  the PyPI publisher isn't active yet. Use option 1 or option 3.
- **`pip install -e .` fails with "hatchling not found"** — old pip;
  upgrade with `pip install --upgrade pip`.
- **`sange doctor` reports `git: not found`** — install git and
  re-run. Sange's Git adapter shells out to a real `git` binary.
- **macOS / Linux: `sange: command not found` after install** —
  the venv isn't activated. Run `source .venv/bin/activate`. Or
  install via pipx (option 4) for PATH-global access.
- **`pip install 'sange[ai-anthropic]'` fails with "extras not
  found"** — the extras come from `pyproject.toml`; if you
  installed via `pip install -e .`, the extras should resolve.
  Otherwise check pip version.

## Cross-references

- [`quickstart.md`](quickstart.md) — 5-minute end-to-end after install.
- [`release.md`](release.md) — operator-facing release recipe;
  Step 0 is the PyPI pre-flight checklist.
- [`security/slsa-and-sbom.md`](security/slsa-and-sbom.md) —
  verify the published image / wheel before deploying.
- [`governance/roadmap.md`](governance/roadmap.md) — what each
  release adds.
- [`reference/cli-reference.md`](reference/cli-reference.md) —
  every flag and command, generated.
- [`reference/exit-codes.md`](reference/exit-codes.md) — what
  every exit code means.
