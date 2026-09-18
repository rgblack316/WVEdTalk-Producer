"""WVEdTalk weekly episode routes — mounted under /api."""

import asyncio
from typing import List, Optional

from fastapi import APIRouter, HTTPException

from lib import producer
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
async def trigger_produce():
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
async def email_latest_episode():
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


@router.get("/episodes/{week_of}", response_model=WeeklyEpisode)
async def get_episode(week_of: str):
    doc = await db.episodes.find_one({"week_of": week_of})
    if not doc:
        raise HTTPException(status_code=404, detail=f"No episode for week of {week_of}")
    return WeeklyEpisode(**_clean(doc))
