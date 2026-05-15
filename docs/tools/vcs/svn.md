# SVN adapter

> **Status: read-only scaffold landed (v0.1.0.post1+).** T-100a shipped
> the `SvnDriver` scaffold + `detect()` + `status()` against a real
> `svn` binary; T-100b is the remaining read methods (log / diff /
> branches / etc.); T-100c is write ops. Tracking in
> [`../../../.design/plans/checklist.md`](../../../.design/plans/checklist.md).
> The doc below covers both what's live today and what's planned.

For the full SVN command catalog with every Sange wrapper + AI
augmentation + safety class + confirmation gate, see
[Appendix E — SVN command catalog](../../reference/appendix-e-svn-catalog.md).
The appendix already covers **46 commands** across `svn` + `svnadmin`
+ `svnlook` + `svndumpfilter` + `svnsync` — auto-regenerated from
a live `svn help`.

## What's already specified

| Surface | Status | Source |
| :--- | :--- | :--- |
| Command catalog | **Generated today** (46 commands) | [`reference/appendix-e-svn-catalog.md`](../../reference/appendix-e-svn-catalog.md), emitted by `tools/generators/svn_catalog.py` (T-G-002). |
| Cross-VCS concept map | **Generated today** | [`reference/appendix-f-cross-vcs.md`](../../reference/appendix-f-cross-vcs.md) — how every Git concept maps onto SVN (and Hg, P4, etc.). |
| Adapter Protocol | **Implemented today** | `src/sange/adapters/vcs/_protocol.py::VCSDriver`. The SVN concrete driver implements this same Protocol. |
| Adapter scaffold (`SvnDriver`) | **Live (T-100a)** | `src/sange/adapters/vcs/svn/` — subprocess wrapper + XML parsers + `SvnDriver.detect()` + `SvnDriver.status()`. |
| Read methods (`log` / `diff` / `branches` / `current_branch` / `remotes` / `tags` / `show_commit`) | **Live (T-100b)** | All seven implemented. `branches()` lists `^/trunk` + every dir under `^/branches/`; `current_branch()` derives from the WC's relative-URL; `tags()` lists `^/tags/` dirs. Total: 58 tests across `tests/unit/test_svn_{driver,parsers}.py`. |
| Write methods (add / commit / branch_create / etc.) | v0.5 (T-100c) | Raise `NotImplementedError("T-100c")` today. |
| Wrappers (`sange commits`...) | v0.5+ | Once T-100c lands, the same `sange commits` verbs (`new` / `ai` / `submit` / `approve` / `reject` / `commit` / `push`) work against SVN working copies. |
| Purge executor | v2.0 | `svnadmin dump → svndumpfilter exclude → swap`. T-246. |

## What it will look like when it ships

The SVN adapter will mirror the Git adapter's structure:

| Surface | Git adapter (today) | SVN adapter (v0.5+) |
| :--- | :--- | :--- |
| Subprocess wrapper | `git/_subprocess.py::run_git()` with `LC_ALL=C` / `SVN_PAGER=cat`-equivalent env | `svn/_subprocess.py::run_svn()` with the same env discipline + `LANG=C.UTF-8` |
| Pure parsers | `git/parsers.py` — 7 functions | `svn/parsers.py` — equivalent set: `parse_status_xml`, `parse_log_xml`, `parse_info_xml`, `parse_propget`, etc. SVN's `--xml` output is the stable parse target. |
| Driver | `git/driver.py::GitDriver(VCSDriver)` | `svn/driver.py::SvnDriver(VCSDriver)` |
| Capability flags | All four sub-Protocols satisfied | `SupportsStash=False`, `SupportsBisect=False`, `SupportsRebase=False` (svn semantics don't map), `SupportsLFS=False` |

The same `VCSDriver` Protocol surface means **callers don't change
when switching VCS**. A `sange commits push` invocation against an
SVN working copy in v0.5 will route through `SvnDriver.commit()` +
`SvnDriver.push()` (which is `svn commit` in SVN parlance — SVN's
commit is centralized, no local-then-push distinction).

## Differences SVN imposes

When the adapter ships, these are the concept gaps users will see
versus Git:

| Concept | Git | SVN |
| :--- | :--- | :--- |
| Local commit then push | Two separate operations (`git commit` then `git push`). Sange's `commits commit` vs `commits push` split mirrors this. | One operation (`svn commit`). The `commits commit` verb in v0.5 SVN mode will do the full network operation; `commits push` will be a no-op alias. |
| Branches | Lightweight refs; `git branch`/`git switch`. | Heavyweight: a branch is a directory copy under `branches/`. `sange branches create` will do `svn copy ^/trunk ^/branches/<name>` then `svn switch`. |
| Stash | Standard. | None. `SupportsStash=False`. `sange stash` will refuse on SVN with an actionable error. |
| Bisect | Standard. | None. `SupportsBisect=False`. The §6.13 "bisect via Sange" feature is Git-only. |
| Rebase / cherry-pick | Standard. | Approximate via `svn merge` with revision ranges. The Sange wrapper will translate where possible; ambiguous cases surface as a confirmation gate. |
| Working-copy state | `git status --porcelain=v2` | `svn status --xml` |
| History rewrite | `git filter-repo` + BFG | `svnadmin dump → svndumpfilter exclude → svnadmin load`. Purge executor in v2.0 wraps this. |

See Appendix F's full concept-by-concept mapping for the
exhaustive table.

## When the adapter lands

Follow [`../../governance/roadmap.md`](../../governance/roadmap.md)
for the milestone schedule. T-100 + T-101 (gitignore-swap engine)
are Phase-1 beta features targeting **v0.5**. The acceptance
criteria for the SVN adapter in v0.5:

1. Every read operation in `VCSDriver` (status, log, diff, branches,
   current_branch, remotes, tags, show_commit) returns the same
   typed value the Git driver returns.
2. Every write operation (add, remove, revert, commit,
   branch_create, switch, push (semantic), tag_create) succeeds
   against a real SVN working copy.
3. Cross-VCS tests in `tests/` exercise the same `sange commits`
   flow against an ephemeral SVN repo via `svnserve` + `svnadmin
   create`.
4. The SVN-specific augmentations from §9.0.3 (the must-cover
   floor) are wired: lock-aware operations, externals handling,
   property scrubbing on commit.

## Cross-references

- [`../../reference/appendix-e-svn-catalog.md`](../../reference/appendix-e-svn-catalog.md)
  — full SVN command catalog with Sange-wrapper plans
  (regenerated by T-G-002).
- [`../../reference/appendix-f-cross-vcs.md`](../../reference/appendix-f-cross-vcs.md)
  — concept-by-concept Git ↔ SVN ↔ Hg ↔ P4 mapping.
- [`./git.md`](./git.md) — Git adapter (the v0.1 reference
  implementation the SVN adapter mirrors).
- [`../../governance/roadmap.md`](../../governance/roadmap.md)
  — v0.5 milestone schedule.
- [`../../../.design/sange-architecture.md`](../../../.design/sange-architecture.md)
  §7 + §9 — canonical adapter spec.
