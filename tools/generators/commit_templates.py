"""Generate Appendix G + the curated commit-template library.

T-G-004 — folds v1's 104-entry `DEFAULT_GIT_COMMIT_MESSAGES` array (from
`sange-v1/configs/config.sh:25-128`) + Conventional Commits 1.0.0 into a
normalized library of ≥50 presets per `.design/sange-architecture-prompt.md`
§6.8.5.

Curation steps (§6.8.5):

  1. Document the existing 104 v1 entries verbatim (the `V1_LEGACY_MESSAGES`
     tuple below).
  2. Dedupe — multiple v1 entries cover the same intent with cosmetic emoji
     variation; collapse to canonical Conventional-Commits forms.
  3. Filter — entries that are pure operational events (a cron run, an email
     send) with no code change are dropped; entries that imply a code/config
     change keep their aliases.
  4. Re-taxonomize under Conventional Commits 1.0.0 (`feat`, `fix`, `docs`,
     `style`, `refactor`, `perf`, `test`, `build`, `ci`, `chore`, `revert`).
  5. Normalize structure — every preset has `id`, `type`, `scope`, `template`,
     `description`, `requires_body`, `breaking_change`, `workflow`, `tags`,
     `aliases`.
  6. Ship ≥50 presets covering type-basic, common scopes, workflows, and
     domain-specific cases.

Determinism (ADR-023):

  * Inputs are static module constants — no external data.
  * Re-runs are byte-identical for the same clock.
  * Tests assert (a) every v1 string maps to exactly one preset's aliases,
    (b) ≥50 presets shipped.

Outputs:

  * `templates/commit-templates/default.toml` — the structured library that
    the §6.8 commit-message subsystem reads at run-time.
  * `docs/reference/appendix-g-commit-templates.md` — the human-readable
    appendix with the curated preset list + the v1→v3 migration table.
"""

from __future__ import annotations

import datetime as _dt
import json
import sys
from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path

# --- Path bootstrap ------------------------------------------------------- #
HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent.parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from _lib import markdown  # noqa: E402
from _lib.fingerprint import sha256_text  # noqa: E402
from _lib.output import (  # noqa: E402
    GeneratorMetadata,
    WriteMode,
    WriteOutcome,
    write_generated_file,
)

GENERATOR_VERSION = "1.0.0"
GENERATED_BY = "tools/generators/commit_templates.py"
LIBRARY_PATH = REPO_ROOT / "templates" / "commit-templates" / "default.toml"
APPENDIX_PATH = REPO_ROOT / "docs" / "reference" / "appendix-g-commit-templates.md"


# Conventional Commits 1.0.0 — the canonical 11 types.
CC_TYPES: tuple[str, ...] = (
    "feat", "fix", "docs", "style", "refactor", "perf",
    "test", "build", "ci", "chore", "revert",
)


# --------------------------------------------------------------------------- #
# v1 legacy array — captured verbatim from sange-v1/configs/config.sh:25-128
# (104 entries). Anti-hallucination: this is the byte-exact source-of-truth;
# do NOT paraphrase. The aliases column on each preset references these.
# --------------------------------------------------------------------------- #


