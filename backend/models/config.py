"""Desk configuration: recipients, watchlist, script length, auto-lock, passcode.

DeskConfig is the client-visible shape. The passcode hash is stored in the same
document but is NOT part of this model, so it is never returned to the frontend.
"""

from datetime import datetime
from typing import List

from pydantic import BaseModel, EmailStr

# Canonical "Value 4 Value" support segment read at the end of the weekly script. Admins can
# override the wording via Settings (stored in desk_config.support_segment); this is the default.
DEFAULT_SUPPORT_SEGMENT = "\n\n".join(
    [
        "WVEdTalk is produced using a Value 4 Value model.",
        "What does that mean? It means WVEdTalk is made possible by listeners who believe the "
        "information we provide has value and want to help keep it going.",
        "There are three ways you can contribute: your time, your talent, or your treasure.",
        "Your time might mean sharing an episode with someone who needs to hear it, telling a friend "
        "about WVEdTalk, or simply taking a few minutes to send us a story we should know about.",
        "Your talent could mean helping us spread the word, providing information or expertise, "
        "suggesting a topic, or finding ways to make WVEdTalk better.",
        "And your treasure means making a financial contribution to help cover the costs of producing "
        "and maintaining the podcast. If WVEdTalk provides value to you and you\u2019d like to give "
        "something back, you can learn more at wvedtalk.com/support.",
        "There\u2019s another important way you can contribute: help us find the news.",
        "If you know about an education story, announcement, issue, or development happening anywhere "
        "in West Virginia that you think we should be watching, send it our way at wvedtalk.com/submit. "
        "The WVEdTalk News Desk reviews every submission and determines which stories may warrant "
        "further research and coverage.",
        "You don't have to contribute financially to be part of WVEdTalk. Your time, your talent, your "
        "treasure\u2014or simply helping us find the stories that matter\u2014all help keep this project going.",
        "Thanks for listening, and thanks for being part of WVEdTalk.",
    ]
)


class DeskConfig(BaseModel):
    recipients: List[str] = []
    watch_terms: List[str] = []
    script_length: str = "standard"  # concise | standard | full
    auto_lock_minutes: int = 0  # 0 = off
    auto_thank_on_use: bool = False  # auto-email a reader when their tip is auto-linked as used
    support_segment: str = DEFAULT_SUPPORT_SEGMENT  # editable "Value 4 Value" outro text
    support_default_on: bool = True  # include the support read on newly produced episodes
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


class SupportUpdate(BaseModel):
    segment: str
    default_on: bool


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
