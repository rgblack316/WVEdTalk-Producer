"""Email digest via Emergent's managed Resend integration.

Recipients come from server-side config; the HTML body is built here from a
server-side template (callers never supply markup) — see G4 in the playbook.
"""

import ipaddress
import logging
import os
import re
from html import escape
from html.parser import HTMLParser
from typing import List, Optional
from urllib.parse import quote, urlparse

import httpx

from lib.auth import make_unsub_token
from lib.db import db

logger = logging.getLogger(__name__)

# Managed email proxy — a CONSTANT, never read from env, so it survives deployment.
EMAIL_BASE_URL = "https://integrations.emergentagent.com"
EMAIL_KEY = os.environ.get("EMERGENT_EMAIL_KEY", "")
EMAIL_FROM_NAME = os.environ.get("EMAIL_FROM_NAME", "WV Education News Desk")
APP_URL = os.environ.get("APP_URL", "https://mountain-school-news.preview.emergentagent.com").rstrip("/")

_SHORTENERS = ("bit.ly", "tinyurl.com", "t.co", "is.gd", "cutt.ly", "goo.gl", "rebrand.ly")
_CRED_ASK = (
    "reply with your password", "reply with the code", "send your password", "cvv",
    "send us your password", "enter your password below", "confirm your card number",
    "your full card number", "seed phrase", "recovery phrase", "verify your card",
    "social security number", "confirm your bank details",
)
_HOSTISH = re.compile(r"\b(?:https?://)?((?:[a-z0-9-]+\.)+[a-z]{2,})", re.I)


def _host_ok(host: str) -> bool:
    if not host or "xn--" in host:
        return False
    try:
        ipaddress.ip_address(host)
        return False
    except ValueError:
        pass
    return not any(host == s or host.endswith("." + s) for s in _SHORTENERS)


def _same_site(shown: str, real: str) -> bool:
    return shown == real or real.endswith("." + shown) or shown.endswith("." + real)


class _EmailScan(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags, self.urls, self.anchors = set(), [], []
        self._href, self._text = None, []

    def handle_starttag(self, tag, attrs):
        self.tags.add(tag.lower())
        self.urls += [v for k, v in attrs if k.lower() in ("href", "src") and v]
        if tag.lower() == "a":
            self._href = dict((k.lower(), v) for k, v in attrs).get("href")
            self._text = []

    def handle_data(self, data):
        if self._href is not None:
            self._text.append(data)

    def handle_endtag(self, tag):
        if tag.lower() == "a" and self._href is not None:
            self.anchors.append((self._href, "".join(self._text)))
            self._href, self._text = None, []


def _assert_safe_email(subject: str, html: str) -> None:
    scan = _EmailScan()
    scan.feed(html)
    if scan.tags & {"form", "input", "textarea", "select"}:
        raise ValueError("No forms or input fields in email (G2)")
    body = f"{subject}\n{html}".lower()
    for p in _CRED_ASK:
        if p in body:
            raise ValueError(f"Email asks the recipient for credentials: {p!r} (G2)")
    for url in scan.urls:
        low = url.strip().lower()
        if low.startswith(("mailto:", "tel:", "cid:", "#")):
            continue
        if not low.startswith("https://"):
            raise ValueError(f"Email links/assets must be absolute https: {url!r} (G3)")
        host = urlparse(low).hostname or ""
        if not _host_ok(host) or urlparse(low).username is not None:
            raise ValueError(f"Shortened, numeric-host or credential-bearing URL: {url!r} (G3)")
    for href, text in scan.anchors:
        real = urlparse(href.strip().lower()).hostname or ""
        if not real:
            continue
        for m in _HOSTISH.finditer(text):
            if not _same_site(m.group(1).lower(), real):
                raise ValueError(f"Anchor text {m.group(1)!r} != real link host {real!r} (G3)")


async def _send_email(*, to: str, subject: str, html: str) -> Optional[str]:
    _assert_safe_email(subject, html)  # G2/G3 gate — never skip
    if not EMAIL_KEY:
        raise RuntimeError("EMERGENT_EMAIL_KEY is not configured")
    payload = {"to": [to], "subject": subject, "html": html, "from_name": EMAIL_FROM_NAME}
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{EMAIL_BASE_URL}/api/v1/email/send",
            headers={"X-Email-Key": EMAIL_KEY},
            json=payload,
        )
    resp.raise_for_status()
    return resp.json().get("id")


