"""Public, unauthenticated routes: token-validated share links + newsletter sign-up.
Mounted WITHOUT the auth guard. Share links carry an HMAC token; unsubscribe carries a
per-email HMAC token. Sign-up is idempotent, email-format validated, and IP-throttled."""

import re
import time
import uuid
from datetime import datetime, timezone
from html import unescape
from urllib.parse import parse_qs, urlparse

import httpx
from fastapi import APIRouter, HTTPException, Query, Request, Response
from fastapi.responses import JSONResponse

from lib import auth
from lib import turnstile
from lib.db import db
from lib.desk import _is_private_host
from models.briefing import Briefing
from models.subscriber import SubscribeRequest, UnsubscribeRequest
from models.submission import SubmissionRequest

router = APIRouter(tags=["public"])

# Light in-memory throttle for public sign-up (defense against abuse / G5).
_ATTEMPTS: dict[str, list[float]] = {}
_WINDOW = 300  # seconds
_MAX = 20


def _throttle(ip: str) -> None:
    now = time.time()
    hits = [t for t in _ATTEMPTS.get(ip, []) if now - t < _WINDOW]
    if len(hits) >= _MAX:
        raise HTTPException(status_code=429, detail="Too many attempts. Please try again shortly.")
    hits.append(now)
    _ATTEMPTS[ip] = hits


EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


async def _persist_subscriber(email: str) -> None:
    email = email.lower().strip()
    existing = await db.subscribers.find_one({"email": email})
    if existing:
        if not existing.get("active"):
            await db.subscribers.update_one({"email": email}, {"$set": {"active": True}})
    else:
        await db.subscribers.insert_one(
            {"email": email, "active": True, "subscribed_at": datetime.now(timezone.utc)}
        )


@router.get("/public/briefings/{date}", response_model=Briefing)
async def public_briefing(date: str, token: str = Query(default="")):
    if not auth.verify_share_token(date, token):
        raise HTTPException(status_code=403, detail="Invalid or expired share link")
    doc = await db.briefings.find_one({"date": date})
    if not doc:
        raise HTTPException(status_code=404, detail=f"No briefing for {date}")
    doc.pop("_id", None)
    return Briefing(**doc)


@router.post("/public/subscribe")
async def subscribe(body: SubscribeRequest, request: Request):
    _throttle(request.client.host if request.client else "unknown")
    await _persist_subscriber(str(body.email))
    # Same response whether new or existing — don't leak who is already subscribed.
    return {"ok": True, "message": "You're subscribed to the WVEdTalk News Desk daily briefing."}


def _valid_story_url(url: str) -> bool:
    p = urlparse(url)
    return p.scheme in ("http", "https") and bool(p.netloc)


async def _fetch_title(url: str) -> str:
    """Best-effort fetch of the submitted article's <title> for the dashboard (SSRF-guarded,
    short timeout). Returns "" on any failure — a missing title never blocks a submission."""
    try:
        host = urlparse(url).hostname or ""
        if not host or _is_private_host(host):
            return ""
        async with httpx.AsyncClient(
            follow_redirects=True, max_redirects=5, timeout=6.0,
            headers={"User-Agent": "Mozilla/5.0 (WV-Desk)"},
        ) as client:
            r = await client.get(url)
        m = re.search(r"<title[^>]*>(.*?)</title>", r.text or "", re.I | re.S)
        if not m:
            return ""
        return unescape(re.sub(r"\s+", " ", m.group(1)).strip())[:300]
    except Exception:
        return ""


async def _persist_submission(url: str, name: str, email: str, title: str = "") -> None:
    await db.submissions.insert_one(
        {
            "id": str(uuid.uuid4()),
            "url": url[:2000],
            "title": title[:300],
            "name": name[:120],
            "email": email.lower().strip(),
            "status": "new",
            "thanked": False,
            "note": "",
            "used_in": None,
            "used_ref": None,
            "submitted_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": None,
        }
    )


@router.get("/public/config")
async def public_config():
    """Public runtime config for the submit form — the Turnstile SITE key is public by design."""
    return {"turnstile_site_key": turnstile.SITE_KEY or None, "turnstile_enabled": turnstile.enabled()}