V1_LEGACY_MESSAGES: tuple[str, ...] = (
    "📧 alert: incident email",
    "📦 analytics: add new endpoint",
    "📢 announce: changelog published",
    "📤 api: mock data",
    "📥 backup: DB snapshot",
    "📦 build: create .zip bundle",
    "📦 build: regenerate dist folder",
    "📦 build: update package.json",
    "📅 calendar: adjust task frequency",
    "📤 cd: deployment script",
    "📥 chore: auto-import from upstream",
    "📤 chore: auto-upload artifacts",
    "📦 chore: package refresh",
    "📦 chore: publish package",
    "📥 chore: mirror sync with repo",
    "📦 chore: update dependencies",
    "📦 chore: update packages",
    "🧹 chore: clean up code",
    "🗑️ chore: cleanup unused files",
    "📤 ci: auto-deploy on push",
    "📤 ci: update GitHub workflow",
    "📤 cleanup: old temp files",
    "📤 code: sync production",
    "🎯 scope: narrow functionality impact",
    "📤 cron: send report",
    "📦 data: normalize import",
    "📊 data: update metrics dashboard",
    "📤 db: schema changes",
    "🗄️ db: add migration for users table",
    "🧹 db: cleanup orphan records",
    "🚢 deploy: publish to staging",
    "📤 deploy: push build to server",
    "📤 dns: add new CNAME",
    "📝 docs: auto-generated update",
    "📈 docs: update analytics",
    "📊 docs: add metrics info",
    "📊 docs: graph updates",
    "📝 docs: update documentation",
    "📤 email: notify team",
    "📧 email: confirmation template",
    "📥 fetch: dependencies",
    "🧊 freeze: lock version ranges",
    "📤 firewall: update rules",
    "📤 ftp: finalize mirror sync",
    "📤 ftp: remove outdated logs",
    "📤 ftp: upload to legacy server",
    "✨ feat: add new feature",
    "📥 import: vendor metadata",
    "📥 ingest: files to data lake",
    "📤 logs: rotate production logs",
    "📥 logs: import archived logs",
    "📩 mail: alert stakeholders",
    "📧 mailer: fix template spacing",
    "📩 message: prepare blast",
    "🗃️ meta: update project metadata",
    "📣 l10n: update regional formats",
    "🚨 lint: resolve style warnings",
    "📦 lint: strict mode fixes",
    "📤 monitoring: add health checks",
    "📛 naming: update identifiers",
    "🛎️ ops: scheduled maintenance update",
    "📥 patch: vendor hotfix",
    "📦 patch: dependency fix",
    "🧬 perf: optimize memory usage",
    "📈 perf: reduce load time",
    "🧬 perf: reduce CPU usage",
    "📤 push: staged files to origin",
    "📦 release: patch update",
    "📦 release: sign final tag",
    "🚀 release: bump version",
    "🚀 release: initial deployment",
    "🧨 release: initial release",
    "🧨 release: initial release (WIP)",
    "🚀 release: publish package",
    "♻️ refactor: extract component",
    "🛠️ refactor: scripted improvements",
    "♻️ refactor: simplify code",
    "♻️ revert: undo recent change",
    "📤 sftp: upload to third-party",
    "📈 seo: update meta tags",
    "📤 send: test report",
    "📐 layout: adjust spacing or grid",
    "📝 compliance: update privacy policy",
    "📤 static: purge cache",
    "🎨 style: color & layout tweaks",
    "🧼 style: formatting cleanup",
    "🧠 system: auto-sync complete",
    "📦 task: bump version constraints",
    "📦 task: routine update",
    "📤 test: test coverage updates",
    "📦 test: refactor test suite",
    "🧪 test: add tests",
    "📜 terms: update ToS",
    "🧰 tools: upgrade CLI tools",
    "📊 track: KPIs improved",
    "🖼️ ux: tweak user interface interactions",
    "📤 upload: assets to CDN",
    "📤 upload: deploy static site",
    "📥 pull: sync with origin/main",
    "🪝 hooks: add commit hook",
    "🚧 wip: in-progress automation",
    "🚧 wip: work in progress",
)


# v1 entries that are pure operational events (notification, ftp upload, cron
# event with no underlying code change) get filtered per §6.8.5 step 3. They
# remain in V1_LEGACY_MESSAGES (the audit trail) but are NOT mapped to a
# preset's aliases — they're recorded in FILTERED with a one-line reason.
FILTERED: dict[str, str] = {
    "📧 alert: incident email": "Notification event, not a code commit.",
    "📤 cron: send report": "Cron firing — operational event, not a commit.",
    "📤 email: notify team": "Notification, not a commit.",
    "📩 mail: alert stakeholders": "Notification, not a commit.",
    "📩 message: prepare blast": "Outbound communication, not a commit.",
    "📤 send: test report": "Outbound report, not a commit.",
    "📤 ftp: finalize mirror sync": "Operational FTP event, not a commit.",
    "📤 ftp: remove outdated logs": "Operational FTP event, not a commit.",
    "📤 ftp: upload to legacy server": "Operational FTP event, not a commit.",
    "📤 sftp: upload to third-party": "Operational SFTP event, not a commit.",
    "📤 upload: assets to CDN": "CDN upload event, not a commit.",
    "📤 upload: deploy static site": "Deployment event (use deploy:/release: instead).",
    "📤 static: purge cache": "Cache purge event, not a commit.",
    "📥 pull: sync with origin/main": "Git pull event, not a commit.",
    "📤 push: staged files to origin": "Git push event, not a commit.",
    "🧠 system: auto-sync complete": "Operational sync event, not a commit.",
    "📊 track: KPIs improved": "Metric event, not a commit.",
    "🎯 scope: narrow functionality impact": "Meta-note about scope; not a commit message.",
}


# --------------------------------------------------------------------------- #
# CommitTemplate data model
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class CommitTemplate:
    """A single curated commit-message preset per §6.8.5.

    `template` uses ${placeholder} interpolation. Recognized placeholders:
      * ${scope}    — Conventional Commits scope
      * ${subject}  — short subject line (≤72 chars)
      * ${body}     — multi-line body (optional)
      * ${refs}     — references footer (issue/PR IDs)
      * ${breaking} — populated for `!`-suffix breaking changes
    """

    id: str
    type: str
    scope: str
    template: str
    description: str
    body_template: str = ""
    requires_body: bool = False
    breaking_change: bool = False
    workflow: str = ""
    tags: tuple[str, ...] = field(default_factory=tuple)
    aliases: tuple[str, ...] = field(default_factory=tuple)


# --------------------------------------------------------------------------- #
# Curated preset library — folds the v1 array into ≥50 normalized presets.
# --------------------------------------------------------------------------- #


