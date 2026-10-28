"""Publishing to the public website (wvedtalk.com).

After a successful daily run the desk pings the website's deploy hook so the site rebuilds with the
new briefing. When the digest emails are about to go out, it then waits (bounded) until the new
briefing page is actually live, so the "view on the web" link in the email works the moment it lands.

Never logs or returns the deploy-hook URL: its path is a secret.
"""

import asyncio
import logging
import time
from typing import Awaitable, Callable, Dict, Optional
from urllib.parse import urlparse

import httpx

from lib import config_secrets

logger = logging.getLogger(__name__)

WAIT_TIMEOUT_SECONDS = 600  # how long to wait for the site to go live before sending emails anyway
POLL_INTERVAL_SECONDS = 20


def valid_https_url(url: str) -> bool:
    p = urlparse((url or "").strip())
    return p.scheme == "https" and bool(p.hostname) and p.username is None and p.password is None


async def trigger_deploy() -> Dict[str, object]:
    """POST the configured deploy hook once. Returns {ok, status?, error?, skipped?}."""
    hook = (await config_secrets.get_deploy_hook()).strip()
    if not hook:
        return {"ok": False, "skipped": True, "error": "No website deploy hook is configured."}
    if not valid_https_url(hook):
        return {"ok": False, "error": "The deploy hook must be an https:// URL."}
    from lib.desk import _is_private_host  # SSRF guard — same one used for outbound fetches

    if _is_private_host(urlparse(hook).hostname or ""):
        return {"ok": False, "error": "The deploy hook points at a private or unresolvable host."}
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            r = await client.post(hook)
    except httpx.HTTPError as exc:
        return {"ok": False, "error": f"Deploy hook request failed ({type(exc).__name__})."}
    if 200 <= r.status_code < 300:
        return {"ok": True, "status": r.status_code}
    return {"ok": False, "status": r.status_code, "error": f"Deploy hook returned HTTP {r.status_code}."}


async def is_live(date: str) -> bool:
    """True once the website serves this date's published briefing file. The site answers unknown
    paths with its HTML app shell (HTTP 200), so the body must parse as JSON for the right date."""
    site = await config_secrets.get_site_url()
    if not site:
        return False
    url = f"{site}/briefings/{date}.json"
    try:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            r = await client.get(url, params={"_": str(int(time.time()))}, headers={"Cache-Control": "no-cache"})
        return r.status_code == 200 and r.json().get("date") == date
    except Exception:
        return False


async def publish_and_wait(
    date: str,
    *,
    wait: bool,
    timeout: float = WAIT_TIMEOUT_SECONDS,
    interval: float = POLL_INTERVAL_SECONDS,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> Dict[str, Optional[object]]:
    """Fire the deploy hook; if `wait`, poll until the briefing page is live or `timeout` passes.

    Returns {configured, triggered, live, error}. `live` is None when we did not wait.
    """
    if not (await config_secrets.get_deploy_hook()).strip():
        return {"configured": False, "triggered": False, "live": None, "error": ""}
    res = await trigger_deploy()
    if not res.get("ok"):
        return {"configured": True, "triggered": False, "live": None, "error": str(res.get("error") or "")}
    if not wait or not await config_secrets.get_site_url():
        return {"configured": True, "triggered": True, "live": None, "error": ""}
    waited = 0.0
    while waited < timeout:
        await sleep(interval)  # a build takes a while — sleep first, then check
        waited += interval
        if await is_live(date):
            return {"configured": True, "triggered": True, "live": True, "error": ""}
    return {
        "configured": True, "triggered": True, "live": False,
        "error": f"The website did not show the new briefing within {int(timeout // 60)} minutes.",
    }
