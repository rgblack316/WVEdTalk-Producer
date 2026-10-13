#!/usr/bin/env bash
# =============================================================================
# WV Education News Desk — one-click updater (HOST-side watcher)
#
# Runs on the HOST (NOT inside a container — a container can't rebuild its own
# stack). Watches control/upgrade.request (written by the app's "Apply update"
# button), runs ./upgrade.sh when one appears, and writes control/upgrade.status
# back for the UI to poll. Heartbeats control/watcher.alive each tick so the app
# can show whether this service is running.
#
# install.sh installs this as the systemd service `wvedtalk-updater`. Run it
# manually with:  ./upgrade-watch.sh           (loop, default 15s)
#                 ./upgrade-watch.sh --once     (single pass, for cron)
# =============================================================================
set -uo pipefail

APP_DIR="${APP_DIR:-$HOME/wvedtalk}"
[ -f "$(pwd)/docker-compose.yml" ] && [ -d "$(pwd)/.git" ] && APP_DIR="$(pwd)"
CONTROL_DIR="$APP_DIR/control"
REQ="$CONTROL_DIR/upgrade.request"
STATUS="$CONTROL_DIR/upgrade.status"
HEARTBEAT="$CONTROL_DIR/watcher.alive"
LOG="$CONTROL_DIR/upgrade.log"
INTERVAL="${WATCH_INTERVAL:-15}"

mkdir -p "$CONTROL_DIR"
iso() { date -u '+%Y-%m-%dT%H:%M:%S+00:00'; }

run_once() {
  [ -f "$REQ" ] || return 0
  local before after
  before="$(cd "$APP_DIR" 2>/dev/null && git rev-parse --short HEAD 2>/dev/null || echo unknown)"
  printf '{"state":"running","message":"Applying update…","started_at":"%s","revision_before":"%s"}\n' \
    "$(iso)" "$before" > "$STATUS"
  if (cd "$APP_DIR" && ./upgrade.sh) > "$LOG" 2>&1; then
    after="$(cd "$APP_DIR" 2>/dev/null && git rev-parse --short HEAD 2>/dev/null || echo unknown)"
    printf '{"state":"success","message":"Update complete.","finished_at":"%s","revision_before":"%s","revision_after":"%s"}\n' \
      "$(iso)" "$before" "$after" > "$STATUS"
  else
    printf '{"state":"failed","message":"Upgrade failed — see control/upgrade.log on the server.","finished_at":"%s","revision_before":"%s"}\n' \
      "$(iso)" "$before" > "$STATUS"
  fi
  rm -f "$REQ"
}

if [ "${1:-}" = "--once" ]; then
  iso > "$HEARTBEAT"
  run_once
  exit 0
fi

echo "[WVEdTalk updater] watching $CONTROL_DIR every ${INTERVAL}s"
while true; do
  iso > "$HEARTBEAT"
  run_once
  sleep "$INTERVAL"
done
