#!/usr/bin/env bash
# Sange gate: make test (pre-push)
#
# Runs `make test` from the repo root. Exits:
#   0   — `make test` succeeded.
#   64  — make not installed OR no `Makefile` / no `test` target.
#   1   — `make test` failed.

set -eu

cd "${SANGE_HOOKS_REPO_ROOT:-.}"

if ! command -v make >/dev/null 2>&1; then
    cat >&2 <<EOF
sange/make-test: make not installed; skipping.
EOF
    exit 64
fi

if [ ! -f Makefile ] && [ ! -f makefile ]; then
    cat >&2 <<EOF
sange/make-test: no Makefile found in $(pwd); skipping.
EOF
    exit 64
fi

# Check the `test` target exists. `make -n` is dry-run; the
# "No rule to make target" message goes to stderr with exit 2.
if ! make -n test >/dev/null 2>&1; then
    cat >&2 <<EOF
sange/make-test: Makefile has no \`test\` target; skipping.
  (Either add one, or \`sange hooks remove make-test\` to drop this gate.)
EOF
    exit 64
fi

# Real run.
if make test; then
    exit 0
else
    rc=$?
    cat >&2 <<EOF
sange/make-test: \`make test\` failed with exit $rc.
EOF
    exit 1
fi
