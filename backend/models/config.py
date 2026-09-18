"""Desk configuration: email digest recipients and watchlist terms.

Mirrored in frontend/src/lib/types.ts. Stored as a single singleton document.
"""

from typing import List

from pydantic import BaseModel, EmailStr


class DeskConfig(BaseModel):
    recipients: List[str] = []
    watch_terms: List[str] = []


class RecipientCreate(BaseModel):
    email: EmailStr


class WatchTermCreate(BaseModel):
    term: str
