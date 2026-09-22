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

from lib.auth import make_share_token, make_unsub_token
from lib.db import db

logger = logging.getLogger(__name__)

# Managed email proxy — a CONSTANT, never read from env, so it survives deployment.
EMAIL_BASE_URL = "https://integrations.emergentagent.com"
EMAIL_KEY = os.environ.get("EMERGENT_EMAIL_KEY", "")
EMAIL_FROM_NAME = os.environ.get("EMAIL_FROM_NAME", "WVEdTalk News Desk")
EMAIL_REPLY_TO = os.environ.get("EMAIL_REPLY_TO")  # maps to Reply-To (contact_email)
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
    if EMAIL_REPLY_TO:
        payload["contact_email"] = EMAIL_REPLY_TO
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
            f'<div style="font-size:11px;letter-spacing:.12em;text-transform:uppercase;color:#a67c00">'
            f'{loc}{imp}</div>'
            f'<div style="font-size:18px;font-weight:bold;color:#16305e;margin-top:2px">{escape(s.headline)}</div>'
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
        f'<div style="text-align:center;margin-bottom:18px"><img src="{APP_URL}/wvedtalk-logo.png" alt="WVEdTalk News Desk" width="150" style="width:150px;height:auto;display:inline-block"/></div>'
        '<div style="font-family:Georgia,serif;font-size:24px;font-weight:bold;color:#16305e">'
        'WVEdTalk News Desk</div>'
        f'<div style="font-family:Arial,sans-serif;font-size:12px;letter-spacing:.14em;'
        f'text-transform:uppercase;color:#a67c00;margin-top:4px">Daily Briefing · {date}</div>'
        + (
            f'<p style="font-family:Arial,sans-serif;font-size:14px;color:#555;line-height:1.6;'
            f'border-left:3px solid #c8971b;padding-left:12px;margin-top:16px">{note}</p>'
            if note else ""
        )
        + '<div style="font-family:Georgia,serif;font-size:16px;font-weight:bold;color:#16305e;'
        'margin:24px 0 4px;border-bottom:2px solid #16305e;padding-bottom:4px">The Big Three</div>'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0">'
        + "".join(rows)
        + "</table>"
        + f'<p style="font-family:Arial,sans-serif;font-size:13px;color:#666;margin-top:20px">'
        f'Plus {other} more stories across K-12, higher education, state policy and developing coverage.</p>'
        f'<p style="margin-top:20px"><a href="{url}" '
        'style="display:inline-block;background:#16305e;color:#fff;text-decoration:none;'
        'font-family:Arial,sans-serif;font-size:14px;padding:11px 20px;border-radius:4px">'
        'Read the full briefing</a></p>'
        '<p style="font-family:Arial,sans-serif;font-size:12px;color:#999;margin-top:28px;'
        'border-top:1px solid #e5e2d8;padding-top:14px">'
        'Sent by WVEdTalk News Desk, your statewide education research briefing. '
        'We never ask for passwords or payment details by email.</p>'
        + (
            '<p style="font-family:Arial,sans-serif;font-size:12px;color:#999;margin-top:10px">'
            'You are receiving this because you subscribed to the daily briefing. '
            f'<a href="{unsubscribe_url}" style="color:#a67c00">Unsubscribe</a>.</p>'
            if unsubscribe_url else ""
        )
        + "</td></tr></table>"
    )


# ---- full briefing email (public subscribers) --------------------------------

# Render order + display labels for the full-briefing email.
_SECTIONS = [
    ("big_three", "The Big Three"),
    ("developing", "Developing Stories"),
    ("state_policy", "State Policy & Politics"),
    ("k12", "K-12 Education"),
    ("higher_ed", "Higher Education"),
    ("other", "Other Significant Stories"),
]


def _safe_source_links(sources) -> str:
    """Render source anchors that are GUARANTEED to pass _assert_safe_email: only https
    links to non-shortener, non-numeric hosts, with the host itself as the anchor text
    (so shown-host always == real-host). Anything unsafe is dropped, never raised — a
    single bad source URL must not block the whole subscriber send."""
    parts = []
    for s in sources or []:
        url = (getattr(s, "url", "") or "").strip()
        if not url.lower().startswith("https://"):
            continue
        parsed = urlparse(url)
        host = parsed.hostname or ""
        if not _host_ok(host) or parsed.username is not None:
            continue
        title = escape((getattr(s, "title", "") or "").strip())
        label = escape(host)
        prefix = f"{title} — " if title else ""
        parts.append(
            f'<div style="font-family:Arial,sans-serif;font-size:12px;color:#666;margin-top:4px">'
            f'{prefix}<a href="{url}" style="color:#a67c00">{label}</a></div>'
        )
    return "".join(parts)


