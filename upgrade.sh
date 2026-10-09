#!/usr/bin/env bash
# =============================================================================
# WV Education News Desk — Upgrade
#
# Safely updates an existing installation WITHOUT touching the MongoDB volume.
# Refuses to overwrite uncommitted/local git work or a diverged branch, and
# always takes a pre-upgrade database backup first.
#
# Run from the install dir (defaults to ~/wvedtalk), or set APP_DIR:
#   ./upgrade.sh
#   APP_DIR=/opt/wvedtalk ./upgrade.sh
# =============================================================================
set -euo pipefail

APP_DIR="${APP_DIR:-$HOME/wvedtalk}"
[ -f docker-compose.yml ] && [ -d .git ] && APP_DIR="$(pwd)"   # allow running in place
TIMESTAMP="$(date '+%Y-%m-%d_%H-%M-%S')"
DB_BACKUP_DIR="$APP_DIR/backups/pre-upgrade-$TIMESTAMP"

log()  { echo "[WVEdTalk] $*"; }
fail() { echo "ERROR: $*" >&2; exit 1; }

[ -d "$APP_DIR/.git" ] || fail "Git repository not found: $APP_DIR (set APP_DIR to your install path)"
cd "$APP_DIR"

command -v docker >/dev/null 2>&1 || fail "Docker is not installed. Run install.sh, or install Docker manually."
docker_cmd() { if docker info >/dev/null 2>&1; then docker "$@"; else sudo docker "$@"; fi; }
docker_cmd compose version >/dev/null 2>&1 || fail "Docker Compose is not available."
[ -f .env ] || fail "No .env in $APP_DIR. Refusing to continue."

echo
echo "=========================================="
echo " WV Education News Desk — Upgrade"
echo "=========================================="
echo
echo "Current revision: $(git rev-parse --short HEAD)"
docker_cmd compose ps

# ---- refuse unsafe git states ----------------------------------------------
if [ -n "$(git status --porcelain)" ]; then
  echo; echo "Local git changes detected:"; git status --short
  fail "Upgrade cancelled. Commit, stash, or discard these changes first."
fi
CURRENT_BRANCH="$(git branch --show-current)"
[ -z "$CURRENT_BRANCH" ] && fail "Repository is in detached HEAD state. Refusing to upgrade automatically."

log "Checking the remote for updates..."
git fetch --prune origin
REMOTE_REF="origin/$CURRENT_BRANCH"
git show-ref --verify --quiet "refs/remotes/$REMOTE_REF" || fail "No matching remote branch '$REMOTE_REF'."

AHEAD="$(git rev-list --count "$REMOTE_REF..HEAD")"
BEHIND="$(git rev-list --count "HEAD..$REMOTE_REF")"
[ "$AHEAD" -gt 0 ] && [ "$BEHIND" -gt 0 ] && fail "Local branch and remote have diverged. Resolve the git history manually."
[ "$AHEAD" -gt 0 ] && fail "Local branch has $AHEAD commit(s) not on the remote. No changes made."
if [ "$BEHIND" -eq 0 ]; then
  log "Already up to date. No rebuild necessary."
  docker_cmd compose ps
  exit 0
fi
echo "Remote has $BEHIND new commit(s)."

# ---- mandatory pre-upgrade DB backup ---------------------------------------
mkdir -p "$DB_BACKUP_DIR"
DB_NAME="$(awk -F= '$1=="DB_NAME"{print substr($0,index($0,"=")+1);exit}' .env | tr -d '"')"
DB_NAME="${DB_NAME:-wvedtalk}"
if docker_cmd compose ps --services --filter "status=running" | grep -q '^mongo$'; then
  log "Creating pre-upgrade MongoDB backup ($DB_NAME)..."
  docker_cmd compose exec -T mongo mongodump --db "$DB_NAME" --archive --gzip > "$DB_BACKUP_DIR/mongodb.archive.gz"
  [ -s "$DB_BACKUP_DIR/mongodb.archive.gz" ] || fail "The database backup is empty. Upgrade cancelled."
  echo "  Backup: $DB_BACKUP_DIR/mongodb.archive.gz"
else
  fail "MongoDB is not running, so a safety backup cannot be taken. Upgrade cancelled."
fi
cp -p .env "$DB_BACKUP_DIR/.env"

# ---- fast-forward + rebuild -------------------------------------------------
log "Pulling latest code..."
git pull --ff-only
log "Rebuilding and recreating containers..."
docker_cmd compose up -d --build
docker_cmd image prune -f >/dev/null 2>&1 || true

HTTP_PORT="$(awk -F= '$1=="HTTP_PORT"{print substr($0,index($0,"=")+1);exit}' .env | tr -d '"')"
HTTP_PORT="${HTTP_PORT:-80}"
log "Waiting for the app at http://localhost:${HTTP_PORT} ..."
for _ in $(seq 1 60); do
  curl -fsS "http://localhost:${HTTP_PORT}/api/schedule/next" >/dev/null 2>&1 && break
  sleep 3
done

echo
echo "=========================================="
echo " Upgrade complete — revision $(git rev-parse --short HEAD)"
echo "=========================================="
docker_cmd compose ps
echo
echo "Restore this pre-upgrade backup if needed:"
echo "  gunzip -c \"$DB_BACKUP_DIR/mongodb.archive.gz\" | docker compose exec -T mongo mongorestore --archive --gzip --drop"
echo "MongoDB data stays in its Docker volume; this script never removes it."
echo
