"""Version / update-availability routes. Mounted under /api (auth-guarded in server.py)."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from lib import auth, version, selfupdate

router = APIRouter(tags=["version"])


class VersionInfo(BaseModel):
    current: str
    latest: Optional[str] = None
    update_available: bool = False
    checked_at: Optional[str] = None
    error: Optional[str] = None


@router.get("/version", response_model=VersionInfo)
async def get_version():
    """Current version + cached update check (any signed-in user)."""
    return await version.check_update()


@router.post("/version/check", response_model=VersionInfo)
async def force_version_check(_: dict = Depends(auth.require_editor)):
    """Force a fresh check against GitHub, bypassing the cache (editors/admins)."""
    return await version.check_update(force=True)


class SelfUpdateStatus(BaseModel):
    state: str = "idle"  # idle | queued | running | success | failed
    message: Optional[str] = None
    pending: bool = False
    available: bool = False
    watcher_alive: bool = False
    requested_at: Optional[str] = None
    requested_by: Optional[str] = None
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    revision_before: Optional[str] = None
    revision_after: Optional[str] = None


class SelfUpdateResult(SelfUpdateStatus):
    queued: bool = False
    already: bool = False


@router.get("/self-update/status", response_model=SelfUpdateStatus)
async def self_update_status(_: dict = Depends(auth.require_admin)):
    """Current one-click-update state, read from the host watcher's control files (admin)."""
    return selfupdate.status()


@router.post("/self-update", response_model=SelfUpdateResult)
async def self_update(user: dict = Depends(auth.require_admin)):
    """Queue an upgrade for the host watcher to apply (admin). Idempotent while one is in flight."""
    if not selfupdate.available():
        raise HTTPException(
            status_code=503,
            detail="One-click update isn't available on this deployment (control volume not mounted).",
        )
    return selfupdate.request_upgrade(user.get("email") or user.get("id") or "admin")
