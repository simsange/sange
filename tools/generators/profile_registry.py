"""Generate the 35-profile gitignore registry + docs/reference/profile-registry.md.

T-G-015 — per §6.5.1 of `.design/sange-architecture-prompt.md` + ADR-026.

Outputs:

  * `templates/gitignore-profiles/<category>/<name>.toml` — one TOML per profile;
    consumed by the gitignore-swap engine (§6.5) and the variant matrix (§6.5.2).
    Integrity covered by `templates/MANIFEST.toml.sig` (T-G-005).
  * `templates/gitignore-profiles/_core/license.toml` — the never-exclude
    safety profile (§6.5.1 Red-Team Pass #5).
  * `docs/reference/profile-registry.md` — the canonical reference document
    with §16.4.1 frontmatter (this is the generator's "primary" output).

Determinism (ADR-023):

  * Profile data is a constant inside this module — no external input.
  * Input hash = sha256 of the canonical JSON of the PROFILES + LICENSE_SAFETY
    + the generator version.
  * Re-runs are byte-identical for the same clock.

Per ADR-026:

  * Profile names are part of the public API surface. Renaming a profile is a
    SemVer-major change. Adding a profile is SemVer-minor.
  * The `_core/license` safety profile is loaded for every repo and rejects
    any composition that would exclude its patterns.
"""

from __future__ import annotations

import datetime as _dt
import json
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

# --- Path bootstrap ------------------------------------------------------- #
HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent.parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

# --- Imports -------------------------------------------------------------- #
from _lib import markdown  # noqa: E402
from _lib.fingerprint import sha256_text  # noqa: E402
from _lib.output import (  # noqa: E402
    GeneratorMetadata,
    WriteMode,
    WriteOutcome,
    write_generated_file,
)

GENERATOR_VERSION = "1.0.0"
GENERATED_BY = "tools/generators/profile_registry.py"

PROFILES_OUTPUT_DIR = REPO_ROOT / "templates" / "gitignore-profiles"
REFERENCE_DOC_PATH = REPO_ROOT / "docs" / "reference" / "profile-registry.md"

MAINTAINER = "Simtabi LLC <opensource@simtabi.com>"
PROFILE_VERSION = "1.0.0"  # bump per-profile when patterns change in a non-trivial way


# --------------------------------------------------------------------------- #
# Data model
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Profile:
    """A single gitignore profile per §6.5.1.

    Fields:

      * `name`              — qualified slug, e.g. `"lang/python"`.
      * `category`          — top-level category from §10.4.
      * `display_name`      — human-readable.
      * `version`           — SemVer; bump on non-trivial pattern change.
      * `maintainer`        — owner contact.
      * `upstream_source`   — citation for where the patterns came from.
      * `detect_required_any` — file patterns that trigger auto-detect.
      * `detect_boost_any`  — additional signals that raise confidence.
      * `patterns_always`   — ignored in BOTH dev and prod variants.
      * `patterns_dev_only` — ignored in dev tree; in prod too (these never
                              ship in publish artifacts).
      * `patterns_prod_only` — ignored only at publish time.
      * `extends`           — slugs of profiles this one composes with.
      * `notes`             — free-text hint (deferred status, special cases).
    """

    name: str
    category: str
    display_name: str
    detect_required_any: tuple[str, ...] = ()
    detect_boost_any: tuple[str, ...] = ()
    patterns_always: tuple[str, ...] = ()
    patterns_dev_only: tuple[str, ...] = ()
    patterns_prod_only: tuple[str, ...] = ()
    extends: tuple[str, ...] = ()
    upstream_source: str = ""
    notes: str = ""
    version: str = PROFILE_VERSION
    maintainer: str = MAINTAINER


# --------------------------------------------------------------------------- #
# The registry (35 profiles per §6.5.1)
# --------------------------------------------------------------------------- #


def _p(name: str, category: str, display_name: str, **kw) -> Profile:
    return Profile(name=name, category=category, display_name=display_name, **kw)


