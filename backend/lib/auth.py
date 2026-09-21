"""Multi-user auth: email + password accounts with two roles (admin | editor).

Sessions are a stateless HMAC-signed httpOnly cookie bound to the user's id and current
password hash, so rotating a user's password (or an admin resetting it) invalidates that
user's existing sessions. Passwords are stored as salted PBKDF2-HMAC-SHA256 (stdlib only).

Programmatic/service clients (e.g. the downstream weekly agent that reads
/api/briefings/{date}) may still authenticate with the X-Desk-Passcode header matching the
APP_PASSCODE service token in backend/.env — this is a machine credential, separate from the
human email/password login.
"""

import hashlib
import hmac
import logging
import os
import secrets
import time
from typing import Optional

from fastapi import Cookie, Header, HTTPException

from lib.db import db

logger = logging.getLogger(__name__)

COOKIE_NAME = "wv_desk_session"
MAX_AGE = 60 * 60 * 24 * 30  # 30 days
_PBKDF2_ROUNDS = 200_000

# Bootstrap admin — seeded once if the users collection is empty.
SEED_ADMIN_EMAIL = "admin"
SEED_ADMIN_PASSWORD = "admin"

# Service token for programmatic/downstream access (header X-Desk-Passcode).
_SERVICE_PASSCODE = os.environ.get("APP_PASSCODE", "")
_SECRET = os.environ.get("SESSION_SECRET", "")
if not _SECRET:
    # Fail closed: never fall back to a public/default signing key.
    raise RuntimeError(
        "SESSION_SECRET is not set. Generate one (python -c 'import secrets;print(secrets.token_hex(32))') "
        "and add it to backend/.env before starting the server."
    )


def _sign(msg: str) -> str:
    return hmac.new(_SECRET.encode(), msg.encode(), hashlib.sha256).hexdigest()


def new_secret() -> str:
    return secrets.token_hex(32)


# ---- public share tokens (unauthenticated read links) ------------------------

def make_share_token(resource: str) -> str:
    """Deterministic, unguessable token for a public read link (e.g. a briefing date).
    Not tied to any user, so a shared link keeps working; rotate SESSION_SECRET to revoke all."""
    return _sign(f"share:{resource}")[:32]


def verify_share_token(resource: str, token: str | None) -> bool:
    if not token:
        return False
    return hmac.compare_digest(make_share_token(resource), token)


# ---- newsletter unsubscribe tokens -------------------------------------------

def make_unsub_token(email: str) -> str:
    """Per-subscriber one-click unsubscribe token (no DB storage needed — recomputed)."""
    return _sign(f"unsub:{email.lower().strip()}")[:32]


def verify_unsub_token(email: str, token: str | None) -> bool:
    if not token:
        return False
    return hmac.compare_digest(make_unsub_token(email), token)


# ---- password hashing (stdlib PBKDF2) ----------------------------------------

def hash_password(password: str, salt: Optional[str] = None) -> str:
    salt = salt or secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), _PBKDF2_ROUNDS)
    return f"{salt}${dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    if not stored or "$" not in stored:
        return False
    salt, _ = stored.split("$", 1)
    return hmac.compare_digest(hash_password(password, salt), stored)


def generate_temp_password() -> str:
    """A readable one-time password an admin can relay to a new user."""
    return secrets.token_urlsafe(9)


# ---- user store --------------------------------------------------------------

def _public(doc: dict) -> dict:
    return {"id": doc["id"], "email": doc["email"], "role": doc.get("role", "editor"),
            "created_at": doc.get("created_at")}


async def get_user_by_email(email: str) -> Optional[dict]:
    return await db.users.find_one({"email": email.lower().strip()}, {"_id": 0})


async def get_user_by_id(user_id: str) -> Optional[dict]:
    return await db.users.find_one({"id": user_id}, {"_id": 0})


async def create_user(email: str, role: str, password: str) -> dict:
    from models.user import User

    email = email.lower().strip()
    if await get_user_by_email(email):
        raise HTTPException(status_code=409, detail="A user with that email already exists")
    user = User(email=email, role=role if role in {"admin", "editor", "viewer"} else "editor")
    doc = user.model_dump()
    doc["password_hash"] = hash_password(password)
    await db.users.insert_one(doc)
    return doc


async def set_password(user_id: str, new_password: str) -> None:
    await db.users.update_one({"id": user_id}, {"$set": {"password_hash": hash_password(new_password)}})


async def ensure_seed_admin() -> None:
    """Create the bootstrap admin the first time the app starts with no users."""
    if await db.users.count_documents({}) > 0:
        return
    await create_user(SEED_ADMIN_EMAIL, "admin", SEED_ADMIN_PASSWORD)
    logger.info("seeded bootstrap admin %s", SEED_ADMIN_EMAIL)


# ---- session token (cookie) --------------------------------------------------

def make_token(user: dict) -> str:
    """token = user_id.issued.signature — bound to the user's current password hash,
    so a password change/reset invalidates all of that user's sessions."""
    issued = str(int(time.time()))
    sig = _sign(f"{user['id']}:{issued}:{user['password_hash'][:16]}")
    return f"{user['id']}.{issued}.{sig}"


async def _user_from_token(token: Optional[str]) -> Optional[dict]:
    if not token or token.count(".") != 2:
        return None
    user_id, issued, sig = token.split(".")
    user = await get_user_by_id(user_id)
    if not user:
        return None
    expected = _sign(f"{user_id}:{issued}:{user['password_hash'][:16]}")
    if not hmac.compare_digest(sig, expected):
        return None
    try:
        if (int(time.time()) - int(issued)) > MAX_AGE:
            return None
    except ValueError:
        return None
    return user


def _service_ok(header_passcode: Optional[str]) -> bool:
    return bool(_SERVICE_PASSCODE) and bool(header_passcode) and hmac.compare_digest(
        header_passcode, _SERVICE_PASSCODE
    )


# ---- guards ------------------------------------------------------------------

async def resolve_user(cookie_token: Optional[str], header_passcode: Optional[str]) -> Optional[dict]:
    user = await _user_from_token(cookie_token)
    if user:
        return user
    if _service_ok(header_passcode):
        # A synthetic admin identity for machine/downstream access.
        return {"id": "service", "email": "service@wv-desk", "role": "admin", "password_hash": ""}
    return None


async def get_current_user(
    wv_desk_session: str | None = Cookie(default=None),
    x_desk_passcode: str | None = Header(default=None),
) -> dict:
    """FastAPI dependency guarding protected routers; returns the authenticated user."""
    user = await resolve_user(wv_desk_session, x_desk_passcode)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user


# Router-level guard alias (return value ignored when used in `dependencies=[...]`).
require_auth = get_current_user


async def require_admin(
    wv_desk_session: str | None = Cookie(default=None),
    x_desk_passcode: str | None = Header(default=None),
) -> dict:
    user = await get_current_user(wv_desk_session, x_desk_passcode)
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Administrator access required")
    return user


async def require_editor(
    wv_desk_session: str | None = Cookie(default=None),
    x_desk_passcode: str | None = Header(default=None),
) -> dict:
    """Guards write actions: admins and editors may write; viewers are read-only."""
    user = await get_current_user(wv_desk_session, x_desk_passcode)
    if user.get("role") not in {"admin", "editor"}:
        raise HTTPException(status_code=403, detail="This action requires editor access — your account is view-only")
    return user
