"""Desk configuration routes — recipients and watchlist terms. Mounted under /api."""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr

from lib import email_digest
from lib import auth
from lib import desk
from lib import config_secrets, llm, mailer, site_publish
from lib.db import db
from models.config import (
    AutoLockUpdate,
    AutoThankUpdate,
    DeskConfig,
    DigestSendResult,
    HideUnverifiedUpdate,
    NextRuns,
    RecipientCreate,
    RunLogEntry,
    ScheduleUpdate,
    ScriptLengthUpdate,
    SupportUpdate,
    TestDigestRequest,
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


# ---- Integrations: AI provider, email (Resend/SMTP), Turnstile, run toggles ---

@router.get("/settings/integrations")
async def get_integrations(_admin=Depends(auth.require_admin)):
    return await config_secrets.public_masked()


class IntegrationUpdate(BaseModel):
    llm_provider: Optional[str] = None
    llm_model: Optional[str] = None
    gemini_api_key: Optional[str] = None
    openai_api_key: Optional[str] = None
    email_provider: Optional[str] = None
    email_from: Optional[str] = None
    public_url: Optional[str] = None
    email_from_name: Optional[str] = None
    email_reply_to: Optional[str] = None
    resend_api_key: Optional[str] = None
    smtp_host: Optional[str] = None
    smtp_port: Optional[int] = None
    smtp_username: Optional[str] = None
    smtp_password: Optional[str] = None
    smtp_starttls: Optional[bool] = None
    turnstile_site_key: Optional[str] = None
    turnstile_secret_key: Optional[str] = None
    runs_enabled: Optional[bool] = None
    digests_enabled: Optional[bool] = None
    site_url: Optional[str] = None
    deploy_hook_url: Optional[str] = None


_SECRET_FIELDS = {
    "gemini_api_key", "openai_api_key", "resend_api_key", "smtp_password", "turnstile_secret_key",
    "deploy_hook_url",
}


@router.post("/settings/integrations")
async def update_integrations(body: IntegrationUpdate, _admin=Depends(auth.require_admin)):
    data = body.model_dump(exclude_none=True)
    # Website publishing: both values must be https URLs (blank clears the setting).
    for key, label in (("site_url", "Website URL"), ("deploy_hook_url", "Deploy hook URL")):
        if key in data:
            data[key] = data[key].strip().rstrip("/") if key == "site_url" else data[key].strip()
            if data[key] and not site_publish.valid_https_url(data[key]):
                raise HTTPException(status_code=422, detail=f"{label} must be a full https:// URL.")
    patch = {}
    for k, v in data.items():
        patch[k] = config_secrets.enc(v) if k in _SECRET_FIELDS else v
    if patch:
        await config_secrets.save_integrations(patch)
    return await config_secrets.public_masked()


@router.post("/settings/integrations/publish-token")
async def rotate_publish_token(_admin=Depends(auth.require_admin)):
    """Generate a new read-only publish token for the website build. Shown ONCE — only a masked
    'set' flag is ever returned afterwards. Rotating invalidates the previous token."""
    return {"token": await config_secrets.rotate_publish_token()}


@router.post("/settings/integrations/test-site-hook")
async def test_site_hook(_admin=Depends(auth.require_admin)):
    """Fire the website deploy hook once (also works as a manual 'rebuild the website now')."""
    return await site_publish.trigger_deploy()


@router.post("/settings/integrations/test-ai")
async def test_ai(_admin=Depends(auth.require_admin)):
    return await llm.test_connection()


class TestEmail(BaseModel):
    email: EmailStr
    provider: Optional[str] = None


@router.post("/settings/integrations/test-email")
async def test_email(body: TestEmail, _admin=Depends(auth.require_admin)):
    return await mailer.test_send(str(body.email), provider=body.provider)


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


@router.post("/settings/support", response_model=DeskConfig)
async def set_support(body: SupportUpdate):
    cfg = await _load()
    cfg.support_segment = body.segment
    cfg.support_default_on = body.default_on
    await _save(cfg)
    return cfg


@router.post("/settings/auto-thank", response_model=DeskConfig)
async def set_auto_thank(body: AutoThankUpdate):
    cfg = await _load()
    cfg.auto_thank_on_use = body.enabled
    await _save(cfg)
    return cfg


@router.post("/settings/hide-unverified", response_model=DeskConfig)
async def set_hide_unverified(body: HideUnverifiedUpdate):
    cfg = await _load()
    cfg.hide_unverified_sources = body.enabled
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


@router.post("/settings/send-digest", response_model=DigestSendResult)
async def send_latest_digest(_edit=Depends(auth.require_editor)):
    """Send the most recent briefing to all configured recipients + active subscribers. Returns
    per-audience counts and a reason for every failed address (so the UI can show what happened)."""
    cfg = await _load()
    sub_count = await db.subscribers.count_documents({"active": True})
    if not cfg.recipients and sub_count == 0:
        raise HTTPException(status_code=400, detail="No recipients or subscribers configured")
    doc = await db.briefings.find_one({}, sort=[("date", -1)])
    if not doc:
        raise HTTPException(status_code=404, detail="No briefing available to send")
    doc.pop("_id", None)
    from models.briefing import Briefing

    return await email_digest.send_digest(Briefing(**doc), cfg.recipients)


@router.post("/settings/test-digest")
async def test_digest(body: TestDigestRequest, _edit=Depends(auth.require_editor)):
    """Send a single subscriber-style test copy of the latest briefing to one address, and report
    back whether it succeeded (and the exact provider error if not) — a pre-flight before a blast."""
    doc = await db.briefings.find_one({}, sort=[("date", -1)])
    if not doc:
        raise HTTPException(status_code=404, detail="No briefing available to send")
    doc.pop("_id", None)
    from models.briefing import Briefing

    err = await email_digest.send_test_digest(Briefing(**doc), str(body.email))
    return {"ok": err is None, "email": str(body.email), "error": err}


@router.post("/settings/resend-digest", response_model=DigestSendResult)
async def resend_digest(_edit=Depends(auth.require_editor)):
    """Resend the latest briefing only to active subscribers who have not yet received it (per the
    delivery log) — for recovering after a partial delivery failure. Idempotent and safe to repeat."""
    sub_count = await db.subscribers.count_documents({"active": True})
    if sub_count == 0:
        raise HTTPException(status_code=400, detail="No public subscribers configured")
    doc = await db.briefings.find_one({}, sort=[("date", -1)])
    if not doc:
        raise HTTPException(status_code=404, detail="No briefing available to send")
    doc.pop("_id", None)
    from models.briefing import Briefing

    return await email_digest.resend_missed(Briefing(**doc))


@router.get("/subscribers", response_model=List[Subscriber])
async def list_subscribers():
    docs = await db.subscribers.find({}, {"_id": 0}).sort("subscribed_at", -1).to_list(5000)
    return [Subscriber(**d) for d in docs]


@router.delete("/subscribers/{email}")
async def remove_subscriber(email: str, _edit=Depends(auth.require_editor)):
    await db.subscribers.delete_one({"email": email.lower().strip()})
    return {"ok": True}
