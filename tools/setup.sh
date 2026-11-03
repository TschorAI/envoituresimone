#!/usr/bin/env bash
# Sets the project up on a new machine, then checks it works. Safe to run again.
#
#   bash tools/setup.sh            all steps
#   bash tools/setup.sh --no-pull  skip the drive download (files already here)
#
# 1. tools: git, gh (signed in), uv, rclone
# 2. drive: sources/ data/ out/ tasks/   (bash .claude/scripts/sync.sh --pull)
# 3. python: uv sync
# 4. .env: the variables in ENV_VARS. If any is missing, writes the empty names and stops.
# 5. check: runs CHECK, if set.
#
# Reads: .env, the network (GitHub, the drive, whatever CHECK reads). Writes: .venv/, sources/
# data/ out/ tasks/, .env (empty variable names only, never values), whatever CHECK writes.

# ---- the project's settings: edit these two lines (and list them in PROJECT.md, sections 2 and 8)
ENV_VARS="ORS_API_KEY"   # space-separated names the project needs in .env, e.g. "PREDICTION_DB_HOSTNAME PREDICTION_DB_PORT"
CHECK="uv run pytest -q"      # one short command that fails if a result changes, e.g. "uv run python src/check.py"
# ----

set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
PULL=1; [ "${1:-}" = "--no-pull" ] && PULL=0
ok()   { printf '  ok    %s\n' "$1"; }
fail() { printf '  FAIL  %s\n' "$1"; exit 1; }

echo "1. tools"
for t in git gh uv rclone; do command -v "$t" >/dev/null && ok "$t" || fail "$t is not installed"; done
gh auth status >/dev/null 2>&1 && ok "gh signed in" || fail "gh is not signed in: run gh auth login"
gh auth setup-git >/dev/null 2>&1 && ok "git uses the GitHub sign-in" || fail "gh auth setup-git failed"

echo "2. drive files"
if [ "$PULL" = 1 ]; then
    bash .claude/scripts/sync.sh --pull >/dev/null 2>&1 && ok "sources/ data/ out/ tasks/ pulled" \
        || fail "sync.sh --pull failed: is the drive connected? (rclone config)"
else
    ok "skipped (--no-pull)"
fi

echo "3. python"
uv sync -q 2>/dev/null && ok "python env installed" \
    || fail "uv sync failed: check access to the repositories in pyproject.toml"

echo "4. .env"
if [ -z "$ENV_VARS" ]; then
    ok "no variables needed"
else
    touch .env; chmod 600 .env
    MISSING=""
    for v in $ENV_VARS; do
        grep -qE "^${v}=.+" .env || MISSING="$MISSING $v"
        grep -qE "^${v}=" .env || echo "${v}=" >> .env
    done
    [ -z "$MISSING" ] && ok "the $(echo $ENV_VARS | wc -w) variables are filled" \
        || fail "fill these in .env (values from the password vault):$MISSING"
fi

echo "5. check"
if [ -z "$CHECK" ]; then
    ok "no check set"
else
    OUT="$(MPLBACKEND=Agg bash -c "$CHECK" 2>&1)" && ok "the project check passed" || { echo "$OUT" | tail -5; fail "the check failed: $CHECK"; }
fi

echo "ready"
