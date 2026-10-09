#!/usr/bin/env bash
# =============================================================================
# WV Education News Desk — upgrade / update (Docker + docker-compose)
#
# Usage:   ./upgrade.sh [--pull] [--no-backup]
#            --pull       git pull the latest code before rebuilding
#            --no-backup  skip the pre-upgrade MongoDB dump (not recommended)
# Re-runnable: yes.
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

c_info() { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
c_ok()   { printf '\033[1;32m✓\033[0m %s\n' "$*"; }
c_warn() { printf '\033[1;33m!\033[0m %s\n' "$*"; }
c_err()  { printf '\033[1;31m✗\033[0m %s\n' "$*" >&2; }

DO_PULL=0
DO_BACKUP=1
for arg in "$@"; do
  case "$arg" in
    --pull) DO_PULL=1 ;;
    --no-backup) DO_BACKUP=0 ;;
    *) c_err "Unknown option: $arg"; exit 2 ;;
  esac
done

DC=""
detect_compose() {
  if docker compose version >/dev/null 2>&1; then
    DC="docker compose"
  elif command -v docker-compose >/dev/null 2>&1; then
    DC="docker-compose"
  else
    c_err "docker compose not found. Install it first."
    exit 1
  fi
}

require_docker() {
  command -v docker >/dev/null 2>&1 || { c_err "docker not found."; exit 1; }
  docker info >/dev/null 2>&1 || { c_err "Docker daemon not running."; exit 1; }
  detect_compose
  [ -f .env ] || c_warn ".env not found — the stack may not start. Run ./install.sh first."
}

HTTP_PORT="$(grep -E '^HTTP_PORT=' .env 2>/dev/null | head -n1 | cut -d= -f2- | tr -d '"' || true)"
HTTP_PORT="${HTTP_PORT:-80}"
DB_NAME="$(grep -E '^DB_NAME=' .env 2>/dev/null | head -n1 | cut -d= -f2- | tr -d '"' || true)"
DB_NAME="${DB_NAME:-wvedtalk}"

backup_mongo() {
  [ "$DO_BACKUP" -eq 1 ] || { c_warn "Skipping pre-upgrade backup (--no-backup)."; return 0; }
  local ts dir
  ts="$(date +%Y%m%d-%H%M%S)"
  dir="backups/${ts}"
  mkdir -p "$dir"
  if ! $DC ps --status running 2>/dev/null | grep -q mongo; then
    c_warn "Mongo container is not running yet — skipping backup (nothing to dump)."
    return 0
  fi
  c_info "Backing up MongoDB '${DB_NAME}' to ${dir} ..."
  # Dump inside the container, then copy the archive out to the host.
  if $DC exec -T mongo sh -c "mongodump --db='${DB_NAME}' --archive=/tmp/wvedtalk.dump --gzip" >/dev/null 2>&1; then
    local cid
    cid="$($DC ps -q mongo)"
    docker cp "${cid}:/tmp/wvedtalk.dump" "${dir}/wvedtalk.dump.gz"
    $DC exec -T mongo rm -f /tmp/wvedtalk.dump >/dev/null 2>&1 || true
    c_ok "Backup written: ${dir}/wvedtalk.dump.gz  (restore with: mongorestore --gzip --archive=... --drop)"
  else
    c_warn "mongodump failed — continuing without a fresh backup. Review before proceeding if this matters."
  fi
}

wait_healthy() {
  local url="http://localhost:${HTTP_PORT}/api/schedule/next"
  c_info "Waiting for the app to become healthy at ${url} ..."
  local i
  for i in $(seq 1 60); do
    curl -fsS "$url" >/dev/null 2>&1 && { c_ok "App is responding."; return 0; }
    sleep 3
  done
  c_warn "App did not respond within ~3 minutes. Check:  $DC logs -f backend"
  return 1
}

main() {
  c_info "WV Education News Desk — upgrade"
  require_docker

  if [ "$DO_PULL" -eq 1 ]; then
    if command -v git >/dev/null 2>&1 && [ -d .git ]; then
      c_info "Pulling latest code (git pull) ..."
      git pull --ff-only
    else
      c_warn "--pull requested but this is not a git checkout; skipping."
    fi
  fi

  backup_mongo

  c_info "Rebuilding and recreating containers ..."
  $DC up -d --build

  c_info "Pruning old/dangling images ..."
  docker image prune -f >/dev/null 2>&1 || true

  if wait_healthy; then
    echo
    c_ok "Upgrade complete."
    echo "  Open: http://localhost:${HTTP_PORT}"
    echo "  Rollback: restore the latest backups/<ts>/wvedtalk.dump.gz and 'git checkout <previous-tag>', then re-run ./upgrade.sh"
  else
    c_err "Upgrade finished but the app is not healthy. Inspect logs and consider rolling back."
    exit 1
  fi
}

main "$@"
