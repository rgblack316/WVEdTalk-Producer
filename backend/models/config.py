"""Desk configuration: recipients, watchlist, script length, auto-lock, passcode.

DeskConfig is the client-visible shape. The passcode hash is stored in the same
document but is NOT part of this model, so it is never returned to the frontend.
"""

from datetime import datetime
from typing import List

from pydantic import BaseModel, EmailStr


class DeskConfig(BaseModel):
    recipients: List[str] = []
    watch_terms: List[str] = []
    script_length: str = "standard"  # concise | standard | full
    auto_lock_minutes: int = 0  # 0 = off
    auto_thank_on_use: bool = False  # auto-email a reader when their tip is auto-linked as used
    # Automatic run schedule, interpreted in the desk's home timezone (DST-aware).
    timezone: str = "America/New_York"  # IANA name
    daily_hour: int = 22  # 0-23
    daily_minute: int = 0  # 0-59
    weekly_dow: int = 4  # 0=Mon .. 6=Sun (default Friday)
    weekly_hour: int = 16  # 0-23
    weekly_minute: int = 0  # 0-59


class RecipientCreate(BaseModel):
    email: EmailStr


class WatchTermCreate(BaseModel):
    term: str


class ScriptLengthUpdate(BaseModel):
    value: str  # concise | standard | full


class AutoLockUpdate(BaseModel):
    minutes: int


class AutoThankUpdate(BaseModel):
    enabled: bool


class ScheduleUpdate(BaseModel):
    timezone: str
    daily_hour: int
    daily_minute: int
    weekly_dow: int
    weekly_hour: int
    weekly_minute: int


class RunLogEntry(BaseModel):
    """One recorded automatic or manual run. Timestamps are UTC ISO strings (with offset)
    so the frontend can render them in the browser's local timezone."""

    id: str
    kind: str  # daily | weekly
    trigger: str  # scheduled | manual
    status: str  # complete | failed
    label: str  # briefing date or episode week_of
    detail: str = ""
    started_at: str
    finished_at: str


class NextRuns(BaseModel):
    daily_next: str  # UTC ISO
    weekly_next: str  # UTC ISO
