#!/usr/bin/env bash
# Installs (or removes, with --remove) the hourly cron job that runs tools/fetch_prices.py at
# minute 7 of every hour. Safe to rerun: replaces its own line only.
# Reads: the user's crontab. Writes: the user's crontab; the job appends to data/prices/fetch.log.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
UV="$(command -v uv)"
TAG="# envoituresimone hourly prices"
LINE="7 * * * * cd '$ROOT' && '$UV' run --quiet python tools/fetch_prices.py >> '$ROOT/data/prices/fetch.log' 2>&1  $TAG"
current="$(crontab -l 2>/dev/null | grep -vF "$TAG" || true)"
if [ "${1:-}" = "--remove" ]; then
    printf '%s\n' "$current" | crontab -; echo "removed"
else
    printf '%s\n%s\n' "$current" "$LINE" | sed '/^$/d' | crontab -; echo "installed:"; crontab -l | grep -F "$TAG"
fi
