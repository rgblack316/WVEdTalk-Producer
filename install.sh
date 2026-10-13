#!/usr/bin/env bash
# =============================================================================
# WV Education News Desk — Initial Installation (Docker + Compose)
#
# Fresh Ubuntu/Debian helper. Installs Docker Engine + Compose if missing,
# clones the repository (or runs in place if you already cloned it), creates
# .env, generates the session secret, and starts the Docker Compose stack.
#
# Run as your NORMAL user (not root); it uses sudo only where needed:
#   ./install.sh
# Override defaults with env vars:
#   REPO_URL=... INSTALL_DIR=/opt/wvedtalk ./install.sh
# =============================================================================
set -euo pipefail

REPO_URL="${REPO_URL:-https://github.com/rgblack316/WVEdTalk-Producer.git}"
INSTALL_DIR="${INSTALL_DIR:-}"

log()  { echo "[WVEdTalk] $*"; }
fail() { echo "ERROR: $*" >&2; exit 1; }

# ---- resolve the real (non-root) user even when run via sudo ----------------
if [ "${EUID}" -eq 0 ]; then
  TARGET_USER="${SUDO_USER:-root}"
  TARGET_HOME="$(getent passwd "$TARGET_USER" | cut -d: -f6)"
else
  TARGET_USER="$(id -un)"
  TARGET_HOME="$HOME"
fi
[ "$TARGET_USER" = "root" ] && fail "Run this as your normal user, not root. It uses sudo when needed."

command -v sudo >/dev/null 2>&1 || fail "sudo is required. Install it: apt-get update && apt-get install -y sudo"
sudo -v

# ---- are we already inside a checkout? --------------------------------------
if [ -f docker-compose.yml ] && { [ -f env.example ] || [ -f .env ]; }; then
  INSTALL_DIR="$(pwd)"
  IN_PLACE=1
  log "Running inside an existing checkout: $INSTALL_DIR"
else
  IN_PLACE=0
  [ -z "$INSTALL_DIR" ] && INSTALL_DIR="$TARGET_HOME/wvedtalk"
fi

# ---- OS gate (auto Docker install is apt/Ubuntu/Debian only) ----------------
command -v apt-get >/dev/null 2>&1 || fail "Auto-install supports Ubuntu/Debian (apt). On other systems install Docker manually, then re-run."
[ -r /etc/os-release ] && . /etc/os-release || fail "Cannot determine the operating system."
case "${ID:-}" in
  ubuntu|debian) ;;
  *) fail "Unsupported OS: ${PRETTY_NAME:-unknown}. Supports Ubuntu/Debian. Install Docker manually, then re-run." ;;
esac

echo
echo "=========================================="
echo " WV Education News Desk — Installation"
echo "=========================================="
echo
log "Installing/checking host packages..."
sudo apt-get update
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y ca-certificates curl git openssl gnupg

install_docker_repo() {
  local arch codename
  arch="$(dpkg --print-architecture)"
  codename="${VERSION_CODENAME:-$(lsb_release -cs 2>/dev/null || echo stable)}"
  sudo install -m 0755 -d /etc/apt/keyrings
  sudo rm -f /etc/apt/keyrings/docker.asc
  sudo curl -fsSL "https://download.docker.com/linux/${ID}/gpg" -o /etc/apt/keyrings/docker.asc
  sudo chmod a+r /etc/apt/keyrings/docker.asc
  echo "deb [arch=${arch} signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/${ID} ${codename} stable" \
    | sudo tee /etc/apt/sources.list.d/docker.list >/dev/null
  sudo apt-get update
}

# ---- Docker Engine + Compose ------------------------------------------------
if ! command -v docker >/dev/null 2>&1; then
  log "Docker not found. Installing Docker Engine + Compose..."
  install_docker_repo
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y \
    docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
else
  log "Docker already installed: $(docker --version)"
  if ! docker compose version >/dev/null 2>&1; then
    log "Compose plugin missing. Installing it..."
    sudo apt-get install -y docker-compose-plugin >/dev/null 2>&1 || { install_docker_repo; sudo apt-get install -y docker-compose-plugin; }
  fi
fi

sudo systemctl enable --now docker
getent group docker >/dev/null 2>&1 || sudo groupadd docker
sudo usermod -aG docker "$TARGET_USER" || true

# The current shell may not have the docker group yet — fall back to sudo.
docker_cmd() { if docker info >/dev/null 2>&1; then docker "$@"; else sudo docker "$@"; fi; }
docker_cmd compose version >/dev/null 2>&1 || fail "Docker Compose is still unavailable after installation."

# ---- clone (unless running in place) ----------------------------------------
if [ "$IN_PLACE" -eq 0 ]; then
  if [ -e "$INSTALL_DIR" ]; then
    [ -d "$INSTALL_DIR/.git" ] && fail "A checkout already exists at $INSTALL_DIR. Use ./upgrade.sh instead."
    fail "Install path exists and is not a git repo: $INSTALL_DIR"
  fi
  log "Cloning into $INSTALL_DIR ..."
  git clone "$REPO_URL" "$INSTALL_DIR"
fi
cd "$INSTALL_DIR"

# ---- .env -------------------------------------------------------------------
if [ ! -f .env ]; then
  [ -f env.example ] || fail "env.example template not found — re-clone the repository."
  cp env.example .env
  SESSION_SECRET="$(openssl rand -hex 32)"
  sed -i "s|^SESSION_SECRET=.*|SESSION_SECRET=${SESSION_SECRET}|" .env
  log ".env created with a generated SESSION_SECRET."
  log "APP_PASSCODE was left blank (optional — only needed for programmatic X-Desk-Passcode access)."
else
  log ".env already exists — leaving it unchanged."
fi

mkdir -p backups
[ "${EUID}" -eq 0 ] && chown -R "$TARGET_USER":"$TARGET_USER" "$INSTALL_DIR" || true

# ---- build + start ----------------------------------------------------------
log "Building and starting the stack (first run can take a few minutes)..."
docker_cmd compose up -d --build

HTTP_PORT="$(awk -F= '$1=="HTTP_PORT"{print substr($0,index($0,"=")+1);exit}' .env | tr -d '"')"
HTTP_PORT="${HTTP_PORT:-80}"
log "Waiting for the app at http://localhost:${HTTP_PORT} ..."
healthy=0
for _ in $(seq 1 60); do
  if curl -fsS "http://localhost:${HTTP_PORT}/api/" >/dev/null 2>&1; then healthy=1; break; fi
  sleep 3
done

echo
echo "=========================================="
echo " Installation complete"
echo "=========================================="
echo
docker_cmd compose ps
echo
if [ "$healthy" -eq 1 ]; then
  echo "WV Education News Desk is available at:  http://localhost:${HTTP_PORT}"
else
  echo "Stack started but did not answer yet. Check logs:  docker compose logs -f backend"
fi
echo "First run: open the site and complete the on-screen setup to create your admin account"
echo "(or import an existing backup). Then add your AI + email keys in Settings → Integrations."
echo
echo "NOTE: user '$TARGET_USER' was added to the 'docker' group — log out/in to use docker without sudo."
echo
