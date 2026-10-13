"""One-click self-update coordination (self-hosted Docker edition).

A container cannot rebuild its own compose stack from the inside — recreating the backend
container would kill the very process running the build. So the flow is decoupled:

  UI (admin) -> POST /api/self-update -> this module drops an `upgrade.request` file into a
  bind-mounted control dir -> a HOST-side watcher (`upgrade-watch.sh`, installed by install.sh)
  sees the request, runs `./upgrade.sh`, and writes progress back to `upgrade.status`, which the
  UI polls via GET /api/self-update/status.

The watcher also touches `watcher.alive` every tick so the backend can tell the UI whether the
updater service is actually running (otherwise a click would silently do nothing).
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path

CONTROL_DIR = Path(os.environ.get("CONTROL_DIR", "/app/control"))
REQUEST_FILE = CONTROL_DIR / "upgrade.request"
STATUS_FILE = CONTROL_DIR / "upgrade.status"
HEARTBEAT_FILE = CONTROL_DIR / "watcher.alive"

_HEARTBEAT_MAX_AGE = 120  # seconds — watcher heartbeats far more often than this


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def available() -> bool:
    """True when the control volume exists and is writable (i.e. self-hosted + mounted)."""
    try:
        CONTROL_DIR.mkdir(parents=True, exist_ok=True)
        probe = CONTROL_DIR / ".write-probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        return True
    except OSError:
        return False


def _read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def watcher_alive() -> bool:
    try:
        age = datetime.now(timezone.utc).timestamp() - HEARTBEAT_FILE.stat().st_mtime
        return age < _HEARTBEAT_MAX_AGE
    except OSError:
        return False


def status() -> dict:
    data = _read_json(STATUS_FILE) or {"state": "idle"}
    data["pending"] = REQUEST_FILE.exists()
    data["available"] = available()
    data["watcher_alive"] = watcher_alive()
    return data


def request_upgrade(by: str) -> dict:
    """Queue an upgrade. Idempotent — returns already=True if one is pending/running."""
    if not available():
        raise RuntimeError("The control volume isn't mounted, so one-click update is unavailable.")
    current = status()
    if current.get("pending") or current.get("state") in {"queued", "running"}:
        return {"queued": False, "already": True, **current}
    requested_at = _now_iso()
    REQUEST_FILE.write_text(
        json.dumps({"requested_at": requested_at, "requested_by": by}), encoding="utf-8"
    )
    STATUS_FILE.write_text(
        json.dumps(
            {
                "state": "queued",
                "message": "Update requested — the updater will apply it shortly.",
                "requested_at": requested_at,
                "requested_by": by,
            }
        ),
        encoding="utf-8",
    )
    return {"queued": True, "already": False, **status()}
