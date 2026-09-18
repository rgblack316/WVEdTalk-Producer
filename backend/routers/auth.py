"""Auth routes for the single shared passcode. Open (not behind require_auth)."""

from fastapi import APIRouter, Cookie, Header, HTTPException, Response
from pydantic import BaseModel

from lib import auth

router = APIRouter(tags=["auth"])


class LoginRequest(BaseModel):
    passcode: str


class AuthState(BaseModel):
    authenticated: bool


@router.get("/auth/me", response_model=AuthState)
async def me(
    wv_desk_session: str | None = Cookie(default=None),
    x_desk_passcode: str | None = Header(default=None),
):
    return AuthState(authenticated=await auth.is_authenticated(wv_desk_session, x_desk_passcode))


@router.post("/auth/login", response_model=AuthState)
async def login(body: LoginRequest, response: Response):
    if not await auth.passcode_matches(body.passcode):
        raise HTTPException(status_code=401, detail="Incorrect passcode")
    response.set_cookie(
        key=auth.COOKIE_NAME,
        value=auth.make_token(),
        max_age=auth.MAX_AGE,
        httponly=True,
        samesite="lax",
        secure=True,
        path="/",
    )
    return AuthState(authenticated=True)


@router.post("/auth/logout", response_model=AuthState)
async def logout(response: Response):
    response.delete_cookie(key=auth.COOKIE_NAME, path="/")
    return AuthState(authenticated=False)
