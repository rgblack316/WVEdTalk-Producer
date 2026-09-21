"""Desk configuration routes — recipients and watchlist terms. Mounted under /api."""

from typing import List

from fastapi import APIRouter, Depends, HTTPException

from lib import email_digest
from lib import auth
from lib import desk
from lib.db import db
from models.config import (
    AutoLockUpdate,
    DeskConfig,
    NextRuns,
    RecipientCreate,
    RunLogEntry,
    ScheduleUpdate,
    ScriptLengthUpdate,
    WatchTermCreate,
)
from models.subscriber import Subscriber
from models.user import PasswordChange

router = APIRouter(tags=["settings"])

_KEY = {"key": "singleton"}
_VALID_LENGTHS = {"concise", "standard", "full"}
_VALID_LOCK = {0, 5, 15, 30, 60}


async def _load() -> DeskConfig:
    doc = await db.desk_config.find_one(_KEY, {"_id": 0, "key": 0})
    return DeskConfig(**(doc or {}))


async def _save(cfg: DeskConfig) -> None:
    await db.desk_config.update_one(_KEY, {"$set": cfg.model_dump()}, upsert=True)


@router.get("/settings", response_model=DeskConfig)
async def get_settings():
    return await _load()


@router.post("/settings/recipients", response_model=DeskConfig)
async def add_recipient(body: RecipientCreate, _edit=Depends(auth.require_editor)):
    cfg = await _load()
    email = str(body.email).lower()
    if email not in [r.lower() for r in cfg.recipients]:
        cfg.recipients.append(email)
        await _save(cfg)
    return cfg


@router.delete("/settings/recipients/{email}", response_model=DeskConfig)
async def remove_recipient(email: str, _edit=Depends(auth.require_editor)):
    cfg = await _load()
    cfg.recipients = [r for r in cfg.recipients if r.lower() != email.lower()]
    await _save(cfg)
    return cfg


@router.post("/settings/watch-terms", response_model=DeskConfig)
async def add_watch_term(body: WatchTermCreate, _edit=Depends(auth.require_editor)):
    term = body.term.strip()
    if not term:
        raise HTTPException(status_code=422, detail="Watch term cannot be empty")
    cfg = await _load()
    if term.lower() not in [t.lower() for t in cfg.watch_terms]:
        cfg.watch_terms.append(term)
        await _save(cfg)
    return cfg


@router.delete("/settings/watch-terms/{term}", response_model=DeskConfig)
async def remove_watch_term(term: str, _edit=Depends(auth.require_editor)):
    cfg = await _load()
    cfg.watch_terms = [t for t in cfg.watch_terms if t.lower() != term.lower()]
    await _save(cfg)
    return cfg


@router.post("/settings/script-length", response_model=DeskConfig)
async def set_script_length(body: ScriptLengthUpdate, _edit=Depends(auth.require_editor)):
    if body.value not in _VALID_LENGTHS:
        raise HTTPException(status_code=422, detail="Length must be concise, standard, or full")
    cfg = await _load()
    cfg.script_length = body.value
    await _save(cfg)
    return cfg


@router.post("/settings/auto-lock", response_model=DeskConfig)
async def set_auto_lock(body: AutoLockUpdate, _edit=Depends(auth.require_editor)):
    if body.minutes not in _VALID_LOCK:
        raise HTTPException(status_code=422, detail="Minutes must be one of 0, 5, 15, 30, 60")
    cfg = await _load()
    cfg.auto_lock_minutes = body.minutes
    await _save(cfg)
    return cfg


@router.post("/settings/schedule", response_model=DeskConfig)
async def set_schedule(body: ScheduleUpdate, _admin=Depends(auth.require_admin)):
    if not (0 <= body.daily_hour <= 23 and 0 <= body.daily_minute <= 59):
        raise HTTPException(status_code=422, detail="Daily time is out of range")
    if not (0 <= body.weekly_dow <= 6 and 0 <= body.weekly_hour <= 23 and 0 <= body.weekly_minute <= 59):
        raise HTTPException(status_code=422, detail="Weekly day/time is out of range")
    if not desk.is_valid_tz(body.timezone):
        raise HTTPException(status_code=422, detail="Unknown timezone")
    cfg = await _load()
    cfg.timezone = body.timezone
    cfg.daily_hour = body.daily_hour
    cfg.daily_minute = body.daily_minute
    cfg.weekly_dow = body.weekly_dow
    cfg.weekly_hour = body.weekly_hour
    cfg.weekly_minute = body.weekly_minute
    await _save(cfg)
    return cfg


@router.get("/schedule/next", response_model=NextRuns)
async def schedule_next():
    return await desk.next_runs()


@router.get("/run-log", response_model=List[RunLogEntry])
async def run_log():
    docs = await db.run_log.find({}, {"_id": 0}).sort("finished_at", -1).to_list(20)
    return [RunLogEntry(**d) for d in docs]


@router.post("/settings/password")
async def change_password(body: PasswordChange, user=Depends(auth.get_current_user)):
    if user.get("id") == "service":
        raise HTTPException(status_code=403, detail="Service accounts cannot change a password")
    if not auth.verify_password(body.current_password, user.get("password_hash", "")):
        raise HTTPException(status_code=401, detail="Current password is incorrect")
    if len(body.new_password.strip()) < 8:
        raise HTTPException(status_code=422, detail="New password must be at least 8 characters")
    await auth.set_password(user["id"], body.new_password.strip())
    return {"ok": True}


@router.post("/settings/send-digest")
async def send_latest_digest(_edit=Depends(auth.require_editor)):
    """Send the most recent briefing to all configured recipients (server-side template)."""
    cfg = await _load()
    sub_count = await db.subscribers.count_documents({"active": True})
    if not cfg.recipients and sub_count == 0:
        raise HTTPException(status_code=400, detail="No recipients or subscribers configured")
    doc = await db.briefings.find_one({}, sort=[("date", -1)])
    if not doc:
        raise HTTPException(status_code=404, detail="No briefing available to send")
    doc.pop("_id", None)
    from models.briefing import Briefing

    sent = await email_digest.send_digest(Briefing(**doc), cfg.recipients)
    if sent == 0:
        raise HTTPException(status_code=502, detail="Email delivery failed — check configuration")
    return {"sent": sent, "recipients": len(cfg.recipients)}


@router.get("/subscribers", response_model=List[Subscriber])
async def list_subscribers():
    docs = await db.subscribers.find({}, {"_id": 0}).sort("subscribed_at", -1).to_list(5000)
    return [Subscriber(**d) for d in docs]


@router.delete("/subscribers/{email}")
async def remove_subscriber(email: str, _edit=Depends(auth.require_editor)):
    await db.subscribers.delete_one({"email": email.lower().strip()})
    return {"ok": True}
