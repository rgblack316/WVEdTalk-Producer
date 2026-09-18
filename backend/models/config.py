"""Desk configuration: email digest recipients, watchlist terms, script-length preference.

Mirrored in frontend/src/lib/types.ts. Stored as a single singleton document.
"""

from typing import List

from pydantic import BaseModel, EmailStr


class DeskConfig(BaseModel):
    recipients: List[str] = []
    watch_terms: List[str] = []
    script_length: str = "standard"  # concise | standard | full


class RecipientCreate(BaseModel):
    email: EmailStr


class WatchTermCreate(BaseModel):
    term: str


class ScriptLengthUpdate(BaseModel):
    value: str  # concise | standard | full
