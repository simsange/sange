"""Git adapter — `GitDriver` implements the `VCSDriver` Protocol for Git.

Per §6.2 of the architecture prompt. Read-only operations land in T-004
(this module); write operations in T-005 (committed separately).

Public surface:

  * `GitDriver`            — the adapter class.
  * `GitNotInstalled`      — raised when `git` is not on PATH.
  * `GitCommandFailed`     — raised on non-zero `git` exit.
  * `GitRepoNotFound`      — raised when `detect()` is called on a non-repo.

Sub-modules:

  * `_subprocess` — env-disciplined subprocess wrapper.
  * `parsers`     — pure parsers for `git status --porcelain=v2`,
                    `git log --pretty=format:...`, `git for-each-ref`, etc.
  * `driver`      — `GitDriver` class, orchestrating subprocess + parsers.

The Protocol-vs-implementation separation: `VCSDriver` (in
`sange.adapters.vcs._protocol`) declares WHAT every adapter does;
`GitDriver` (here) is the concrete HOW for Git. Application code depends
on the Protocol, never on this module.
"""

from __future__ import annotations

from sange.adapters.vcs.git._subprocess import (
    GitCommandFailed,
    GitNotInstalled,
)
from sange.adapters.vcs.git.driver import GitDriver, GitRepoNotFound

__all__ = [
    "GitCommandFailed",
    "GitDriver",
    "GitNotInstalled",
    "GitRepoNotFound",
]
