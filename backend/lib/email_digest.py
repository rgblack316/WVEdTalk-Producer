"""Email digest via Emergent's managed Resend integration.

Recipients come from server-side config; the HTML body is built here from a
server-side template (callers never supply markup) — see G4 in the playbook.
"""

import ipaddress
import logging
import os
import re
from datetime import datetime, timezone
from html import escape
from html.parser import HTMLParser
from typing import List, Optional
from urllib.parse import quote, urlparse

import httpx

from lib.auth import make_unsub_token
from lib.db import db

logger = logging.getLogger(__name__)

# Email sender identity + transport are configured in Settings → Integrations (see lib/mailer).
EMAIL_FROM_NAME = os.environ.get("EMAIL_FROM_NAME", "WV Education News Desk")
EMAIL_REPLY_TO = os.environ.get("EMAIL_REPLY_TO")  # optional default Reply-To
APP_URL = os.environ.get("APP_URL", "http://localhost").rstrip("/")


async def _resolve_base() -> str:
    """Refresh the module base URL from Settings → Integrations (public_url) before building any
    email, so links/assets use the public https URL (required by the G3 gate) rather than a local
    http://localhost that the gate — correctly — rejects."""
    global APP_URL
    from lib import config_secrets
    base = await config_secrets.get_public_url()
    if base:
        APP_URL = base.rstrip("/")
    return APP_URL

async def _web_url(briefing) -> str:
    """The public 'view on the web' link for a briefing: its page on the website, or "" when no
    website URL is configured (Settings -> Integrations -> Website publishing)."""
    from lib import config_secrets

    site = await config_secrets.get_site_url()
    return f"{site}/daily/{briefing.date}" if site else ""


