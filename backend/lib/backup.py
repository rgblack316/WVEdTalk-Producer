"""Scheduled + on-demand backups to any S3-compatible bucket (AWS S3, Cloudflare R2, Backblaze B2,
DigitalOcean Spaces, Wasabi, MinIO, ...).

Each backup is the same portable archive as Settings -> Data export, gzipped, uploaded as
`<prefix>/wvedtalk-backup-YYYYMMDD-HHMMSS.json.gz`. Schedule and retention are independent settings:

  * schedule  - how often (every N hours / daily / weekly, in the desk timezone)
  * retention - keep the newest N backups AND/OR drop backups older than D days (0 = no limit);
                the newest backup is never deleted by retention.

Config lives in desk_config.backup. The secret access key is encrypted at rest (same scheme as the
Integrations credentials). Backups contain user accounts (hashed passwords) and all desk data, so the
bucket MUST be private.
"""

import asyncio
import gzip
import json
import logging
import re
import urllib.parse
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from lib import config_secrets, desk
from lib.db import db

logger = logging.getLogger(__name__)

_KEY = {"key": "singleton"}
_NAME_RE = re.compile(r"wvedtalk-backup-(\d{8}-\d{6})\.json\.gz$")
_RETRY_AFTER_FAILURE = timedelta(minutes=30)
_lock = asyncio.Lock()

FREQUENCIES = {"hours", "daily", "weekly"}
INTERVAL_CHOICES = {1, 2, 3, 4, 6, 8, 12}
ADDRESSING = {"auto", "path", "virtual"}

DEFAULTS: Dict[str, Any] = {
    "enabled": False,
    "endpoint_url": "",  # blank = AWS S3
    "region": "",
    "bucket": "",
    "prefix": "wvedtalk-backups",
    "addressing_style": "auto",
    "access_key_id": "",  # stored encrypted
    "secret_access_key": "",  # stored encrypted
    # schedule
    "frequency": "daily",
    "every_hours": 6,
    "hour": 2,
    "minute": 0,
    "dow": 6,  # Sunday, used when frequency == weekly (0=Mon)
    # retention (0 = no limit on that dimension)
    "keep_last": 14,
    "keep_days": 0,
}


# ---------------------------------------------------------------- config

async def _raw() -> Dict[str, Any]:
    doc = await db.desk_config.find_one(_KEY, {"_id": 0, "backup": 1}) or {}
    return doc.get("backup") or {}


async def get_config() -> Dict[str, Any]:
    """Effective config with secrets decrypted (server-side use only)."""
    raw = await _raw()
    cfg = {**DEFAULTS, **{k: v for k, v in raw.items() if k in DEFAULTS}}
    cfg["access_key_id"] = config_secrets.dec(raw.get("access_key_id", ""))
    cfg["secret_access_key"] = config_secrets.dec(raw.get("secret_access_key", ""))
    return cfg


def configured(cfg: Dict[str, Any]) -> bool:
    return bool(cfg["bucket"] and cfg["access_key_id"] and cfg["secret_access_key"])


async def public_config() -> Dict[str, Any]:
    """UI view model: secrets masked, plus derived status."""
    cfg = await get_config()
    out = {k: v for k, v in cfg.items() if k not in ("access_key_id", "secret_access_key")}
    out["access_key_id_mask"] = config_secrets.mask(cfg["access_key_id"])
    out["secret_access_key_set"] = bool(cfg["secret_access_key"])
    out["configured"] = configured(cfg)
    nxt = await next_run(cfg)
    out["next_run"] = nxt.isoformat() if nxt else None
    last = await db.backup_log.find_one({}, {"_id": 0}, sort=[("at", -1)])
    out["last"] = last
    return out


