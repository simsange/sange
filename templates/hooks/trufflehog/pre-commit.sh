#!/usr/bin/env bash
# Sange gate: trufflehog pre-commit
#
# Runs `trufflehog git file://. --only-verified --since-commit HEAD`
# against the diff between the staged tree and HEAD. Exits:
#   0   — no verified leaks found.
#   64  — trufflehog not installed.
#   1   — at least one verified leak detected OR trufflehog failed.

set -eu

if ! command -v trufflehog >/dev/null 2>&1; then
    cat >&2 <<EOF
sange/trufflehog: trufflehog not installed; skipping.
  install:  brew install trufflehog
          # or https://github.com/trufflesecurity/trufflehog
EOF
    exit 64
fi

cd "${SANGE_HOOKS_REPO_ROOT:-.}"

# `--only-verified` filters to credentials trufflehog could
# programmatically confirm (live keys). False-positive resistance is
# the priority for a pre-commit gate. Use `sange hooks run --no-abort`
# + a separate periodic scan for the broader "unverified" sweep.
if trufflehog git file://. --only-verified --since-commit HEAD --fail \
        --no-update >/dev/null 2>&1; then
    exit 0
else
    rc=$?
    cat >&2 <<EOF
sange/trufflehog: verified leak(s) detected.
  Re-run manually for the full report:
    trufflehog git file://. --only-verified --since-commit HEAD
  Exit code was $rc.
EOF
    exit 1
fi