_SHORTENERS = ("bit.ly", "tinyurl.com", "t.co", "is.gd", "cutt.ly", "goo.gl", "rebrand.ly")
# Imperative credential/payment REQUESTS directed at the recipient — genuine phishing
# signals, always fatal. Bare topical nouns ("social security number", "cvv", "seed
# phrase") are deliberately NOT listed on their own: legitimate WV education news routinely
# mentions them (data breaches, benefits, pensions), and a mention inside escaped, form-less
# prose asks the reader for nothing. Listing them as bare substrings silently dropped ENTIRE
# subscriber sends whenever a briefing story referenced one. Actual data-entry surfaces are
# already hard-blocked below via the form/input/textarea/select tag check, so a mention
# without a collection form carries no phishing risk.
_CRED_ASK = (
    "reply with your password", "reply with the code", "send your password",
    "send us your password", "enter your password below", "confirm your card number",
    "your full card number", "verify your card", "confirm your bank details",
    "send us your cvv", "enter your cvv", "your seed phrase", "your recovery phrase",
    "confirm your social security number", "enter your social security number",
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
    from lib import mailer

    return await mailer.send(to=to, subject=subject, html=html)


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


def _full_digest_html(briefing, web_url: str, unsubscribe_url: Optional[str] = None) -> str:
    """The COMPLETE briefing rendered inline for public subscribers (every section), plus a
    'view on the web' link to the briefing's website page (omitted when `web_url` is empty) and a
    one-click unsubscribe. No login required to read."""
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
        f'<p style="margin:18px 0 4px"><a href="{escape(web_url, quote=True)}" '
        'style="display:inline-block;background:#16305e;color:#fff;text-decoration:none;'
        'font-family:Arial,sans-serif;font-size:14px;padding:11px 20px;border-radius:4px">'
        'View this briefing on the web</a></p>'
        if web_url else ""
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


def _error_detail(exc: Exception) -> str:
    """A concise, admin-readable reason a send failed — includes the email proxy's HTTP status
    and response body when present (e.g. Resend's 'undeliverable_recipient'), else the exception
    text. This is what surfaces in delivery alerts and the test-send UI."""
    resp = getattr(exc, "response", None)
    if resp is not None:
        try:
            return f"HTTP {resp.status_code}: {(resp.text or '').strip()[:200]}"
        except Exception:
            return f"HTTP error {getattr(resp, 'status_code', '?')}"
    return (str(exc) or exc.__class__.__name__)[:200]


async def _record_delivery(date: str, email: str, status: str, error: str = "") -> None:
    """Upsert one subscriber delivery outcome so 'resend to who missed it' and the delivery
    alert have an audit trail. Best-effort — never raise into a send."""
    try:
        await db.digest_deliveries.update_one(
            {"date": date, "email": email.lower()},
            {"$set": {"date": date, "email": email.lower(), "status": status,
                      "error": (error or "")[:300],
                      "at": datetime.now(timezone.utc).isoformat()}},
            upsert=True,
        )
    except Exception:
        logger.exception("recording digest delivery failed (non-fatal)")


async def delivered_subscriber_emails(date: str) -> set:
    """Lower-cased subscriber emails that already received the digest for this date."""
    docs = await db.digest_deliveries.find(
        {"date": date, "status": "sent"}, {"_id": 0, "email": 1}
    ).to_list(10000)
    return {d["email"] for d in docs if d.get("email")}


async def _send_to_lists(briefing, admin: List[str], sub_emails: List[str], *,
                         record: bool, alert: bool):
    """Core fan-out: the compact digest to each admin recipient, the FULL briefing to each
    subscriber. Captures a per-address failure reason, records subscriber outcomes to the
    delivery log, and (optionally) emails admins when any subscriber send fails. Returns a
    DigestSendResult."""
    from models.config import DeliveryFailure, DigestSendResult

    await _resolve_base()
    subject = f"WVEdTalk News Desk — Daily Briefing, {briefing.date}"
    res = DigestSendResult(date=briefing.date)

    for to in admin:
        try:
            await _send_email(to=to, subject=subject, html=_digest_html(briefing))
            res.admin_sent += 1
        except Exception as exc:
            det = _error_detail(exc)
            res.admin_failed += 1
            res.failures.append(DeliveryFailure(email=to, error=det))
            logger.error("admin digest to %s failed: %s", to, det)

    web_url = await _web_url(briefing)
    for email in sub_emails:
        unsub = f"{APP_URL}/unsubscribe?email={quote(email)}&t={make_unsub_token(email)}"
        try:
            await _send_email(
                to=email, subject=subject,
                html=_full_digest_html(briefing, web_url, unsubscribe_url=unsub),
            )
            res.sub_sent += 1
            if record:
                await _record_delivery(briefing.date, email, "sent")
        except Exception as exc:
            det = _error_detail(exc)
            res.sub_failed += 1
            res.failures.append(DeliveryFailure(email=email, error=det))
            logger.error("digest to subscriber %s failed: %s", email, det)
            if record:
                await _record_delivery(briefing.date, email, "failed", det)

    if alert and res.sub_failed:
        try:
            await send_delivery_alert(res)
        except Exception:
            logger.exception("delivery-failure alert failed (non-fatal)")
    return res


async def send_digest(briefing, recipients: List[str], *, record: bool = True, alert: bool = True):
    """Send the daily digest — the compact edition to each admin recipient AND the full briefing
    to each active public subscriber. Individual sends (never a group To/CC) keep every address
    private and give each subscriber a personal one-click unsubscribe link. Returns a
    DigestSendResult with per-audience counts and a reason for every failed address."""
    admin = list(recipients or [])
    admin_set = {r.lower() for r in admin}
    docs = await db.subscribers.find({"active": True}, {"_id": 0, "email": 1}).to_list(5000)
    sub_emails = [
        d["email"] for d in docs if d.get("email") and d["email"].lower() not in admin_set
    ]
    return await _send_to_lists(briefing, admin, sub_emails, record=record, alert=alert)


async def resend_missed(briefing):
    """Resend the full briefing only to active subscribers who have NOT already received this
    date's digest (per the delivery log). Safe to run repeatedly. Returns a DigestSendResult."""
    delivered = await delivered_subscriber_emails(briefing.date)
    docs = await db.subscribers.find({"active": True}, {"_id": 0, "email": 1}).to_list(5000)
    missed = [
        d["email"] for d in docs if d.get("email") and d["email"].lower() not in delivered
    ]
    return await _send_to_lists(briefing, [], missed, record=True, alert=True)


async def send_test_digest(briefing, email: str) -> Optional[str]:
    """Send ONE subscriber-style full briefing to a test address (clearly marked [TEST]). Returns
    None on success, or the exact failure reason so the UI can show what went wrong. Does not
    touch the delivery log or fire alerts."""
    email = (email or "").strip()
    await _resolve_base()
    web_url = await _web_url(briefing)
    unsub = f"{APP_URL}/unsubscribe?email={quote(email)}&t={make_unsub_token(email)}"
    try:
        await _send_email(
            to=email,
            subject=f"[TEST] WVEdTalk News Desk — Daily Briefing, {briefing.date}",
            html=_full_digest_html(briefing, web_url, unsubscribe_url=unsub),
        )
        return None
    except Exception as exc:
        det = _error_detail(exc)
        logger.error("test digest to %s failed: %s", email, det)
        return det


def _delivery_alert_html(res) -> str:
    rows = []
    for f in res.failures[:20]:
        rows.append(
            '<tr>'
            f'<td style="padding:6px 10px;border-bottom:1px solid #e5e2d8;font-family:Arial,sans-serif;'
            f'font-size:13px;color:#16305e;word-break:break-all">{escape(f.email)}</td>'
            f'<td style="padding:6px 10px;border-bottom:1px solid #e5e2d8;font-family:Arial,sans-serif;'
            f'font-size:12px;color:#b91c1c">{escape(f.error)}</td></tr>'
        )
    more = len(res.failures) - 20
    extra = (
        f'<p style="font-family:Arial,sans-serif;font-size:12px;color:#666;margin-top:8px">'
        f'\u2026and {more} more.</p>' if more > 0 else ""
    )
    return (
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        'style="max-width:620px;margin:0 auto;background:#fbfaf5"><tr><td style="padding:28px 24px">'
        '<div style="font-family:Georgia,serif;font-size:20px;font-weight:bold;color:#16305e">'
        'WVEdTalk News Desk</div>'
        '<div style="font-family:Arial,sans-serif;font-size:12px;letter-spacing:.14em;'
        'text-transform:uppercase;color:#b91c1c;margin-top:6px">Subscriber email delivery issue</div>'
        f'<p style="font-family:Arial,sans-serif;font-size:15px;color:#222;margin-top:16px">'
        f'The daily briefing for <strong>{escape(res.date)}</strong> could not be delivered to '
        f'<strong>{res.sub_failed}</strong> subscriber(s). '
        f'{res.sub_sent} subscriber(s) and {res.admin_sent} desk recipient(s) received it.</p>'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        'style="margin-top:12px;background:#fff;border:1px solid #e5e2d8">'
        '<tr><th style="text-align:left;padding:6px 10px;font-family:Arial,sans-serif;font-size:11px;'
        'letter-spacing:.1em;text-transform:uppercase;color:#a67c00;border-bottom:2px solid #16305e">Address</th>'
        '<th style="text-align:left;padding:6px 10px;font-family:Arial,sans-serif;font-size:11px;'
        'letter-spacing:.1em;text-transform:uppercase;color:#a67c00;border-bottom:2px solid #16305e">Reason</th></tr>'
        + "".join(rows) + '</table>' + extra +
        '<p style="font-family:Arial,sans-serif;font-size:13px;color:#555;margin-top:16px">'
        'Addresses flagged "undeliverable" were blocked by the email provider (invalid or bouncing) \u2014 '
        'remove or correct them, then retry from Settings \u2192 "Resend today\'s briefing".</p>'
        f'<p style="margin:16px 0 0"><a href="{APP_URL}/settings" '
        'style="display:inline-block;background:#16305e;color:#fff;text-decoration:none;'
        'font-family:Arial,sans-serif;font-size:14px;padding:10px 18px;border-radius:4px">Open the desk</a></p>'
        '<p style="font-family:Arial,sans-serif;font-size:12px;color:#999;margin-top:24px;'
        'border-top:1px solid #e5e2d8;padding-top:12px">'
        'You are receiving this because you are an admin on WVEdTalk News Desk.</p>'
        '</td></tr></table>'
    )


async def send_delivery_alert(res) -> int:
    """Email every admin (real inbox) when one or more subscriber digest sends fail, so a silent
    partial miss never goes unnoticed. Best-effort; returns how many alerts were sent."""
    if not res.sub_failed:
        return 0
    await _resolve_base()
    admins = await db.users.find({"role": "admin"}, {"_id": 0, "email": 1}).to_list(200)
    tos = [u["email"] for u in admins if "@" in (u.get("email") or "")]
    if not tos:
        logger.warning("%d subscriber digest sends failed but no admin email for an alert", res.sub_failed)
        return 0
    subject = f"[WVEdTalk] {res.sub_failed} subscriber email(s) failed — {res.date}"
    html = _delivery_alert_html(res)
    _assert_safe_email(subject, html)
    return await _fan_out(subject, html, tos)


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
    await _resolve_base()
    subject = f"WVEdTalk Weekly Script — Week of {episode.week_end}"
    html = _episode_html(episode)
    return await _fan_out(subject, html, recipients)


def _alert_html(title: str, label: str, detail: str, *, heading: str = "Scheduled run failed",
                message: Optional[str] = None) -> str:
    detail = escape(detail or "No further detail was captured.")
    if message is None:
        message = (
            f'The scheduled <strong>{escape(title)}</strong> run for <strong>{escape(label)}</strong> '
            'did not complete.'
        )
    return (
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        'style="max-width:560px;margin:0 auto;background:#fbfaf5"><tr><td style="padding:28px 24px">'
        '<div style="font-family:Georgia,serif;font-size:20px;font-weight:bold;color:#16305e">'
        'WVEdTalk News Desk</div>'
        '<div style="font-family:Arial,sans-serif;font-size:12px;letter-spacing:.14em;'
        f'text-transform:uppercase;color:#b91c1c;margin-top:6px">{escape(heading)}</div>'
        f'<p style="font-family:Arial,sans-serif;font-size:15px;color:#222;margin-top:16px">'
        f'{message}</p>'
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
    await _resolve_base()
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


def _site_alert_html(label: str, detail: str) -> str:
    return _alert_html(
        "website publish", label, detail,
        heading="Website publish problem",
        message=(
            f"The briefing for <strong>{escape(label)}</strong> may not be on the website yet. "
            "Digest emails were still sent; their web link may not work until the website finishes rebuilding."
        ),
    )


async def send_site_publish_alert(*, label: str, detail: str) -> int:
    """Email every admin when publishing a briefing to the website did not complete."""
    await _resolve_base()
    admins = await db.users.find({"role": "admin"}, {"_id": 0, "email": 1}).to_list(200)
    tos = [u["email"] for u in admins if "@" in (u.get("email") or "")]
    if not tos:
        logger.warning("website publish problem for %s but no admin email is available for an alert", label)
        return 0
    subject = f"[WVEdTalk] Website publish problem ({label})"
    html = _site_alert_html(label, detail)
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
    await _resolve_base()
    subject = "Thank you for your WVEdTalk story submission"
    html = _thanks_html(name, url)
    _assert_safe_email(subject, html)
    return await _fan_out(subject, html, [email])


async def send_submission_rejection(*, name: str, email: str, url: str) -> int:
    """Email a reader a brief, kind 'not a fit this time' note when their tip is rejected."""
    email = (email or "").strip()
    if "@" not in email:
        return 0
    await _resolve_base()
    who = escape((name or "there").strip() or "there")
    link = escape((url or "").strip())
    subject = "About your WVEdTalk story submission"
    html = (
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        'style="max-width:560px;margin:0 auto;background:#fbfaf5"><tr><td style="padding:28px 24px">'
        f'<div style="text-align:center;margin-bottom:18px"><img src="{APP_URL}/wvedtalk-logo.png" '
        'alt="WVEdTalk News Desk" width="150" style="width:150px;height:auto;display:inline-block"/></div>'
        '<div style="font-family:Georgia,serif;font-size:20px;font-weight:bold;color:#16305e">Thanks for the tip</div>'
        f'<p style="font-family:Arial,sans-serif;font-size:15px;color:#222;margin-top:14px;line-height:1.6">'
        f'Hi {who}, thank you for sending us a story. After a look, it isn\'t a fit for our West Virginia '
        'education coverage this time — but we truly appreciate you thinking of us, and we hope you\'ll keep '
        'the tips coming.</p>'
        f'<div style="font-family:Arial,sans-serif;font-size:12px;color:#666;background:#fff;'
        f'border-left:3px solid #c8971b;padding:10px 12px;margin-top:12px;word-break:break-all">{link}</div>'
        '<p style="font-family:Arial,sans-serif;font-size:14px;color:#444;margin-top:16px;line-height:1.6">'
        'You are still subscribed to our daily briefing — every edition has a one-click unsubscribe link.</p>'
        '<p style="font-family:Arial,sans-serif;font-size:12px;color:#999;margin-top:24px;'
        'border-top:1px solid #e5e2d8;padding-top:12px">WVEdTalk News Desk · Statewide education research</p>'
        '</td></tr></table>'
    )
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
