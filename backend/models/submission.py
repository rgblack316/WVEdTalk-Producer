"""Public story submissions — a reader sends a link (plus their name + email) for the desk to
consider in the next daily briefing and weekly episode. Submitting also subscribes the email to
the daily briefing. Timestamps are stored as UTC ISO strings so the dashboard can render them in
the viewer's local timezone. Mirrored in frontend/src/lib/types.ts."""

from typing import Optional

from pydantic import BaseModel, EmailStr


class SubmissionRequest(BaseModel):
    url: str
    name: str
    email: EmailStr
    turnstile_token: Optional[str] = None
    website: Optional[str] = ""  # honeypot — must stay empty (real users never see this field)


class StorySubmission(BaseModel):
    id: str
    url: str
    title: str = ""  # fetched <title> of the submitted article (best-effort), shown on the dashboard
    name: str
    email: str
    status: str = "new"  # new | used | archived | rejected
    thanked: bool = False
    note: str = ""  # private editor note (why it matters, follow-ups)
    used_in: Optional[str] = None  # e.g. "Daily briefing 2026-09-22" when auto-linked
    used_ref: Optional[str] = None  # in-app path to the briefing/episode it appeared in
    submitted_at: str  # UTC ISO
    updated_at: Optional[str] = None  # UTC ISO


class SubmissionUpdate(BaseModel):
    status: Optional[str] = None  # new | used | archived | rejected
    note: Optional[str] = None
