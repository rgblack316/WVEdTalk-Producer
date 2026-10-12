"""First-run setup routes (self-hosted edition).

On a brand-new install the `users` collection is empty. Until an owner is established, the frontend
shows a setup wizard instead of the login screen. These routes are OPEN (no auth) but each one is a
strict one-shot: every write refuses the moment any user exists, so they cannot be used to hijack a
configured instance. They live under /api but are NOT behind the auth guard (mounted like /api/auth).
"""

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel, EmailStr

from lib import auth
from lib.db import db

router = APIRouter(tags=["setup"])


async def _needs_setup() -> bool:
    return (await db.users.count_documents({}, limit=1)) == 0


@router.get("/setup/status")
async def setup_status():
    return {"needs_setup": await _needs_setup()}


class FirstAdmin(BaseModel):
    email: str
    password: str
    name: str = ""


@router.post("/setup/admin")
async def create_first_admin(body: FirstAdmin, response: Response):
    if not await _needs_setup():
        raise HTTPException(status_code=409, detail="Setup has already been completed.")
    email = (body.email or "").strip()
    if not email:
        raise HTTPException(status_code=422, detail="Email or username is required.")
    if len(body.password.strip()) < 8:
        raise HTTPException(status_code=422, detail="Password must be at least 8 characters.")
    user = await auth.create_user(email=email, role="admin", password=body.password.strip())
    response.set_cookie(
        key=auth.COOKIE_NAME, value=auth.make_token(user), max_age=auth.MAX_AGE,
        httponly=True, samesite="lax", secure=True, path="/",
    )
    return {"ok": True, "email": email}


@router.post("/setup/import")
async def setup_import(body: dict):
    """First-run migration: load a backup archive into the empty instance (one-shot). Restores
    accounts (hashed passwords) + data, so the operator signs in with their existing credentials."""
    if not await _needs_setup():
        raise HTTPException(status_code=409, detail="Setup has already been completed.")
    from routers.data_io import import_data, ImportRequest

    archive = body.get("archive") if isinstance(body, dict) else None
    if not isinstance(archive, dict):
        raise HTTPException(status_code=422, detail="Upload a News Desk export file.")
    return await import_data(ImportRequest(mode="replace", confirm=True, archive=archive))
