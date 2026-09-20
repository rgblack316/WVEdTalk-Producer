"""Public, unauthenticated routes: token-validated share links + newsletter sign-up.
Mounted WITHOUT the auth guard. Share links carry an HMAC token; unsubscribe carries a
per-email HMAC token. Sign-up is idempotent, email-format validated, and IP-throttled."""

import time
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query, Request

from lib import auth
from lib.db import db
from models.briefing import Briefing
from models.subscriber import SubscribeRequest, UnsubscribeRequest

router = APIRouter(tags=["public"])

# Light in-memory throttle for public sign-up (defense against abuse / G5).
_ATTEMPTS: dict[str, list[float]] = {}
_WINDOW = 300  # seconds
_MAX = 20


def _throttle(ip: str) -> None:
    now = time.time()
    hits = [t for t in _ATTEMPTS.get(ip, []) if now - t < _WINDOW]
    if len(hits) >= _MAX:
        raise HTTPException(status_code=429, detail="Too many attempts. Please try again shortly.")
    hits.append(now)
    _ATTEMPTS[ip] = hits


@router.get("/public/briefings/{date}", response_model=Briefing)
async def public_briefing(date: str, token: str = Query(default="")):
    if not auth.verify_share_token(date, token):
        raise HTTPException(status_code=403, detail="Invalid or expired share link")
    doc = await db.briefings.find_one({"date": date})
    if not doc:
        raise HTTPException(status_code=404, detail=f"No briefing for {date}")
    doc.pop("_id", None)
    return Briefing(**doc)


@router.post("/public/subscribe")
async def subscribe(body: SubscribeRequest, request: Request):
    _throttle(request.client.host if request.client else "unknown")
    email = str(body.email).lower().strip()
    existing = await db.subscribers.find_one({"email": email})
    if existing:
        if not existing.get("active"):
            await db.subscribers.update_one({"email": email}, {"$set": {"active": True}})
    else:
        await db.subscribers.insert_one(
            {"email": email, "active": True, "subscribed_at": datetime.now(timezone.utc)}
        )
    # Same response whether new or existing — don't leak who is already subscribed.
    return {"ok": True, "message": "You're subscribed to the WV Education News Desk daily briefing."}


@router.post("/public/unsubscribe")
async def unsubscribe(body: UnsubscribeRequest):
    email = str(body.email).lower().strip()
    if not auth.verify_unsub_token(email, body.token):
        raise HTTPException(status_code=403, detail="This unsubscribe link is invalid.")
    await db.subscribers.update_one({"email": email}, {"$set": {"active": False}})
    return {"ok": True, "message": "You've been unsubscribed. You won't receive further briefings."}
