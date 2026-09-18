"""Single shared-passcode auth: a stateless HMAC-signed httpOnly cookie.

One passcode gates the whole desk. Programmatic clients (e.g. the downstream weekly
agent reading the JSON contract) may instead send the passcode in the X-Desk-Passcode
header. Both are checked by require_auth.
"""

import hashlib
import hmac
import logging
import os
import secrets
import time

from fastapi import Cookie, Header, HTTPException

logger = logging.getLogger(__name__)

COOKIE_NAME = "wv_desk_session"
MAX_AGE = 60 * 60 * 24 * 30  # 30 days

_PASSCODE = os.environ.get("APP_PASSCODE", "")
_SECRET = os.environ.get("SESSION_SECRET", "") or "insecure-dev-secret-change-me"


def _sign(msg: str) -> str:
    return hmac.new(_SECRET.encode(), msg.encode(), hashlib.sha256).hexdigest()


def make_token() -> str:
    """token = issued_at.signature — proves the passcode was entered, no server state."""
    issued = str(int(time.time()))
    return f"{issued}.{_sign(issued)}"


def _token_valid(token: str) -> bool:
    if not token or "." not in token:
        return False
    issued, sig = token.rsplit(".", 1)
    if not hmac.compare_digest(sig, _sign(issued)):
        return False
    try:
        return (int(time.time()) - int(issued)) <= MAX_AGE
    except ValueError:
        return False


def passcode_matches(candidate: str) -> bool:
    if not _PASSCODE:
        return False
    return hmac.compare_digest(candidate or "", _PASSCODE)


def is_authenticated(cookie_token: str | None, header_passcode: str | None) -> bool:
    if cookie_token and _token_valid(cookie_token):
        return True
    if header_passcode and passcode_matches(header_passcode):
        return True
    return False


async def require_auth(
    wv_desk_session: str | None = Cookie(default=None),
    x_desk_passcode: str | None = Header(default=None),
) -> None:
    """FastAPI dependency guarding protected routers."""
    if not is_authenticated(wv_desk_session, x_desk_passcode):
        raise HTTPException(status_code=401, detail="Passcode required")


def new_secret() -> str:
    return secrets.token_hex(32)
