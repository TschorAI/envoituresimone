#!/usr/bin/env bash
# Silent autosave, called by the Claude Code hooks in .claude/settings.json.
#   autosave.sh prompt   after each prompt: commit. Every 10th: push + drive sync.
#   autosave.sh end      end of session: commit, push, drive sync.
# Never fails and never prints, except a one-line warning (project size, drive not connected).
# Everything else goes to .claude/state/autosave.log.
set +e
MODE="${1:-prompt}"
[ -t 0 ] || cat >/dev/null 2>&1
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT" || exit 0
STATE=.claude/state; mkdir -p "$STATE"; LOG="$STATE/autosave.log"
git rev-parse --git-dir >/dev/null 2>&1 || exit 0

git add -A >>"$LOG" 2>&1
git diff --cached --quiet || git commit -q -m "auto: $(date '+%F %H:%M')" >>"$LOG" 2>&1

N=$(( $(cat "$STATE/count" 2>/dev/null || echo 0) + 1 )); echo "$N" > "$STATE/count"
[ "$MODE" = end ] || [ $((N % 10)) -eq 0 ] || exit 0

MSG="$(bash .claude/scripts/sync.sh --check 2>>"$LOG")"; RC=$?
(
    git remote get-url origin >/dev/null 2>&1 && git push -q origin HEAD >>"$LOG" 2>&1
    [ "$RC" -eq 0 ] && bash .claude/scripts/sync.sh >>"$LOG" 2>&1
) </dev/null >/dev/null 2>&1 &
disown 2>/dev/null

if [ -n "$MSG" ]; then
    echo "$(date '+%F %H:%M') $MSG" >>"$LOG"
    [ "$MODE" = prompt ] && printf '{"systemMessage":"%s"}\n' "$(printf '%s' "$MSG" | tr -d '"\\')"
fi
exit 0
