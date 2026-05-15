# Releasing Sange

This document is the **operator-facing release recipe** for shipping
a tagged version of Sange (`v0.1.0`, `v0.1.1`, `v0.2.0`, etc.). It
covers the one-time setup, the per-release procedure, and the
recovery path when things go wrong.

## Audience

The maintainer (Imani Manyara) and any contributor who's been
granted release permissions. This is not user-facing — end-users
just `pip install sange` once a release is on PyPI.

## How releases work in this repo

Releases are **tag-driven**. Pushing an annotated tag matching
`v*.*.*` (or `v*.*.*-*` for pre-releases) triggers the
[`.github/workflows/release.yml`](../.github/workflows/release.yml)
pipeline, which:

1. Builds sdist + wheel and smoke-installs them.
2. Publishes to PyPI via OIDC trusted-publisher (no API token).
3. Builds a multi-arch Docker image (`linux/amd64` + `linux/arm64`)
   with sigstore provenance + SBOM attached, pushes to
   `ghcr.io/simsange/sange:<tag>` and `:latest`.
4. Creates a GitHub Release with sdist + wheel attached and notes
   extracted from `docs/CHANGELOG.md`.

End-to-end: from `git push --tags` to "the new version is installable
via `pip`" takes about 7 minutes on first run.

## One-time setup

You only need to do these once per repo, not per release.

### 1. PyPI trusted publisher

PyPI's [trusted publishers](https://docs.pypi.org/trusted-publishers/)
let GitHub Actions publish without storing an API token in repo
secrets. The OIDC token from the workflow run is checked against the
trusted-publisher record you configure on PyPI.

Setup steps:

1. **Reserve the package name on PyPI.** First time only:
   - Log in to <https://pypi.org/manage/account/publishing/>.
   - Click "Add a new pending publisher".
   - PyPI project name: `sange`.
   - Owner: `simsange`.
   - Repository name: `sange`.
   - Workflow filename: `release.yml`.
   - Environment name: `pypi`.

2. **Create the `pypi` environment in this repo.** GitHub →
   Settings → Environments → New environment. Name: `pypi`. Add
   a deployment-protection rule restricting deploys to the `main`
   branch + tag refs matching `v*.*.*`.

3. **Verify the `id-token: write` permission** is set on the
   release workflow's `pypi` job (already configured in
   `.github/workflows/release.yml`).

After step 1 ships its first release, the PyPI publisher record
goes from "pending" to "active". Subsequent releases reuse it.

### 2. GitHub Container Registry (GHCR)

GHCR ships with every GitHub org for free; no extra secrets are
needed. The release workflow uses `${{ secrets.GITHUB_TOKEN }}`
with `packages: write` permission (already in the workflow's
`permissions` block).

After the first release pushes an image:

1. Go to <https://github.com/orgs/simsange/packages>.
2. Find `sange` in the package list.
3. Click → Settings → "Manage Actions access" — add this repo
   with `Write` role if it's not already there.
4. (Optional) Set the package visibility to "Public" so anonymous
   `docker pull` works.

### 3. Repo settings

- **Branch protection** on `main`: require PR + at least 1 review +
  passing CI checks before merge.
- **Tag protection**: restrict who can create tags matching `v*` to
  the maintainer team. (GitHub → Settings → Rules → New
  ruleset → "Tag" target.)
- **Actions → General → Workflow permissions**: "Read and write
  permissions" + "Allow GitHub Actions to create and approve pull
  requests" enabled.

## Per-release procedure

Once the one-time setup is done, every release follows the same
recipe.

### Step 0 — Pre-flight checklist

Before any tag push, walk this list. Skipping it cost ~6 minutes
of wasted CI on the v0.1.0 release attempt; doing it takes ~90
seconds.

- [ ] **PyPI trusted-publisher record is _active_** (not "pending")
      for the current `owner` + `repository` + `workflow` +
      `environment` tuple. The record turns active only after the
      first successful publish. Visit
      <https://pypi.org/manage/account/publishing/>. If the record
      is still listed under "Pending publishers", the tag push
      will trigger an `invalid-publisher` failure even though the
      workflow OIDC token is valid.
- [ ] **`pypi` GitHub Environment exists** in this repo's settings
      with the deployment-protection rule restricting deploys to
      `main` + `v*.*.*` tag refs.
