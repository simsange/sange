# Contributing to simsange

Thanks for considering a contribution to the Sange ecosystem. This
guide covers what applies **across every repo in the
[`simsange`](https://github.com/simsange) GitHub org**. Per-product
specifics (test commands, code-style nuances) live in each repo's
own `CONTRIBUTING.md`.

## Code of Conduct

Every interaction in the simsange org is governed by the
[Contributor Covenant 2.1](https://github.com/simsange/.github/blob/main/CODE_OF_CONDUCT.md).
Enforcement contact: [opensource@simtabi.com](mailto:opensource@simtabi.com).

## Before opening a PR

1. **Open an issue first** for anything bigger than a typo. A short
   discussion about the approach saves time on both sides.
2. **Read the per-repo `CONTRIBUTING.md`** — it lists the test
   commands, code-style requirements, and the specific PR template
   for that product.
3. **One concern per PR.** Refactors and feature work do not share
   a PR. Smaller PRs review faster.

## Sign-off

By submitting a PR you certify the
[Developer Certificate of Origin v1.1](https://developercertificate.org/).
The repo's commit hooks check for a `Signed-off-by:` trailer; add
one to each commit via:

```bash
git commit -s -m "your message"
```

Or set `git config commit.gpgsign true` once and let your platform
add it automatically.

## Branch + commit conventions

- Work on a feature branch off `main`. Branch names are short +
  descriptive (`feat/passkey-auth`, `fix/race-in-token-refresh`).
- Commit messages follow [Conventional Commits 1.0.0](https://www.conventionalcommits.org/).
- Per-product repos may use [Sange itself](https://github.com/simsange/sange)
  to generate commit messages — `git diff --staged | sange commit`
  is the canonical path. (Sange's own commits go through this flow
  as a dogfood.)

## Per-repo CI gates

Every simsange repo runs the same gates on every PR:

- Tests (`pytest`, `vendor/bin/pest`, `npm test`, `go test`, etc.
  depending on the stack).
- Lint (`ruff`, `phpcs`, `eslint`, `golangci-lint`).
- Type-check (`mypy`, `phpstan`, `tsc --noEmit`).
- Build (`python -m build`, `npm run build`, `docker build`).

A PR can't merge if any gate is red. Don't `--no-verify` past hooks
or `# noqa` past linter complaints; if a check is wrong, fix the
check.

## Code review

- We review for **correctness first**, **style second**, **design
  third**. Style nits go in the PR body; correctness issues are
  blocking comments.
- We expect **PR descriptions that explain the *why*** — the diff
  shows the *what*.
- We try to respond to PRs within 5 working days. Maintainer
  bandwidth is limited; please be patient.

## Reporting security issues

**Do NOT open a public issue** for security vulnerabilities. See
[SECURITY.md](https://github.com/simsange/.github/blob/main/SECURITY.md)
for the disclosure process. Short version: email
[opensource@simtabi.com](mailto:opensource@simtabi.com) with details;
we coordinate a fix + responsible disclosure timeline.

## License

By contributing you agree your contribution is licensed under the
Apache License 2.0 (the same license the project uses).
