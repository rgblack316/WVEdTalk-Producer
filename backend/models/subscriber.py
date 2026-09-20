"""Public newsletter subscribers for the daily briefing. Separate from the admin-managed
`recipients` in desk_config, so this can grow into a subscription service. Mirrored in
frontend/src/lib/types.ts."""

from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, EmailStr


class SubscribeRequest(BaseModel):
    email: EmailStr


class UnsubscribeRequest(BaseModel):
    email: EmailStr
    token: str


class Subscriber(BaseModel):
    email: str
    active: bool = True
    subscribed_at: Optional[datetime] = None
