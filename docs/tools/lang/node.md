# Node.js projects with Sange

Sange is provider-agnostic and language-agnostic — every flow that
works for [Python projects](./python.md) works identically for
Node.js. This doc covers the Node-specific bits: the gitignore
profile, package-manager differences, and CI integration.

## The Node.js gitignore profile

Sange ships a curated `lang/node` profile in the 35-profile
registry. Auto-detected when any of these is at the repo root:

- `package.json`
- `package-lock.json`
- `yarn.lock`
- `pnpm-lock.yaml`
- `bun.lockb`

Confidence-boosting if it also sees `npm-shrinkwrap.json` or
`.nvmrc`. Generated upstream from
[github/gitignore/Node.gitignore](https://github.com/github/gitignore/blob/main/Node.gitignore)
and re-emitted via T-G-015.

To inspect or apply:

```bash
sange init --profile lang/node                # scaffold .sange/
sange scaffold list | grep node               # list profiles (v0.5+)
sange scaffold show lang/node                 # see profile contents (v0.5+)
```

Source on disk: `templates/gitignore-profiles/lang/node.toml`.
Full registry: [`../../reference/profile-registry.md`](../../reference/profile-registry.md).

## Recommended layout

For a modern Node / TypeScript library or service:

```
my-node-project/
├── src/
│   └── index.ts
├── tests/
│   └── index.test.ts
├── package.json
├── tsconfig.json
├── eslint.config.js              # flat config (v9+)
├── .prettierrc
├── .gitignore
├── README.md
├── LICENSE
├── CHANGELOG.md
└── .github/
    ├── workflows/
    │   ├── ci.yml
    │   └── release.yml
    ├── ISSUE_TEMPLATE/
    └── PULL_REQUEST_TEMPLATE.md
```

`sange init` works the same on Node projects as on Python — it
lays down `.sange/commits/` + `.sange/telemetry/` + `.sange/.gitignore`.

## Package manager support

Sange doesn't care which package manager you use. The gitignore
profile covers every output any of them produces:

| Tool | Lockfile detected | Outputs gitignored |
| :--- | :--- | :--- |
| npm | `package-lock.json` | `node_modules/`, `npm-debug.log*` |
| Yarn (Classic + Berry) | `yarn.lock` | `.yarn/cache`, `.yarn/install-state.gz`, `.pnp.*` |
| pnpm | `pnpm-lock.yaml` | `node_modules/`, `.pnpm-store/` |
| Bun | `bun.lockb` | `bun.lockb` (kept), bun cache (ignored) |

For monorepos, both `lang/node` and the per-workspace profiles
compose — Sange's profile composition mirrors the Android Studio
multi-dimensional variant matrix (ADR-032).

## A typical Node commit flow

Identical to Python:

```bash
# Stage changes.
git add src/

# AI-driven commit message via Sange.
git diff --cached | sange commit \
    --provider anthropic --model claude-sonnet-4-6

# Approve + push.
sange commits approve 1
sange commits push 1
```

Or manual:

```bash
sange commits new feat "add user auth" --scope auth \
    --body "Adds JWT token rotation."
sange commits approve 1
sange commits push 1
```

Conventional Commits 1.0.0 conventions for JS/TS projects:

| Type | When |
| :--- | :--- |
| `feat` | New public API / new component / new exported function. |
| `fix` | Bug fix. |
| `docs` | README / JSDoc / inline comments. |
| `refactor` | Internal restructuring with no behavior change. |
| `test` | Test-only changes. |
| `chore` | Dependency bumps, CI config, build tooling. |
| `perf` | Measurable performance change. |

For scope, conventions vary by project — common patterns: package
name in a monorepo (`@scope/pkg`), feature area (`auth` / `ui` /
`api`), or library subsystem (`router` / `store` / `cli`).

## Local quality gates

Modern Node project gates (the equivalents to Python's
ruff+mypy+pytest+build):

| Gate | Tool | Command |
| :--- | :--- | :--- |
| Lint | ESLint 9+ (flat config) | `npx eslint .` |
| Format | Prettier | `npx prettier --check .` |
| Types | TypeScript | `npx tsc --noEmit` |
| Tests | Vitest / Jest / Node's built-in | `npm test` |
| Build | tsup / Rollup / esbuild / tsc | `npm run build` |

Sange's CLI flow runs **alongside** those, not in place of them.
The commit lifecycle wraps the *message authoring* + *approval* +
*audit*. Your existing lint/test gates run via `husky` /
`lint-staged` / GitHub Actions / etc.

## CI integration

Copy-friendly Node workflow (`.github/workflows/ci.yml`):

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  build:
    runs-on: ${{ matrix.os }}
    strategy:
      matrix:
        os: [ubuntu-24.04, macos-14]
        node: ["20", "22"]
    steps:
      - uses: actions/checkout@v6
      - uses: actions/setup-node@v5
        with:
          node-version: ${{ matrix.node }}
          cache: npm
      - run: npm ci
      - run: npm run lint
      - run: npm test
      - run: npm run build
```

Action versions verified against
`api.github.com/repos/<action>/releases/latest` per CLAUDE.md
"Verification before pinning". Re-pin via Dependabot on every
merged dep PR.

## Release pipeline

For Node packages, the same OIDC trusted-publisher posture Sange
uses for PyPI applies to npm. The npm-side equivalent:

```yaml
- uses: actions/setup-node@v5
  with:
    node-version: "22"
    registry-url: "https://registry.npmjs.org"

- run: npm ci
- run: npm run build
- run: npm publish --provenance --access public
  env:
    NODE_AUTH_TOKEN: ${{ secrets.NPM_TOKEN }}
```

`--provenance` produces the same SLSA + sigstore attestation
trail that Sange's PyPI publish produces — see
[`../../security/slsa-and-sbom.md`](../../security/slsa-and-sbom.md)
for the supply-chain claims.

For trustless OIDC publish (no `NPM_TOKEN` needed), see npm's
[trusted-publishing docs](https://docs.npmjs.com/) — same shape
as PyPI's, configured at `npmjs.com/settings/<user>/packages/<pkg>`.

## TypeScript-specific notes

- **`tsconfig.json`** lives at the repo root. The Sange CLI
  doesn't read it; your build pipeline does. Sange's commit
  message generation reads the diff regardless of TS-vs-JS.
- **Type-error commits** — when a commit's primary purpose is
  fixing type errors, use `type` scope: `fix(types): tighten
  Foo<T> constraint`.
- **Build artifacts** — `dist/` is in the default `lang/node`
  gitignore profile. If your build outputs go elsewhere, override
  via the profile composition or the local `.gitignore`.

## What's NOT in v0.1

These ship later:

- **`sange scaffold add lang/node`** — the full per-tool surface
  (v1.0).
- **`sange bootstrap`** — orchestrate `brew install node` / `corepack
  enable` / `nvm install` cross-platform (v0.5+).
- **`sange lang node`** sub-app — Node-specific shortcuts (publish
  to npm, regenerate `package.json::engines` from `.nvmrc`, etc.).
  v0.5+.
- **Per-framework profiles** — React / Next.js / Remix / Astro /
  SvelteKit etc. extending `lang/node`. v0.5+.

## Cross-references

- [`./python.md`](./python.md) — the Python sibling doc; identical
  flow.
- [`../workflow/commit-lifecycle.md`](../workflow/commit-lifecycle.md)
  — end-to-end commit lifecycle.
- [`../vcs/git.md`](../vcs/git.md) — Git adapter under the hood.
- [`../../reference/profile-registry.md`](../../reference/profile-registry.md)
  — full gitignore profile registry.
- [`../../release.md`](../../release.md) — operator-facing release
  recipe.
- [`../../security/slsa-and-sbom.md`](../../security/slsa-and-sbom.md)
  — supply-chain integrity claims.
- [`templates/gitignore-profiles/lang/node.toml`](../../../templates/gitignore-profiles/lang/node.toml)
  — the on-disk profile source.