def _ct(
    id_: str,
    type_: str,
    template: str,
    description: str,
    *,
    scope: str = "",
    body_template: str = "",
    requires_body: bool = False,
    breaking_change: bool = False,
    workflow: str = "",
    tags: Sequence[str] = (),
    aliases: Sequence[str] = (),
) -> CommitTemplate:
    return CommitTemplate(
        id=id_,
        type=type_,
        scope=scope,
        template=template,
        description=description,
        body_template=body_template,
        requires_body=requires_body,
        breaking_change=breaking_change,
        workflow=workflow,
        tags=tuple(tags),
        aliases=tuple(aliases),
    )


PRESETS: tuple[CommitTemplate, ...] = (
    # ============ feat ============
    _ct(
        "feat-basic", "feat",
        "feat: ${subject}",
        "A new user-facing feature.",
        tags=("starter",),
        aliases=("✨ feat: add new feature",),
    ),
    _ct(
        "feat-scoped", "feat",
        "feat(${scope}): ${subject}",
        "A new feature in a specific area of the codebase.",
        tags=("scoped",),
    ),
    _ct(
        "feat-api", "feat",
        "feat(api): ${subject}",
        "A new API endpoint or behavior.",
        scope="api",
        tags=("api",),
        aliases=("📦 analytics: add new endpoint", "📤 api: mock data"),
    ),
    _ct(
        "feat-db", "feat",
        "feat(db): ${subject}",
        "A schema change, migration, or data-model addition.",
        scope="db",
        requires_body=True,
        tags=("db", "migration"),
        aliases=("📤 db: schema changes", "🗄️ db: add migration for users table"),
    ),
    _ct(
        "feat-auth", "feat",
        "feat(auth): ${subject}",
        "A new authentication / authorization feature.",
        scope="auth",
        tags=("auth", "security"),
    ),
    _ct(
        "feat-ui", "feat",
        "feat(ui): ${subject}",
        "A new UI element or interaction.",
        scope="ui",
        tags=("ui",),
        aliases=("🖼️ ux: tweak user interface interactions",),
    ),
    _ct(
        "feat-cli", "feat",
        "feat(cli): ${subject}",
        "A new CLI command or option.",
        scope="cli",
        tags=("cli",),
    ),
    _ct(
        "feat-monitoring", "feat",
        "feat(monitoring): ${subject}",
        "New observability — metrics, logs, traces, or health checks.",
        scope="monitoring",
        tags=("observability",),
        aliases=("📤 monitoring: add health checks", "📊 data: update metrics dashboard"),
    ),
    _ct(
        "feat-breaking", "feat",
        "feat(${scope})!: ${subject}",
        "A breaking-change feature; the `!` suffix is mandatory.",
        breaking_change=True,
        requires_body=True,
        body_template="\n\nBREAKING CHANGE: ${body}\n",
        tags=("breaking",),
    ),

    # ============ fix ============
    _ct(
        "fix-basic", "fix",
        "fix: ${subject}",
        "A bug fix.",
        tags=("starter",),
    ),
    _ct(
        "fix-scoped", "fix",
        "fix(${scope}): ${subject}",
        "A bug fix in a specific area.",
    ),
    _ct(
        "fix-security-cve", "fix",
        "fix(security): ${subject} (CVE-${refs})",
        "A security fix with a CVE reference.",
        scope="security",
        requires_body=True,
        body_template="\n\nReferences: CVE-${refs}\nSeverity: ${body}\n",
        tags=("security", "cve"),
    ),
    _ct(
        "fix-race", "fix",
        "fix(race): ${subject}",
        "A concurrency / race-condition fix.",
        scope="race",
        requires_body=True,
        tags=("concurrency",),
    ),
    _ct(
        "fix-perf-regression", "fix",
        "fix(perf): ${subject}",
        "Restore performance after a regression.",
        scope="perf",
        tags=("perf", "regression"),
    ),
    _ct(
        "fix-mailer-template", "fix",
        "fix(mailer): ${subject}",
        "A fix in an email-template or mailer code.",
        scope="mailer",
        tags=("mailer",),
        aliases=("📧 mailer: fix template spacing",),
    ),
    _ct(
        "fix-hotfix", "fix",
        "fix: ${subject}",
        "Hot-fix landing on a release branch; pair with `hotfix-release` workflow.",
        workflow="hotfix",
        tags=("hotfix",),
        aliases=("📥 patch: vendor hotfix",),
    ),

    # ============ docs ============
    _ct(
        "docs-basic", "docs",
        "docs: ${subject}",
        "A documentation change.",
        tags=("starter",),
        aliases=(
            "📝 docs: auto-generated update",
            "📝 docs: update documentation",
        ),
    ),
    _ct(
        "docs-scoped", "docs",
        "docs(${scope}): ${subject}",
        "Docs in a specific area.",
    ),
    _ct(
        "docs-metrics", "docs",
        "docs(metrics): ${subject}",
        "Metrics, analytics, or dashboard documentation updates.",
        scope="metrics",
        aliases=(
            "📈 docs: update analytics",
            "📊 docs: add metrics info",
            "📊 docs: graph updates",
        ),
    ),
    _ct(
        "docs-compliance", "docs",
        "docs(compliance): ${subject}",
        "Compliance, privacy, or terms-of-service documentation.",
        scope="compliance",
        requires_body=True,
        tags=("compliance", "legal"),
        aliases=(
            "📝 compliance: update privacy policy",
            "📜 terms: update ToS",
        ),
    ),
    _ct(
        "docs-announce", "docs",
        "docs(changelog): ${subject}",
        "Changelog or release-notes publication.",
        scope="changelog",
        aliases=("📢 announce: changelog published",),
    ),
    _ct(
        "docs-seo", "docs",
        "docs(seo): ${subject}",
        "SEO / meta-tag / sitemap documentation changes.",
        scope="seo",
        aliases=("📈 seo: update meta tags",),
    ),

    # ============ style ============
    _ct(
        "style-basic", "style",
        "style: ${subject}",
        "Formatting, whitespace, or non-functional style change.",
        tags=("starter",),
        aliases=(
            "🧼 style: formatting cleanup",
            "🎨 style: color & layout tweaks",
        ),
    ),
    _ct(
        "style-layout", "style",
        "style(layout): ${subject}",
        "UI layout / spacing / grid tweaks.",
        scope="layout",
        aliases=("📐 layout: adjust spacing or grid",),
    ),
    _ct(
        "style-lint", "style",
        "style(lint): ${subject}",
        "Lint-rule-driven style fix.",
        scope="lint",
        aliases=(
            "🚨 lint: resolve style warnings",
            "📦 lint: strict mode fixes",
        ),
    ),

    # ============ refactor ============
    _ct(
        "refactor-basic", "refactor",
        "refactor: ${subject}",
        "A change that neither fixes a bug nor adds a feature.",
        tags=("starter",),
        aliases=(
            "♻️ refactor: extract component",
            "♻️ refactor: simplify code",
            "🛠️ refactor: scripted improvements",
            "🧹 chore: clean up code",
        ),
    ),
    _ct(
        "refactor-scoped", "refactor",
        "refactor(${scope}): ${subject}",
        "Refactor in a specific area.",
    ),
    _ct(
        "refactor-naming", "refactor",
        "refactor(naming): ${subject}",
        "Identifier rename or naming-convention sweep.",
        scope="naming",
        aliases=("📛 naming: update identifiers",),
    ),
    _ct(
        "refactor-db-cleanup", "refactor",
        "refactor(db): ${subject}",
        "Database refactor — orphan cleanup, index reorganization.",
        scope="db",
        aliases=("🧹 db: cleanup orphan records",),
    ),

    # ============ perf ============
    _ct(
        "perf-basic", "perf",
        "perf: ${subject}",
        "A performance improvement.",
        tags=("starter",),
        aliases=(
            "🧬 perf: optimize memory usage",
            "📈 perf: reduce load time",
            "🧬 perf: reduce CPU usage",
        ),
    ),
    _ct(
        "perf-scoped", "perf",
        "perf(${scope}): ${subject}",
        "Perf improvement in a specific area.",
    ),

    # ============ test ============
    _ct(
        "test-basic", "test",
        "test: ${subject}",
        "A change in the test surface.",
        tags=("starter",),
        aliases=(
            "🧪 test: add tests",
            "📤 test: test coverage updates",
        ),
    ),
    _ct(
        "test-scoped", "test",
        "test(${scope}): ${subject}",
        "Test in a specific area.",
    ),
    _ct(
        "test-refactor", "test",
        "test(refactor): ${subject}",
        "Reshape or refactor existing tests.",
        scope="refactor",
        aliases=("📦 test: refactor test suite",),
    ),

    # ============ build ============
    _ct(
        "build-basic", "build",
        "build: ${subject}",
        "Build-system or packaging change.",
        tags=("starter",),
        aliases=(
            "📦 build: create .zip bundle",
            "📦 build: regenerate dist folder",
            "📦 build: update package.json",
        ),
    ),
    _ct(
        "build-scoped", "build",
        "build(${scope}): ${subject}",
        "Build change in a specific area.",
    ),
    _ct(
        "build-data-import", "build",
        "build(data): ${subject}",
        "Data-pipeline / import-pipeline build change.",
        scope="data",
        aliases=(
            "📦 data: normalize import",
            "📥 import: vendor metadata",
            "📥 ingest: files to data lake",
        ),
    ),

    # ============ ci ============
    _ct(
        "ci-basic", "ci",
        "ci: ${subject}",
        "CI / CD pipeline change.",
        tags=("starter",),
        aliases=(
            "📤 ci: auto-deploy on push",
            "📤 ci: update GitHub workflow",
            "📤 cd: deployment script",
        ),
    ),
    _ct(
        "ci-scoped", "ci",
        "ci(${scope}): ${subject}",
        "CI/CD change in a specific area.",
    ),
    _ct(
        "ci-deploy-staging", "ci",
        "ci(deploy): ${subject}",
        "Deployment-pipeline change targeting staging or production.",
        scope="deploy",
        aliases=(
            "🚢 deploy: publish to staging",
            "📤 deploy: push build to server",
            "📤 code: sync production",
        ),
    ),
    _ct(
        "ci-firewall", "ci",
        "ci(firewall): ${subject}",
        "CI-level firewall or network-rule change.",
        scope="firewall",
        aliases=("📤 firewall: update rules",),
    ),
    _ct(
        "ci-dns", "ci",
        "ci(dns): ${subject}",
        "DNS / domain configuration change tracked in repo.",
        scope="dns",
        aliases=("📤 dns: add new CNAME",),
    ),
    _ct(
        "ci-ops", "ci",
        "ci(ops): ${subject}",
        "Scheduled-maintenance or ops-runbook change.",
        scope="ops",
        aliases=("🛎️ ops: scheduled maintenance update",),
    ),
    _ct(
        "ci-logs", "ci",
        "ci(logs): ${subject}",
        "Log-rotation / log-archive pipeline change.",
        scope="logs",
        aliases=(
            "📤 logs: rotate production logs",
            "📥 logs: import archived logs",
        ),
    ),
    _ct(
        "ci-backup", "ci",
        "ci(backup): ${subject}",
        "Backup / snapshot pipeline change.",
        scope="backup",
        aliases=("📥 backup: DB snapshot",),
    ),

    # ============ chore ============
    _ct(
        "chore-basic", "chore",
        "chore: ${subject}",
        "Maintenance work with no production-code change.",
        tags=("starter",),
    ),
    _ct(
        "chore-deps", "chore",
        "chore(deps): bump ${scope} from ${refs} to ${subject}",
        "Dependency bump with from/to versions in the `refs` placeholder.",
        scope="deps",
        tags=("deps",),
        aliases=(
            "📦 chore: update dependencies",
            "📦 chore: update packages",
            "📦 patch: dependency fix",
            "📦 task: bump version constraints",
            "📥 fetch: dependencies",
        ),
    ),
    _ct(
        "chore-freeze", "chore",
        "chore(deps): ${subject}",
        "Pin or freeze dependency version ranges.",
        scope="deps",
        aliases=("🧊 freeze: lock version ranges",),
    ),
    _ct(
        "chore-cleanup", "chore",
        "chore: ${subject}",
        "Cleanup of unused files, temp data, or stale resources.",
        aliases=(
            "🗑️ chore: cleanup unused files",
            "📤 cleanup: old temp files",
        ),
    ),
    _ct(
        "chore-publish", "chore",
        "chore(release): ${subject}",
        "Package publication step in the release workflow.",
        scope="release",
        workflow="release",
        aliases=(
            "📦 chore: package refresh",
            "📦 chore: publish package",
            "📦 task: routine update",
        ),
    ),
    _ct(
        "chore-mirror", "chore",
        "chore(mirror): ${subject}",
        "Mirror-sync / upstream-import maintenance.",
        scope="mirror",
        aliases=(
            "📥 chore: mirror sync with repo",
            "📥 chore: auto-import from upstream",
            "📤 chore: auto-upload artifacts",
        ),
    ),
    _ct(
        "chore-meta", "chore",
        "chore(meta): ${subject}",
        "Project-metadata update (descriptions, keywords, badges).",
        scope="meta",
        aliases=("🗃️ meta: update project metadata",),
    ),
    _ct(
        "chore-l10n", "chore",
        "chore(l10n): ${subject}",
        "Localization / regional-formatting update.",
        scope="l10n",
        aliases=("📣 l10n: update regional formats",),
    ),
    _ct(
        "chore-tools", "chore",
        "chore(tools): ${subject}",
        "Developer-tooling upgrades (CLI tools, generators, scripts).",
        scope="tools",
        aliases=("🧰 tools: upgrade CLI tools",),
    ),
    _ct(
        "chore-hooks", "chore",
        "chore(hooks): ${subject}",
        "Git-hook installation, removal, or update.",
        scope="hooks",
        aliases=("🪝 hooks: add commit hook",),
    ),
    _ct(
        "chore-scheduler", "chore",
        "chore(scheduler): ${subject}",
        "Scheduled-job / cron frequency change.",
        scope="scheduler",
        aliases=("📅 calendar: adjust task frequency",),
    ),
    _ct(
        "chore-mailer-config", "chore",
        "chore(mailer): ${subject}",
        "Mailer configuration / template change.",
        scope="mailer",
        aliases=("📧 email: confirmation template",),
    ),

    # ============ revert ============
    _ct(
        "revert-basic", "revert",
        'revert: "${subject}"',
        "Revert a previous commit; subject mirrors the original.",
        body_template='\n\nThis reverts commit ${refs}.\n',
        requires_body=True,
        tags=("starter",),
        aliases=("♻️ revert: undo recent change",),
    ),

    # ============ workflow-specific (release / hotfix / merge / squash / wip / initial / cherry-pick) ============
    _ct(
        "release-bump", "chore",
        "chore(release): bump version to ${subject}",
        "Version-bump preparing the next release tag.",
        scope="release",
        workflow="release",
        tags=("release",),
        aliases=(
            "🚀 release: bump version",
            "📦 release: patch update",
        ),
    ),
    _ct(
        "release-sign", "chore",
        "chore(release): sign tag ${subject}",
        "GPG / sigstore signing of a release tag.",
        scope="release",
        workflow="release",
        tags=("release", "signing"),
        aliases=("📦 release: sign final tag",),
    ),
    _ct(
        "release-publish", "chore",
        "chore(release): publish ${subject}",
        "Publication step of the release workflow.",
        scope="release",
        workflow="release",
        aliases=("🚀 release: publish package",),
    ),
    _ct(
        "release-initial", "chore",
        "chore(release): initial release ${subject}",
        "The first published release of the project.",
        scope="release",
        workflow="initial",
        tags=("release", "initial"),
        aliases=(
            "🧨 release: initial release",
            "🚀 release: initial deployment",
        ),
    ),
    _ct(
        "release-initial-wip", "chore",
        "chore(release): initial release (WIP) ${subject}",
        "Initial release marked work-in-progress.",
        scope="release",
        workflow="initial",
        tags=("release", "initial", "wip"),
        aliases=("🧨 release: initial release (WIP)",),
    ),
    _ct(
        "merge-commit", "chore",
        "Merge branch '${scope}' into ${subject}",
        "Standard merge-commit subject.",
        workflow="merge",
        tags=("merge",),
    ),
    _ct(
        "squash-merge", "chore",
        "chore(merge): squash ${scope} into ${subject}",
        "Squash-merge of a feature branch.",
        workflow="squash",
        tags=("merge", "squash"),
    ),
    _ct(
        "cherry-pick", "chore",
        "${type}(${scope}): ${subject} (cherry-pick from ${refs})",
        "Cherry-pick of a commit from another branch.",
        workflow="cherry-pick",
        tags=("cherry-pick",),
    ),
    _ct(
        "wip", "chore",
        "wip: ${subject}",
        "Work-in-progress save-point; squash before merging.",
        workflow="wip",
        tags=("wip",),
        aliases=(
            "🚧 wip: work in progress",
            "🚧 wip: in-progress automation",
        ),
    ),
)


