"""WVEdTalk weekly episode routes — mounted under /api."""

import asyncio
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from lib import producer
from lib.auth import require_editor
from lib.db import db
from lib.email_digest import send_episode
from models.episode import EpisodeSummary, ProduceStatus, WeeklyEpisode

router = APIRouter(tags=["episodes"])


def _clean(doc: dict) -> dict:
    doc.pop("_id", None)
    return doc


@router.get("/episodes", response_model=List[EpisodeSummary])
async def list_episodes():
    docs = await db.episodes.find().sort("week_of", -1).to_list(200)
    out = []
    for d in docs:
        sel = d.get("selected_stories", [])
        out.append(
            EpisodeSummary(
                week_of=d["week_of"],
                week_start=d.get("week_start", ""),
                week_end=d.get("week_end", ""),
                generated_at=d["generated_at"],
                status=d.get("status", "complete"),
                story_count=len(sel),
                selected_headlines=[s.get("story", "") for s in sel],
            )
        )
    return out


@router.get("/episodes/latest", response_model=Optional[WeeklyEpisode])
async def latest_episode():
    doc = await db.episodes.find_one({}, sort=[("week_of", -1)])
    return WeeklyEpisode(**_clean(doc)) if doc else None


@router.get("/produce-status", response_model=ProduceStatus)
async def produce_status():
    return producer.get_status()


@router.post("/produce", response_model=ProduceStatus)
async def trigger_produce(_edit=Depends(require_editor)):
    status = producer.get_status()
    if status.running:
        raise HTTPException(status_code=409, detail="An episode is already being produced")

    async def _bg():
        try:
            await producer.produce_episode()
        except Exception:
            pass  # status object carries the error

    asyncio.create_task(_bg())
    await asyncio.sleep(0.2)
    return producer.get_status()


@router.post("/episodes/send")
async def email_latest_episode(_edit=Depends(require_editor)):
    """Email the most recent episode to configured recipients (server-side template)."""
    cfg = await db.desk_config.find_one({"key": "singleton"}, {"_id": 0}) or {}
    recipients = cfg.get("recipients") or []
    if not recipients:
        raise HTTPException(status_code=400, detail="No recipients configured")
    doc = await db.episodes.find_one({}, sort=[("week_of", -1)])
    if not doc:
        raise HTTPException(status_code=404, detail="No episode available to send")
    doc.pop("_id", None)
    sent = await send_episode(WeeklyEpisode(**doc), recipients)
    if sent == 0:
        raise HTTPException(status_code=502, detail="Email delivery failed — check configuration")
    return {"sent": sent, "recipients": len(recipients)}


@router.post("/episodes/{week_of}/chapterize", response_model=WeeklyEpisode)
async def chapterize(week_of: str, _edit=Depends(require_editor)):
    """Backfill chapter headers on an existing episode (inserts headers without rewriting)."""
    try:
        doc = await producer.chapterize_episode(week_of)
    except ValueError as exc:
        if str(exc) == "not_found":
            raise HTTPException(status_code=404, detail=f"No episode for week of {week_of}")
        raise HTTPException(status_code=400, detail="This episode has no script to chapterize")
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Could not add chapters: {exc}")
    return WeeklyEpisode(**doc)


class _SupportToggle(BaseModel):
    enabled: bool


@router.post("/episodes/{week_of}/support", response_model=WeeklyEpisode)
async def toggle_support(week_of: str, body: _SupportToggle, _edit=Depends(require_editor)):
    """Add or remove the Value 4 Value support read on a single episode's script."""
    doc = await db.episodes.find_one({"week_of": week_of})
    if not doc:
        raise HTTPException(status_code=404, detail=f"No episode for week of {week_of}")
    doc.pop("_id", None)
    script = str(doc.get("recording_script") or "")
    cfg = await db.desk_config.find_one({"key": "singleton"}, {"_id": 0}) or {}
    seg = cfg.get("support_segment") or producer.REQUIRED_SUPPORT
    new_script = producer._ensure_support(script, seg) if body.enabled else producer._remove_support(script)
    chapters = producer._extract_chapters(new_script)
    await db.episodes.update_one(
        {"week_of": week_of},
        {"$set": {"recording_script": new_script, "chapters": chapters, "support_included": body.enabled}},
    )
    doc["recording_script"] = new_script
    doc["chapters"] = chapters
    doc["support_included"] = body.enabled
    return WeeklyEpisode(**doc)


@router.get("/episodes/{week_of}", response_model=WeeklyEpisode)
async def get_episode(week_of: str):
    doc = await db.episodes.find_one({"week_of": week_of})
    if not doc:
        raise HTTPException(status_code=404, detail=f"No episode for week of {week_of}")
    return WeeklyEpisode(**_clean(doc))
