"""Briefing routes — mounted onto api_router (/api) from server.py."""

import asyncio
from typing import List, Optional

from fastapi import APIRouter, HTTPException

from lib import desk
from lib.db import db
from models.briefing import (
    Briefing,
    BriefingSummary,
    CandidateStory,
    RunStatus,
    StoryUpdate,
)

router = APIRouter(tags=["briefings"])


def _clean(doc: dict) -> dict:
    doc.pop("_id", None)
    return doc


@router.get("/briefings", response_model=List[BriefingSummary])
async def list_briefings():
    docs = await db.briefings.find().sort("date", -1).to_list(200)
    out = []
    for d in docs:
        stories = d.get("stories", [])
        out.append(
            BriefingSummary(
                date=d["date"],
                generated_at=d["generated_at"],
                status=d.get("status", "complete"),
                story_count=len(stories),
                big_three=[s.get("headline", "") for s in stories if s.get("section") == "big_three"],
            )
        )
    return out


@router.get("/briefings/latest", response_model=Optional[Briefing])
async def latest_briefing():
    doc = await db.briefings.find_one({}, sort=[("date", -1)])
    return Briefing(**_clean(doc)) if doc else None


@router.get("/candidates", response_model=List[CandidateStory])
async def list_candidates():
    docs = await db.briefings.find({"stories.is_candidate": True}).sort("date", -1).to_list(200)
    out: List[CandidateStory] = []
    for d in docs:
        for s in d.get("stories", []):
            if s.get("is_candidate"):
                out.append(CandidateStory(date=d["date"], story=s))
    return out


@router.get("/run-status", response_model=RunStatus)
async def run_status():
    return desk.get_run_status()


@router.post("/run", response_model=RunStatus)
async def trigger_run():
    status = desk.get_run_status()
    if status.running:
        raise HTTPException(status_code=409, detail="A research run is already in progress")

    async def _bg():
        try:
            await desk.run_briefing()
        except Exception:
            pass  # status object carries the error

    asyncio.create_task(_bg())
    await asyncio.sleep(0.2)
    return desk.get_run_status()


@router.get("/briefings/{date}", response_model=Briefing)
async def get_briefing(date: str):
    doc = await db.briefings.find_one({"date": date})
    if not doc:
        raise HTTPException(status_code=404, detail=f"No briefing for {date}")
    return Briefing(**_clean(doc))


@router.patch("/briefings/{date}/stories/{story_id}", response_model=Briefing)
async def update_story(date: str, story_id: str, update: StoryUpdate):
    doc = await db.briefings.find_one({"date": date})
    if not doc:
        raise HTTPException(status_code=404, detail=f"No briefing for {date}")
    found = False
    for s in doc.get("stories", []):
        if s.get("id") == story_id:
            found = True
            if update.is_candidate is not None:
                s["is_candidate"] = update.is_candidate
            if update.notes is not None:
                s["notes"] = update.notes
    if not found:
        raise HTTPException(status_code=404, detail="Story not found in this briefing")
    await db.briefings.replace_one({"date": date}, _clean(doc))
    return Briefing(**_clean(doc))
