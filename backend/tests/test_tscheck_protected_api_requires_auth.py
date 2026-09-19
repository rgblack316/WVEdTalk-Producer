"""Criterion: Protected API requires auth.

GET /api/briefings without cookie/header -> 401.
GET /api/ (health) -> 200.
"""

from .conftest import api_url
import httpx


def test_briefings_requires_auth(client):
    resp = client.get("/briefings")
    assert resp.status_code == 401, f"expected 401, got {resp.status_code}: {resp.text}"


def test_health_endpoint_ok():
    resp = httpx.get(api_url("/"), timeout=30.0)
    assert resp.status_code == 200, f"expected 200, got {resp.status_code}: {resp.text}"