# --------------------------------------------------------------------------- #
# Cross-checks
# --------------------------------------------------------------------------- #


def _alias_to_preset_map() -> dict[str, str]:
    """Map every v1 alias to its preset's `id`."""

    out: dict[str, str] = {}
    for preset in PRESETS:
        for alias in preset.aliases:
            if alias in out:
                raise ValueError(
                    f"v1 alias {alias!r} mapped to TWO presets: "
                    f"{out[alias]!r} and {preset.id!r}"
                )
            out[alias] = preset.id
    return out


def coverage_report() -> dict[str, object]:
    """Audit coverage of V1_LEGACY_MESSAGES against PRESETS + FILTERED.

    Used by the test suite to assert: every v1 string is either aliased into
    a preset OR explicitly filtered. No orphans, no double-coverage.
    """

    aliases = _alias_to_preset_map()
    legacy = set(V1_LEGACY_MESSAGES)
    aliased_legacy = legacy & set(aliases.keys())
    filtered_legacy = legacy & set(FILTERED.keys())
    orphans = legacy - aliased_legacy - filtered_legacy
    overlap = aliased_legacy & filtered_legacy
    extra_aliases = set(aliases.keys()) - legacy
    extra_filtered = set(FILTERED.keys()) - legacy
    return {
        "legacy_total": len(legacy),
        "aliased": len(aliased_legacy),
        "filtered": len(filtered_legacy),
        "orphans": sorted(orphans),
        "overlap": sorted(overlap),
        "extra_aliases": sorted(extra_aliases),
        "extra_filtered": sorted(extra_filtered),
    }


