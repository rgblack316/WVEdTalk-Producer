"""Criterion: Programmatic header auth works.

GET /api/briefings with header X-Desk-Passcode: <passcode> -> 200.
"""

import os

PASSCODE = os.environ.get("APP_PASSCODE", "WVEdTalk-Desk-2026")


def test_header_auth_allows_briefings(client):
    resp = client.get("/briefings", headers={"X-Desk-Passcode": PASSCODE})
    assert resp.status_code == 200, f"expected 200, got {resp.status_code}: {resp.text}"
    body = resp.json()
    assert isinstance(body, list), f"expected list body, got: {body!r}"
