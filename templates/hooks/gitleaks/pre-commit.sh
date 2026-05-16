#!/usr/bin/env bash
# Sange gate: gitleaks pre-commit
#
# Runs `gitleaks protect --staged` against the staged diff. Exits:
#   0   — no leaks found.
#   64  — gitleaks not installed (Sange's SKIPPED convention).
#   1   — at least one leak found OR gitleaks failed.
#
# The hook runs from `$SANGE_HOOKS_REPO_ROOT` (set by HookEngine).

set -eu

if ! command -v gitleaks >/dev/null 2>&1; then
    cat >&2 <<EOF
sange/gitleaks: gitleaks not installed; skipping.
  install:  brew install gitleaks  # or https://gitleaks.io/
EOF
    exit 64
fi

cd "${SANGE_HOOKS_REPO_ROOT:-.}"

# `gitleaks protect --staged` scans only what's staged for the next
# commit. --redact replaces matched secret values in the output so
# even the hook's stderr can't leak the credential.
if gitleaks protect --staged --redact --no-banner; then
    exit 0
else
    rc=$?
    cat >&2 <<EOF
sange/gitleaks: leak(s) detected in the staged diff.
  Unstage the offending file(s) + remove the secret(s) before retrying.
  Exit code was $rc.
EOF
    exit 1
fi