def validate_patch(patch: Dict[str, Any]) -> Dict[str, Any]:
    """Validate/normalize a partial config update; raises ValueError with a user-facing message."""
    out: Dict[str, Any] = {}
    for k, v in patch.items():
        if k not in DEFAULTS:
            continue
        if k in ("enabled",):
            out[k] = bool(v)
        elif k in ("hour", "minute", "dow", "every_hours", "keep_last", "keep_days"):
            try:
                out[k] = int(v)
            except (TypeError, ValueError):
                raise ValueError(f"{k.replace('_', ' ')} must be a number")
        else:
            out[k] = str(v if v is not None else "").strip()
    if "frequency" in out and out["frequency"] not in FREQUENCIES:
        raise ValueError("Frequency must be hours, daily, or weekly")
    if "addressing_style" in out and out["addressing_style"] not in ADDRESSING:
        raise ValueError("Addressing style must be auto, path, or virtual")
    if "every_hours" in out and out["every_hours"] not in INTERVAL_CHOICES:
        raise ValueError("Interval must be one of 1, 2, 3, 4, 6, 8, or 12 hours")
    if "hour" in out and not 0 <= out["hour"] <= 23:
        raise ValueError("Hour must be 0-23")
    if "minute" in out and not 0 <= out["minute"] <= 59:
        raise ValueError("Minute must be 0-59")
    if "dow" in out and not 0 <= out["dow"] <= 6:
        raise ValueError("Day of week must be 0 (Mon) to 6 (Sun)")
    if "keep_last" in out and not 0 <= out["keep_last"] <= 1000:
        raise ValueError("Keep-last must be between 0 and 1000 (0 = no limit)")
    if "keep_days" in out and not 0 <= out["keep_days"] <= 3650:
        raise ValueError("Keep-days must be between 0 and 3650 (0 = no limit)")
    if out.get("endpoint_url"):
        if not re.match(r"^https?://[^\s/]+", out["endpoint_url"]):
            raise ValueError("Endpoint must be a full URL such as https://<account>.r2.cloudflarestorage.com")
        out["endpoint_url"] = out["endpoint_url"].rstrip("/")
    if "prefix" in out:
        out["prefix"] = out["prefix"].strip("/ ")
    if "bucket" in out and out["bucket"] and not re.match(r"^[A-Za-z0-9][A-Za-z0-9._-]{2,62}$", out["bucket"]):
        raise ValueError("That doesn't look like a valid bucket name")
    return out


async def save_config(patch: Dict[str, Any]) -> None:
    """Persist a validated patch. Blank secret fields in the patch are ignored (keep the saved value)."""
    sets: Dict[str, Any] = {}
    for k, v in validate_patch({k: v for k, v in patch.items() if k not in ("access_key_id", "secret_access_key")}).items():
        sets[f"backup.{k}"] = v
    for k in ("access_key_id", "secret_access_key"):
        val = (patch.get(k) or "").strip()
        if val:
            sets[f"backup.{k}"] = config_secrets.enc(val)
    if sets:
        await db.desk_config.update_one(_KEY, {"$set": sets}, upsert=True)


# ---------------------------------------------------------------- S3

def _is_r2(endpoint_url: str) -> bool:
    """True when the endpoint's HOST is Cloudflare R2 (not just a URL containing the text)."""
    host = (urllib.parse.urlparse(endpoint_url or "").hostname or "").lower()
    return host == "r2.cloudflarestorage.com" or host.endswith(".r2.cloudflarestorage.com")


def _client(cfg: Dict[str, Any]):
    import boto3
    from botocore.config import Config

    style = cfg["addressing_style"]
    return boto3.client(
        "s3",
        endpoint_url=cfg["endpoint_url"] or None,
        region_name=cfg["region"] or ("auto" if _is_r2(cfg["endpoint_url"]) else "us-east-1"),
        aws_access_key_id=cfg["access_key_id"],
        aws_secret_access_key=cfg["secret_access_key"],
        config=Config(
            signature_version="s3v4",
            s3={"addressing_style": style},
            retries={"max_attempts": 3, "mode": "standard"},
            connect_timeout=10,
            read_timeout=120,
        ),
    )


def _key_for(cfg: Dict[str, Any], stamp: str) -> str:
    name = f"wvedtalk-backup-{stamp}.json.gz"
    return f"{cfg['prefix']}/{name}" if cfg["prefix"] else name


def _list_sync(cfg: Dict[str, Any]) -> List[Dict[str, Any]]:
    s3 = _client(cfg)
    prefix = f"{cfg['prefix']}/" if cfg["prefix"] else ""
    out: List[Dict[str, Any]] = []
    for page in s3.get_paginator("list_objects_v2").paginate(Bucket=cfg["bucket"], Prefix=prefix):
        for o in page.get("Contents", []):
            rest = o["Key"][len(prefix):]
            m = _NAME_RE.fullmatch(rest) if "/" not in rest else None
            if not m:
                continue  # only objects we created; never touch anything else in the bucket
            at = datetime.strptime(m.group(1), "%Y%m%d-%H%M%S").replace(tzinfo=timezone.utc)
            out.append({"key": o["Key"], "size": o["Size"], "at": at.isoformat()})
    out.sort(key=lambda x: x["at"], reverse=True)
    return out


async def list_backups() -> List[Dict[str, Any]]:
    cfg = await get_config()
    if not configured(cfg):
        return []
    return await asyncio.to_thread(_list_sync, cfg)


