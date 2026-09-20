"""Auth routes for email + password login. Open (not behind the auth guard)."""

import time

from fastapi import APIRouter, Cookie, Header, HTTPException, Request, Response

from lib import auth
from models.user import AuthState, LoginRequest, User

router = APIRouter(tags=["auth"])

# Simple in-memory brute-force throttle for login.
_ATTEMPTS: dict[str, list[float]] = {}
_WINDOW = 300  # seconds
_MAX_ATTEMPTS = 10


def _throttle(ip: str) -> None:
    now = time.time()
    hits = [t for t in _ATTEMPTS.get(ip, []) if now - t < _WINDOW]
    if len(hits) >= _MAX_ATTEMPTS:
        raise HTTPException(status_code=429, detail="Too many attempts. Try again in a few minutes.")
    hits.append(now)
    _ATTEMPTS[ip] = hits


def _state(user: dict | None) -> AuthState:
    if not user:
        return AuthState(authenticated=False, user=None)
    return AuthState(authenticated=True, user=User(**{k: user[k] for k in ("id", "email", "role", "created_at") if k in user}))


@router.get("/auth/me", response_model=AuthState)
async def me(
    wv_desk_session: str | None = Cookie(default=None),
    x_desk_passcode: str | None = Header(default=None),
):
    return _state(await auth.resolve_user(wv_desk_session, x_desk_passcode))


@router.post("/auth/login", response_model=AuthState)
async def login(body: LoginRequest, request: Request, response: Response):
    _throttle(request.client.host if request.client else "unknown")
    user = await auth.get_user_by_email(str(body.email))
    if not user or not auth.verify_password(body.password, user.get("password_hash", "")):
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    response.set_cookie(
        key=auth.COOKIE_NAME,
        value=auth.make_token(user),
        max_age=auth.MAX_AGE,
        httponly=True,
        samesite="lax",
        secure=True,
        path="/",
    )
    return _state(user)


@router.post("/auth/logout", response_model=AuthState)
async def logout(response: Response):
    response.delete_cookie(key=auth.COOKIE_NAME, path="/")
    return AuthState(authenticated=False, user=None)
