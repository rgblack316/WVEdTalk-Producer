"""Version / update-availability routes. Mounted under /api (auth-guarded in server.py)."""

from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from lib import auth, version

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