def _field(label: str, value: str) -> str:
    value = (value or "").strip()
    if not value:
        return ""
    return (
        f'<div style="font-family:Arial,sans-serif;font-size:13px;color:#444;margin-top:8px;line-height:1.55">'
        f'<span style="color:#a67c00;font-weight:bold">{escape(label)}: </span>{escape(value)}</div>'
    )


def _story_block(s) -> str:
    loc = escape(s.location) if s.location else ""
    badges = []
    if s.classification:
        badges.append(" / ".join(escape(c) for c in s.classification))
    if s.importance is not None:
        badges.append(f"Importance {s.importance}/10")
    if s.podcast_potential is not None:
        badges.append(f"Podcast {s.podcast_potential}/10")
    meta = " · ".join([b for b in ([loc] if loc else []) + badges if b])

    body = _field("What happened", s.what_happened) + _field("Why it matters", s.why_it_matters)
    # Developing-story fields, when present.
    body += _field("What is new", s.what_is_new)
    body += _field("Previously known", s.previously_known)
    body += _field("Unresolved", s.unresolved)
    body += _field("What to watch next", s.watch_next)

    return (
        '<div style="padding:14px 0;border-bottom:1px solid #e5e2d8">'
        + (
            f'<div style="font-family:Arial,sans-serif;font-size:11px;letter-spacing:.1em;'
            f'text-transform:uppercase;color:#a67c00">{meta}</div>' if meta else ""
        )
        + f'<div style="font-family:Georgia,serif;font-size:17px;font-weight:bold;color:#16305e;margin-top:2px">'
        f'{escape(s.headline)}</div>'
        + body
        + _safe_source_links(s.sources)
        + "</div>"
    )


def _full_digest_html(briefing, share_url: str, unsubscribe_url: Optional[str] = None) -> str:
    """The COMPLETE briefing rendered inline for public subscribers (every section), plus a
    public 'view on the web' share link and a one-click unsubscribe. No login required to read."""
    date = escape(briefing.date)
    note = escape(briefing.editor_note) if briefing.editor_note else ""

    sections_html = []
    for key, label in _SECTIONS:
        stories = [s for s in briefing.stories if s.section == key]
        if not stories:
            continue
        sections_html.append(
            f'<div style="font-family:Georgia,serif;font-size:16px;font-weight:bold;color:#16305e;'
            f'margin:26px 0 2px;border-bottom:2px solid #16305e;padding-bottom:4px">{escape(label)}</div>'
            + "".join(_story_block(s) for s in stories)
        )
    if not sections_html:
        sections_html.append(
            '<p style="font-family:Arial,sans-serif;font-size:14px;color:#444;margin-top:16px">'
            f'{escape(briefing.editor_note or "A short edition today — no major developments to report.")}</p>'
        )

    share_btn = (
        f'<p style="margin:18px 0 4px"><a href="{share_url}" '
        'style="display:inline-block;background:#16305e;color:#fff;text-decoration:none;'
        'font-family:Arial,sans-serif;font-size:14px;padding:11px 20px;border-radius:4px">'
        'View this briefing on the web</a></p>'
    )

    return (
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        'style="max-width:640px;margin:0 auto;background:#fbfaf5"><tr><td style="padding:28px 24px">'
        f'<div style="text-align:center;margin-bottom:18px"><img src="{APP_URL}/wvedtalk-logo.png" alt="WVEdTalk News Desk" width="150" style="width:150px;height:auto;display:inline-block"/></div>'
        '<div style="font-family:Georgia,serif;font-size:24px;font-weight:bold;color:#16305e">'
        'WVEdTalk News Desk</div>'
        f'<div style="font-family:Arial,sans-serif;font-size:12px;letter-spacing:.14em;'
        f'text-transform:uppercase;color:#a67c00;margin-top:4px">Daily Briefing · {date}</div>'
        + (
            f'<p style="font-family:Arial,sans-serif;font-size:14px;color:#555;line-height:1.6;'
            f'border-left:3px solid #c8971b;padding-left:12px;margin-top:16px">{note}</p>'
            if note else ""
        )
        + share_btn
        + "".join(sections_html)
        + '<p style="font-family:Arial,sans-serif;font-size:12px;color:#999;margin-top:28px;'
        'border-top:1px solid #e5e2d8;padding-top:14px">'
        'Sent by WVEdTalk News Desk, your statewide education research briefing. '
        'We never ask for passwords or payment details by email.</p>'
        + (
            '<p style="font-family:Arial,sans-serif;font-size:12px;color:#999;margin-top:10px">'
            'You are receiving this because you subscribed to the daily briefing. '
            f'<a href="{unsubscribe_url}" style="color:#a67c00">Unsubscribe</a>.</p>'
            if unsubscribe_url else ""
        )
        + "</td></tr></table>"
    )


