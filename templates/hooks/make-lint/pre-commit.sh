#!/usr/bin/env bash
# Sange gate: make lint (pre-commit)
#
# Runs `make lint` from the repo root. Exits:
#   0   — `make lint` succeeded.
#   64  — make not installed OR no Makefile / no `lint` target.
#   1   — `make lint` failed.

set -eu

cd "${SANGE_HOOKS_REPO_ROOT:-.}"

if ! command -v make >/dev/null 2>&1; then
    cat >&2 <<EOF
sange/make-lint: make not installed; skipping.
EOF
    exit 64
fi

if [ ! -f Makefile ] && [ ! -f makefile ]; then
    cat >&2 <<EOF
sange/make-lint: no Makefile found in $(pwd); skipping.
EOF
    exit 64
fi

if ! make -n lint >/dev/null 2>&1; then
    cat >&2 <<EOF
sange/make-lint: Makefile has no \`lint\` target; skipping.
  (Either add one, or \`sange hooks remove make-lint\` to drop this gate.)
EOF
    exit 64
fi

if make lint; then
    exit 0
else
    rc=$?
    cat >&2 <<EOF
sange/make-lint: \`make lint\` failed with exit $rc.
EOF
    exit 1
fi