PROFILES: tuple[Profile, ...] = (
    # ---- _core (2 profiles + 1 safety) ----
    _p(
        "_core/secrets",
        "_core",
        "Secrets safety net",
        notes="Always-on. Cannot be disabled without audit-logged override.",
        patterns_always=(
            "*.pem",
            "*.key",
            "*.p12",
            "*.pfx",
            "id_rsa", "id_rsa.pub",
            "id_ed25519", "id_ed25519.pub",
            ".env",
            ".env.*",
            "!.env.example",
            "credentials*",
            "secrets*",
        ),
    ),
    _p(
        "_core/editor-noise",
        "_core",
        "Editor + OS noise (cross-platform)",
        notes="Always-on. Catches accidental commits of editor backup files.",
        patterns_always=(
            ".DS_Store",
            "Thumbs.db",
            "desktop.ini",
            "*.swp", "*.swo",
            "*~",
        ),
    ),
    # ---- lang (12 profiles; kotlin is extends-only per §6.5.1) ----
    _p(
        "lang/python",
        "lang",
        "Python",
        upstream_source="https://github.com/github/gitignore/blob/main/Python.gitignore",
        detect_required_any=("pyproject.toml", "setup.py", "requirements.txt", "Pipfile"),
        detect_boost_any=(".python-version", "uv.lock", "poetry.lock", "Pipfile.lock"),
        patterns_always=(
            "__pycache__/",
            "*.py[cod]",
            "*$py.class",
            ".Python",
            "*.so",
        ),
        patterns_dev_only=(
            ".venv/", "venv/", "env/", ".tox/",
            ".ruff_cache/", ".mypy_cache/", ".pytest_cache/",
            "htmlcov/", ".coverage", ".coverage.*",
            "dist/", "build/", "*.egg-info/",
        ),
    ),
    _p(
        "lang/node",
        "lang",
        "Node.js",
        upstream_source="https://github.com/github/gitignore/blob/main/Node.gitignore",
        detect_required_any=("package.json", "package-lock.json", "yarn.lock", "pnpm-lock.yaml", "bun.lockb"),
        detect_boost_any=("npm-shrinkwrap.json", ".nvmrc"),
        patterns_always=(
            "node_modules/",
            "npm-debug.log*",
            "yarn-debug.log*",
            "yarn-error.log*",
        ),
        patterns_dev_only=(
            ".npm/", ".yarn/", ".pnp.*",
            "dist/", "build/", "coverage/",
            ".next/", ".nuxt/", ".output/",
        ),
    ),
    _p(
        "lang/php",
        "lang",
        "PHP",
        upstream_source="https://github.com/github/gitignore/blob/main/Composer.gitignore",
        detect_required_any=("composer.json", "composer.lock"),
        patterns_always=(
            "vendor/",
            "composer.phar",
        ),
        patterns_dev_only=(
            ".phpunit.cache",
            ".phpunit.result.cache",
            ".phpunit-watcher.yml",
        ),
    ),
    _p(
        "lang/go",
        "lang",
        "Go",
        upstream_source="https://github.com/github/gitignore/blob/main/Go.gitignore",
        detect_required_any=("go.mod", "go.sum"),
        patterns_always=(
            "bin/",
            "pkg/",
            "*.exe",
            "*.test",
            "*.out",
        ),
        patterns_dev_only=("vendor/",),
        notes="Track vendor/ when `go.mod` declares `vendor` directive; the engine warns when both signals coexist.",
    ),
    _p(
        "lang/rust",
        "lang",
        "Rust",
        upstream_source="https://github.com/github/gitignore/blob/main/Rust.gitignore",
        detect_required_any=("Cargo.toml", "Cargo.lock"),
        patterns_always=(
            "target/",
            "**/*.rs.bk",
        ),
        notes="Cargo.lock is tracked for binaries and gitignored in libraries; the engine doesn't make the call automatically.",
    ),
    _p(
        "lang/ruby",
        "lang",
        "Ruby",
        upstream_source="https://github.com/github/gitignore/blob/main/Ruby.gitignore",
        detect_required_any=("Gemfile", "Gemfile.lock", "*.gemspec"),
        patterns_always=(
            ".bundle/",
            "vendor/bundle/",
            "*.gem",
        ),
        patterns_dev_only=(
            ".byebug_history",
            ".rspec_status",
            "coverage/",
            "spec/reports/",
        ),
    ),
    _p(
        "lang/java",
        "lang",
        "Java",
        upstream_source="https://github.com/github/gitignore/blob/main/Java.gitignore",
        detect_required_any=("pom.xml", "build.gradle", "build.gradle.kts", "gradlew"),
        patterns_always=(
            "target/",
            "build/",
            "*.class",
            "*.jar",
            "*.war",
        ),
        patterns_dev_only=(
            ".gradle/",
            "out/",
            "hs_err_pid*",
        ),
    ),
    _p(
        "lang/dotnet",
        "lang",
        ".NET",
        upstream_source="https://github.com/github/gitignore/blob/main/VisualStudio.gitignore",
        detect_required_any=("*.csproj", "*.fsproj", "*.sln", "global.json"),
        patterns_always=(
            "bin/",
            "obj/",
            "*.user",
            "*.suo",
            "packages/",
            "*.nupkg",
        ),
    ),
    _p(
        "lang/elixir",
        "lang",
        "Elixir",
        upstream_source="https://github.com/github/gitignore/blob/main/Elixir.gitignore",
        detect_required_any=("mix.exs", "mix.lock"),
        patterns_always=(
            "_build/",
            "deps/",
            "*.beam",
        ),
        patterns_dev_only=(
            ".elixir_ls/",
            "cover/",
            "doc/",
        ),
    ),
    _p(
        "lang/swift",
        "lang",
        "Swift",
        upstream_source="https://github.com/github/gitignore/blob/main/Swift.gitignore",
        detect_required_any=("Package.swift", "*.xcodeproj/", "*.xcworkspace/"),
        patterns_always=(
            ".build/",
            "DerivedData/",
            "Pods/",
            "Carthage/Build/",
            "*.xcuserstate",
        ),
    ),
    # NOTE: `lang/kotlin` is intentionally NOT shipped as its own TOML.
    # Per ADR-026 the v1.0 registry counts 35 patterns-owning profiles.
    # Kotlin builds share `build.gradle.kts` with Java and use JetBrains
    # editor noise — composing `lang/java` + `editor/jetbrains` covers it
    # cleanly. Shipping a Kotlin TOML would create an auto-detect collision
    # on `build.gradle.kts`. The reference doc documents this as a "covered
    # by other profiles" callout.
    _p(
        "lang/dart",
        "lang",
        "Dart",
        upstream_source="https://github.com/github/gitignore/blob/main/Dart.gitignore",
        detect_required_any=("pubspec.yaml", "pubspec.lock"),
        patterns_always=(
            ".dart_tool/",
            ".packages",
            "build/",
        ),
        patterns_dev_only=(
            "doc/api/",
        ),
    ),
    # ---- framework (9 profiles) ----
    _p(
        "framework/laravel",
        "framework",
        "Laravel",
        detect_required_any=("artisan",),
        detect_boost_any=("composer.json",),  # plus composer.json contains laravel/framework
        extends=("lang/php",),
        patterns_always=(
            "bootstrap/cache/",
            "storage/logs/",
            "storage/framework/cache/",
            "storage/framework/sessions/",
            "storage/framework/views/",
            ".phpunit.result.cache",
            "Homestead.*",
        ),
        patterns_dev_only=(
            ".env",  # already in _core/secrets — explicit duplication is OK
            ".env.backup",
            "Homestead.json",
        ),
    ),
    _p(
        "framework/django",
        "framework",
        "Django",
        detect_required_any=("manage.py",),
        detect_boost_any=("requirements.txt",),  # plus contains "Django"
        extends=("lang/python",),
        patterns_always=(
            "*.log",
            "db.sqlite3*",
            "staticfiles/",
        ),
        patterns_dev_only=(
            "media/",
            ".env.local",
            "local_settings.py",
        ),
        notes="media/ is ignored only when MEDIA_ROOT is project-local; the operator overrides via per-project user/ profile if uploaded media is tracked intentionally.",
    ),
    _p(
        "framework/rails",
        "framework",
        "Ruby on Rails",
        upstream_source="https://github.com/github/gitignore/blob/main/Rails.gitignore",
        detect_required_any=("bin/rails", "config/application.rb"),
        extends=("lang/ruby",),
        patterns_always=(
            "tmp/",
            "log/",
            "*.rbc",
            "storage/",
            "config/master.key",
            "node_modules/",
        ),
        patterns_dev_only=(
            ".byebug_history",
            ".rspec_status",
        ),
    ),
    _p(
        "framework/nextjs",
        "framework",
        "Next.js",
        detect_required_any=("next.config.js", "next.config.mjs", "next.config.ts"),
        extends=("lang/node",),
        patterns_always=(
            ".next/",
            "out/",
            "next-env.d.ts",
        ),
    ),
    _p(
        "framework/nuxt",
        "framework",
        "Nuxt",
        detect_required_any=("nuxt.config.js", "nuxt.config.ts"),
        extends=("lang/node",),
        patterns_always=(
            ".nuxt/",
            ".output/",
            "dist/",
        ),
    ),
    _p(
        "framework/symfony",
        "framework",
        "Symfony",
        detect_required_any=("bin/console",),
        detect_boost_any=("composer.json",),  # plus composer.json declares symfony/symfony
        extends=("lang/php",),
        patterns_always=(
            "var/",
            "public/bundles/",
            ".phpunit.result.cache",
            "config/jwt/*.pem",
        ),
    ),
    _p(
        "framework/astro",
        "framework",
        "Astro",
        detect_required_any=("astro.config.mjs", "astro.config.ts"),
        extends=("lang/node",),
        patterns_always=(
            "dist/",
            ".astro/",
        ),
    ),
    _p(
        "framework/sveltekit",
        "framework",
        "SvelteKit",
        detect_required_any=("svelte.config.js", "svelte.config.ts"),
        extends=("lang/node",),
        patterns_always=(
            ".svelte-kit/",
            "build/",
        ),
    ),
    _p(
        "framework/flutter",
        "framework",
        "Flutter",
        upstream_source="https://github.com/flutter/flutter/blob/master/.gitignore",
        detect_required_any=("pubspec.yaml",),  # plus contains "flutter:" block
        extends=("lang/dart",),
        patterns_always=(
            ".flutter-plugins",
            ".flutter-plugins-dependencies",
            ".pub-cache/",
            "build/",
            "*.iml",
        ),
        patterns_dev_only=(
            ".dart_tool/package_config_subset",
        ),
    ),
    # ---- infra (5 profiles) ----
    _p(
        "infra/docker",
        "infra",
        "Docker",
        detect_required_any=("Dockerfile", "compose.yml", "docker-compose.yml"),
        patterns_always=(
            "*.local",
            "docker-compose.override.yml",
        ),
        notes="The container image itself uses a .dockerignore Sange materializes separately.",
    ),
    _p(
        "infra/kubernetes",
        "infra",
        "Kubernetes",
        detect_required_any=("kustomization.yaml", "helm/Chart.yaml", "*.k8s.yaml"),
        patterns_always=(
            "charts/*.tgz",
            "kubeconfig*",
        ),
        notes="kubeconfig is treated as secret-class (also covered by _core/secrets).",
    ),
    _p(
        "infra/terraform",
        "infra",
        "Terraform",
        upstream_source="https://github.com/github/gitignore/blob/main/Terraform.gitignore",
        detect_required_any=("*.tf", "*.tfvars"),
        patterns_always=(
            ".terraform/",
            "*.tfstate",
            "*.tfstate.backup",
            "*.tfplan",
            ".terraform.lock.hcl",
            "crash.log",
            "crash.*.log",
        ),
        notes="`.terraform.lock.hcl` is dev_only-or-prod-tracked depending on team convention; default is gitignore — override via user/ profile to track.",
    ),
    _p(
        "infra/ansible",
        "infra",
        "Ansible",
        detect_required_any=("ansible.cfg", "inventory.yml", "playbook.yml"),
        patterns_always=(
            "*.retry",
            "roles/*.tar.gz",
            "ansible.log",
            "*.vault",
        ),
    ),
    _p(
        "infra/pulumi",
        "infra",
        "Pulumi",
        detect_required_any=("Pulumi.yaml",),
        patterns_always=(
            "Pulumi.*.yaml.bak",
        ),
        patterns_dev_only=(
            "node_modules/",  # TS Pulumi projects
            ".pulumi/",
        ),
    ),
    # ---- editor (5 profiles) ----
    _p(
        "editor/jetbrains",
        "editor",
        "JetBrains IDEs",
        upstream_source="https://github.com/github/gitignore/blob/main/Global/JetBrains.gitignore",
        detect_required_any=(".idea/",),
        patterns_always=(
            ".idea/",
            "*.iml",
            "*.iws",
            "out/",
            ".idea_modules/",
        ),
    ),
    _p(
        "editor/vscode",
        "editor",
        "VS Code",
        upstream_source="https://github.com/github/gitignore/blob/main/Global/VisualStudioCode.gitignore",
        detect_required_any=(".vscode/",),
        patterns_always=(
            ".vscode/*",
            "!.vscode/extensions.json",
            "!.vscode/settings.json.shared",
            ".history/",
            "*.vsix",
        ),
        notes="Most VSCode dot-files are user-specific; teams selectively track `settings.json` via the `!` negation pattern.",
    ),
    _p(
        "editor/vim",
        "editor",
        "Vim",
        detect_required_any=(".vim/",),
        patterns_always=(
            "*.swp", "*.swo",
            "*~",
            "Session.vim",
            ".netrwhist",
            "tags",
        ),
    ),
    _p(
        "editor/emacs",
        "editor",
        "Emacs",
        detect_required_any=(".emacs.d/",),
        patterns_always=(
            "*~",
            "\\#*\\#",
            ".\\#*",
            "auto-save-list/",
            "tramp",
            "*_archive",
        ),
    ),
    _p(
        "editor/claude",
        "editor",
        "Claude Code",
        detect_required_any=(".claude/",),
        patterns_always=(
            ".claude/local-settings.json",
            "CLAUDE.local.md",
        ),
        notes="The shared `CLAUDE.md` is tracked; only local-* overrides are gitignored.",
    ),
    # ---- os (3 profiles) ----
    _p(
        "os/macos",
        "os",
        "macOS",
        upstream_source="https://github.com/github/gitignore/blob/main/Global/macOS.gitignore",
        patterns_always=(
            ".DS_Store",
            ".AppleDouble",
            ".LSOverride",
            "._*",
            ".Spotlight-V100",
            ".Trashes",
            ".VolumeIcon.icns",
            ".com.apple.timemachine.donotpresent",
        ),
        notes="Detected automatically when the host OS is macOS.",
    ),
    _p(
        "os/windows",
        "os",
        "Windows",
        upstream_source="https://github.com/github/gitignore/blob/main/Global/Windows.gitignore",
        patterns_always=(
            "Thumbs.db",
            "ehthumbs.db",
            "Desktop.ini",
            "$RECYCLE.BIN/",
            "*.lnk",
            "*.cab",
            "*.msi",
            "*.msm",
            "*.msp",
        ),
        notes="Detected automatically when the host OS is Windows.",
    ),
    _p(
        "os/linux",
        "os",
        "Linux",
        upstream_source="https://github.com/github/gitignore/blob/main/Global/Linux.gitignore",
        patterns_always=(
            "*~",
            ".fuse_hidden*",
            ".directory",
            ".Trash-*",
            ".nfs*",
        ),
        notes="Detected automatically when the host OS is Linux.",
    ),
)


