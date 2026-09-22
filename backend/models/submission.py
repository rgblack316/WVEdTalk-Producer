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


class StorySubmission(BaseModel):
    id: str
    url: str
    name: str
    email: str
    status: str = "new"  # new | used | archived
    thanked: bool = False
    submitted_at: str  # UTC ISO
    updated_at: Optional[str] = None  # UTC ISO


class SubmissionStatusUpdate(BaseModel):
    status: str  # new | used | archived
