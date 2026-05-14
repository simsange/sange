"""Sange core — the Application + Domain layers per §6.2.

Sub-packages:

  * `config`     — `SangeConfig` Pydantic v2 model + loader (§6.3).
  * `models`     — domain entities (Repo, Commit, Branch, …) [Phase 0b+].
  * `lifecycle`  — commit-message lifecycle state machine [Phase 0b+].
  * `enhancer`   — prompt enhancer (§6.7.1) [Phase 0b+].
  * `scheduler`  — local cron-equivalent [Phase 1+].
  * `audit`      — hash-chained audit JSONL writer (§7.0.7) [Phase 0b+].
  * `policy`     — hooks, secret scanning, large-file warner [Phase 1+].
  * `purge`      — history-purge subsystem (§6.11) [Phase 1-3].
  * `ui`         — TerminalProfile + tree/progress/gate primitives [Phase 1+].
  * `scanners`   — gitleaks + trufflehog wrappers [Phase 1+].

The package is import-safe even before sub-packages exist; downstream code
imports the specific sub-package it needs.
"""

from __future__ import annotations

__all__: list[str] = []
