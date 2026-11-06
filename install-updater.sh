#!/usr/bin/env bash
# =============================================================================
# WV Education News Desk — install / repair the one-click updater service
#
# Makes sure the host-side watcher (upgrade-watch.sh) runs as the systemd service
# `wvedtalk-updater`, which is what the dashboard's "Download & apply update" button talks to.
# Safe to run any number of times. Called by install.sh and upgrade.sh; you can also run it by hand:
#   ./install-updater.sh
# =============================================================================
set -uo pipefail

INSTALL_DIR="${INSTALL_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}"
TARGET_USER="${TARGET_USER:-$(id -un)}"
UNIT="/etc/systemd/system/wvedtalk-updater.service"
log() { echo "[WVEdTalk] $*"; }

if ! command -v systemctl >/dev/null 2>&1; then
  log "systemd not found — to enable one-click updates run ./upgrade-watch.sh on the host (cron/tmux)."
  exit 0
fi

chmod +x "$INSTALL_DIR/upgrade.sh" "$INSTALL_DIR/upgrade-watch.sh" 2>/dev/null || true
mkdir -p "$INSTALL_DIR/control" 2>/dev/null || true

if systemctl is-active --quiet wvedtalk-updater.service 2>/dev/null; then
  log "One-click updater service is running."
  exit 0
fi

# Needs root. Don't hang waiting for a password when nobody is at a terminal (e.g. run by the watcher).
SUDO=""
if [ "$(id -u)" -ne 0 ]; then
  SUDO="sudo"
  if ! sudo -n true 2>/dev/null && [ ! -t 0 ]; then
    log "The one-click updater service isn't running, and this session can't use sudo."
    log "Run ./install-updater.sh from a terminal to set it up."
    exit 0
  fi
fi

# The app (in Docker, as root) and the watcher (as $TARGET_USER) both write into control/.
if [ ! -w "$INSTALL_DIR/control" ]; then
  $SUDO chown "$TARGET_USER":"$(id -gn "$TARGET_USER" 2>/dev/null || echo "$TARGET_USER")" "$INSTALL_DIR/control" || true
fi

log "Installing the one-click updater service (wvedtalk-updater) for user $TARGET_USER..."
$SUDO tee "$UNIT" >/dev/null <<UNITEOF
[Unit]
Description=WV Education News Desk one-click updater
After=docker.service
Requires=docker.service

[Service]
Type=simple
User=$TARGET_USER
WorkingDirectory=$INSTALL_DIR
ExecStart=/usr/bin/env bash $INSTALL_DIR/upgrade-watch.sh
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
UNITEOF
$SUDO systemctl daemon-reload
if $SUDO systemctl enable --now wvedtalk-updater.service; then
  log "Updater service started. The dashboard's Update button will now work."
else
  log "Could not start wvedtalk-updater — check: sudo systemctl status wvedtalk-updater"
fi
exit 0
