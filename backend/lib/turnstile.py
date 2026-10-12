"""Cloudflare Turnstile server-side verification. Keys are read from Settings → Integrations
(DB-over-env via lib.config_secrets), so the CAPTCHA is fully in-app managed. Graceful: if the keys
are not configured the CAPTCHA is disabled (verify() returns True) so the form keeps working before
keys are set. The site key is public (served to the browser via /api/public/config); the secret key
stays server-side."""

import logging
from typing import Optional, Tuple

import httpx

from lib import config_secrets

logger = logging.getLogger(__name__)

VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"


async def _keys() -> Tuple[str, str]:
    cfg = await config_secrets.get_turnstile_config()
    return (cfg.get("site_key") or "").strip(), (cfg.get("secret_key") or "").strip()


async def site_key() -> str:
    sk, _ = await _keys()
    return sk


async def enabled() -> bool:
    sk, secret = await _keys()
    return bool(sk and secret)


async def verify(token: str, remoteip: Optional[str] = None) -> bool:
    """Validate a Turnstile token with Cloudflare siteverify. Returns True when CAPTCHA is
    disabled (no keys), else True only on a genuine success. Tokens are single-use + expire in 5m."""
    site, secret = await _keys()
    if not (site and secret):
        return True
    if not token:
        return False
    payload = {"secret": secret, "response": token}
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
