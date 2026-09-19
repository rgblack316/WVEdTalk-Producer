"""Criterion: Settings security controls work (API side).

Selecting an auto-lock value persists: PATCH/PUT /api/settings then GET /api/settings
reflects auto_lock_minutes. Restores the previous value afterward so other checks/humans
are unaffected.
"""

import os

PASSCODE = os.environ.get("APP_PASSCODE", "WVEdTalk-Desk-2026")
HEADERS = {"X-Desk-Passcode": PASSCODE}


def test_auto_lock_minutes_persists(client):
    original = client.get("/settings", headers=HEADERS)
    assert original.status_code == 200, original.text
    original_value = original.json().get("auto_lock_minutes")

    new_value = 15 if original_value != 15 else 30
    try:
        update = client.post("/settings/auto-lock", headers=HEADERS, json={"minutes": new_value})
        assert update.status_code == 200, f"expected 200, got {update.status_code}: {update.text}"

        check = client.get("/settings", headers=HEADERS)
        assert check.status_code == 200, check.text
        assert check.json().get("auto_lock_minutes") == new_value
    finally:
        # restore original value
        client.post("/settings/auto-lock", headers=HEADERS, json={"minutes": original_value})
