"""S3-compatible backup routes — mounted under /api behind require_admin in server.py."""

import json
from typing import Optional

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel

from lib import backup
from routers.data_io import ImportRequest, import_data, preview_import

router = APIRouter(tags=["backups"])

PRESETS = [
    {"id": "aws", "label": "Amazon S3", "endpoint": "", "region": "us-east-1", "style": "auto",
     "hint": "Leave the endpoint blank. Pick the bucket's region (for example us-east-1)."},
    {"id": "r2", "label": "Cloudflare R2", "endpoint": "https://<ACCOUNT_ID>.r2.cloudflarestorage.com", "region": "auto", "style": "path",
     "hint": "Create an R2 API token with Object Read & Write, scoped to this bucket. Region: auto."},
    {"id": "b2", "label": "Backblaze B2", "endpoint": "https://s3.<REGION>.backblazeb2.com", "region": "<REGION>", "style": "path",
     "hint": "Use an application key with read/write/delete on the bucket. Region looks like us-west-004."},
    {"id": "spaces", "label": "DigitalOcean Spaces", "endpoint": "https://<REGION>.digitaloceanspaces.com", "region": "<REGION>", "style": "virtual",
     "hint": "Region looks like nyc3. Create a Spaces access key."},
    {"id": "wasabi", "label": "Wasabi", "endpoint": "https://s3.<REGION>.wasabisys.com", "region": "<REGION>", "style": "auto",
     "hint": "Region looks like us-east-1."},
    {"id": "minio", "label": "MinIO / other S3-compatible", "endpoint": "https://", "region": "us-east-1", "style": "path",
     "hint": "Use your server's S3 API URL. Path-style addressing is usually required."},
]


class ConfigPatch(BaseModel):
    enabled: Optional[bool] = None
    endpoint_url: Optional[str] = None
    region: Optional[str] = None
    bucket: Optional[str] = None
    prefix: Optional[str] = None
    addressing_style: Optional[str] = None
    access_key_id: Optional[str] = None
    secret_access_key: Optional[str] = None
    frequency: Optional[str] = None
    every_hours: Optional[int] = None
    hour: Optional[int] = None
    minute: Optional[int] = None
    dow: Optional[int] = None
    keep_last: Optional[int] = None
    keep_days: Optional[int] = None


@router.get("/backups/config")
async def get_config():
    return {**await backup.public_config(), "presets": PRESETS}


@router.post("/backups/config")
async def set_config(body: ConfigPatch):
    patch = body.model_dump(exclude_none=True)
    try:
        await backup.save_config(patch)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return {**await backup.public_config(), "presets": PRESETS}


@router.post("/backups/test")
async def test():
    return await backup.test_connection()


@router.post("/backups/run")
async def run_now():
    entry = await backup.run_backup("manual")
    if entry["status"] != "complete":
        raise HTTPException(status_code=502, detail=entry["error"] or "Backup failed")
    return entry


@router.get("/backups")
async def list_backups():
    try:
        return {"backups": await backup.list_backups(), "error": ""}
    except Exception as exc:
        return {"backups": [], "error": backup._friendly(exc)}


@router.get("/backups/log")
async def log():
    from lib.db import db

    return await db.backup_log.find({}, {"_id": 0}).sort("at", -1).to_list(20)


@router.get("/backups/download")
async def download(key: str):
    """Fetch a backup from the bucket and return it as plain JSON, so it can be loaded with the
    normal import tool or the first-run wizard."""
    try:
        archive = await backup.fetch_archive(key)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=backup._friendly(exc))
    name = key.rsplit("/", 1)[-1].replace(".json.gz", ".json")
    return Response(
        content=json.dumps(archive, ensure_ascii=False),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{name}"'},
    )


class RestoreBody(BaseModel):
    key: str
    mode: str = "merge"
    confirm: bool = False
    preview: bool = False


@router.post("/backups/restore")
async def restore(body: RestoreBody):
    """Load a backup from the bucket into this install (merge, or replace with confirm)."""
    try:
        archive = await backup.fetch_archive(body.key)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=backup._friendly(exc))
    req = ImportRequest(mode=body.mode, confirm=body.confirm, archive=archive)
    return await (preview_import(req) if body.preview else import_data(req))