# The never-exclude safety profile — §6.5.1 Red-Team Pass #5.
# Loaded for every repo; the kit-loader rejects any composition that would
# exclude paths matched here.
LICENSE_SAFETY = Profile(
    name="_core/license",
    category="_core",
    display_name="License + README never-exclude safety net",
    notes=(
        "Reverse-pattern profile: declares paths that must NEVER be excluded "
        "from a publish tree, regardless of any other profile's ignore rules. "
        "Per §6.5.1 Red-Team Pass #5. Loaded for every repo; immutable."
    ),
    patterns_always=(
        "!LICENSE",
        "!LICENSE.*",
        "!COPYING",
        "!COPYING.*",
        "!NOTICE",
        "!NOTICE.*",
        "!README",
        "!README.*",
    ),
    version="1.0.0",
    maintainer=MAINTAINER,
)


# --------------------------------------------------------------------------- #
# Rendering
# --------------------------------------------------------------------------- #


def _toml_array(values: Iterable[str]) -> str:
    """Render a TOML array, one quoted entry per line."""

    items = list(values)
    if not items:
        return "[]"
    lines = ["["]
    for item in items:
        escaped = item.replace("\\", "\\\\").replace('"', '\\"')
        lines.append(f'    "{escaped}",')
    lines.append("]")
    return "\n".join(lines)


