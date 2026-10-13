"""App version + 'update available' check for the self-hosted edition.

`current_version()` reads the repo's VERSION file (baked into the image). The update check
fetches the same file from the GitHub default branch and compares — so an operator signals a
release simply by bumping VERSION. Result is cached in-process to avoid hammering GitHub.
"""

import os
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

# lib/version.py -> parent.parent resolves to the backend root both in-pod (/app/backend)
# and in Docker (WORKDIR /app), where VERSION sits next to the copied source.
_VERSION_FILE = Path(__file__).resolve().parent.parent / "VERSION"

_REPO = os.environ.get("GITHUB_REPO", "rgblack316/WVEdTalk-Producer").strip("/")
_BRANCH = os.environ.get("UPDATE_BRANCH", "main")
_RAW_URL = f"https://raw.githubusercontent.com/{_REPO}/{_BRANCH}/backend/VERSION"

_TTL_SECONDS = 3600
_cache: dict = {"at": 0.0, "data": None}


def current_version() -> str:
    try:
        return _VERSION_FILE.read_text(encoding="utf-8").strip() or "unknown"
    except OSError:
        return "unknown"


def _parse(v: str):
    """Dotted-integer version to a tuple, or None if it isn't purely numeric."""
    parts = []
    for p in v.split("."):
        p = p.strip()
        if not p.isdigit():
            return None
        parts.append(int(p))
    return tuple(parts) or None


def _is_newer(latest: str, current: str) -> bool:
    lp, cp = _parse(latest), _parse(current)
    if lp is not None and cp is not None:
        return lp > cp
    # Non-numeric scheme: any difference counts as an available update.
    return latest != current


async def check_update(force: bool = False) -> dict:
    now = time.time()
    cached = _cache["data"]
    if not force and cached is not None and now - _cache["at"] < _TTL_SECONDS:
        return cached

    current = current_version()
    latest = None
    error = None
    try:
        async with httpx.AsyncClient(timeout=6.0, follow_redirects=True) as http:
            resp = await http.get(_RAW_URL, headers={"Accept": "text/plain"})
        if resp.status_code == 200:
            latest = resp.text.strip() or None
        else:
            error = f"update server returned {resp.status_code}"
    except Exception:
        error = "could not reach the update server"

    update_available = bool(latest and current != "unknown" and _is_newer(latest, current))
    data = {
        "current": current,
        "latest": latest,
        "update_available": update_available,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "error": error,
    }
    _cache["data"] = data
    _cache["at"] = now
    return data