def _digest_html(briefing, unsubscribe_url: Optional[str] = None) -> str:
    """Build the HTML digest from the briefing (server-side template, no caller input)."""
    date = escape(briefing.date)
    big_three = [s for s in briefing.stories if s.section == "big_three"]
    url = f"{APP_URL}/briefings/{briefing.date}"

    rows = []
    for s in big_three:
        loc = escape(s.location) if s.location else ""
        imp = f" · Importance {s.importance}/10" if s.importance is not None else ""
        rows.append(
            f'<tr><td style="padding:12px 0;border-bottom:1px solid #e5e2d8;font-family:Georgia,serif">'
            f'<div style="font-size:11px;letter-spacing:.12em;text-transform:uppercase;color:#8a6a3b">'
            f'{loc}{imp}</div>'
            f'<div style="font-size:18px;font-weight:bold;color:#1f3a2e;margin-top:2px">{escape(s.headline)}</div>'
            f'<div style="font-family:Arial,sans-serif;font-size:14px;color:#444;margin-top:6px;line-height:1.5">'
            f'{escape(s.what_happened)}</div></td></tr>'
        )
    if not rows:
        rows.append(
            '<tr><td style="padding:12px 0;font-family:Arial,sans-serif;font-size:14px;color:#444">'
            f'{escape(briefing.editor_note or "A short edition today.")}</td></tr>'
        )

    other = sum(1 for s in briefing.stories if s.section != "big_three")
    note = escape(briefing.editor_note) if briefing.editor_note else ""

    return (
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        'style="max-width:640px;margin:0 auto;background:#fbfaf5"><tr><td style="padding:28px 24px">'
        '<div style="font-family:Georgia,serif;font-size:24px;font-weight:bold;color:#1f3a2e">'
        'WV Education News Desk</div>'
        f'<div style="font-family:Arial,sans-serif;font-size:12px;letter-spacing:.14em;'
        f'text-transform:uppercase;color:#8a6a3b;margin-top:4px">Daily Briefing · {date}</div>'
        + (
            f'<p style="font-family:Arial,sans-serif;font-size:14px;color:#555;line-height:1.6;'
            f'border-left:3px solid #b5652e;padding-left:12px;margin-top:16px">{note}</p>'
            if note else ""
        )
        + '<div style="font-family:Georgia,serif;font-size:16px;font-weight:bold;color:#1f3a2e;'
        'margin:24px 0 4px;border-bottom:2px solid #1f3a2e;padding-bottom:4px">The Big Three</div>'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0">'
        + "".join(rows)
        + "</table>"
        + f'<p style="font-family:Arial,sans-serif;font-size:13px;color:#666;margin-top:20px">'
        f'Plus {other} more stories across K-12, higher education, state policy and developing coverage.</p>'
        f'<p style="margin-top:20px"><a href="{url}" '
        'style="display:inline-block;background:#1f3a2e;color:#fff;text-decoration:none;'
        'font-family:Arial,sans-serif;font-size:14px;padding:11px 20px;border-radius:4px">'
        'Read the full briefing</a></p>'
        '<p style="font-family:Arial,sans-serif;font-size:12px;color:#999;margin-top:28px;'
        'border-top:1px solid #e5e2d8;padding-top:14px">'
        'Sent by WV Education News Desk, your statewide education research briefing. '
        'We never ask for passwords or payment details by email.</p>'
        + (
            '<p style="font-family:Arial,sans-serif;font-size:12px;color:#999;margin-top:10px">'
            'You are receiving this because you subscribed to the daily briefing. '
            f'<a href="{unsubscribe_url}" style="color:#8a6a3b">Unsubscribe</a>.</p>'
            if unsubscribe_url else ""
        )
        + "</td></tr></table>"
    )