def _render_profile_toml(profile: Profile) -> str:
    """Render a single profile to TOML.

    Stable key ordering, deterministic array formatting.
    """

    lines: list[str] = []
    lines.append(f"# {profile.display_name} — gitignore profile.")
    lines.append(f"# Generated by {GENERATED_BY} (T-G-015).")
    lines.append("# Hand-edits are discouraged; regenerate via")
    lines.append("# `python tools/generators/all.py --only T-G-015 --write`.")
    lines.append("")
    lines.append("[profile]")
    lines.append(f'name = "{profile.name}"')
    lines.append(f'display_name = "{profile.display_name}"')
    lines.append(f'category = "{profile.category}"')
    lines.append(f'version = "{profile.version}"')
    lines.append(f'maintainer = "{profile.maintainer}"')
    if profile.upstream_source:
        lines.append(f'upstream_source = "{profile.upstream_source}"')
    if profile.notes:
        # TOML multi-line strings with """ would be cleaner but a single-line
        # escaped form is more portable across parsers.
        notes_escaped = profile.notes.replace("\\", "\\\\").replace('"', '\\"')
        lines.append(f'notes = "{notes_escaped}"')
    lines.append("")

    lines.append("[detect]")
    lines.append(f"required_any = {_toml_array(profile.detect_required_any)}")
    if profile.detect_boost_any:
        lines.append(f"boost_any = {_toml_array(profile.detect_boost_any)}")
    else:
        lines.append("boost_any = []")
    lines.append("")

    lines.append("[patterns]")
    lines.append(f"always = {_toml_array(profile.patterns_always)}")
    lines.append(f"dev_only = {_toml_array(profile.patterns_dev_only)}")
    lines.append(f"prod_only = {_toml_array(profile.patterns_prod_only)}")
    lines.append("")

    lines.append("[extends]")
    if profile.extends:
        lines.append(f"profiles = {_toml_array(profile.extends)}")
    else:
        lines.append("profiles = []")
    lines.append("")
    return "\n".join(lines)


