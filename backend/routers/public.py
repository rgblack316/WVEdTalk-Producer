"""Public, unauthenticated read routes — token-validated share links. Mounted WITHOUT the
auth guard so a briefing can be shared with people who don't have an account. Each link
carries an HMAC share token that must validate before the briefing is returned."""

from fastapi import APIRouter, HTTPException, Query

from lib import auth
from lib.db import db
from models.briefing import Briefing

router = APIRouter(tags=["public"])


@router.get("/public/briefings/{date}", response_model=Briefing)
async def public_briefing(date: str, token: str = Query(default="")):
    if not auth.verify_share_token(date, token):
        raise HTTPException(status_code=403, detail="Invalid or expired share link")
    doc = await db.briefings.find_one({"date": date})
    if not doc:
        raise HTTPException(status_code=404, detail=f"No briefing for {date}")
    doc.pop("_id", None)
    return Briefing(**doc)
