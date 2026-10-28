"""Publish API — the website build reads sanitized briefings from here.

Mounted WITHOUT the login guard: it is authenticated by a dedicated, read-only publish token sent
as `Authorization: Bearer <token>` (rotate it in Settings -> Integrations). The token grants access to
this one endpoint only, never to the rest of the desk. Output is the sanitized public view
(lib.publish): stories, sources and trends only.
"""

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Header, HTTPException

from lib import config_secrets
from lib.db import db
from lib.publish import public_briefing

router = APIRouter(tags=["publish"])


async def load_complete_briefings() -> list:
    docs = await db.briefings.find({"status": "complete"}).sort("date", -1).to_list(5000)
    for d in docs:
        d.pop("_id", None)
    return docs


def _bearer(authorization: Optional[str]) -> str:
    if not authorization:
        return ""
    scheme, _, value = authorization.partition(" ")
    return value.strip() if scheme.lower() == "bearer" else ""


@router.get("/publish/briefings")
async def publish_briefings(authorization: Optional[str] = Header(default=None)):
    if not await config_secrets.verify_publish_token(_bearer(authorization)):
        # Same response whether the token is missing, wrong, or not configured at all.
        raise HTTPException(status_code=401, detail="Invalid publish token", headers={"WWW-Authenticate": "Bearer"})
    out = []
    for doc in await load_complete_briefings():
        pb = public_briefing(doc)
        if pb:
            out.append(pb)
    return {"generated_at": datetime.now(timezone.utc).isoformat(), "briefings": out}