def _profile_path(profile: Profile) -> Path:
    return PROFILES_OUTPUT_DIR / profile.category / f"{profile.name.split('/', 1)[1]}.toml"


def _write_toml_atomically(path: Path, content: str) -> None:
    """TOML writer — same atomic-write contract as `_lib/output._atomic_write`
    but without the §16.4.1 frontmatter (TOMLs derive integrity from the
    `templates/MANIFEST.toml.sig` per ADR-020)."""

    import os
    import tempfile

    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = content.encode("utf-8")
    tmp_fd, tmp_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=str(path.parent),
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


# --------------------------------------------------------------------------- #
# Reference doc body
# --------------------------------------------------------------------------- #


def _by_category(profiles: Iterable[Profile]) -> dict[str, list[Profile]]:
    grouped: dict[str, list[Profile]] = {}
    for p in profiles:
        grouped.setdefault(p.category, []).append(p)
    for cat in grouped:
        grouped[cat].sort(key=lambda p: p.name)
    return grouped


CATEGORY_ORDER = ("_core", "lang", "framework", "infra", "editor", "os")


def _render_reference_body(all_profiles: list[Profile]) -> str:
    parts: list[str] = []
    parts.append(markdown.heading(1, "Sange gitignore profile registry"))
    parts.append(
        "> Generated by `tools/generators/profile_registry.py` (T-G-015). "
        "Source of truth: §6.5.1 + §6.5.2 (variant composition) of "
        "`.design/sange-architecture-prompt.md`; policy in ADR-026.\n"
    )
    parts.append(
        f"Total profiles in this release: **{len(all_profiles)}** "
        "(including the `_core/license` safety net). Each profile is also "
        "available as a TOML under `templates/gitignore-profiles/<category>/<name>.toml` "
        "whose integrity is covered by `templates/MANIFEST.toml.sig` (per ADR-020).\n"
    )
    parts.append(
        "Per ADR-026: profile names are part of Sange's public API. Adding a "
        "profile is a SemVer-minor change; renaming or repurposing a profile "
        "is a SemVer-major change. Pattern revisions bump the per-profile "
        "version field independently.\n"
    )

    parts.append(markdown.heading(2, "Profile catalog"))

    grouped = _by_category(all_profiles)
    summary_rows = []
    for category in CATEGORY_ORDER:
        rows = grouped.get(category, [])
        summary_rows.append([f"`{category}/`", str(len(rows))])
    summary_rows.append(["**Total**", str(len(all_profiles))])
    parts.append(
        markdown.table(["Category", "Profile count"], summary_rows, alignments=["left", "right"])
    )
    parts.append("")

    for category in CATEGORY_ORDER:
        rows = grouped.get(category, [])
        if not rows:
            continue
        parts.append(markdown.heading(3, f"`{category}/`"))
        table_rows = []
        for p in rows:
            detect = ", ".join(f"`{x}`" for x in p.detect_required_any) or "—"
            extends = ", ".join(f"`{x}`" for x in p.extends) or "—"
            always_count = len(p.patterns_always)
            dev_count = len(p.patterns_dev_only)
            prod_count = len(p.patterns_prod_only)
            table_rows.append(
                [
                    f"`{p.name}`",
                    p.display_name,
                    detect,
                    extends,
                    f"{always_count} / {dev_count} / {prod_count}",
                    p.notes or "—",
                ]
            )
        parts.append(
            markdown.table(
                [
                    "Profile",
                    "Display name",
                    "Auto-detect signals",
                    "Extends",
                    "Patterns (always/dev/prod)",
                    "Notes",
                ],
                table_rows,
            )
        )
        parts.append("")

    parts.append(markdown.heading(2, "Auto-detection algorithm"))
    parts.append(
        markdown.bullet_list(
            [
                "Walk the repo root + the first directory level for each profile's `detect.required_any`.",
                "Boost confidence by checking `detect.boost_any` (e.g. `uv.lock` raises confidence in `lang/python`).",
                "Always include `_core/secrets`, `_core/editor-noise`, and `_core/license` (safety net).",
                "Auto-include the appropriate `os/*` profile for the host OS.",
                "For each language match, include its dependent framework profiles via `extends` (Django pulls `lang/python`, Laravel pulls `lang/php`, etc.).",
                "For each editor whose dot-folder is present, include that editor profile.",
                "For infra signals, include them only when their declaring files exist.",
                "Emit a ranked suggestion list; the operator accepts/rejects sequentially per ADR-024.",
            ]
        )
    )
    parts.append("")

    parts.append(markdown.heading(2, "Composition order (when combined with the §6.5.2 Variant Matrix)"))
    parts.append(
        "When the swap engine composes the effective `.gitignore` for the active variant, "
        "fragments merge **highest-priority first** per §6.5.2.4:"
    )
    parts.append("")
    parts.append(
        markdown.bullet_list(
            [
                "`.sange/variants/matrix/<full-variant>/`",
                "`.sange/variants/stage/<stage>/`",
                "`.sange/variants/<dimension>/<flavor>/` — once per declared flavor dimension",
                "`.sange/variants/_core/`",
                "**This registry** (`templates/gitignore-profiles/`) — defaults",
            ]
        )
    )
    parts.append("")
    parts.append(
        "Gitignore patterns merge via **union** (a pattern ignored at any level is ignored "
        "in the composed result); use explicit `!path/pattern` negations to re-include a "
        "path a lower-level profile excluded."
    )
    parts.append("")

    parts.append(markdown.heading(2, "Documented-not-shipped profiles"))
    parts.append(
        "Some languages and frameworks are covered by composition of existing "
        "profiles rather than a dedicated TOML. Listed here so the absence is "
        "intentional and discoverable:"
    )
    parts.append("")
    parts.append(
        markdown.bullet_list(
            [
                "**Kotlin** — covered by `lang/java` + `editor/jetbrains`. Kotlin builds "
                "share `build.gradle.kts` and `settings.gradle.kts` signals with Java; "
                "shipping a separate `lang/kotlin` profile would create an auto-detect "
                "collision. Per ADR-026 v1.0 ships 35 patterns-owning profiles + the "
                "`_core/license` safety net.",
            ]
        )
    )
    parts.append("")

    parts.append(markdown.heading(2, "Safety profile (`_core/license`)"))
    parts.append(
        "The `_core/license` profile is **always loaded** and rejects any composition "
        "that would exclude `LICENSE*`, `COPYING*`, `NOTICE*`, or `README*` files. "
        "Plugin-supplied profiles that violate this rule are refused at load time."
    )
    parts.append("")

    parts.append(markdown.heading(2, "Extending the registry"))
    parts.append(
        markdown.bullet_list(
            [
                "**Add a profile** — append a `Profile(...)` literal to `PROFILES` in `tools/generators/profile_registry.py`; bump SemVer-minor on the next release.",
                "**Add a category** — requires an ADR (per §10.4); update the canonical category list in §10.4.1 first.",
                "**Plugin-supplied profile** — third-party plugins (per ADR-020 signed-manifest discipline) declare profiles in their manifest; the registry tags them `provenance: plugin (<name>)` in `sange profile list`.",
                "**Regenerate after a change** — `python tools/generators/all.py --only T-G-015 --write`; `verify_generated.py` enforces the integrity contract.",
            ]
        )
    )
    return "\n".join(parts)