async def send_digest(briefing, recipients: List[str]) -> int:
    """Send the daily digest — individually to each admin recipient AND each active public
    subscriber. Individual sends (never a group To/CC) keep every address hidden from the
    others, and each subscriber gets a personalized one-click unsubscribe link. Best-effort;
    returns how many succeeded."""
    subject = f"WVEdTalk News Desk — Daily Briefing, {briefing.date}"
    admin = list(recipients or [])
    admin_set = {r.lower() for r in admin}

    docs = await db.subscribers.find({"active": True}, {"_id": 0, "email": 1}).to_list(5000)
    sub_emails = [
        d["email"] for d in docs if d.get("email") and d["email"].lower() not in admin_set
    ]

    sent = 0
    if admin:
        sent += await _fan_out(subject, _digest_html(briefing), admin)
    share_url = f"{APP_URL}/share/briefing/{briefing.date}?t={make_share_token(briefing.date)}"
    for email in sub_emails:
        unsub = f"{APP_URL}/unsubscribe?email={quote(email)}&t={make_unsub_token(email)}"
        try:
            await _send_email(
                to=email,
                subject=subject,
                html=_full_digest_html(briefing, share_url, unsubscribe_url=unsub),
            )
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
        loc = f' <span style="color:#a67c00">· {escape(s.location)}</span>' if s.location else ""
        items.append(
            f'<li style="font-family:Georgia,serif;font-size:16px;color:#16305e;margin:8px 0">'
            f'{escape(s.story)}{loc}</li>'
        )
    words = len((episode.recording_script or "").split())
    minutes = max(1, round(words / 150))

    return (
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        'style="max-width:640px;margin:0 auto;background:#fbfaf5"><tr><td style="padding:28px 24px">'
        f'<div style="text-align:center;margin-bottom:18px"><img src="{APP_URL}/wvedtalk-logo.png" alt="WVEdTalk News Desk" width="150" style="width:150px;height:auto;display:inline-block"/></div>'
        '<div style="font-family:Georgia,serif;font-size:24px;font-weight:bold;color:#16305e">'
        'WVEdTalk — Weekly Episode Script</div>'
        f'<div style="font-family:Arial,sans-serif;font-size:12px;letter-spacing:.14em;'
        f'text-transform:uppercase;color:#a67c00;margin-top:4px">Week of {span}</div>'
        + (
            f'<p style="font-family:Arial,sans-serif;font-size:14px;color:#555;line-height:1.6;'
            f'border-left:3px solid #c8971b;padding-left:12px;margin-top:16px">{summary}</p>'
            if summary else ""
        )
        + '<div style="font-family:Georgia,serif;font-size:16px;font-weight:bold;color:#16305e;'
        'margin:22px 0 4px;border-bottom:2px solid #16305e;padding-bottom:4px">This week\u2019s stories</div>'
        f'<ul style="padding-left:20px;margin:8px 0">{"".join(items)}</ul>'
        f'<p style="font-family:Arial,sans-serif;font-size:13px;color:#666">'
        f'Recording script: ~{words} words · about {minutes} minutes of audio.</p>'
        f'<p style="margin-top:20px"><a href="{url}" '
        'style="display:inline-block;background:#16305e;color:#fff;text-decoration:none;'
        'font-family:Arial,sans-serif;font-size:14px;padding:11px 20px;border-radius:4px">'
        'Open the full script</a></p>'
        '<p style="font-family:Arial,sans-serif;font-size:12px;color:#999;margin-top:28px;'
        'border-top:1px solid #e5e2d8;padding-top:14px">'
        'Sent by WVEdTalk News Desk. We never ask for passwords or payment details by email.</p>'
        "</td></tr></table>"
    )


async def send_episode(episode, recipients: List[str]) -> int:
    """Send the weekly episode script email. Best-effort; returns how many succeeded."""
    if not recipients:
        return 0
    subject = f"WVEdTalk Weekly Script — Week of {episode.week_end}"
    html = _episode_html(episode)
    return await _fan_out(subject, html, recipients)


