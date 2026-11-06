"""Backup scheduling, retention and S3 round-trip (S3 mocked with moto; no network, no real DB)."""

import asyncio
import gzip
import json
import os
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

os.environ.setdefault("DB_NAME", "test_db")
os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("SESSION_SECRET", "test-secret")

from lib import backup  # noqa: E402

UTC = timezone.utc
NY = ZoneInfo("America/New_York")


def cfg(**kw):
    base = {**backup.DEFAULTS, "bucket": "test-bucket", "access_key_id": "k", "secret_access_key": "s", "enabled": True}
    base.update(kw)
    return base


def b(days_ago, now):
    return {"key": f"p/x{days_ago}", "size": 1, "at": (now - timedelta(days=days_ago)).isoformat()}


# ---- retention (schedule and retention are independent) --------------------------------------

def test_keep_last_only():
    now = datetime(2026, 11, 6, tzinfo=UTC)
    items = [b(i, now) for i in range(6)]  # newest first
    gone = backup.select_for_deletion(items, keep_last=3, keep_days=0, now=now)
    assert [g["key"] for g in gone] == ["p/x3", "p/x4", "p/x5"]


def test_keep_days_only():
    now = datetime(2026, 11, 6, tzinfo=UTC)
    items = [b(i, now) for i in (0, 1, 8, 20)]
    gone = backup.select_for_deletion(items, keep_last=0, keep_days=7, now=now)
    assert [g["key"] for g in gone] == ["p/x8", "p/x20"]


def test_both_limits_combine_and_zero_means_unlimited():
    now = datetime(2026, 11, 6, tzinfo=UTC)
    items = [b(i, now) for i in (0, 1, 2, 3, 40)]
    assert len(backup.select_for_deletion(items, keep_last=3, keep_days=30, now=now)) == 2
    assert backup.select_for_deletion(items, keep_last=0, keep_days=0, now=now) == []


def test_newest_backup_is_never_deleted():
    now = datetime(2026, 11, 6, tzinfo=UTC)
    items = [b(400, now)]  # only backup is ancient
    assert backup.select_for_deletion(items, keep_last=1, keep_days=1, now=now) == []


# ---- schedule ---------------------------------------------------------------------------------

def test_daily_due_after_slot_when_last_backup_before_it():
    c = cfg(frequency="daily", hour=2, minute=0)
    now = datetime(2026, 11, 6, 14, 0, tzinfo=NY).astimezone(UTC)  # 2pm ET
    yesterday = datetime(2026, 11, 5, 2, 5, tzinfo=NY).astimezone(UTC)
    today_done = datetime(2026, 11, 6, 2, 5, tzinfo=NY).astimezone(UTC)
    assert backup.is_due(c, now, NY, yesterday, None)
    assert not backup.is_due(c, now, NY, today_done, None)


def test_daily_not_due_before_todays_slot_if_yesterdays_ran():
    c = cfg(frequency="daily", hour=2)
    now = datetime(2026, 11, 6, 1, 0, tzinfo=NY).astimezone(UTC)
    last = datetime(2026, 11, 5, 2, 1, tzinfo=NY).astimezone(UTC)
    assert not backup.is_due(c, now, NY, last, None)


def test_weekly_uses_day_of_week():
    c = cfg(frequency="weekly", dow=6, hour=3)  # Sundays 3am
    sat = datetime(2026, 11, 7, 12, 0, tzinfo=NY).astimezone(UTC)  # Saturday
    last_sun = datetime(2026, 11, 1, 3, 5, tzinfo=NY).astimezone(UTC)
    assert not backup.is_due(c, sat, NY, last_sun, None)
    mon = datetime(2026, 11, 9, 9, 0, tzinfo=NY).astimezone(UTC)  # the Sunday slot (Nov 8) has passed
    assert backup.is_due(c, mon, NY, last_sun, None)


