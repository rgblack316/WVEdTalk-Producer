"""Public story submissions — a reader sends a link (plus their name + email) for the desk to
consider in the next daily briefing and weekly episode. Submitting also subscribes the email to
the daily briefing. Timestamps are stored as UTC ISO strings so the dashboard can render them in
the viewer's local timezone. Mirrored in frontend/src/lib/types.ts."""

from typing import List, Optional

from pydantic import BaseModel, EmailStr, Field


class SubmissionRequest(BaseModel):
    url: str
    name: str
    email: EmailStr
    turnstile_token: Optional[str] = None
    website: Optional[str] = ""  # honeypot — must stay empty (real users never see this field)


class Contributor(BaseModel):
    """A reader credited on a merged tip (the primary tip keeps a list of everyone who sent
    in the same article so no submitter loses credit when duplicates are consolidated)."""
    name: str = ""
    email: str = ""
    submitted_at: str = ""


class StorySubmission(BaseModel):
    id: str
    url: str
    title: str = ""  # fetched <title> of the submitted article (best-effort), shown on the dashboard
    name: str
    email: str
    status: str = "new"  # new | used | archived | rejected | merged
    thanked: bool = False
    note: str = ""  # private editor note (why it matters, follow-ups)
    used_in: Optional[str] = None  # e.g. "Daily briefing 2026-09-22" when auto-linked
    used_ref: Optional[str] = None  # in-app path to the briefing/episode it appeared in
    contributors: List[Contributor] = Field(default_factory=list)  # extra submitters credited after a merge
    merged_into: Optional[str] = None  # set on a duplicate folded into another tip (status == "merged")
    submitted_at: str  # UTC ISO
    updated_at: Optional[str] = None  # UTC ISO


class MergeRequest(BaseModel):
    primary_id: str  # the tip to keep
    duplicate_ids: List[str] = Field(default_factory=list)  # tips folded into the primary (credited, status=merged)


class SubmissionUpdate(BaseModel):
    status: Optional[str] = None  # new | used | archived | rejected
    note: Optional[str] = None
