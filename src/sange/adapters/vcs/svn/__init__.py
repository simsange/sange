"""`sange.adapters.vcs.svn` — Subversion adapter (T-100).

Exposed public surface:

  * `SvnDriver`            — the `VCSDriver` implementation.
  * `SvnRepoNotFound`      — raised when `detect()` is called on a non-repo.
  * `SvnNotInstalled`      — raised when the `svn` binary is missing.
  * `SvnCommandFailed`     — raised when `svn` exits non-zero.
  * `SvnVersion` / `SvnInfo` — typed parser outputs.
  * `run_svn`              — subprocess wrapper (advanced; tests + plugins only).

v0.5 first slice ships read-only **detect + status**. Subsequent
commits (T-100b read ops, T-100c write ops) extend the surface
without changing the public API shape.
"""

from __future__ import annotations

from sange.adapters.vcs.svn._subprocess import (
    SvnCommandFailed,
    SvnNotInstalled,
    run_svn,
)
from sange.adapters.vcs.svn.driver import SvnDriver, SvnRepoNotFound
from sange.adapters.vcs.svn.parsers import (
    SvnInfo,
    SvnVersion,
    parse_info_xml,
    parse_status_xml,
    parse_version,
)

__all__ = [
    "SvnCommandFailed",
    "SvnDriver",
    "SvnInfo",
    "SvnNotInstalled",
    "SvnRepoNotFound",
    "SvnVersion",
    "parse_info_xml",
    "parse_status_xml",
    "parse_version",
    "run_svn",
]
