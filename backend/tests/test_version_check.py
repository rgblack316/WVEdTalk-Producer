"""Commit-based update detection (GitHub mocked, no network)."""

import asyncio
import os

import httpx

os.environ.setdefault("DB_NAME", "test_db")
os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")

from lib import version  # noqa: E402

SHA = "a" * 40


def _run(monkeypatch, handler, commit):
    monkeypatch.setenv("APP_COMMIT", commit)
    real = httpx.AsyncClient
    monkeypatch.setattr(
        version.httpx, "AsyncClient", lambda **kw: real(transport=httpx.MockTransport(handler), **kw)
    )
    version._cache.update(at=0.0, data=None)
    return asyncio.run(version.check_update(force=True))


def _gh(compare_json):
    def handler(req: httpx.Request):
        if req.url.path.endswith("/backend/VERSION"):
            return httpx.Response(200, text="1.0.0\n")
        if "/compare/" in req.url.path:
            return httpx.Response(200, json=compare_json)
        if req.url.path.endswith("/commits/main"):
            return httpx.Response(200, text="b" * 40)
        return httpx.Response(404)
    return handler


def test_same_version_file_but_new_commits_is_an_update(monkeypatch):
    j = {"ahead_by": 2, "commits": [
        {"sha": "c" * 40, "commit": {"message": "Older change\n\nbody"}},
        {"sha": "d" * 40, "commit": {"message": "Newest change"}},
    ]}
    r = _run(monkeypatch, _gh(j), SHA)
    assert r["update_available"] and r["behind_by"] == 2
    assert r["changes"] == ["Newest change", "Older change"]
    assert r["latest_commit"] == "ddddddd" and r["current_commit"] == "aaaaaaa"


def test_identical_commit_is_up_to_date(monkeypatch):
    r = _run(monkeypatch, _gh({"ahead_by": 0, "commits": []}), SHA)
    assert not r["update_available"] and r["behind_by"] == 0


def test_unknown_build_offers_update(monkeypatch):
    r = _run(monkeypatch, _gh({}), "unknown")
    assert r["unknown_build"] and r["update_available"] and r["current_commit"] is None


def test_unpushed_build_reports_error_not_update(monkeypatch):
    def handler(req):
        if req.url.path.endswith("/backend/VERSION"):
            return httpx.Response(200, text="1.0.0")
        return httpx.Response(404)
    r = _run(monkeypatch, handler, SHA)
    assert not r["update_available"] and "isn't on GitHub" in r["error"]
