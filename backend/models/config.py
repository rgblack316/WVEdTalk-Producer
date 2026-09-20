"""Desk configuration: recipients, watchlist, script length, auto-lock, passcode.

DeskConfig is the client-visible shape. The passcode hash is stored in the same
document but is NOT part of this model, so it is never returned to the frontend.
"""

from typing import List

from pydantic import BaseModel, EmailStr


class DeskConfig(BaseModel):
    recipients: List[str] = []
    watch_terms: List[str] = []
    script_length: str = "standard"  # concise | standard | full
    auto_lock_minutes: int = 0  # 0 = off


class RecipientCreate(BaseModel):
    email: EmailStr


class WatchTermCreate(BaseModel):
    term: str


class ScriptLengthUpdate(BaseModel):
    value: str  # concise | standard | full


class AutoLockUpdate(BaseModel):
    minutes: int