# --------------------------------------------------------------------------- #
# TOML rendering
# --------------------------------------------------------------------------- #


def _toml_quote(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
    return f'"{escaped}"'


def _toml_array(values: Iterable[str]) -> str:
    items = list(values)
    if not items:
        return "[]"
    lines = ["["]
    for item in items:
        lines.append(f"    {_toml_quote(item)},")
    lines.append("]")
    return "\n".join(lines)


def _render_library_toml() -> str:
    """Render templates/commit-templates/default.toml."""

    lines: list[str] = []
    lines.append("# Sange curated commit-message preset library.")
    lines.append(f"# Generated by {GENERATED_BY} (T-G-004).")
    lines.append(
        "# Source: v1 `DEFAULT_GIT_COMMIT_MESSAGES` + Conventional Commits 1.0.0,"
    )
    lines.append("# normalized per §6.8.5 of `.design/sange-architecture-prompt.md`.")
    lines.append("")
    lines.append("[meta]")
    lines.append(f'generator = "{GENERATED_BY}"')
    lines.append(f'generator_version = "{GENERATOR_VERSION}"')
    lines.append(f"preset_count = {len(PRESETS)}")
    lines.append(f"v1_legacy_total = {len(V1_LEGACY_MESSAGES)}")
    lines.append(f"v1_aliased = {sum(len(p.aliases) for p in PRESETS)}")
    lines.append(f"v1_filtered = {len(FILTERED)}")
    lines.append("")

    for preset in sorted(PRESETS, key=lambda p: (p.type, p.id)):
        lines.append(f"[[preset]]")
        lines.append(f"id = {_toml_quote(preset.id)}")
        lines.append(f"type = {_toml_quote(preset.type)}")
        if preset.scope:
            lines.append(f"scope = {_toml_quote(preset.scope)}")
        else:
            lines.append('scope = ""')
        lines.append(f"template = {_toml_quote(preset.template)}")
        lines.append(f"description = {_toml_quote(preset.description)}")
        if preset.body_template:
            lines.append(f"body_template = {_toml_quote(preset.body_template)}")
        lines.append(
            f"requires_body = {'true' if preset.requires_body else 'false'}"
        )
        lines.append(
            f"breaking_change = {'true' if preset.breaking_change else 'false'}"
        )
        if preset.workflow:
            lines.append(f"workflow = {_toml_quote(preset.workflow)}")
        if preset.tags:
            lines.append(f"tags = {_toml_array(preset.tags)}")
        if preset.aliases:
            lines.append(f"aliases = {_toml_array(preset.aliases)}")
        lines.append("")

    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Appendix-G markdown rendering
# --------------------------------------------------------------------------- #


def _render_appendix_body() -> str:
    parts: list[str] = []
    parts.append(markdown.heading(1, "Appendix G — Commit message preset library"))
    parts.append(
        "> Generated by `tools/generators/commit_templates.py` (T-G-004). "
        "Folds v1's 104-entry `DEFAULT_GIT_COMMIT_MESSAGES` array "
        "(`sange-v1/configs/config.sh:25-128`) + Conventional Commits 1.0.0 "
        "into a normalized library per §6.8.5 of `.design/sange-architecture-prompt.md`.\n"
    )

    coverage = coverage_report()
    parts.append(markdown.heading(2, "Coverage summary"))
    parts.append(
        markdown.table(
            ["Metric", "Count"],
            [
                ["v1 legacy entries (verbatim, audit trail)", str(coverage["legacy_total"])],
                ["v1 entries aliased into a preset", str(coverage["aliased"])],
                ["v1 entries filtered (operational events, not commits)", str(coverage["filtered"])],
                ["Curated presets shipped (≥50 target per §6.8.5)", str(len(PRESETS))],
                ["Conventional Commits types covered", str(len({p.type for p in PRESETS}))],
            ],
            alignments=["left", "right"],
        )
    )
    parts.append("")

    parts.append(markdown.heading(2, "Preset catalog"))
    grouped: dict[str, list[CommitTemplate]] = defaultdict(list)
    for preset in PRESETS:
        grouped[preset.type].append(preset)

    for cc_type in CC_TYPES:
        rows = grouped.get(cc_type, [])
        if not rows:
            continue
        parts.append(markdown.heading(3, f"`{cc_type}` ({len(rows)})"))
        table_rows = []
        for p in sorted(rows, key=lambda x: x.id):
            tags = ", ".join(f"`{t}`" for t in p.tags) if p.tags else "—"
            aliases_count = str(len(p.aliases)) if p.aliases else "—"
            flags = []
            if p.breaking_change:
                flags.append("breaking")
            if p.requires_body:
                flags.append("requires body")
            if p.workflow:
                flags.append(f"workflow={p.workflow}")
            flags_str = ", ".join(flags) if flags else "—"
            table_rows.append(
                [
                    f"`{p.id}`",
                    f"`{p.template}`",
                    p.description,
                    p.scope or "—",
                    flags_str,
                    tags,
                    aliases_count,
                ]
            )
        parts.append(
            markdown.table(
                ["Preset ID", "Template", "Description", "Scope", "Flags", "Tags", "v1 aliases"],
                table_rows,
            )
        )
        parts.append("")

    parts.append(markdown.heading(2, "v1 → v3 migration table"))
    parts.append(
        "Every v1 `DEFAULT_GIT_COMMIT_MESSAGES` entry resolves to one of:"
    )
    parts.append("")
    parts.append(
        markdown.bullet_list(
            [
                "An **aliased preset** — the v1 string is registered in a preset's `aliases` field; selecting that preset in the §6.8 commit-message lifecycle UI uses the canonical CC-shaped template.",
                "An **explicitly filtered** entry — pure operational events (notifications, FTP uploads, cron fires) with no underlying code change are dropped with a one-line reason.",
            ]
        )
    )
    parts.append("")

    parts.append(markdown.heading(3, "Aliased entries"))
    aliases_map = _alias_to_preset_map()
    aliased_rows = sorted(
        ((legacy, preset_id) for legacy, preset_id in aliases_map.items()),
        key=lambda x: (x[1], x[0]),
    )
    parts.append(
        markdown.table(
            ["v1 legacy string", "Maps to preset"],
            [[legacy, f"`{preset_id}`"] for legacy, preset_id in aliased_rows],
        )
    )
    parts.append("")

    parts.append(markdown.heading(3, "Filtered entries"))
    parts.append("These v1 strings do not map to a commit-message preset:")
    parts.append("")
    parts.append(
        markdown.table(
            ["v1 legacy string", "Reason"],
            [[legacy, reason] for legacy, reason in sorted(FILTERED.items())],
        )
    )
    parts.append("")

    parts.append(markdown.heading(2, "Programmatic access"))
    parts.append(
        "The library at `templates/commit-templates/default.toml` is "
        "consumed by the §6.8 commit-message subsystem at run-time. Users "
        "extend it via `~/.sange/commit-templates/user.toml` and "
        "`${repo}/.sange/commit-templates/user/*.toml`. Plugin-supplied "
        "templates (per ADR-020 signed-manifest discipline) merge via "
        "`extends`.\n"
    )

    parts.append(markdown.heading(2, "Extending the library"))
    parts.append(
        markdown.bullet_list(
            [
                "Add a preset → append a `_ct(...)` literal to `PRESETS` in "
                "`tools/generators/commit_templates.py`.",
                "Map a legacy v1 string to a preset → add it to that preset's "
                "`aliases` tuple.",
                "Explicitly filter a v1 string → add it to `FILTERED` with a "
                "one-line reason.",
                "Regenerate → `python tools/generators/all.py --only T-G-004 --write`.",
                "Verify integrity → `python tools/generators/verify_generated.py`.",
            ]
        )
    )
    return "\n".join(parts)


# --------------------------------------------------------------------------- #
# Generator entry-point
# --------------------------------------------------------------------------- #


def _input_sha256() -> str:
    payload = {
        "generator_version": GENERATOR_VERSION,
        "v1_legacy_messages": list(V1_LEGACY_MESSAGES),
        "filtered": dict(sorted(FILTERED.items())),
        "presets": [
            {
                "id": p.id,
                "type": p.type,
                "scope": p.scope,
                "template": p.template,
                "description": p.description,
                "body_template": p.body_template,
                "requires_body": p.requires_body,
                "breaking_change": p.breaking_change,
                "workflow": p.workflow,
                "tags": list(p.tags),
                "aliases": list(p.aliases),
            }
            for p in sorted(PRESETS, key=lambda x: x.id)
        ],
    }
    return sha256_text(json.dumps(payload, sort_keys=True))


def _write_toml_atomically(path: Path, content: str) -> None:
    import os, tempfile  # noqa: E401 — local helper

    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = content.encode("utf-8")
    tmp_fd, tmp_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent),
    )
    try:
        with os.fdopen(tmp_fd, "wb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
        try:
            os.chmod(path, 0o644)
        except OSError:
            pass
    except BaseException:
        try:
            Path(tmp_name).unlink(missing_ok=True)
        except OSError:
            pass
        raise


def run(
    *,
    mode: WriteMode,
    clock: _dt.datetime,
    library_path: Path | None = None,
    appendix_path: Path | None = None,
) -> list[WriteOutcome]:
    """Generator entry-point.

    Test parameters (`library_path`, `appendix_path`) override the output
    locations for sandboxed tests.
    """

    target_library = library_path or LIBRARY_PATH
    target_appendix = appendix_path or APPENDIX_PATH

    if mode is WriteMode.WRITE:
        _write_toml_atomically(target_library, _render_library_toml())

    meta = GeneratorMetadata(
        generated_by=GENERATED_BY,
        generator_version=GENERATOR_VERSION,
        input_sha256=_input_sha256(),
        manual_edits_allowed=False,
        generated_at=clock,
    )
    body = _render_appendix_body()
    outcome = write_generated_file(target_appendix, body, meta, mode=mode)
    return [outcome]


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if not (args.write or args.check):
        args.write = True
    mode = WriteMode.WRITE if args.write else WriteMode.CHECK

    results = run(mode=mode, clock=_dt.datetime.now(tz=_dt.timezone.utc))
    rc = 0
    for r in results:
        if r.result is not None and r.result.value != "match":
            rc = 66
        line = f"[{mode.value}] {r.path}  sha256={r.output_sha256}"
        if r.result is not None:
            line += f"  ({r.result.value})"
        print(line)
    if mode is WriteMode.WRITE:
        print(f"  + library written to {LIBRARY_PATH.relative_to(REPO_ROOT)}")
    raise SystemExit(rc)