- [ ] **`git remote -v` matches the org you mean to push to.** If
      the repo was renamed (e.g. an in-place GitHub org rename or
      a transfer), `git remote set-url origin <new-url>` first.
      Out-of-date remotes silently push to the redirected location
      but bake the **new** URL into the upload metadata while the
      tag annotation may still reference the **old** URL — that
      mismatch is permanent.
- [ ] **Auth method matches the remote URL.** HTTPS remotes use
      the local credential helper, which is scoped per GitHub
      user; an HTTPS remote pointing at a different org may fail
      with `403: Permission denied` even when the SSH key on that
      account would have worked. If unsure, switch to SSH:
      `git remote set-url origin git@github.com:<org>/<repo>.git`.
- [ ] **Local CI gates pass** before tagging. The release pipeline
      doesn't re-run `pytest` / `ruff` / `mypy` — if main is red,
      the release ships red.

### Step 1 — Pre-release smoke

In a fresh venv, validate the end-to-end flow:

```bash
cd /path/to/sange
python3 -m venv .venv-smoke
source .venv-smoke/bin/activate
pip install -e ".[dev]"

# Plumbing-only (no tokens)
./scripts/smoke_v01.sh --dry-run

# Real AI (~$0.005 in Claude calls)
export ANTHROPIC_API_KEY=sk-ant-...
./scripts/smoke_v01.sh --provider anthropic
```

The smoke script's last line should read `smoke test SUCCESS`. If
it fails, fix the bug + re-test before tagging.

### Step 2 — Bump the version

Edit `src/sange/_version.py`:

```python
__version__ = "0.1.0"  # was 0.1.0.dev0
```

Commit:

```bash
git add src/sange/_version.py
git commit -m "release: v0.1.0"
```

### Step 3 — Regenerate the changelog

The `docs/CHANGELOG.md` `## Unreleased` section becomes the new
release's notes. v0.5+ will rewrite the section header to the
tagged version + date when `sange release tag v0.1.0` lands; for
v0.1 the operator does this by hand:

```bash
# Open docs/CHANGELOG.md, change:
#    ## Unreleased
# to:
#    ## v0.1.0 — 2026-05-15
#
# Then add a new empty "## Unreleased" section above.

git add docs/CHANGELOG.md
git commit -m "docs(changelog): cut v0.1.0"
```

### Step 4 — Tag

```bash
git tag -a v0.1.0 -m "Initial release"
```

The annotation message is what shows on the GitHub Release page +
on `git show v0.1.0`. Make it brief but informative — what's new,
what's changed since the previous tag.

### Step 5 — Push

```bash
git push origin main
git push origin v0.1.0
```

Tag push triggers `release.yml`. Monitor the run at
<https://github.com/simsange/sange/actions>.

### Step 6 — Verify

After the workflow completes:

```bash
# PyPI
pip index versions sange    # should show v0.1.0

# GHCR
docker manifest inspect ghcr.io/simsange/sange:v0.1.0
# expect: amd64 + arm64 manifests

# GitHub Release
# Visit https://github.com/simsange/sange/releases/v0.1.0
# expect: sdist + wheel attached, notes from CHANGELOG.md
```

Tag a new GitHub Release as "latest" if it's the newest version.

## Recovery: when something fails

### release.yml failed mid-flight

The pipeline runs four jobs in sequence: `build` → `pypi` →
`docker` + `release`. Failure modes by job:

**`build` fails:**
- Most common: wheel doesn't build because a dep is missing.
- Fix: bump the missing dep in `pyproject.toml`, push to main,
  delete + re-tag at the new HEAD.

**`pypi` fails:**
- Most common: trusted-publisher record not yet active.
- Fix: complete the one-time setup (above), then re-run the
  failed `pypi` job in the workflow UI. The artifact is still
  uploaded from `build`; the publish step re-runs against it.

**`docker` fails:**
- Most common: GHCR write permission missing for the
  `GITHUB_TOKEN`.
- Fix: verify the workflow has `packages: write` + the repo has
  GHCR write access. Re-run the failed `docker` job.

**`release` fails:**
- Most common: notes-extraction awk found nothing in
  `docs/CHANGELOG.md`.
- Fix: ensure the `## Unreleased` section had content (or for the
  first release, the `## v0.1.0` section after the cut). Re-run
  the `release` job.

### A bad release shipped

**The tag is immutable once pushed.** You cannot re-publish
`v0.1.0` after a bad release — PyPI rejects re-uploads of the
same version, and a force-pushed tag doesn't trigger a re-run.