def _friendly(exc: Exception) -> str:
    """A short, safe message for the UI. The full exception is logged server-side only, so provider
    error bodies, request IDs or stack details are never returned to the browser."""
    logger.warning("backup storage error: %s", exc)
    msg = str(exc)
    for needle, text in (
        ("InvalidAccessKeyId", "The access key ID isn't recognized by that provider."),
        ("SignatureDoesNotMatch", "The secret access key is wrong (or the region/endpoint doesn't match)."),
        ("NoSuchBucket", "That bucket doesn't exist at this endpoint."),
        ("AccessDenied", "The key is valid but isn't allowed to do that. It needs read, write and delete on this bucket."),
        ("Could not connect", "Couldn't reach the endpoint. Check the endpoint URL."),
        ("Name or service not known", "Couldn't resolve the endpoint host. Check the endpoint URL."),
    ):
        if needle in msg:
            return text
    code = (getattr(exc, "response", None) or {}).get("Error", {}).get("Code") if hasattr(exc, "response") else None
    if code and re.fullmatch(r"[A-Za-z0-9_.-]{1,40}", str(code)):
        return f"The storage service returned an error ({code})."
    return "The backup storage request failed. Check the settings and try again (details are in the server log)."


def _test_sync(cfg: Dict[str, Any]) -> Dict[str, Any]:
    s3 = _client(cfg)
    key = f"{cfg['prefix']}/.wvedtalk-connection-test" if cfg["prefix"] else ".wvedtalk-connection-test"
    s3.put_object(Bucket=cfg["bucket"], Key=key, Body=b"ok")
    s3.head_object(Bucket=cfg["bucket"], Key=key)
    s3.delete_object(Bucket=cfg["bucket"], Key=key)
    return {"ok": True, "message": "Connected: wrote, read and deleted a test file."}


async def test_connection() -> Dict[str, Any]:
    cfg = await get_config()
    if not configured(cfg):
        return {"ok": False, "message": "Enter the bucket and both keys first, then save."}
    try:
        return await asyncio.to_thread(_test_sync, cfg)
    except Exception as exc:
        return {"ok": False, "message": _friendly(exc)}


# ---------------------------------------------------------------- run + retention

def select_for_deletion(
    backups: List[Dict[str, Any]], keep_last: int, keep_days: int, now: datetime
) -> List[Dict[str, Any]]:
    """Which backups retention removes. `backups` newest-first. Never includes the newest one."""
    doomed: List[Dict[str, Any]] = []
    for i, b in enumerate(backups):
        if i == 0:
            continue
        too_many = keep_last > 0 and i >= keep_last
        too_old = keep_days > 0 and datetime.fromisoformat(b["at"]) < now - timedelta(days=keep_days)
        if too_many or too_old:
            doomed.append(b)
    return doomed


def _upload_sync(cfg: Dict[str, Any], key: str, body: bytes) -> None:
    s3 = _client(cfg)
    s3.put_object(Bucket=cfg["bucket"], Key=key, Body=body, ContentType="application/gzip")
    head = s3.head_object(Bucket=cfg["bucket"], Key=key)
    if head["ContentLength"] != len(body):
        raise RuntimeError("Uploaded size doesn't match; the backup may be incomplete.")


def _prune_sync(cfg: Dict[str, Any], now: datetime) -> int:
    backups = _list_sync(cfg)
    doomed = select_for_deletion(backups, cfg["keep_last"], cfg["keep_days"], now)
    s3 = _client(cfg)
    for b in doomed:
        s3.delete_object(Bucket=cfg["bucket"], Key=b["key"])
    return len(doomed)


async def run_backup(trigger: str = "manual") -> Dict[str, Any]:
    """Create one backup now. Always records a log entry; raises nothing (errors go in the entry)."""
    from routers.data_io import build_archive

    cfg = await get_config()
    entry: Dict[str, Any] = {
        "id": str(uuid.uuid4()), "at": datetime.now(timezone.utc).isoformat(), "trigger": trigger,
        "status": "failed", "key": "", "size": 0, "pruned": 0, "error": "",
    }
    if not configured(cfg):
        entry["error"] = "Backups aren't configured yet."
        await db.backup_log.insert_one(dict(entry))
        return entry
    async with _lock:
        try:
            now = datetime.now(timezone.utc)
            archive = await build_archive()
            body = gzip.compress(json.dumps(archive, ensure_ascii=False).encode("utf-8"))
            key = _key_for(cfg, now.strftime("%Y%m%d-%H%M%S"))
            await asyncio.to_thread(_upload_sync, cfg, key, body)
            entry.update(status="complete", key=key, size=len(body))
            try:
                entry["pruned"] = await asyncio.to_thread(_prune_sync, cfg, now)
            except Exception as exc:  # the backup itself succeeded
                logger.exception("backup retention failed (non-fatal)")
                entry["error"] = f"Backup saved, but cleanup of old backups failed: {_friendly(exc)}"
        except Exception as exc:
            logger.exception("backup failed")
            entry["error"] = _friendly(exc)
    await db.backup_log.insert_one(dict(entry))
    entry.pop("_id", None)
    return entry