async def send_digest(briefing, recipients: List[str]) -> int:
    """Send the daily digest — individually to each admin recipient AND each active public
    subscriber. Individual sends (never a group To/CC) keep every address hidden from the
    others, and each subscriber gets a personalized one-click unsubscribe link. Best-effort;
    returns how many succeeded."""
    subject = f"WV Education News Desk — Daily Briefing, {briefing.date}"
    admin = list(recipients or [])
    admin_set = {r.lower() for r in admin}

    docs = await db.subscribers.find({"active": True}, {"_id": 0, "email": 1}).to_list(5000)
    sub_emails = [
        d["email"] for d in docs if d.get("email") and d["email"].lower() not in admin_set
    ]

    sent = 0
    if admin:
        sent += await _fan_out(subject, _digest_html(briefing), admin)
    for email in sub_emails:
        unsub = f"{APP_URL}/unsubscribe?email={quote(email)}&t={make_unsub_token(email)}"
        try:
            await _send_email(to=email, subject=subject, html=_digest_html(briefing, unsubscribe_url=unsub))
            sent += 1
        except Exception as exc:
            logger.error("digest to subscriber %s failed: %s", email, exc)
    return sent


def _episode_html(episode) -> str:
    """Build the WVEdTalk weekly-episode email from the episode (server-side template)."""
    url = f"{APP_URL}/episodes/{episode.week_of}"
    span = f"{escape(episode.week_start)} – {escape(episode.week_end)}"
    summary = escape(episode.editorial_summary) if episode.editorial_summary else ""

    items = []
    for s in episode.selected_stories:
        loc = f' <span style="color:#8a6a3b">· {escape(s.location)}</span>' if s.location else ""
        items.append(
            f'<li style="font-family:Georgia,serif;font-size:16px;color:#1f3a2e;margin:8px 0">'
            f'{escape(s.story)}{loc}</li>'
        )
    words = len((episode.recording_script or "").split())
    minutes = max(1, round(words / 150))

    return (
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        'style="max-width:640px;margin:0 auto;background:#fbfaf5"><tr><td style="padding:28px 24px">'
        '<div style="font-family:Georgia,serif;font-size:24px;font-weight:bold;color:#1f3a2e">'
        'WVEdTalk — Weekly Episode Script</div>'
        f'<div style="font-family:Arial,sans-serif;font-size:12px;letter-spacing:.14em;'
        f'text-transform:uppercase;color:#8a6a3b;margin-top:4px">Week of {span}</div>'
        + (
            f'<p style="font-family:Arial,sans-serif;font-size:14px;color:#555;line-height:1.6;'
            f'border-left:3px solid #b5652e;padding-left:12px;margin-top:16px">{summary}</p>'
            if summary else ""
        )
        + '<div style="font-family:Georgia,serif;font-size:16px;font-weight:bold;color:#1f3a2e;'
        'margin:22px 0 4px;border-bottom:2px solid #1f3a2e;padding-bottom:4px">This week\u2019s stories</div>'
        f'<ul style="padding-left:20px;margin:8px 0">{"".join(items)}</ul>'
        f'<p style="font-family:Arial,sans-serif;font-size:13px;color:#666">'
        f'Recording script: ~{words} words · about {minutes} minutes of audio.</p>'
        f'<p style="margin-top:20px"><a href="{url}" '
        'style="display:inline-block;background:#1f3a2e;color:#fff;text-decoration:none;'
        'font-family:Arial,sans-serif;font-size:14px;padding:11px 20px;border-radius:4px">'
        'Open the full script</a></p>'
        '<p style="font-family:Arial,sans-serif;font-size:12px;color:#999;margin-top:28px;'
        'border-top:1px solid #e5e2d8;padding-top:14px">'
        'Sent by WV Education News Desk for WVEdTalk. We never ask for passwords or payment details by email.</p>'
        "</td></tr></table>"
    )


async def send_episode(episode, recipients: List[str]) -> int:
    """Send the weekly episode script email. Best-effort; returns how many succeeded."""
    if not recipients:
        return 0
    subject = f"WVEdTalk Weekly Script — Week of {episode.week_end}"
    html = _episode_html(episode)
    return await _fan_out(subject, html, recipients)


async def _fan_out(subject: str, html: str, recipients: List[str]) -> int:
    sent = 0
    for to in recipients:
        try:
            await _send_email(to=to, subject=subject, html=html)
            sent += 1
        except Exception as exc:
            logger.error("email to %s failed: %s", to, exc)
    return sent