The fix-forward path is **`v0.1.0.post1`** (per
[PEP 440 post-releases](https://peps.python.org/pep-0440/#post-releases)):

```bash
# Fix the bug in code, commit
git add ...
git commit -m "fix: <description>"

# Bump version
# Edit src/sange/_version.py to "0.1.0.post1"
git add src/sange/_version.py
git commit -m "release: v0.1.0.post1"

# Update changelog
# Add ## v0.1.0.post1 — YYYY-MM-DD with the fix description
git add docs/CHANGELOG.md
git commit -m "docs(changelog): cut v0.1.0.post1"

# Tag and push
git tag -a v0.1.0.post1 -m "Bug-fix release."
git push origin main
git push origin v0.1.0.post1
```

`v0.1.0.post1` ships through the same release.yml pipeline. PyPI
treats `.postN` as a strictly-greater version than `v0.1.0`, so
`pip install --upgrade sange` will pick it up.

For larger fixes that include new functionality, bump to
`v0.1.1` instead.

### A tag was created but not yet pushed

This is the **easy case** — the tag is local-only, no remote saw
it, so deleting + retagging is safe:

```bash
git tag -d v0.1.0           # delete local
git tag -a v0.1.0 -m "..."  # retag at the corrected commit
```

This is what we did for the v0.1.0 → v0.1.0 retag during the URL
migration (session-log row S-003-T-43). The operation is unsafe
ONLY after a push.

### Failure modes seen in production

Empirical record of what's actually gone wrong, in chronological
order. Each row links to the session-log audit entry that documents
the incident in full. The pattern across all three: the failure
was preventable by a Step 0 pre-flight check.

| Release | Job that failed | Root cause | Fix |
|---|---|---|---|
| `v0.1.0` (2026-05-15) | `pypi` | Trusted-publisher record still in "pending" — the pending → active transition requires a first successful publish, which is exactly what's being attempted. The pending record was filed only **after** the tag push. (`S-003-T-54`) | Configure the record **before** tag push (Step 0). After the fact: configure it, then re-run only the failed `pypi` job + the auto-triggered `release` job. The `build` artifact is preserved on the workflow run. |
| `v0.1.0` (2026-05-15) — pre-flight | `git push` itself | HTTPS remote URL with credential-helper scope mismatched the org. `403: Permission denied` to the `sangedev` org despite valid PAT. (`S-003-T-54`) | Switched to SSH via `git remote set-url`. Step 0's auth-method check would have caught this. |
| `v0.1.0` (2026-05-15) — post-release | n/a — tag-annotation drift | GitHub org renamed `sangedev` → `simsange` after the tag was pushed. The annotated tag body says `Source: https://github.com/sangedev/sange` — immutable. The codebase + GHCR image migrated cleanly via redirect, but the tag annotation is now a permanent historical artifact pointing at the old URL. (`S-003-T-55`) | Per CLAUDE.md "release-as-immutable": **the tag is not retagged**. Future releases ship with the new URL baked in correctly; the v0.1.0 annotation is the historical record of when the rename happened. |

## Pre-release versions

For betas and release candidates use the PEP 440 pre-release
suffixes:

- `v0.1.0-rc1`, `v0.1.0-rc2` — release candidates
- `v0.1.0-b1`, `v0.1.0-b2` — betas
- `v0.1.0-a1`, `v0.1.0-a2` — alphas

The release workflow matches `v*.*.*-*` for these. PyPI installs
them only with `pip install sange --pre`.

## After the release

1. Open a PR bumping `__version__` back to the dev suffix:
   `0.1.0` → `0.1.1.dev0`.
2. Move any unreleased work in `docs/CHANGELOG.md` under a fresh
   `## Unreleased` header.
3. Update the homepage / external announcements if applicable.

## Related references

- `.github/workflows/release.yml` — the workflow this doc describes.
- `tools/generators/changelog_from_commits.py` — auto-generates
  the changelog from `.sange/commits/` PUSHED rows (v0.5+ will
  also handle the version-header rewrite at tag-time).
- ADR-033 in `docs/adr/0033-multi-arch-docker.md` — why multi-arch
  builds + `linux/amd64,linux/arm64` are non-negotiable.
- [PyPI trusted publishers docs](https://docs.pypi.org/trusted-publishers/)
- [PEP 440 — version specifiers](https://peps.python.org/pep-0440/)
- [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/)
- [Conventional Commits 1.0.0](https://www.conventionalcommits.org/)
