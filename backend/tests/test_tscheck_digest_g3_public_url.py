"""Covers: digest sends (test-digest and send-digest) no longer fail the G3 'absolute https'
safety check now that Settings -> Integrations has a public https URL configured, and that
the public_url field is exposed/persisted correctly on the integrations settings endpoint.
"""

import httpx
import pytest

from .conftest import api_url

ADMIN_EMAIL = "admin@johnscreekstudios.com"
ADMIN_PASSWORD = "WVEd!Desk-Admin2026"

G3_MARKERS = ("absolute https", "(G3)", "http://localhost")


@pytest.fixture
def admin_client():
    with httpx.Client(base_url=api_url(), timeout=30.0) as c:
        r = c.post("/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
        assert r.status_code == 200, r.text
        assert r.json().get("authenticated") is True
        # the session cookie is marked Secure; httpx's cookie jar won't replay it over plain
        # http, so pin it onto the client headers explicitly for subsequent requests.
        session_cookie = r.cookies.get("wv_desk_session")
        assert session_cookie, "login did not set wv_desk_session cookie"
        c.headers["Cookie"] = f"wv_desk_session={session_cookie}"
        yield c


def test_send_test_digest_no_g3_error(admin_client):
    """POST /api/settings/test-digest as authenticated admin returns 200 and any failure
    reported must be a transport failure, never the G3 absolute-https gate."""
    r = admin_client.post("/settings/test-digest", json={"email": "tscheck-g3-digest@example.com"})
    assert r.status_code == 200, r.text
    body = r.json()
    err = body.get("error") or ""
    for marker in G3_MARKERS:
        assert marker not in err, f"G3 safety error leaked into test-digest response: {err!r}"
    # if it failed, it must be about the transport/provider not configured, not about links
    if not body.get("ok"):
        assert "transport" in err.lower() or "provider" in err.lower() or "resend" in err.lower() or "smtp" in err.lower(), err


def test_send_digest_no_g3_error(admin_client):
    """POST /api/settings/send-digest as admin returns a DigestSendResult; no per-address
    failure reason mentions absolute-https / G3. Transport failures (no provider configured)
    are expected and acceptable."""
    r = admin_client.post("/settings/send-digest")
    assert r.status_code == 200, r.text
    body = r.json()
    assert "failures" in body
    for failure in body["failures"]:
        reason = failure.get("error") or ""
        for marker in G3_MARKERS:
            assert marker not in reason, f"G3 safety error leaked into send-digest failure: {reason!r}"


def test_integrations_public_url_round_trip(admin_client):
    """GET /api/settings/integrations exposes public_url; POST persists a new value and the
    following GET reflects it. Restores the original value afterward (not a seeded-data mutation
    since we restore the known baseline)."""
    original_url = "https://mountain-school-news.preview.emergentagent.com"

    r = admin_client.get("/settings/integrations")
    assert r.status_code == 200, r.text
    before = r.json()
    assert "public_url" in before

    try:
        r2 = admin_client.post("/settings/integrations", json={"public_url": "https://example.org"})
        assert r2.status_code == 200, r2.text

        r3 = admin_client.get("/settings/integrations")
        assert r3.status_code == 200, r3.text
        assert r3.json().get("public_url") == "https://example.org"
    finally:
        r4 = admin_client.post("/settings/integrations", json={"public_url": original_url})
        assert r4.status_code == 200, r4.text
        r5 = admin_client.get("/settings/integrations")
        assert r5.json().get("public_url") == original_url