@router.post("/public/submit-story")
async def submit_story(body: SubmissionRequest, request: Request):
    """A reader submits a news link for the desk to consider. Submitting also subscribes their
    email to the daily briefing. The link is validated as a well-formed http(s) URL here — the
    research model verifies it independently before any story is included."""
    ip = request.client.host if request.client else "unknown"
    _throttle(ip)
    if (body.website or "").strip():  # honeypot: bots fill hidden fields — accept, store nothing
        return {"ok": True, "message": "Thank you! Your story has been submitted for the desk to consider."}
    if not await turnstile.verify(body.turnstile_token or "", ip if ip != "unknown" else None):
        raise HTTPException(status_code=400, detail="Verification failed. Please try again.")
    url = (body.url or "").strip()
    if not _valid_story_url(url):
        raise HTTPException(status_code=422, detail="Please submit a valid link starting with http:// or https://")
    name = (body.name or "").strip()
    if not name:
        raise HTTPException(status_code=422, detail="Please include your name.")
    email = str(body.email).lower().strip()
    await _persist_submission(url, name, email, await _fetch_title(url))
    await _persist_subscriber(email)  # submitting opts them into the daily briefing
    return {
        "ok": True,
        "message": "Thank you! Your story has been submitted for the desk to consider, and you're now subscribed to the daily briefing.",
    }


@router.post("/public/unsubscribe")
async def unsubscribe(body: UnsubscribeRequest):
    email = str(body.email).lower().strip()
    if not auth.verify_unsub_token(email, body.token):
        raise HTTPException(status_code=403, detail="This unsubscribe link is invalid.")
    await db.subscribers.update_one({"email": email}, {"$set": {"active": False}})
    return {"ok": True, "message": "You've been unsubscribed. You won't receive further briefings."}


@router.options("/public/embed-subscribe")
async def embed_subscribe_options():
    return Response(
        status_code=204,
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type",
        },
    )


@router.post("/public/embed-subscribe")
async def embed_subscribe(request: Request):
    """Cross-origin sign-up target for the embeddable widget on external sites. Accepts
    application/x-www-form-urlencoded (so a no-CORS form submit works from any origin) or JSON."""
    _throttle(request.client.host if request.client else "unknown")
    ctype = request.headers.get("content-type", "")
    email = ""
    try:
        if "application/json" in ctype:
            data = await request.json()
            email = str((data or {}).get("email", ""))
        else:
            raw = (await request.body()).decode("utf-8", "ignore")
            email = parse_qs(raw).get("email", [""])[0]
    except Exception:
        email = ""
    email = email.strip().lower()
    cors = {"Access-Control-Allow-Origin": "*"}
    if not email or not EMAIL_RE.match(email):
        return JSONResponse(
            {"ok": False, "message": "A valid email address is required."}, status_code=400, headers=cors
        )
    await _persist_subscriber(email)
    return JSONResponse(
        {"ok": True, "message": "You're subscribed to the WVEdTalk daily briefing."}, headers=cors
    )


@router.options("/public/embed-submit-story")
async def embed_submit_story_options():
    return Response(
        status_code=204,
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type",
        },
    )


@router.post("/public/embed-submit-story")
async def embed_submit_story(request: Request):
    """Cross-origin story-tip target for the embeddable widget on external sites. Accepts
    x-www-form-urlencoded (no-CORS form submit) or JSON. Honeypot-guarded (Turnstile can't run
    cross-origin here); the research model still verifies every link before it is used."""
    _throttle(request.client.host if request.client else "unknown")
    ctype = request.headers.get("content-type", "")
    url = name = email = hp = ""
    try:
        if "application/json" in ctype:
            data = await request.json() or {}
            url = str(data.get("url", ""))
            name = str(data.get("name", ""))
            email = str(data.get("email", ""))
            hp = str(data.get("website", ""))
        else:
            raw = (await request.body()).decode("utf-8", "ignore")
            q = parse_qs(raw)
            url = q.get("url", [""])[0]
            name = q.get("name", [""])[0]
            email = q.get("email", [""])[0]
            hp = q.get("website", [""])[0]
    except Exception:
        url = name = email = hp = ""
    cors = {"Access-Control-Allow-Origin": "*"}
    if hp.strip():  # honeypot
        return JSONResponse({"ok": True, "message": "Thanks! Your story has been submitted."}, headers=cors)
    url, name, email = url.strip(), name.strip(), email.strip().lower()
    if not _valid_story_url(url) or not name or not EMAIL_RE.match(email):
        return JSONResponse(
            {"ok": False, "message": "A valid story link, your name, and a valid email are required."},
            status_code=400,
            headers=cors,
        )
    await _persist_submission(url, name, email, await _fetch_title(url))
    await _persist_subscriber(email)
    return JSONResponse(
        {"ok": True, "message": "Thanks! Your story has been submitted for the desk to consider."}, headers=cors
    )
