"""Criterion: Removed demo endpoints are gone.

GET /api/status and POST /api/status both must be 404 (routes removed in the security fix).
"""


def test_status_get_removed(client):
    resp = client.get("/status")
    assert resp.status_code == 404, f"expected 404, got {resp.status_code}: {resp.text}"


def test_status_post_removed(client):
    resp = client.post("/status", json={"client_name": "tscheck-status-removed"})
    assert resp.status_code == 404, f"expected 404, got {resp.status_code}: {resp.text}"
