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
    notes: Optional[str] = None


class CandidateStory(BaseModel):
    date: str
    story: Story
