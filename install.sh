#!/usr/bin/env bash
# =============================================================================
# WV Education News Desk — first-time installer (Docker + docker-compose)
#
# Usage:   ./install.sh
# Re-runnable: yes (idempotent — safe to run again to repair/restart the stack).
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# ---- pretty output ----------------------------------------------------------
c_info() { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
c_ok()   { printf '\033[1;32m✓\033[0m %s\n' "$*"; }
c_warn() { printf '\033[1;33m!\033[0m %s\n' "$*"; }
c_err()  { printf '\033[1;31m✗\033[0m %s\n' "$*" >&2; }

# ---- docker compose shim (v2 `docker compose` or legacy `docker-compose`) ----
DC=""
detect_compose() {
  if docker compose version >/dev/null 2>&1; then
    DC="docker compose"
  elif command -v docker-compose >/dev/null 2>&1; then
    DC="docker-compose"
  else
    c_err "docker compose not found. Install Docker Engine + the compose plugin first:"
    c_err "  https://docs.docker.com/engine/install/ and https://docs.docker.com/compose/install/"
    exit 1
  fi
}

require_docker() {
  if ! command -v docker >/dev/null 2>&1; then
    c_err "docker not found. Install Docker Engine first: https://docs.docker.com/engine/install/"
    exit 1
  fi
  if ! docker info >/dev/null 2>&1; then
    c_err "Docker daemon is not running (or this user lacks permission)."
    c_err "Start Docker, or add your user to the 'docker' group, then re-run."
    exit 1
  fi
  detect_compose
  c_ok "Docker and compose detected ($DC)."
}

# ---- secret generation ------------------------------------------------------
gen_secret() {
  if command -v openssl >/dev/null 2>&1; then
    openssl rand -hex 32
  else
    python3 -c "import secrets; print(secrets.token_hex(32))"
  fi
}

# Set KEY=<generated> in .env only when the current value is empty or a placeholder.
fill_if_blank() {
  local key="$1" val
  val="$(grep -E "^${key}=" .env | head -n1 | cut -d= -f2- || true)"
  val="${val%\"}"; val="${val#\"}"
  if [ -z "$val" ] || echo "$val" | grep -qiE 'replace-with|choose-a|changeme'; then
    local new; new="$(gen_secret)"
    # portable in-place edit (GNU + BSD sed)
    if sed --version >/dev/null 2>&1; then
      sed -i "s|^${key}=.*|${key}=${new}|" .env
    else
      sed -i '' "s|^${key}=.*|${key}=${new}|" .env
    fi
    c_ok "Generated ${key}."
  fi
}

prepare_env() {
  if [ ! -f .env ]; then
    cp .env.example .env
    c_ok "Created .env from .env.example."
  else
    c_info ".env already exists — leaving it untouched."
  fi
  fill_if_blank SESSION_SECRET
  fill_if_blank APP_PASSCODE
}

# ---- health wait ------------------------------------------------------------
HTTP_PORT="$(grep -E '^HTTP_PORT=' .env | head -n1 | cut -d= -f2- | tr -d '"' || true)"
HTTP_PORT="${HTTP_PORT:-80}"

wait_healthy() {
  local url="http://localhost:${HTTP_PORT}/api/schedule/next"
  c_info "Waiting for the app to become healthy at ${url} ..."
  local i
  for i in $(seq 1 60); do
    if curl -fsS "$url" >/dev/null 2>&1; then
      c_ok "App is responding."
      return 0
    fi
    sleep 3
  done
  c_warn "App did not respond within ~3 minutes."
  c_warn "Check logs with:  $DC logs -f backend"
  return 1
}

# ---- run --------------------------------------------------------------------
main() {
  c_info "WV Education News Desk — installer"
  require_docker
  prepare_env

  c_info "Building and starting containers (this can take a few minutes on first run) ..."
  $DC up -d --build

  if wait_healthy; then
    echo
    c_ok "Install complete."
    echo "  Open:            http://localhost:${HTTP_PORT}"
    echo "  Bootstrap login: admin / admin  (change it immediately in Settings → My account)"
    echo
    echo "  Next: open Settings → Integrations to add your AI model key and email (Resend/SMTP)."
    echo "  Logs:            $DC logs -f"
    echo "  Stop:            $DC down"
  else
    exit 1
  fi
}

main "$@"
