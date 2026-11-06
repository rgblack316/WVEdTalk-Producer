"""App version + 'update available' check for the self-hosted edition.

`current_version()` reads the repo's VERSION file (baked into the image). The update check
fetches the same file from the GitHub default branch and compares — so an operator signals a
release simply by bumping VERSION. Result is cached in-process to avoid hammering GitHub.
"""

import os
import re
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


def current_commit() -> str:
    """Git commit this image was built from (APP_COMMIT, set at build time); 'unknown' if not baked in."""
    v = os.environ.get("APP_COMMIT", "").strip()
    return v if re.fullmatch(r"[0-9a-f]{40}", v) else "unknown"


_API = f"https://api.github.com/repos/{_REPO}"
_HEADERS = {"Accept": "application/vnd.github+json", "User-Agent": "wvedtalk-desk"}


async def check_update(force: bool = False) -> dict:
    """Is the GitHub branch ahead of the commit this build came from?

    The primary signal is the commit (GitHub compare API), so ordinary merges count as updates — the
    VERSION file is only the display label. If the build predates commit-stamping, the build is
    reported as unknown and an update is offered (applying it rebuilds and stamps the commit)."""
    now = time.time()
    cached = _cache["data"]
    if not force and cached is not None and now - _cache["at"] < _TTL_SECONDS:
        return cached

    current = current_version()
    cur_sha = current_commit()
    latest = None
    latest_sha = None
    behind_by = 0
    changes: list = []
    error = None
    try:
        async with httpx.AsyncClient(timeout=8.0, follow_redirects=True, headers=_HEADERS) as http:
            resp = await http.get(_RAW_URL, headers={"Accept": "text/plain"})
            if resp.status_code == 200:
                latest = resp.text.strip() or None
            else:
                error = f"update server returned {resp.status_code}"
            if cur_sha != "unknown":
                r = await http.get(f"{_API}/compare/{cur_sha}...{_BRANCH}")
                if r.status_code == 200:
                    j = r.json()
                    behind_by = int(j.get("ahead_by", 0))  # commits on the branch that this build lacks
                    latest_sha = (j.get("commits") or [{}])[-1].get("sha") if behind_by else cur_sha
                    changes = [
                        (c.get("commit", {}).get("message", "").split("\n")[0])[:120]
                        for c in (j.get("commits") or [])[-10:]
                    ][::-1]
                elif r.status_code == 404:
                    error = "this build's commit isn't on GitHub (local or unpushed changes)"
                else:
                    error = f"GitHub returned {r.status_code}"
            else:
                r = await http.get(f"{_API}/commits/{_BRANCH}", headers={"Accept": "application/vnd.github.sha"})
                if r.status_code == 200:
                    latest_sha = r.text.strip()
    except Exception:
        error = error or "could not reach the update server"

    unknown_build = cur_sha == "unknown"
    if unknown_build:
        update_available = latest_sha is not None  # can't prove it's current: offer a rebuild that stamps it
    else:
        update_available = behind_by > 0
    if not update_available and latest and current != "unknown" and _is_newer(latest, current):
        update_available = True  # an explicit version bump always counts too
    data = {
        "current": current,
        "latest": latest,
        "update_available": update_available,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "error": error,
        "current_commit": None if unknown_build else cur_sha[:7],
        "latest_commit": latest_sha[:7] if latest_sha else None,
        "behind_by": behind_by,
        "changes": changes,
        "unknown_build": unknown_build,
    }
    _cache["data"] = data
    _cache["at"] = now
    return data
