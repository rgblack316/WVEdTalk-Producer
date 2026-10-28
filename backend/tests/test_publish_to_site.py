"""Publishing briefings to the public website: sanitizer, publish API, deploy-hook + wait flow, and
the email 'view on the web' link. These are self-contained unit tests (no live backend / MongoDB):
database and settings reads are monkeypatched."""

import os

os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "wvedtalk_test")
os.environ.setdefault("SESSION_SECRET", "unit-test-secret")

import pytest
from fastapi.testclient import TestClient

from lib import config_secrets, email_digest, site_publish
from lib.publish import public_briefing
from models.briefing import Briefing, SourceLink, Story


def _doc(**over):
    doc = {
        "id": "b1",
        "date": "2026-10-28",
        "status": "complete",
        "model": "gemini/x",
        "editor_note": "A busy day.",
        "error": "",
        "stories": [
            {
                "id": "s1", "section": "big_three", "rank": 1, "headline": "Big news", "location": "Kanawha",
                "classification": ["Policy"], "importance": 9, "podcast_potential": 8,
                "what_happened": "It happened.", "why_it_matters": "It matters.",
                "podcast_angle": "SECRET ANGLE", "questions": ["SECRET Q?"],
                "is_candidate": True, "is_excluded": True, "is_positive": True, "notes": "PRIVATE NOTE",
                "sources": [
                    {"title": "Good", "url": "https://example.com/a", "outlet": "Ex", "verified": True},
                    {"title": "Unverified", "url": "https://example.com/b", "outlet": "Ex", "verified": False},
                    {"title": "Bad scheme", "url": "javascript:alert(1)", "outlet": "Ex"},
                ],
            }
        ],
        "trends": [{"title": "T", "why_it_matters": "W", "evidence": ["e"], "missing_evidence": ["m"], "watch_next": "n"}],
        "podcast_ideas": [{"working_title": "SECRET IDEA"}],
        "source_log": [{"title": "Log", "url": "https://example.com/log", "outlet": "Ex", "verified": True}],
    }
    doc.update(over)
    return doc


# ---- sanitizer -------------------------------------------------------------

def test_public_briefing_keeps_stories_sources_trends():
    pb = public_briefing(_doc())
    assert pb["date"] == "2026-10-28"
    assert pb["editor_note"] == "A busy day."
    story = pb["stories"][0]
    assert story["headline"] == "Big news" and story["section"] == "big_three" and story["rank"] == 1
    assert story["what_happened"] == "It happened." and story["why_it_matters"] == "It matters."
    assert pb["trends"][0]["title"] == "T"
    assert pb["source_log"][0]["url"] == "https://example.com/log"


def test_public_briefing_strips_scores_podcast_content_and_private_fields():
    text = repr(public_briefing(_doc()))
    for leaked in ("SECRET ANGLE", "SECRET Q", "SECRET IDEA", "PRIVATE NOTE"):
        assert leaked not in text
    story = public_briefing(_doc())["stories"][0]
    for key in ("importance", "podcast_potential", "podcast_angle", "questions", "notes",
                "is_candidate", "is_excluded", "is_positive"):
        assert key not in story
    pb = public_briefing(_doc())
    for key in ("podcast_ideas", "model", "error", "status", "id"):
        assert key not in pb


def test_public_briefing_drops_unverified_and_non_http_sources():
    urls = [s["url"] for s in public_briefing(_doc())["stories"][0]["sources"]]
    assert urls == ["https://example.com/a"]


def test_public_briefing_skips_failed_runs():
    assert public_briefing(_doc(status="failed")) is None


# ---- publish API -----------------------------------------------------------

@pytest.fixture
def api(monkeypatch):
    import server
    from routers import publish as publish_router

    async def fake_load():
        return [_doc(), _doc(date="2026-10-27", status="failed")]

    async def fake_verify(candidate):
        return candidate == "good-token"

    monkeypatch.setattr(publish_router, "load_complete_briefings", fake_load)
    monkeypatch.setattr(config_secrets, "verify_publish_token", fake_verify)
    return TestClient(server.app)


def test_publish_endpoint_requires_token(api):
    assert api.get("/api/publish/briefings").status_code == 401
    assert api.get("/api/publish/briefings", headers={"Authorization": "Bearer nope"}).status_code == 401
    assert api.get("/api/publish/briefings", headers={"Authorization": "good-token"}).status_code == 401


def test_publish_endpoint_returns_sanitized_complete_briefings(api):
    r = api.get("/api/publish/briefings", headers={"Authorization": "Bearer good-token"})
    assert r.status_code == 200
    body = r.json()
    assert [b["date"] for b in body["briefings"]] == ["2026-10-28"]  # failed run excluded
    assert "PRIVATE NOTE" not in r.text and "podcast_potential" not in r.text


# ---- deploy hook + wait ----------------------------------------------------

