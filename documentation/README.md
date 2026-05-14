# documentation/ — seed of `sangedev/documentation`

This directory is the **seed of the future `github.com/sangedev/documentation`
repo** — the public docs site for the Sange ecosystem.

## Why a separate repo?

Two reasons (per the Sange ecosystem plan):

1. **Cross-product docs.** The `sangedev` org will host multiple
   Sange-family projects (the main `sange` CLI/daemon, future
   `sange-server`, `sange-web`, and the §6.12 Premade Operations Kit
   sub-products). One docs site indexes all of them; a per-product
   repo for docs would fragment the navigation.

2. **Independent release cadence.** Docs ship more often than the
   tool (typo fixes, walkthrough updates, new examples). A separate
   repo lets docs land without retagging the tool, and lets the tool
   release cleanly without the docs-PR queue blocking it.

## What lives here today

This is the **seed content** — the minimum to run `mkdocs serve`
locally and see a working site. When `sangedev/documentation` is
created, the contents of this directory move there as the initial
commit of that repo.

```
documentation/
├── README.md            (this file)
├── mkdocs.yml           MkDocs Material theme config
├── requirements.txt     mkdocs + mkdocs-material + plugins
└── docs/
    ├── index.md         site landing page
    ├── getting-started.md  install + first commit walkthrough
    ├── cli/             CLI reference (mirrors src/sange/cli/)
    └── architecture/    high-level architecture (links into main repo)
```

The current `docs/` tree in this repo (root-level `docs/`) is for
**developer-internal** reference: ADRs, threat model, generator
catalogs, kit manifest. The docs site here links to these via the
GitHub URL rather than duplicating content.

## Local preview

```bash
cd documentation
pip install -r requirements.txt
mkdocs serve
# Open http://127.0.0.1:8000
```

## Migration plan to `sangedev/documentation`

When the user creates the new repo, the move is straightforward:

```bash
# 1. Create the empty sangedev/documentation repo on GitHub
#    (manual step — visit https://github.com/organizations/sangedev/repositories/new)

# 2. Extract the seed into a fresh git history
cd /tmp
git init documentation-bootstrap
cp -r /Users/imanimanyara/Artisan/projects/opensource/sange/documentation/. documentation-bootstrap/
cd documentation-bootstrap
git add .
git commit -m "Initial release — seeded from sangedev/sange documentation/"
git remote add origin https://github.com/sangedev/documentation.git
git push -u origin main

# 3. (Optional) Delete the seed from the main sange repo:
cd /Users/imanimanyara/Artisan/projects/opensource/sange
git rm -r documentation/
git commit -m "Move docs site to sangedev/documentation"
```

`opensource.simtabi.com/documentation/sange` continues to point at
the published site (via a CNAME on the sangedev/documentation Pages
deployment).

## What lives at `opensource.simtabi.com/documentation/sange`?

The org-level OSS portal (Simtabi LLC's existing infrastructure)
serves the rendered MkDocs output from `sangedev/documentation`. A
GitHub Pages → custom domain config maps the rendered site to the
canonical URL. Users find docs at the canonical URL; the source
of truth is the docs repo.
