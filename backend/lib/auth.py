"""Single shared-passcode auth: a stateless HMAC-signed httpOnly cookie.

The passcode itself is stored (hashed) in desk_config so it can be rotated in-app;
until one is set there, the APP_PASSCODE env value is used. Programmatic clients
(e.g. the downstream weekly agent) may send the passcode in the X-Desk-Passcode
header instead of the cookie. Both are checked by require_auth.
"""

import hashlib
import hmac
import logging
import os
import secrets
import time

from fastapi import Cookie, Header, HTTPException

from lib.db import db

logger = logging.getLogger(__name__)

COOKIE_NAME = "wv_desk_session"
MAX_AGE = 60 * 60 * 24 * 30  # 30 days
_CONFIG_KEY = {"key": "singleton"}

_ENV_PASSCODE = os.environ.get("APP_PASSCODE", "")
_SECRET = os.environ.get("SESSION_SECRET", "")
if not _SECRET:
    # Fail closed: never fall back to a public/default signing key.
    raise RuntimeError(
        "SESSION_SECRET is not set. Generate one (python -c 'import secrets;print(secrets.token_hex(32))') "
        "and add it to backend/.env before starting the server."
    )


def _sign(msg: str) -> str:
    return hmac.new(_SECRET.encode(), msg.encode(), hashlib.sha256).hexdigest()


def hash_passcode(passcode: str) -> str:
    return _sign(f"passcode:{passcode}")


# ---- session token (cookie) --------------------------------------------------

async def _session_key() -> str:
    """Signing key component that changes when the passcode is rotated, so rotation
    (and thus a compromised or shared token) is invalidated server-side."""
    return (await _current_hash())[:16]


async def make_token() -> str:
    """token = issued_at.signature — proves the passcode was entered; bound to the
    current passcode so rotating the passcode invalidates all existing sessions."""
    issued = str(int(time.time()))
    return f"{issued}.{_sign(issued + ':' + await _session_key())}"


async def _token_valid(token: str | None) -> bool:
    if not token or "." not in token:
        return False
    issued, sig = token.rsplit(".", 1)
    expected = _sign(issued + ":" + await _session_key())
    if not hmac.compare_digest(sig, expected):
        return False
    try:
        return (int(time.time()) - int(issued)) <= MAX_AGE
    except ValueError:
        return False


# ---- passcode (DB-backed, env fallback) --------------------------------------

async def _current_hash() -> str:
    doc = await db.desk_config.find_one(_CONFIG_KEY, {"_id": 0, "passcode_hash": 1})
    stored = (doc or {}).get("passcode_hash")
    if stored:
        return stored
    return hash_passcode(_ENV_PASSCODE) if _ENV_PASSCODE else ""


async def passcode_matches(candidate: str | None) -> bool:
    current = await _current_hash()
    if not current or not candidate:
        return False
    return hmac.compare_digest(hash_passcode(candidate), current)


async def set_passcode(new_passcode: str) -> None:
    await db.desk_config.update_one(
        _CONFIG_KEY, {"$set": {"passcode_hash": hash_passcode(new_passcode)}}, upsert=True
    )


# ---- guards ------------------------------------------------------------------

async def is_authenticated(cookie_token: str | None, header_passcode: str | None) -> bool:
    if await _token_valid(cookie_token):
        return True
    if header_passcode and await passcode_matches(header_passcode):
        return True
    return False


async def require_auth(
    wv_desk_session: str | None = Cookie(default=None),
    x_desk_passcode: str | None = Header(default=None),
) -> None:
    """FastAPI dependency guarding protected routers."""
    if not await is_authenticated(wv_desk_session, x_desk_passcode):
        raise HTTPException(status_code=401, detail="Passcode required")


def new_secret() -> str:
    return secrets.token_hex(32)
