"""Clear / undo for episode candidates and positive stories (same flow, different flag).
Self-contained: db is replaced with a tiny in-memory fake supporting what these endpoints use."""

import os

os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "wvedtalk_test")
os.environ.setdefault("SESSION_SECRET", "unit-test-secret")

import pytest

from models.briefing import ClearCandidatesRequest, ReflagRequest
from routers import briefings


class _Cursor:
    def __init__(self, docs):
        self.docs = docs

    async def to_list(self, _n):
        return self.docs


class _FakeBriefings:
    def __init__(self, docs):
        self.docs = docs

    @staticmethod
    def _match(doc, query):
        for k, v in query.items():
            if k == "date":
                if isinstance(v, dict):
                    if "$gte" in v and doc["date"] < v["$gte"]:
                        return False
                    if "$lte" in v and doc["date"] > v["$lte"]:
                        return False
                elif doc["date"] != v:
                    return False
            elif k.startswith("stories."):
                f = k.split(".", 1)[1]
                if not any(s.get(f) == v for s in doc["stories"]):
                    return False
        return True

    def find(self, query, _proj=None):
        return _Cursor([d for d in self.docs if self._match(d, query)])

    def _apply(self, doc, update, array_filters):
        (path, val), = update["$set"].items()
        field = path.split(".")[-1]
        (fk, fv), = array_filters[0].items()
        key = fk.split(".", 1)[1]
        for s in doc["stories"]:
            hit = s.get(key) in fv["$in"] if isinstance(fv, dict) else s.get(key) == fv
            if hit:
                s[field] = val

    async def update_many(self, query, update, array_filters=None):
        for d in self.docs:
            if self._match(d, query):
                self._apply(d, update, array_filters)

    async def update_one(self, query, update, array_filters=None):
        for d in self.docs:
            if self._match(d, query):
                self._apply(d, update, array_filters)
                return


def _docs():
    return [
        {"date": "2026-11-02", "stories": [
            {"id": "a", "is_candidate": True, "is_positive": True},
            {"id": "b", "is_candidate": True, "is_positive": False}]},
        {"date": "2026-11-09", "stories": [{"id": "c", "is_candidate": False, "is_positive": True}]},
        {"date": "2026-11-16", "stories": [{"id": "d", "is_candidate": True, "is_positive": True}]},
    ]


@pytest.fixture
def fake(monkeypatch):
    fb = _FakeBriefings(_docs())
    monkeypatch.setattr(briefings.db, "briefings", fb, raising=False)
    return fb


def _flags(fb, field):
    return sorted(s["id"] for d in fb.docs for s in d["stories"] if s[field])


@pytest.mark.asyncio
async def test_clear_all_positive_leaves_candidates(fake):
    r = await briefings.clear_positive_stories(None)
    assert r["cleared"] == 3
    assert _flags(fake, "is_positive") == []
    assert _flags(fake, "is_candidate") == ["a", "b", "d"]


@pytest.mark.asyncio
async def test_clear_positive_by_day_and_range(fake):
    r = await briefings.clear_positive_stories(ClearCandidatesRequest(date="2026-11-09"))
    assert [x["story_id"] for x in r["refs"]] == ["c"]
    r = await briefings.clear_positive_stories(ClearCandidatesRequest(from_date="2026-11-01", to_date="2026-11-10"))
    assert [x["story_id"] for x in r["refs"]] == ["a"]
    assert _flags(fake, "is_positive") == ["d"]


@pytest.mark.asyncio
async def test_positive_undo_restores_only_positive(fake):
    r = await briefings.clear_positive_stories(None)
    await briefings.reflag_positive_stories(ReflagRequest(refs=r["refs"]))
    assert _flags(fake, "is_positive") == ["a", "c", "d"]
    assert _flags(fake, "is_candidate") == ["a", "b", "d"]


@pytest.mark.asyncio
async def test_candidate_clear_still_works_and_spares_positive(fake):
    r = await briefings.clear_candidates(None)
    assert r["cleared"] == 3
    assert _flags(fake, "is_candidate") == []
    assert _flags(fake, "is_positive") == ["a", "c", "d"]
    await briefings.reflag_candidates(ReflagRequest(refs=r["refs"]))
    assert _flags(fake, "is_candidate") == ["a", "b", "d"]