# --------------------------------------------------------------------------- #
# Generator entry-point
# --------------------------------------------------------------------------- #


def _all_profiles() -> list[Profile]:
    return [*PROFILES, LICENSE_SAFETY]


def _input_sha256() -> str:
    payload = {
        "generator_version": GENERATOR_VERSION,
        "profile_count": len(_all_profiles()),
        "profiles": [
            {
                "name": p.name,
                "category": p.category,
                "display_name": p.display_name,
                "version": p.version,
                "detect_required_any": list(p.detect_required_any),
                "detect_boost_any": list(p.detect_boost_any),
                "patterns_always": list(p.patterns_always),
                "patterns_dev_only": list(p.patterns_dev_only),
                "patterns_prod_only": list(p.patterns_prod_only),
                "extends": list(p.extends),
                "upstream_source": p.upstream_source,
                "notes": p.notes,
            }
            for p in sorted(_all_profiles(), key=lambda x: x.name)
        ],
    }
    return sha256_text(json.dumps(payload, sort_keys=True))


def run(
    *,
    mode: WriteMode,
    clock: _dt.datetime,
    profiles_output_dir: Path | None = None,
    reference_doc_path: Path | None = None,
) -> list[WriteOutcome]:
    """Generator entry-point.

    Writes 36 TOML profile files + one reference markdown doc.
    Test parameters override the output locations.
    """

    out_dir = profiles_output_dir or PROFILES_OUTPUT_DIR
    out_doc = reference_doc_path or REFERENCE_DOC_PATH
    profiles = _all_profiles()

    outcomes: list[WriteOutcome] = []

    if mode is WriteMode.WRITE:
        for profile in profiles:
            target = out_dir / profile.category / f"{profile.name.split('/', 1)[1]}.toml"
            toml_text = _render_profile_toml(profile)
            _write_toml_atomically(target, toml_text)
            # We don't append per-TOML WriteOutcome to the public list — they
            # share integrity via the kit MANIFEST. The reference doc is the
            # one consumed by verify_generated.py.

    meta = GeneratorMetadata(
        generated_by=GENERATED_BY,
        generator_version=GENERATOR_VERSION,
        input_sha256=_input_sha256(),
        manual_edits_allowed=False,
        generated_at=clock,
    )
    body = _render_reference_body(profiles)
    outcomes.append(write_generated_file(out_doc, body, meta, mode=mode))
    return outcomes


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if not (args.write or args.check):
        args.write = True
    mode = WriteMode.WRITE if args.write else WriteMode.CHECK

    results = run(mode=mode, clock=_dt.datetime.now(tz=_dt.UTC))
    rc = 0
    for r in results:
        if r.result is not None and r.result.value != "match":
            rc = 66
        line = f"[{mode.value}] {r.path}  sha256={r.output_sha256}"
        if r.result is not None:
            line += f"  ({r.result.value})"
        print(line)
    if mode is WriteMode.WRITE:
        print(
            f"  + {len(_all_profiles())} TOMLs emitted under "
            f"{PROFILES_OUTPUT_DIR.relative_to(REPO_ROOT)}/"
        )
    raise SystemExit(rc)
