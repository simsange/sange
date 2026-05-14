#!/usr/bin/env bash
# scripts/smoke_v01.sh — v0.1 end-to-end smoke test against a real AI provider.
#
# Drives the full §14.1 happy path:
#   sange init  →  sange commit (real AI)  →  approve  →  push  →  remote verify
#
# Operator-driven only — NEVER run automatically from CI. Real AI calls burn
# real tokens; the cost is small (~one short Claude/GPT/Ollama call per
# invocation) but non-zero. Run by hand before tagging a release.
#
# Usage:
#   export ANTHROPIC_API_KEY=sk-ant-...
#   ./scripts/smoke_v01.sh                       # default: anthropic
#   ./scripts/smoke_v01.sh --provider openai     # uses OPENAI_API_KEY
#   ./scripts/smoke_v01.sh --provider mock       # plumbing-only, no API call
#   ./scripts/smoke_v01.sh --dry-run             # alias for --provider mock
#   ./scripts/smoke_v01.sh --keep                # don't clean up tmp dirs on exit
#
# Exit codes:
#   0  — full happy path completed; remote has the AI-generated commit.
#   1  — generic failure (see stderr for details).
#   2  — pre-flight check failed (missing dep or API key).
#  70  — sange / AI provider error.

set -euo pipefail

# --------------------------------------------------------------------------- #
# Argument parsing
# --------------------------------------------------------------------------- #

PROVIDER="anthropic"
MODEL=""
KEEP_TMP=0

while [[ $# -gt 0 ]]; do
    case "$1" in
        --provider)
            PROVIDER="$2"; shift 2
            ;;
        --provider=*)
            PROVIDER="${1#*=}"; shift
            ;;
        --model)
            MODEL="$2"; shift 2
            ;;
        --model=*)
            MODEL="${1#*=}"; shift
            ;;
        --dry-run)
            PROVIDER="mock"; shift
            ;;
        --keep)
            KEEP_TMP=1; shift
            ;;
        -h|--help)
            sed -n '2,25p' "$0" | sed 's/^# \{0,1\}//'
            exit 0
            ;;
        *)
            echo "error: unknown argument $1" >&2
            exit 2
            ;;
    esac
done

# Default model picks per provider (the operator can override with --model).
if [[ -z "$MODEL" ]]; then
    case "$PROVIDER" in
        anthropic)  MODEL="claude-opus-4-7" ;;
        openai)     MODEL="gpt-4o" ;;
        ollama)     MODEL="llama3" ;;
        mock)       MODEL="mock-1" ;;
        *)          MODEL="" ;;
    esac
fi

# --------------------------------------------------------------------------- #
# Pre-flight checks
# --------------------------------------------------------------------------- #

require_cmd() {
    if ! command -v "$1" >/dev/null 2>&1; then
        echo "error: required command not found: $1" >&2
        exit 2
    fi
}

require_cmd sange
require_cmd git

# Provider-specific API-key precondition.
case "$PROVIDER" in
    anthropic)
        if [[ -z "${ANTHROPIC_API_KEY:-}" ]]; then
            echo "error: ANTHROPIC_API_KEY is not set" >&2
            echo "Set it before running: export ANTHROPIC_API_KEY=sk-ant-..." >&2
            exit 2
        fi
        ;;
    openai)
        if [[ -z "${OPENAI_API_KEY:-}" ]]; then
            echo "error: OPENAI_API_KEY is not set" >&2
            exit 2
        fi
        ;;
    ollama)
        # Ollama runs locally; expect the daemon to be reachable.
        if ! curl -sS --max-time 2 http://localhost:11434/api/tags >/dev/null 2>&1; then
            echo "error: Ollama daemon not reachable at localhost:11434" >&2
            exit 2
        fi
        ;;
    mock)
        : # no precondition
        ;;
    *)
        echo "error: unknown provider $PROVIDER" >&2
        exit 2
        ;;
esac

# --------------------------------------------------------------------------- #
# Tmp workspace setup + teardown
# --------------------------------------------------------------------------- #

WORK="$(mktemp -d)"
REPO="$WORK/repo"
REMOTE="$WORK/remote.git"

cleanup() {
    if [[ "$KEEP_TMP" -eq 1 ]]; then
        echo "----"
        echo "kept tmp workspace: $WORK"
    else
        rm -rf "$WORK"
    fi
}
trap cleanup EXIT

