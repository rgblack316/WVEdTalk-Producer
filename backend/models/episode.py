"""WeeklyEpisode models for the WVEdTalk weekly producer. Mirrored in frontend/src/lib/types.ts."""

import uuid
from datetime import datetime, timezone
from typing import List, Optional

from pydantic import BaseModel, Field

from models.briefing import SourceLink


def _now() -> datetime:
    return datetime.now(timezone.utc)


class EpisodeStory(BaseModel):
    story: str = ""  # headline / title
    location: str = ""
    classification: List[str] = Field(default_factory=list)
    importance: Optional[int] = None
    podcast_potential: Optional[int] = None
    estimated_minutes: Optional[float] = None  # model's estimate of spoken time for this story
    why_it_made_the_cut: str = ""
    what_happened_during_week: str = ""
    what_remains_unresolved: str = ""
    why_it_matters: str = ""
    sources: List[SourceLink] = Field(default_factory=list)


class NotSelectedStory(BaseModel):
    story: str = ""
    location: str = ""
    why_considered: str = ""
    why_not_selected: str = ""


class LookAheadItem(BaseModel):
    label: str = ""
    date: str = ""


class WeeklyEpisode(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    week_of: str  # the Friday date, YYYY-MM-DD (ET) — the key
    week_start: str = ""
    week_end: str = ""
    generated_at: datetime = Field(default_factory=_now)
    status: str = "complete"  # complete | failed
    model: str = ""
    editorial_summary: str = ""
    selected_stories: List[EpisodeStory] = Field(default_factory=list)
    not_selected: List[NotSelectedStory] = Field(default_factory=list)
    look_ahead: List[LookAheadItem] = Field(default_factory=list)
    recording_script: str = ""
    chapters: List[str] = Field(default_factory=list)
    support_included: bool = True  # whether the Value 4 Value support read is in the script
    source_log: List[SourceLink] = Field(default_factory=list)
    # De-duplicated links to every article used to build the episode — the show-notes list
    # rendered as "Links to New Sources for This Week" after the recording script.
    episode_links: List[SourceLink] = Field(default_factory=list)
    error: str = ""


class EpisodeSummary(BaseModel):
    week_of: str
    week_start: str
    week_end: str
    generated_at: datetime
    status: str
    story_count: int
    selected_headlines: List[str] = Field(default_factory=list)


class ProduceStatus(BaseModel):
    running: bool = False
    week_of: str = ""
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    message: str = ""
    last_error: str = ""