def _download_sync(cfg: Dict[str, Any], key: str) -> bytes:
    return _client(cfg).get_object(Bucket=cfg["bucket"], Key=key)["Body"].read()


def _check_key(cfg: Dict[str, Any], key: str) -> None:
    prefix = f"{cfg['prefix']}/" if cfg["prefix"] else ""
    rest = key[len(prefix):] if key.startswith(prefix) else ""
    if not rest or "/" in rest or not _NAME_RE.fullmatch(rest):
        raise ValueError("That isn't one of this app's backups.")


async def fetch_archive(key: str) -> Dict[str, Any]:
    cfg = await get_config()
    _check_key(cfg, key)
    raw = await asyncio.to_thread(_download_sync, cfg, key)
    try:
        return json.loads(gzip.decompress(raw).decode("utf-8"))
    except (OSError, EOFError, ValueError):
        raise ValueError("That backup file is corrupt or isn't a valid archive.") from None


# ---------------------------------------------------------------- schedule

def last_slot(cfg: Dict[str, Any], now_local: datetime) -> Optional[datetime]:
    """Most recent scheduled moment <= now (local tz), for daily/weekly. None for interval mode."""
    if cfg["frequency"] == "hours":
        return None
    slot = now_local.replace(hour=cfg["hour"], minute=cfg["minute"], second=0, microsecond=0)
    if cfg["frequency"] == "daily":
        return slot if slot <= now_local else slot - timedelta(days=1)
    back = (now_local.weekday() - cfg["dow"]) % 7
    slot = slot - timedelta(days=back)
    return slot if slot <= now_local else slot - timedelta(days=7)


def next_slot(cfg: Dict[str, Any], now_local: datetime) -> Optional[datetime]:
    prev = last_slot(cfg, now_local)
    if prev is None:
        return None
    step = timedelta(days=1 if cfg["frequency"] == "daily" else 7)
    nxt = (prev.replace(tzinfo=None) + step).replace(tzinfo=prev.tzinfo)
    return nxt


async def _last_success() -> Optional[datetime]:
    d = await db.backup_log.find_one({"status": "complete"}, {"_id": 0, "at": 1}, sort=[("at", -1)])
    return datetime.fromisoformat(d["at"]) if d else None


async def _last_attempt() -> Optional[Tuple[datetime, str]]:
    d = await db.backup_log.find_one({}, {"_id": 0, "at": 1, "status": 1}, sort=[("at", -1)])
    return (datetime.fromisoformat(d["at"]), d["status"]) if d else None


def is_due(cfg: Dict[str, Any], now_utc: datetime, tz, last_ok: Optional[datetime],
           last_try: Optional[Tuple[datetime, str]]) -> bool:
    if not cfg["enabled"] or not configured(cfg):
        return False
    if last_try and last_try[1] == "failed" and now_utc - last_try[0] < _RETRY_AFTER_FAILURE:
        return False  # don't hammer a failing destination
    if cfg["frequency"] == "hours":
        return last_ok is None or now_utc - last_ok >= timedelta(hours=cfg["every_hours"])
    slot = last_slot(cfg, now_utc.astimezone(tz))
    return last_ok is None or last_ok < slot.astimezone(timezone.utc)


async def next_run(cfg: Dict[str, Any]) -> Optional[datetime]:
    if not cfg["enabled"] or not configured(cfg):
        return None
    s = await desk.load_schedule()
    tz = desk._safe_zone(s["timezone"])
    now = datetime.now(timezone.utc)
    last_ok = await _last_success()
    if cfg["frequency"] == "hours":
        due = (last_ok + timedelta(hours=cfg["every_hours"])) if last_ok else now
        return max(due, now)
    if is_due(cfg, now, tz, last_ok, None):
        return now
    return next_slot(cfg, now.astimezone(tz))


async def scheduler_loop() -> None:
    """Check once a minute whether a scheduled backup is due."""
    while True:
        try:
            cfg = await get_config()
            if cfg["enabled"] and configured(cfg):
                s = await desk.load_schedule()
                tz = desk._safe_zone(s["timezone"])
                if is_due(cfg, datetime.now(timezone.utc), tz, await _last_success(), await _last_attempt()) and not _lock.locked():
                    logger.info("backup scheduler: running scheduled backup")
                    await run_backup("scheduled")
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("backup scheduler loop error")
        await asyncio.sleep(60)