def test_interval_mode():
    c = cfg(frequency="hours", every_hours=6)
    now = datetime(2026, 11, 6, 12, 0, tzinfo=UTC)
    assert not backup.is_due(c, now, NY, now - timedelta(hours=5), None)
    assert backup.is_due(c, now, NY, now - timedelta(hours=6), None)
    assert backup.is_due(c, now, NY, None, None)


def test_failed_attempt_backs_off_and_disabled_never_runs():
    c = cfg(frequency="hours", every_hours=1)
    now = datetime(2026, 11, 6, 12, 0, tzinfo=UTC)
    assert not backup.is_due(c, now, NY, None, (now - timedelta(minutes=5), "failed"))
    assert backup.is_due(c, now, NY, None, (now - timedelta(minutes=45), "failed"))
    assert not backup.is_due(cfg(enabled=False), now, NY, None, None)
    assert not backup.is_due(cfg(bucket=""), now, NY, None, None)


# ---- validation + key safety --------------------------------------------------------------------

def test_validate_patch_rejects_bad_values():
    for bad in ({"frequency": "monthly"}, {"hour": 24}, {"keep_last": -1}, {"every_hours": 5},
                {"endpoint_url": "ftp://x"}, {"bucket": "bad bucket!"}, {"bucket": "ab"}, {"keep_days": "abc"}):
        with pytest.raises(ValueError):
            backup.validate_patch(bad)
    ok = backup.validate_patch({"endpoint_url": "https://x.r2.cloudflarestorage.com/", "prefix": "/a/b/", "keep_last": "7"})
    assert ok == {"endpoint_url": "https://x.r2.cloudflarestorage.com", "prefix": "a/b", "keep_last": 7}


def test_check_key_only_allows_our_backups():
    c = cfg(prefix="bk")
    backup._check_key(c, "bk/wvedtalk-backup-20261106-020000.json.gz")
    for bad in ("other/wvedtalk-backup-20261106-020000.json.gz", "bk/secret.txt", "bk/sub/wvedtalk-backup-20261106-020000.json.gz", "bk/"):
        with pytest.raises(ValueError):
            backup._check_key(c, bad)


# ---- real S3 round trip against moto -------------------------------------------------------------

def test_upload_list_prune_download_roundtrip(monkeypatch):
    moto = pytest.importorskip("moto")
    import boto3

    with moto.mock_aws():
        boto3.client("s3", region_name="us-east-1").create_bucket(Bucket="test-bucket")
        c = cfg(prefix="bk", keep_last=2, region="us-east-1")
        s3 = boto3.client("s3", region_name="us-east-1")
        for stamp in ("20261101-020000", "20261102-020000", "20261103-020000", "20261104-020000"):
            backup._upload_sync(c, backup._key_for(c, stamp), gzip.compress(b'{"format":"x"}'))
        s3.put_object(Bucket="test-bucket", Key="bk/unrelated.txt", Body=b"keep me")
        s3.put_object(Bucket="test-bucket", Key="other/wvedtalk-backup-20200101-000000.json.gz", Body=b"x")

        assert backup._test_sync(c)["ok"]
        listed = backup._list_sync(c)
        assert len(listed) == 4 and listed[0]["key"].endswith("20261104-020000.json.gz")

        removed = backup._prune_sync(c, datetime(2026, 11, 5, tzinfo=UTC))
        assert removed == 2
        left = [x["key"] for x in backup._list_sync(c)]
        assert left == ["bk/wvedtalk-backup-20261104-020000.json.gz", "bk/wvedtalk-backup-20261103-020000.json.gz"]
        # foreign objects are never touched
        keys = {o["Key"] for o in s3.list_objects_v2(Bucket="test-bucket")["Contents"]}
        assert "bk/unrelated.txt" in keys and "other/wvedtalk-backup-20200101-000000.json.gz" in keys
        assert json.loads(gzip.decompress(backup._download_sync(c, left[0]))) == {"format": "x"}
