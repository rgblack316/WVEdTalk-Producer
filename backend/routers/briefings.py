"""Briefing routes — mounted onto api_router (/api) from server.py."""

import asyncio
import re
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException

from lib import config_secrets, desk
from lib.auth import require_editor, require_admin
from lib.db import db
from models.briefing import (
    Briefing,
    BriefingSummary,
    CandidateStory,
    ClearCandidatesRequest,
    ClearCandidatesResponse,
    ReflagRequest,
    RunStatus,
    SourceLink,
    StoryUpdate,
)

router = APIRouter(tags=["briefings"])


def _clean(doc: dict) -> dict:
    doc.pop("_id", None)
    return doc


def _links_from(items) -> List[SourceLink]:
    return [SourceLink(**s) for s in (items or []) if isinstance(s, dict)]


async def _recheck_briefing(d: dict) -> tuple[int, int]:
    all_links: List[SourceLink] = []
    sl = _links_from(d.get("source_log"))
    stories = {i: _links_from(s.get("sources")) for i, s in enumerate(d.get("stories") or [])}
    for objs in stories.values():
        all_links.extend(objs)
    all_links.extend(sl)
    if not all_links:
        return 0, 0
    await desk.resolve_links(all_links)
    set_doc = {"source_log": [o.model_dump() for o in sl]}
    for i, objs in stories.items():
        set_doc[f"stories.{i}.sources"] = [o.model_dump() for o in objs]
    await db.briefings.update_one({"date": d["date"]}, {"$set": set_doc})
    return len(all_links), sum(1 for o in all_links if not o.verified)


async def _recheck_episode(e: dict) -> tuple[int, int]:
    all_links: List[SourceLink] = []
    sl = _links_from(e.get("source_log"))
    el = _links_from(e.get("episode_links"))
    stories = {i: _links_from(s.get("sources")) for i, s in enumerate(e.get("selected_stories") or [])}
    for objs in stories.values():
        all_links.extend(objs)
    all_links.extend(sl)
    all_links.extend(el)
    if not all_links:
        return 0, 0
    await desk.resolve_links(all_links)
    set_doc = {"source_log": [o.model_dump() for o in sl], "episode_links": [o.model_dump() for o in el]}
    for i, objs in stories.items():
        set_doc[f"selected_stories.{i}.sources"] = [o.model_dump() for o in objs]
    await db.episodes.update_one({"week_of": e["week_of"]}, {"$set": set_doc})
    return len(all_links), sum(1 for o in all_links if not o.verified)


@router.get("/unverified-count")
async def unverified_count():
    """Rough desk-wide count of source links currently flagged unverified (verified == False) across
    briefings and episodes — powers the nav badge."""
    n = 0
    async for d in db.briefings.find({}, {"_id": 0, "source_log": 1, "stories.sources": 1}):
        for s in d.get("source_log") or []:
            if s.get("verified") is False:
                n += 1
        for st in d.get("stories") or []:
            for x in st.get("sources") or []:
                if x.get("verified") is False:
                    n += 1
    async for e in db.episodes.find({}, {"_id": 0, "episode_links": 1}):
        for s in e.get("episode_links") or []:
            if s.get("verified") is False:
                n += 1
    return {"count": n}


@router.post("/briefings/recheck-sources")
async def recheck_sources(_admin=Depends(require_admin)):
    """Admin one-pass maintenance: re-resolve and re-verify every source link across ALL past
    briefings AND weekly episodes (source logs, story sources, episode link lists). Returns how many
    briefings/episodes and links were checked, and how many are now unverified."""
    briefings = episodes = links = unverified = 0
    for d in await db.briefings.find({}).sort("date", -1).to_list(2000):
        n, u = await _recheck_briefing(d)
        if n:
            briefings += 1
            links += n
            unverified += u
    for e in await db.episodes.find({}).to_list(2000):
        n, u = await _recheck_episode(e)
        if n:
            episodes += 1
            links += n
            unverified += u
    return {"briefings": briefings, "episodes": episodes, "links_checked": links, "unverified": unverified}


def _drop_unverified(items) -> tuple[list, int]:
    kept = [s for s in (items or []) if not (isinstance(s, dict) and s.get("verified") is False)]
    return kept, len(items or []) - len(kept)


