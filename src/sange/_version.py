# Sange single source of version truth (per Simtabi CLAUDE.md).
#
# hatchling reads __version__ from this module via [tool.hatch.version] in
# pyproject.toml. Do not import this module from runtime code other than the
# package __init__ — the build system needs to be able to parse it without
# executing the package's imports.
#
# Versioning is SemVer 2.0.0 + PEP 440. The 0.1.0.devN scheme marked the v0.1
# MVP build phase. The v0.1.0 tag shipped against `.dev0` (a wart caught in
# S-003-T-79); v0.1.0.post1 is the real first published release per PEP 440
# post-release semantics, fix-forwarding the .dev0 mistake.

__version__ = "0.1.1.dev0"