echo "smoke test config:"
echo "  provider:  $PROVIDER"
echo "  model:     $MODEL"
echo "  workspace: $WORK"
echo ""

# --------------------------------------------------------------------------- #
# Step 1 — initialize the working repo
# --------------------------------------------------------------------------- #

echo "[1/8] git init + initial commit"
git init --bare -q -b main "$REMOTE"
mkdir -p "$REPO"
cd "$REPO"
git init -q -b main
git config user.email "smoke@sange.test"
git config user.name "Smoke Tester"
echo "# Smoke test repo" > README.md
git add README.md
git commit -q -m "initial"
git remote add origin "$REMOTE"
git push -q origin main

# --------------------------------------------------------------------------- #
# Step 2 — sange init
# --------------------------------------------------------------------------- #

echo "[2/8] sange init"
sange init --repo "$REPO" >/dev/null

if [[ ! -d "$REPO/.sange/commits" ]]; then
    echo "error: sange init did not create .sange/commits/" >&2
    exit 1
fi
if [[ ! -f "$REPO/.gitignore" ]] || ! grep -q "/Makefile" "$REPO/.gitignore"; then
    echo "error: sange init did not update .gitignore" >&2
    exit 1
fi

# --------------------------------------------------------------------------- #
# Step 3 — stage a real change
# --------------------------------------------------------------------------- #

echo "[3/8] stage a change"
cat > "$REPO/src/passkey.py" <<'EOF'
"""WebAuthn-backed passkey authentication helpers."""

from __future__ import annotations


def register_passkey(user_id: str, credential: bytes) -> str:
    """Persist a passkey credential for `user_id`. Returns the credential id."""
    raise NotImplementedError("stub for smoke test")


def verify_assertion(user_id: str, assertion: bytes) -> bool:
    """Verify a WebAuthn assertion. Returns True on success."""
    raise NotImplementedError("stub for smoke test")
EOF
mkdir -p "$REPO/src"
mv "$REPO/src/passkey.py" "$REPO/src/passkey.py"  # idempotent — mkdir came after
cd "$REPO"
git add src/passkey.py

# --------------------------------------------------------------------------- #
# Step 4 — sange commit (the real AI call)
# --------------------------------------------------------------------------- #

echo "[4/8] sange commit (provider=$PROVIDER)"
DIFF="$(git diff --staged)"
echo "$DIFF" | sange commit \
    --repo "$REPO" \
    --provider "$PROVIDER" \
    --model "$MODEL" \
    --no-telemetry

DRAFT="$(find "$REPO/.sange/commits" -name '0001-*.json' -print -quit)"
if [[ -z "$DRAFT" ]]; then
    echo "error: sange commit did not write a DRAFT row" >&2
    exit 70
fi
echo "  wrote: $(basename "$DRAFT")"

# --------------------------------------------------------------------------- #
# Step 5 — sange commits list
# --------------------------------------------------------------------------- #

echo "[5/8] sange commits list"
sange commits list --repo "$REPO" | head -5

# --------------------------------------------------------------------------- #
# Step 6 — sange commits approve 1
# --------------------------------------------------------------------------- #

echo "[6/8] sange commits approve 1"
sange commits approve 1 --repo "$REPO" --actor "smoke-test" >/dev/null

# --------------------------------------------------------------------------- #
# Step 7 — sange commits push 1
# --------------------------------------------------------------------------- #

echo "[7/8] sange commits push 1"
sange commits push 1 --repo "$REPO" --remote origin >/dev/null

# --------------------------------------------------------------------------- #
# Step 8 — verify the remote received the commit
# --------------------------------------------------------------------------- #

echo "[8/8] verify remote"
REMOTE_LOG="$(git --git-dir="$REMOTE" log --oneline -2 2>&1)"
echo "$REMOTE_LOG"

if ! echo "$REMOTE_LOG" | grep -qE '^[a-f0-9]{7,} '; then
    echo "error: remote log doesn't show the new commit" >&2
    exit 1
fi

LATEST_SUBJECT="$(echo "$REMOTE_LOG" | head -1 | cut -d' ' -f2-)"
echo ""
echo "----"
echo "smoke test SUCCESS"
echo "remote latest commit: $LATEST_SUBJECT"
echo "provider: $PROVIDER  model: $MODEL"
