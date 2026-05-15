# org-github/ — seed of `github.com/simsange/.github`

This directory is the **seed of the future `github.com/simsange/.github`
repo** — the org-wide community-health-files repo for the Sange
ecosystem GitHub org (`github.com/simsange`).

## What a `.github` repo does

GitHub special-cases an org-level `.github` repo: any file at the
root (`README.md`, `CODE_OF_CONDUCT.md`, `SECURITY.md`, etc.) becomes
the **default** for every other repo in the org that doesn't supply
its own. The `profile/README.md` becomes the org's profile-page
landing card.

So when `github.com/simsange/sange` doesn't have its own SECURITY.md
(it does, but for hypothetical sister repos that don't), GitHub
falls back to the one in `github.com/simsange/.github/SECURITY.md`.
One canonical org-wide policy; no per-repo drift.

## What lives here

```
org-github/
├── README.md                        (this file — explains the seed)
├── LICENSE                          Apache 2.0 (cp from main repo)
├── CODE_OF_CONDUCT.md               Contributor Covenant 2.1 (cp from main repo)
├── SECURITY.md                      Vulnerability disclosure (cp from main repo)
├── CONTRIBUTING.md                  Org-wide contributor guide
├── SUPPORT.md                       Where to get help across simsange
├── profile/
│   └── README.md                    Org landing-page card (appears at github.com/simsange)
└── .github/
    ├── ISSUE_TEMPLATE/
    │   ├── bug_report.yml
    │   ├── feature_request.yml
    │   └── config.yml               Disables blank issues + links to security
    └── PULL_REQUEST_TEMPLATE.md
```

## Canonical-source files

`CODE_OF_CONDUCT.md`, `SECURITY.md`, and `LICENSE` are **disk-to-disk
copies** from `github.com/simsange/sange` per the
`~/.claude/CLAUDE.md` "canonical / upstream files" rule. They are
NOT paraphrased; they are byte-equal to the main repo's versions
at copy-time.

When either repo's canonical version is updated, the other should
be re-cp'd to keep them in sync. A periodic check via
`shasum -a 256` flags drift.

## Migration plan to `github.com/simsange/.github`

When the user creates the new repo, the move is mechanical:

```bash
# 1. Create the empty simsange/.github repo on GitHub
#    (manual step — visit https://github.com/organizations/simsange/repositories/new
#     and name the repo exactly `.github`)

# 2. Bootstrap the seed into the fresh repo
cd /tmp
git init org-github-bootstrap
cp -R /Users/imanimanyara/Artisan/projects/opensource/sange/org-github/. \
      org-github-bootstrap/
cd org-github-bootstrap
git add .
git commit -m "Initial release — seeded from simsange/sange org-github/"
git remote add origin https://github.com/simsange/.github.git
git push -u origin main

# 3. (Optional) Delete the seed from the main sange repo
cd /Users/imanimanyara/Artisan/projects/opensource/sange
git rm -r org-github/
git commit -m "Move simsange/.github seed to its own repo"
```

After that:

- The org landing page at `github.com/simsange` displays the
  `profile/README.md` content.
- Every simsange repo that doesn't have a CODE_OF_CONDUCT.md falls
  back to this one.
- Issue templates and the PR template apply to every simsange repo
  by default (each repo can still override locally).

## What does NOT belong here

- Per-product documentation — that lives in
  `github.com/simsange/documentation` (the docs-site seed in the
  `documentation/` directory of the main repo).
- Per-product CHANGELOG, README, technical specs — those live in
  each product's own repo.
- Build / release CI workflows — those are per-product too; the
  org-level `.github/workflows/` directory is reserved for workflows
  that GitHub should treat as org-wide defaults (rare; usually
  per-repo is preferred).
