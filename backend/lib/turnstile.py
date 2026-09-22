"""Cloudflare Turnstile server-side verification. Graceful: if the keys are not configured the
CAPTCHA is disabled (verify() returns True) so the form keeps working in dev / before keys are set.
Site key is public (served to the browser via /api/public/config); secret key stays server-side."""

import logging
import os
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

SITE_KEY = os.environ.get("TURNSTILE_SITE_KEY", "").strip()
SECRET_KEY = os.environ.get("TURNSTILE_SECRET_KEY", "").strip()
VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"


def enabled() -> bool:
    return bool(SITE_KEY and SECRET_KEY)


async def verify(token: str, remoteip: Optional[str] = None) -> bool:
    """Validate a Turnstile token with Cloudflare siteverify. Returns True when CAPTCHA is
    disabled (no keys), else True only on a genuine success. Tokens are single-use + expire in 5m."""
    if not enabled():
        return True
    if not token:
        return False
    payload = {"secret": SECRET_KEY, "response": token}
    if remoteip:
        payload["remoteip"] = remoteip
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(VERIFY_URL, data=payload)
            resp.raise_for_status()
            data = resp.json()
        if not data.get("success"):
            logger.info("turnstile rejected: %s", data.get("error-codes"))
        return bool(data.get("success"))
    except Exception:
        logger.exception("turnstile siteverify request failed")
        return False
