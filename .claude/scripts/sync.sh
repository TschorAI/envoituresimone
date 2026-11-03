#!/usr/bin/env bash
# Copy what git does not hold to a drive, <SYNC_DEST>/<project>: sources/ data/ out/ tasks/ README.md.
# Code and document sources (src/ tools/ .claude/ CLAUDE.md) live in git only. Secrets (.env) never leave.
#   sync.sh            push; refuses above 20 GB
#   sync.sh --confirm  push even above 20 GB (only after the user said yes)
#   sync.sh --check    print a warning if any, no copy. Exit 0 ok, 2 too big, 3 drive not connected
#   sync.sh --pull     fetch sources/ data/ out/ tasks/ from the drive (after a fresh clone)
# After a push, the shared index of all projects (<SYNC_DEST>/INDEX.md) is rebuilt by index.sh.
# Copies never delete anything on the other side.
#
# The drive is the project's own choice, in .claude/sync.conf. Without that file, or without
# SYNC_DEST in it, the project has no drive: every mode does nothing.
#   SYNC_DEST="remote:folder"    an rclone remote and a folder in it, or a local folder
#   SYNC_NAME="SharePoint"       what the messages call the drive (default: Drive)
#   SYNC_FLAGS="--transfers 2"   more rclone flags, for what this drive needs
#   SYNC_FOLDERS="data out"      the folders copied (default: sources data out tasks)
#   SYNC_TITLE="Our projects"    the title of the shared index (index.sh)
# PROJECT_SYNC_DEST in the environment replaces SYNC_DEST.
set -u
MODE="${1:-push}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT" || exit 1
SYNC_DEST=""; SYNC_NAME="Drive"; SYNC_FLAGS=""; SYNC_FOLDERS="sources data out tasks"
# shellcheck disable=SC1091
[ -f .claude/sync.conf ] && . ./.claude/sync.conf
BASE="${PROJECT_SYNC_DEST:-$SYNC_DEST}"
[ -n "$BASE" ] || exit 0
NAME="$(basename "$ROOT")"
DEST="$BASE/$NAME"
STATE=.claude/state; mkdir -p "$STATE"
WARN_KB=$((2 * 1024 * 1024)); LIMIT_KB=$((20 * 1024 * 1024))
read -r -a SYNCED <<< "$SYNC_FOLDERS"
read -r -a EXTRA <<< "$SYNC_FLAGS"
# Filters apply in order: secrets and caches out first, then the synced folders in, then nothing else.
FLAGS=(--update --quiet ${EXTRA[@]+"${EXTRA[@]}"}
       --filter "- *.env" --filter "- .env.*" --filter "- __pycache__/**")
for d in "${SYNCED[@]}"; do FLAGS+=(--filter "+ /$d/**"); done
FLAGS+=(--filter "+ /README.md" --filter "- **")

kb() { local v; v="$(du -sk "$1" 2>/dev/null | awk '{print $1}')"; echo "${v:-0}"; }
SIZE_KB=0; for d in "${SYNCED[@]}"; do SIZE_KB=$(( SIZE_KB + $(kb "$d") )); done
GB="$(LC_ALL=C awk -v k="$SIZE_KB" 'BEGIN{printf "%.1f", k/1048576}')"

connected() {
    command -v rclone >/dev/null 2>&1 || return 1
    [[ "$BASE" =~ ^([A-Za-z0-9_-]{2,}): ]] || return 0          # local folder
    rclone listremotes 2>/dev/null | grep -qx "${BASH_REMATCH[1]}:"
}

if ! connected; then
    echo "$SYNC_NAME sync skipped: rclone remote '${BASE%%:*}' is not connected on this machine."
    exit 3
fi

case "$MODE" in
--check)
    if [ "$SIZE_KB" -gt "$LIMIT_KB" ]; then
        echo "Project $NAME is $GB GB (over 20 GB): $SYNC_NAME sync is paused until you confirm. Ask Claude to sync, or run: bash .claude/scripts/sync.sh --confirm"
        exit 2
    elif [ "$SIZE_KB" -gt "$WARN_KB" ]; then
        echo "Project $NAME is $GB GB (over 2 GB): $SYNC_NAME sync will be slow."
    fi
    exit 0 ;;
--pull)
    rclone copy "$DEST" . "${FLAGS[@]}"
    exit $? ;;
push|--confirm)
    if [ "$SIZE_KB" -gt "$LIMIT_KB" ] && [ "$MODE" != --confirm ]; then
        echo "refused: $NAME is $GB GB (over 20 GB). Needs the user's confirmation, then: sync.sh --confirm" >&2
        exit 2
    fi
    [ "$SIZE_KB" -gt "$WARN_KB" ] && echo "warning: $NAME is $GB GB (over 2 GB)" >&2
    mkdir "$STATE/sync.lock" 2>/dev/null || { echo "a sync is already running" >&2; exit 0; }
    trap 'rmdir "$STATE/sync.lock" 2>/dev/null' EXIT
    rclone copy . "$DEST" "${FLAGS[@]}" || exit $?
    echo "$(date '+%F %H:%M') synced $GB GB to $DEST"
    date '+%F %H:%M' | rclone rcat "$DEST/.last-sync" --quiet
    bash .claude/scripts/index.sh || echo "warning: shared index not rebuilt" >&2
    exit 0 ;;
*)  echo "usage: sync.sh [--check | --confirm | --pull]" >&2; exit 1 ;;
esac