@router.post("/briefings/purge-unverified")
async def purge_unverified(_admin=Depends(require_admin)):
    """Admin: permanently delete every link currently flagged unverified (verified == False) from all
    briefings and episodes. Destructive — confirm in the UI first. Returns how many links were removed."""
    removed = briefings = episodes = 0
    for d in await db.briefings.find({}).to_list(2000):
        sl, r = _drop_unverified(d.get("source_log"))
        set_doc = {"source_log": sl}
        n = r
        for i, s in enumerate(d.get("stories") or []):
            kept, rr = _drop_unverified(s.get("sources"))
            if rr:
                set_doc[f"stories.{i}.sources"] = kept
                n += rr
        if n:
            await db.briefings.update_one({"date": d["date"]}, {"$set": set_doc})
            removed += n
            briefings += 1
    for e in await db.episodes.find({}).to_list(2000):
        sl, r1 = _drop_unverified(e.get("source_log"))
        el, r2 = _drop_unverified(e.get("episode_links"))
        set_doc = {"source_log": sl, "episode_links": el}
        n = r1 + r2
        for i, s in enumerate(e.get("selected_stories") or []):
            kept, rr = _drop_unverified(s.get("sources"))
            if rr:
                set_doc[f"selected_stories.{i}.sources"] = kept
                n += rr
        if n:
            await db.episodes.update_one({"week_of": e["week_of"]}, {"$set": set_doc})
            removed += n
            episodes += 1
    return {"removed": removed, "briefings": briefings, "episodes": episodes}


@router.post("/briefings/{date}/stories/{story_id}/verify-links", response_model=Briefing)
async def verify_story_links(date: str, story_id: str, _edit=Depends(require_editor)):
    """Re-resolve and re-verify a single story's source links on demand (from its detail page)."""
    doc = await db.briefings.find_one({"date": date})
    if not doc:
        raise HTTPException(status_code=404, detail=f"No briefing for {date}")
    for i, s in enumerate(doc.get("stories") or []):
        if s.get("id") == story_id:
            objs = _links_from(s.get("sources"))
            await desk.resolve_links(objs)
            await db.briefings.update_one(
                {"date": date}, {"$set": {f"stories.{i}.sources": [o.model_dump() for o in objs]}}
            )
            fresh = await db.briefings.find_one({"date": date})
            return Briefing(**_clean(fresh))
    raise HTTPException(status_code=404, detail="Story not found")


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


@router.get("/excluded-stories", response_model=List[CandidateStory])
async def list_excluded_stories():
    """Every briefing story the host has explicitly ruled out of weekly-episode consideration
    (is_excluded == True), newest edition first — powers the Excluded review page and its Restore."""
    docs = await db.briefings.find({"stories.is_excluded": True}).sort("date", -1).to_list(200)
    out: List[CandidateStory] = []
    for d in docs:
        for s in d.get("stories", []):
            if s.get("is_excluded"):
                out.append(CandidateStory(date=d["date"], story=s))
    return out


@router.get("/positive-stories", response_model=List[CandidateStory])
async def list_positive_stories():
    """Every briefing story the host flagged as a good-news/positive story to end the episode on
    (is_positive == True), newest edition first — powers the nav badge and the Podcast Prep filter."""
    docs = await db.briefings.find({"stories.is_positive": True}).sort("date", -1).to_list(200)
    out: List[CandidateStory] = []
    for d in docs:
        for s in d.get("stories", []):
            if s.get("is_positive"):
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


@router.get("/briefings/{date}/public-url")
async def briefing_public_url(date: str):
    """The public page for this briefing on the website. Readable by any signed-in user (including
    viewers) so they can copy a link to send to people without accounts. 409 until a website URL is
    set in Settings -> Integrations."""
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date):
        raise HTTPException(status_code=422, detail="Date must look like YYYY-MM-DD")
    doc = await db.briefings.find_one({"date": date}, {"_id": 1})
    if not doc:
        raise HTTPException(status_code=404, detail=f"No briefing for {date}")
    site = await config_secrets.get_site_url()
    if not site:
        raise HTTPException(status_code=409, detail="No website URL is configured (Settings → Integrations).")
    return {"date": date, "url": f"{site}/daily/{date}"}


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
                    s["is_positive"] = False  # an excluded story can't also be the positive close
            if update.is_positive is not None:
                s["is_positive"] = update.is_positive
                if update.is_positive:
                    s["is_excluded"] = False  # a positive-close story can't also be excluded
            if update.notes is not None:
                s["notes"] = update.notes
    if not found:
        raise HTTPException(status_code=404, detail="Story not found in this briefing")
    await db.briefings.replace_one({"date": date}, _clean(doc))
    return Briefing(**_clean(doc))