def _alert_html(title: str, label: str, detail: str) -> str:
    detail = escape(detail or "No further detail was captured.")
    return (
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        'style="max-width:560px;margin:0 auto;background:#fbfaf5"><tr><td style="padding:28px 24px">'
        '<div style="font-family:Georgia,serif;font-size:20px;font-weight:bold;color:#16305e">'
        'WVEdTalk News Desk</div>'
        '<div style="font-family:Arial,sans-serif;font-size:12px;letter-spacing:.14em;'
        'text-transform:uppercase;color:#b91c1c;margin-top:6px">Scheduled run failed</div>'
        f'<p style="font-family:Arial,sans-serif;font-size:15px;color:#222;margin-top:16px">'
        f'The scheduled <strong>{escape(title)}</strong> run for <strong>{escape(label)}</strong> '
        'did not complete.</p>'
        f'<div style="font-family:Arial,sans-serif;font-size:13px;color:#444;background:#fff;'
        f'border-left:3px solid #b91c1c;padding:12px 14px;margin-top:12px;line-height:1.55">{detail}</div>'
        '<p style="font-family:Arial,sans-serif;font-size:13px;color:#555;margin-top:16px">'
        'Open the desk to review the run history and try again manually.</p>'
        f'<p style="margin:16px 0 0"><a href="{APP_URL}/settings" '
        'style="display:inline-block;background:#16305e;color:#fff;text-decoration:none;'
        'font-family:Arial,sans-serif;font-size:14px;padding:10px 18px;border-radius:4px">'
        'Open the desk</a></p>'
        '<p style="font-family:Arial,sans-serif;font-size:12px;color:#999;margin-top:24px;'
        'border-top:1px solid #e5e2d8;padding-top:12px">'
        'You are receiving this because you are an admin on WVEdTalk News Desk.</p>'
        '</td></tr></table>'
    )


async def send_failure_alert(*, kind: str, label: str, detail: str) -> int:
    """Email every admin when a SCHEDULED run fails, so a silent miss never goes unnoticed.
    Only real email-address admins are targeted (a fresh 'admin' username has no inbox)."""
    admins = await db.users.find({"role": "admin"}, {"_id": 0, "email": 1}).to_list(200)
    tos = [u["email"] for u in admins if "@" in (u.get("email") or "")]
    if not tos:
        logger.warning("scheduled %s run failed but no admin email is available for an alert", kind)
        return 0
    title = "daily briefing" if kind == "daily" else "weekly script"
    subject = f"[WVEdTalk] Scheduled {title} run failed ({label})"
    html = _alert_html(title, label, detail)
    _assert_safe_email(subject, html)
    return await _fan_out(subject, html, tos)


def _thanks_html(name: str, url: str) -> str:
    who = escape((name or "there").strip() or "there")
    link = escape((url or "").strip())
    return (
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        'style="max-width:560px;margin:0 auto;background:#fbfaf5"><tr><td style="padding:28px 24px">'
        f'<div style="text-align:center;margin-bottom:18px"><img src="{APP_URL}/wvedtalk-logo.png" '
        'alt="WVEdTalk News Desk" width="150" style="width:150px;height:auto;display:inline-block"/></div>'
        '<div style="font-family:Georgia,serif;font-size:20px;font-weight:bold;color:#16305e">Thank you!</div>'
        f'<p style="font-family:Arial,sans-serif;font-size:15px;color:#222;margin-top:14px;line-height:1.6">'
        f'Hi {who}, thank you for sending the WVEdTalk News Desk a West Virginia education story. '
        'We used it as we put together our coverage — submissions like yours help us cover education '
        'across all 55 counties, not just the biggest institutions.</p>'
        f'<div style="font-family:Arial,sans-serif;font-size:12px;color:#666;background:#fff;'
        f'border-left:3px solid #c8971b;padding:10px 12px;margin-top:12px;word-break:break-all">{link}</div>'
        '<p style="font-family:Arial,sans-serif;font-size:14px;color:#444;margin-top:16px;line-height:1.6">'
        'You are subscribed to our daily briefing — every edition has a one-click unsubscribe link. '
        'Keep the tips coming!</p>'
        '<p style="font-family:Arial,sans-serif;font-size:12px;color:#999;margin-top:24px;'
        'border-top:1px solid #e5e2d8;padding-top:12px">WVEdTalk News Desk · Statewide education research</p>'
        '</td></tr></table>'
    )


async def send_submission_thanks(*, name: str, email: str, url: str) -> int:
    """Email a reader to thank them when their submitted story is used. Returns count sent (0 if
    the address is unusable)."""
    email = (email or "").strip()
    if "@" not in email:
        return 0
    subject = "Thank you for your WVEdTalk story submission"
    html = _thanks_html(name, url)
    _assert_safe_email(subject, html)
    return await _fan_out(subject, html, [email])


async def _fan_out(subject: str, html: str, recipients: List[str]) -> int:
    sent = 0
    for to in recipients:
        try:
            await _send_email(to=to, subject=subject, html=html)
            sent += 1
        except Exception as exc:
            logger.error("email to %s failed: %s", to, exc)
    return sent
