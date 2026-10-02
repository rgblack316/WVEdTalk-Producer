"""Briefing routes — mounted onto api_router (/api) from server.py."""

import asyncio
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException

from lib import desk
from lib.auth import require_editor, make_share_token
from lib.db import db
from models.briefing import (
    Briefing,
    BriefingSummary,
    CandidateStory,
    ClearCandidatesRequest,
    ClearCandidatesResponse,
    ReflagRequest,
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


@router.post("/candidates/clear", response_model=ClearCandidatesResponse)
async def clear_candidates(body: Optional[ClearCandidatesRequest] = None, _edit=Depends(require_editor)):
    """Un-flag stories tagged as episode candidates. Scope by `date` (one edition/day), by an
    inclusive `from_date`/`to_date` range, or omit all to clear every flagged story. Prep notes are
    preserved so a story can be re-flagged and reconsidered later. Returns the exact refs cleared so
    the UI can offer Undo. Manual only — candidates never auto-clear."""
    query: dict = {"stories.is_candidate": True}
    if body and body.date:
        query["date"] = body.date
    elif body and (body.from_date or body.to_date):
        rng: dict = {}
        if body.from_date:
            rng["$gte"] = body.from_date
        if body.to_date:
            rng["$lte"] = body.to_date
        if rng:
            query["date"] = rng
    docs = await db.briefings.find(
        query, {"date": 1, "stories.id": 1, "stories.is_candidate": 1}
    ).to_list(1000)
    refs = [
        {"date": d["date"], "story_id": s.get("id")}
        for d in docs
        for s in d.get("stories", [])
        if s.get("is_candidate") and s.get("id")
    ]
    if refs:
        await db.briefings.update_many(
            query,
            {"$set": {"stories.$[el].is_candidate": False}},
            array_filters=[{"el.is_candidate": True}],
        )
    return {"cleared": len(refs), "refs": refs}


@router.post("/candidates/reflag")
async def reflag_candidates(body: ReflagRequest, _edit=Depends(require_editor)):
    """Re-flag specific stories that were just cleared — powers the 'Undo' on the Podcast Prep board."""
    by_date: dict = {}
    for r in body.refs:
        by_date.setdefault(r.date, []).append(r.story_id)
    for date, ids in by_date.items():
        await db.briefings.update_one(
            {"date": date},
            {"$set": {"stories.$[el].is_candidate": True}},
            array_filters=[{"el.id": {"$in": ids}}],
        )
    return {"restored": len(body.refs)}


@router.get("/run-status", response_model=RunStatus)
async def run_status():
    return desk.get_run_status()


@router.post("/run", response_model=RunStatus)
async def trigger_run(_edit=Depends(require_editor)):
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


@router.get("/briefings/{date}/share")
async def briefing_share_link(date: str):
    """Return a public share token/path for this briefing. Readable by any signed-in
    user (including viewers) so they can copy a link to send to people without accounts."""
    doc = await db.briefings.find_one({"date": date}, {"_id": 1})
    if not doc:
        raise HTTPException(status_code=404, detail=f"No briefing for {date}")
    token = make_share_token(date)
    return {"date": date, "token": token, "path": f"/share/briefing/{date}?t={token}"}


@router.get("/briefings/{date}", response_model=Briefing)
async def get_briefing(date: str):
    doc = await db.briefings.find_one({"date": date})
    if not doc:
        raise HTTPException(status_code=404, detail=f"No briefing for {date}")
    return Briefing(**_clean(doc))


@router.patch("/briefings/{date}/stories/{story_id}", response_model=Briefing)
async def update_story(date: str, story_id: str, update: StoryUpdate, _edit=Depends(require_editor)):
    doc = await db.briefings.find_one({"date": date})
    if not doc:
        raise HTTPException(status_code=404, detail=f"No briefing for {date}")
    found = False
    for s in doc.get("stories", []):
        if s.get("id") == story_id:
            found = True
            if update.is_candidate is not None:
                s["is_candidate"] = update.is_candidate
                if update.is_candidate:
                    s["is_excluded"] = False  # a story can't be both prioritized and excluded
            if update.is_excluded is not None:
                s["is_excluded"] = update.is_excluded
                if update.is_excluded:
                    s["is_candidate"] = False
            if update.notes is not None:
                s["notes"] = update.notes
    if not found:
        raise HTTPException(status_code=404, detail="Story not found in this briefing")
    await db.briefings.replace_one({"date": date}, _clean(doc))
    return Briefing(**_clean(doc))
