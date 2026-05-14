# Sange single source of version truth (per Simtabi CLAUDE.md).
#
# hatchling reads __version__ from this module via [tool.hatch.version] in
# pyproject.toml. Do not import this module from runtime code other than the
# package __init__ — the build system needs to be able to parse it without
# executing the package's imports.
#
# Versioning is SemVer 2.0.0. The 0.1.0.devN scheme marks the v0.1 MVP build
# phase per the Phase 0 roadmap (§14.1 of .design/sange-architecture-prompt.md).

__version__ = "0.1.0.dev0"
