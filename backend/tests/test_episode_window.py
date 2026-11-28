"""Custom coverage window for the weekly episode."""

import os

os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "wvedtalk_test")
os.environ.setdefault("SESSION_SECRET", "unit-test-secret")

import pytest

from lib.producer import MAX_WINDOW_DAYS, validate_window

ANCHOR, TODAY = "2026-11-27", "2026-11-28"


def test_defaults_to_standard_week():
    assert validate_window(None, None, ANCHOR, TODAY) == ("2026-11-21", "2026-11-27")


def test_catch_up_two_weeks():
    assert validate_window("2026-11-14", "2026-11-27", ANCHOR, TODAY) == ("2026-11-14", "2026-11-27")


def test_end_only_keeps_seven_days():
    assert validate_window(None, "2026-11-20", ANCHOR, TODAY) == ("2026-11-14", "2026-11-20")


def test_start_only_ends_on_anchor():
    assert validate_window("2026-11-10", None, ANCHOR, TODAY) == ("2026-11-10", "2026-11-27")


@pytest.mark.parametrize(
    "start,end,msg",
    [
        ("2026-11-28", "2026-11-27", "on or before"),
        ("2026-11-20", "2026-12-05", "future"),
        ("2026-09-01", "2026-11-27", "at most"),
        ("not-a-date", "2026-11-27", "Start date"),
        ("2026-11-20", "2026/11/27", "End date"),
    ],
)
def test_rejects_bad_windows(start, end, msg):
    with pytest.raises(ValueError, match=msg):
        validate_window(start, end, ANCHOR, TODAY)


def test_max_window_boundary():
    from datetime import datetime, timedelta

    end = datetime(2026, 11, 27)
    start = (end - timedelta(days=MAX_WINDOW_DAYS - 1)).strftime("%Y-%m-%d")
    assert validate_window(start, "2026-11-27", ANCHOR, TODAY)[0] == start
    too_early = (end - timedelta(days=MAX_WINDOW_DAYS)).strftime("%Y-%m-%d")
    with pytest.raises(ValueError):
        validate_window(too_early, "2026-11-27", ANCHOR, TODAY)
