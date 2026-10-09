"""Pydantic models for the WV Education News Desk briefing. Mirrored in frontend/src/lib/types.ts."""

import uuid
from datetime import datetime, timezone
from typing import List, Optional

from pydantic import BaseModel, Field


def _now() -> datetime:
    return datetime.now(timezone.utc)


class SourceLink(BaseModel):
    title: str = ""
    url: str = ""
    outlet: str = ""
    verified: bool = True  # False = we couldn't confirm the page is reachable (likely LLM-fabricated)
    grounded: bool = False  # True = came directly from a Google Search grounding citation


class Story(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    section: str = "other"  # big_three | other | developing | state_policy | k12 | higher_ed
    rank: Optional[int] = None
    headline: str = ""
    location: str = ""
    classification: List[str] = Field(default_factory=list)
    importance: Optional[int] = None
    podcast_potential: Optional[int] = None
    what_happened: str = ""
    why_it_matters: str = ""
    podcast_angle: str = ""
    questions: List[str] = Field(default_factory=list)
    # developing-story fields
    original_date: str = ""
    what_is_new: str = ""
    previously_known: str = ""
    unresolved: str = ""
    watch_next: str = ""
    sources: List[SourceLink] = Field(default_factory=list)
    # host workspace
    is_candidate: bool = False
    is_excluded: bool = False  # host explicitly ruled this out of weekly-episode consideration
    is_positive: bool = False  # host flagged this as a good-news story to end the episode on
    notes: str = ""


class Trend(BaseModel):
    title: str = ""
    why_it_matters: str = ""
    evidence: List[str] = Field(default_factory=list)
    missing_evidence: List[str] = Field(default_factory=list)
    watch_next: str = ""


class PodcastIdea(BaseModel):
    working_title: str = ""
    central_question: str = ""
    why_worth_exploring: str = ""
    supporting_stories: List[str] = Field(default_factory=list)
    research_needed: List[str] = Field(default_factory=list)
    potential_guests: List[str] = Field(default_factory=list)


class Briefing(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    date: str  # YYYY-MM-DD, America/New_York
    generated_at: datetime = Field(default_factory=_now)
    status: str = "complete"  # complete | failed
    model: str = ""
    editor_note: str = ""
    stories: List[Story] = Field(default_factory=list)
    trends: List[Trend] = Field(default_factory=list)
    podcast_ideas: List[PodcastIdea] = Field(default_factory=list)
    source_log: List[SourceLink] = Field(default_factory=list)
    error: str = ""


class BriefingSummary(BaseModel):
    date: str
    generated_at: datetime
    status: str
    story_count: int
    big_three: List[str] = Field(default_factory=list)


class RunStatus(BaseModel):
    running: bool = False
    date: str = ""
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    message: str = ""
    last_error: str = ""


class StoryUpdate(BaseModel):
    is_candidate: Optional[bool] = None
    is_excluded: Optional[bool] = None
    is_positive: Optional[bool] = None
    notes: Optional[str] = None


class CandidateStory(BaseModel):
    date: str
    story: Story


class ClearCandidatesRequest(BaseModel):
    # Clear scope, all optional. `date` = one edition/day; `from_date`/`to_date` = an inclusive
    # date range. Omit all three to clear every flagged story.
    date: Optional[str] = None
    from_date: Optional[str] = None
    to_date: Optional[str] = None


class CandidateRef(BaseModel):
    date: str
    story_id: str


class ReflagRequest(BaseModel):
    refs: List[CandidateRef] = []


class ClearCandidatesResponse(BaseModel):
    cleared: int = 0
    refs: List[CandidateRef] = []  # exactly which stories were un-flagged, so the UI can offer Undo
