"""Desk configuration routes — recipients and watchlist terms. Mounted under /api."""

from fastapi import APIRouter, HTTPException

from lib import email_digest
from lib.db import db
from models.config import DeskConfig, RecipientCreate, WatchTermCreate

router = APIRouter(tags=["settings"])

_KEY = {"key": "singleton"}


async def _load() -> DeskConfig:
    doc = await db.desk_config.find_one(_KEY, {"_id": 0, "key": 0})
    return DeskConfig(**(doc or {}))


async def _save(cfg: DeskConfig) -> None:
    await db.desk_config.update_one(_KEY, {"$set": cfg.model_dump()}, upsert=True)


@router.get("/settings", response_model=DeskConfig)
async def get_settings():
    return await _load()


@router.post("/settings/recipients", response_model=DeskConfig)
async def add_recipient(body: RecipientCreate):
    cfg = await _load()
    email = str(body.email).lower()
    if email not in [r.lower() for r in cfg.recipients]:
        cfg.recipients.append(email)
        await _save(cfg)
    return cfg


@router.delete("/settings/recipients/{email}", response_model=DeskConfig)
async def remove_recipient(email: str):
    cfg = await _load()
    cfg.recipients = [r for r in cfg.recipients if r.lower() != email.lower()]
    await _save(cfg)
    return cfg


@router.post("/settings/watch-terms", response_model=DeskConfig)
async def add_watch_term(body: WatchTermCreate):
    term = body.term.strip()
    if not term:
        raise HTTPException(status_code=422, detail="Watch term cannot be empty")
    cfg = await _load()
    if term.lower() not in [t.lower() for t in cfg.watch_terms]:
        cfg.watch_terms.append(term)
        await _save(cfg)
    return cfg


@router.delete("/settings/watch-terms/{term}", response_model=DeskConfig)
async def remove_watch_term(term: str):
    cfg = await _load()
    cfg.watch_terms = [t for t in cfg.watch_terms if t.lower() != term.lower()]
    await _save(cfg)
    return cfg


@router.post("/settings/send-digest")
async def send_latest_digest():
    """Send the most recent briefing to all configured recipients (server-side template)."""
    cfg = await _load()
    if not cfg.recipients:
        raise HTTPException(status_code=400, detail="No recipients configured")
    doc = await db.briefings.find_one({}, sort=[("date", -1)])
    if not doc:
        raise HTTPException(status_code=404, detail="No briefing available to send")
    doc.pop("_id", None)
    from models.briefing import Briefing

    sent = await email_digest.send_digest(Briefing(**doc), cfg.recipients)
    if sent == 0:
        raise HTTPException(status_code=502, detail="Email delivery failed — check configuration")
    return {"sent": sent, "recipients": len(cfg.recipients)}