def _patch_cfg(monkeypatch, *, hook="https://hooks.example/abc", site="https://wvedtalk.com"):
    async def get_hook():
        return hook

    async def get_site():
        return site

    monkeypatch.setattr(config_secrets, "get_deploy_hook", get_hook)
    monkeypatch.setattr(config_secrets, "get_site_url", get_site)


async def _no_sleep(_):
    return None


async def test_publish_skipped_when_no_hook(monkeypatch):
    _patch_cfg(monkeypatch, hook="")
    res = await site_publish.publish_and_wait("2026-10-28", wait=True, sleep=_no_sleep)
    assert res["configured"] is False and res["triggered"] is False


async def test_publish_waits_until_live(monkeypatch):
    _patch_cfg(monkeypatch)
    calls = {"hook": 0, "live": 0}

    async def trigger():
        calls["hook"] += 1
        return {"ok": True, "status": 201}

    async def live(date):
        calls["live"] += 1
        return calls["live"] >= 3

    monkeypatch.setattr(site_publish, "trigger_deploy", trigger)
    monkeypatch.setattr(site_publish, "is_live", live)
    res = await site_publish.publish_and_wait("2026-10-28", wait=True, sleep=_no_sleep)
    assert res["live"] is True and calls == {"hook": 1, "live": 3}


async def test_publish_times_out_without_raising(monkeypatch):
    _patch_cfg(monkeypatch)

    async def trigger():
        return {"ok": True, "status": 201}

    async def live(date):
        return False

    monkeypatch.setattr(site_publish, "trigger_deploy", trigger)
    monkeypatch.setattr(site_publish, "is_live", live)
    res = await site_publish.publish_and_wait("2026-10-28", wait=True, timeout=60, interval=20, sleep=_no_sleep)
    assert res["triggered"] is True and res["live"] is False and "did not show" in res["error"]


async def test_publish_without_wait_fires_hook_only(monkeypatch):
    _patch_cfg(monkeypatch)

    async def trigger():
        return {"ok": True, "status": 201}

    async def live(date):  # must not be polled
        raise AssertionError("is_live should not be called when wait=False")

    monkeypatch.setattr(site_publish, "trigger_deploy", trigger)
    monkeypatch.setattr(site_publish, "is_live", live)
    res = await site_publish.publish_and_wait("2026-10-28", wait=False, sleep=_no_sleep)
    assert res["triggered"] is True and res["live"] is None


async def test_publish_reports_hook_failure(monkeypatch):
    _patch_cfg(monkeypatch)

    async def trigger():
        return {"ok": False, "status": 500, "error": "Deploy hook returned HTTP 500."}

    monkeypatch.setattr(site_publish, "trigger_deploy", trigger)
    res = await site_publish.publish_and_wait("2026-10-28", wait=True, sleep=_no_sleep)
    assert res["triggered"] is False and "HTTP 500" in res["error"]


def test_valid_https_url():
    assert site_publish.valid_https_url("https://wvedtalk.com")
    assert not site_publish.valid_https_url("http://wvedtalk.com")
    assert not site_publish.valid_https_url("https://user:pw@wvedtalk.com")
    assert not site_publish.valid_https_url("wvedtalk.com")


# ---- email link ------------------------------------------------------------

async def test_email_links_to_website_when_site_url_set(monkeypatch):
    async def get_site():
        return "https://wvedtalk.com"

    monkeypatch.setattr(config_secrets, "get_site_url", get_site)
    monkeypatch.setattr(email_digest, "APP_URL", "https://news-desk.wvedtalk.com")
    briefing = Briefing(date="2026-10-28")
    url = await email_digest._web_url(briefing)
    assert url == "https://wvedtalk.com/daily/2026-10-28"
    html = email_digest._full_digest_html(
        Briefing(
            date="2026-10-28",
            stories=[Story(section="big_three", headline="H", sources=[SourceLink(title="t", url="https://example.com/x")])],
        ),
        url,
        unsubscribe_url="https://news-desk.wvedtalk.com/unsubscribe?email=a%40b.co&t=x",
    )
    email_digest._assert_safe_email("subject", html)  # the G2/G3 link gate must accept the website link
    assert 'href="https://wvedtalk.com/daily/2026-10-28"' in html


async def test_email_omits_web_link_without_site_url(monkeypatch):
    async def get_site():
        return ""

    monkeypatch.setattr(config_secrets, "get_site_url", get_site)
    monkeypatch.setattr(email_digest, "APP_URL", "https://news-desk.wvedtalk.com")
    assert await email_digest._web_url(Briefing(date="2026-10-28")) == ""
    html = email_digest._full_digest_html(
        Briefing(date="2026-10-28"), "",
        unsubscribe_url="https://news-desk.wvedtalk.com/unsubscribe?email=a%40b.co&t=x",
    )
    assert "View this briefing on the web" not in html
    email_digest._assert_safe_email("subject", html)
