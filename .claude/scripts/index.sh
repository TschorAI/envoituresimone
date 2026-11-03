#!/usr/bin/env bash
# Rebuild the shared index of all projects, <SYNC_DEST>/INDEX.md on the drive: one row per project,
# read from the Summary of each project's README.md. Called by sync.sh after every push, so a
# project is listed as soon as it is synced, finished or not. Never edit INDEX.md by hand.
#   index.sh           rebuild and upload
#   index.sh --print   rebuild and print, no upload
# The drive and the title come from .claude/sync.conf (see sync.sh). No drive: does nothing.
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SYNC_DEST=""; SYNC_TITLE="Projects"
# shellcheck disable=SC1091
[ -f "$ROOT/.claude/sync.conf" ] && . "$ROOT/.claude/sync.conf"
BASE="${PROJECT_SYNC_DEST:-$SYNC_DEST}"
[ -n "$BASE" ] || exit 0
FOLDER="${BASE##*[:/]}"; FOLDER="${FOLDER:-.}"
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT

# One call fetches every project's README.md and .last-sync (written by sync.sh).
rclone copy "$BASE" "$TMP/in" --max-depth 2 --include "/*/README.md" --include "/*/.last-sync" --quiet || exit $?

field() { sed -n "s/^- \*\*$2:\*\* *//p" "$1" | head -1 | tr -d '\r' | sed 's/|/\\|/g'; }

{
    echo "# $SYNC_TITLE"
    echo
    echo "Every project on this drive, in \`$FOLDER/<project>/\`. Rebuilt at every sync: do not edit."
    echo
    echo "- **Read-only.** Use what you need, never write in another project's folder."
    echo "- **Pin what you use.** Files change while a project is in progress. Copy what you use into your own project's \`sources/\`."
    echo "- **Status.** \`in progress\`: results may change or be wrong. \`usable\`: results can be relied on. \`closed\`: no further change."
    echo "- Each project's \`README.md\` lists what is where. Results are in \`out/\`, data in \`data/\`. Code is in the repository."
    echo
    echo "| Project | What | Status | Owner | Created | Last sync | Repository |"
    echo "|---|---|---|---|---|---|---|"
    for readme in "$TMP"/in/*/README.md; do
        [ -f "$readme" ] || continue
        dir="$(dirname "$readme")"; name="$(basename "$dir")"
        what="$(field "$readme" What)"; case "$what" in ""|_*) what="_not described yet_" ;; esac
        status="$(field "$readme" Status)"
        owner="$(field "$readme" "Created by")"
        created="$(field "$readme" "Created on")"
        repo="$(field "$readme" Repository)"
        synced="$(head -1 "$dir/.last-sync" 2>/dev/null | tr -d '\r')"
        echo "| \`$name\` | $what | ${status:-not stated} | ${owner:--} | ${created:--} | ${synced:--} | ${repo:--} |"
    done
} > "$TMP/INDEX.md"

if [ "${1:-}" = --print ]; then cat "$TMP/INDEX.md"; exit 0; fi
rclone copyto "$TMP/INDEX.md" "$BASE/INDEX.md" --quiet
