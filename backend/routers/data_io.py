"""Admin-only full database export/import — a portable JSON archive of every application
collection, for migrating the News Desk off Emergent hosting (or keeping an off-platform backup).

Mounted under /api behind a require_admin guard in server.py, so every route here is admin-only.
The export reflects whatever database the running app is connected to, so running it on the live
site captures production data. Secrets that live outside the DB (SESSION_SECRET, API keys) are
configuration, not data, and are intentionally NOT part of the archive."""

from datetime import datetime, timezone
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel

from lib.db import db

router = APIRouter(tags=["data-io"])

ARCHIVE_FORMAT = "wvedtalk-news-desk-export"
ARCHIVE_VERSION = 1

# Every application collection, with the field(s) that uniquely identify a record so Merge can
# replace-by-id instead of duplicating. Collections without a natural key match on a composite.
COLLECTIONS: Dict[str, List[str]] = {
    "briefings": ["date"],
    "episodes": ["week_of"],
    "submissions": ["id"],
    "subscribers": ["email"],
    "users": ["email"],
    "desk_config": ["key"],
    "run_log": ["id"],
    "digest_deliveries": ["date", "email"],
}


class ImportRequest(BaseModel):
    mode: str = "merge"  # merge | replace
    confirm: bool = False  # required True for the destructive replace mode
    archive: Dict[str, Any]


@router.get("/data/export")
async def export_data():
    """Return a complete, portable JSON archive of every collection the app uses. Includes user
    accounts with hashed passwords (never plaintext). `_id` is stripped — the target DB regenerates it."""
    collections: Dict[str, List[dict]] = {}
    counts: Dict[str, int] = {}
    for name in COLLECTIONS:
        docs = await db[name].find({}, {"_id": 0}).to_list(1_000_000)
        collections[name] = docs
        counts[name] = len(docs)
    archive = {
        "format": ARCHIVE_FORMAT,
        "version": ARCHIVE_VERSION,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "db_name": db.name,
        "counts": counts,
        "collections": collections,
    }
    # jsonable_encoder turns any stored datetimes into ISO strings so the archive is pure JSON.
    return jsonable_encoder(archive)


@router.post("/data/import")
async def import_data(body: ImportRequest):
    """Load an archive produced by /data/export into this instance's database.
    - merge (default): replace/add records by their id; leave anything not in the archive untouched.
    - replace: clear each collection first, then load (exact copy). Requires confirm=True."""
    mode = (body.mode or "merge").lower()
    if mode not in {"merge", "replace"}:
        raise HTTPException(status_code=422, detail="Mode must be 'merge' or 'replace'")
    if mode == "replace" and not body.confirm:
        raise HTTPException(status_code=400, detail="Replace mode must be explicitly confirmed")

    archive = body.archive or {}
    if archive.get("format") != ARCHIVE_FORMAT or not isinstance(archive.get("collections"), dict):
        raise HTTPException(
            status_code=422,
            detail="This file is not a News Desk export archive (missing or wrong format).",
        )

    source = archive["collections"]
    results: Dict[str, dict] = {}
    for name, keys in COLLECTIONS.items():
        docs = source.get(name) or []
        loaded = 0
        failed = 0
        if mode == "replace":
            try:
                await db[name].delete_many({})
            except Exception:
                pass
        for raw in docs:
            if not isinstance(raw, dict):
                failed += 1
                continue
            doc = {k: v for k, v in raw.items() if k != "_id"}
            try:
                if keys and all(doc.get(k) is not None for k in keys):
                    await db[name].replace_one({k: doc[k] for k in keys}, doc, upsert=True)
                else:
                    await db[name].insert_one(doc)
                loaded += 1
            except Exception:
                failed += 1
        actual = await db[name].count_documents({})
        # Replace yields an exact copy (actual == source); Merge should contain at least everything
        # in the archive. Either way, no record may have failed to load.
        match = failed == 0 and (actual == len(docs) if mode == "replace" else actual >= len(docs))
        results[name] = {
            "in_archive": len(docs),
            "loaded": loaded,
            "failed": failed,
            "actual": actual,
            "match": match,
        }

    integrity_ok = all(r["match"] for r in results.values())
    return {"mode": mode, "integrity_ok": integrity_ok, "results": results}
