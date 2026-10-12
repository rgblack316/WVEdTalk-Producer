"""Criterion: Authenticated session is recognized on protected API.

Once logged in via POST /api/auth/login, GET /api/auth/me returns
authenticated=true with the user's email/role (session cookie carried
automatically by the httpx client across requests). Also covers that
invalid credentials are rejected with 401 and do not create a session,
and that logout flips /api/auth/me back to authenticated=false.

Note: this preview's session cookie is set with Secure=True (derived from
APP_URL being https, per the login-cookie-fix spec deviations). httpx's
cookie jar — like a real browser — will not persist/resend a Secure cookie
over a plain-http connection, so this test deliberately targets the public
https ingress (APP_URL) rather than http://localhost:8001, to match how a
real browser session actually works on this deployment.
"""

import os
from pathlib import Path

import httpx


def _read_app_url() -> str:
    """APP_URL isn't exported to the shell; the backend process loads it from .env itself."""
    env_path = Path(__file__).resolve().parents[1] / ".env"
    try:
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line.startswith("APP_URL="):
                return line.split("=", 1)[1].strip().strip('"')
    except OSError:
        pass
    return ""


APP_URL = os.environ.get("APP_URL", "").strip() or _read_app_url()
BACKEND_URL = APP_URL if APP_URL.startswith("https://") else os.environ.get("BACKEND_URL", "http://localhost:8001")
API_URL = f"{BACKEND_URL}/api"

ADMIN_EMAIL = "admin@johnscreekstudios.com"
ADMIN_PASSWORD = "WVEd!Desk-Admin2026"


def test_login_then_me_reports_authenticated():
    with httpx.Client(base_url=API_URL, timeout=30.0) as c:
        resp = c.post("/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
        assert resp.status_code == 200, f"login failed: {resp.status_code} {resp.text}"
        body = resp.json()
        assert body["authenticated"] is True
        assert body["user"]["email"] == ADMIN_EMAIL

        # session cookie persisted by the client -> /auth/me should recognize it
        me_resp = c.get("/auth/me")
        assert me_resp.status_code == 200
        me_body = me_resp.json()
        assert me_body["authenticated"] is True, f"expected authenticated=true, got: {me_body}"
        assert me_body["user"]["email"] == ADMIN_EMAIL
        assert me_body["user"]["role"]

        # logout clears the session
        logout_resp = c.post("/auth/logout")
        assert logout_resp.status_code == 200
        assert logout_resp.json()["authenticated"] is False

        me_after = c.get("/auth/me")
        assert me_after.status_code == 200
        assert me_after.json()["authenticated"] is False, f"expected authenticated=false after logout, got: {me_after.json()}"


def test_login_with_wrong_password_rejected():
    with httpx.Client(base_url=API_URL, timeout=30.0) as c:
        resp = c.post("/auth/login", json={"email": ADMIN_EMAIL, "password": "definitely-wrong-pw"})
        assert resp.status_code == 401, f"expected 401, got {resp.status_code}: {resp.text}"
        assert "incorrect" in resp.text.lower() or "password" in resp.text.lower()

        # no session cookie should have been set -> /auth/me still unauthenticated
        me_resp = c.get("/auth/me")
        assert me_resp.status_code == 200
        assert me_resp.json()["authenticated"] is False
