from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from app.domain.sync_schedule import (
    MODE_AT_TIME,
    parse_run_at,
    parse_weekdays,
    serialize_weekdays,
    should_run_incremental,
)
from app.schemas import SyncScheduleUpdate


def test_parse_weekdays_defaults_and_dedupes():
    assert parse_weekdays(None) == [0, 1, 2, 3, 4, 5, 6]
    assert parse_weekdays("") == [0, 1, 2, 3, 4, 5, 6]
    assert parse_weekdays("0,1,1,9,x") == [0, 1]
    assert serialize_weekdays([6, 0, 0, 2]) == "0,2,6"
    assert serialize_weekdays([]) == "0,1,2,3,4,5,6"


def test_should_run_skips_disabled_running_and_wrong_day():
    now = datetime(2026, 9, 7, 12, 0, tzinfo=timezone.utc)  # Monday
    assert should_run_incremental(
        enabled=False, weekdays=[0], interval_minutes=15, now=now, last_run=None, is_running=False
    ) is False
    assert should_run_incremental(
        enabled=True, weekdays=[0], interval_minutes=15, now=now, last_run=None, is_running=True
    ) is False
    assert should_run_incremental(
        enabled=True, weekdays=[6], interval_minutes=15, now=now, last_run=None, is_running=False
    ) is False


def test_should_run_respects_interval():
    now = datetime(2026, 9, 7, 12, 0, tzinfo=timezone.utc)
    last = now - timedelta(minutes=14)
    assert should_run_incremental(
        enabled=True, weekdays=[0], interval_minutes=15, now=now, last_run=last, is_running=False
    ) is False
    assert should_run_incremental(
        enabled=True,
        weekdays=[0],
        interval_minutes=15,
        now=now,
        last_run=now - timedelta(minutes=15),
        is_running=False,
    ) is True
    assert should_run_incremental(
        enabled=True, weekdays=[0, 1, 2, 3, 4, 5, 6], interval_minutes=15, now=now, last_run=None, is_running=False
    ) is True
    assert should_run_incremental(
        enabled=True,
        weekdays=[0],
        interval_minutes=99,
        now=now,
        last_run=now - timedelta(minutes=15),
        is_running=False,
    ) is True


def test_schedule_update_rejects_bad_interval_and_days():
    ok = SyncScheduleUpdate(enabled=True, interval_minutes=60, weekdays=[0, 2, 4])
    assert ok.weekdays == [0, 2, 4]
    with pytest.raises(ValidationError):
        SyncScheduleUpdate(enabled=True, interval_minutes=20, weekdays=[0])
    with pytest.raises(ValidationError):
        SyncScheduleUpdate(enabled=True, interval_minutes=15, weekdays=[9])


def test_parse_run_at():
    assert parse_run_at("3:00") == "03:00"
    assert parse_run_at("03:05") == "03:05"
    assert parse_run_at("24:00") is None
    assert parse_run_at("03:60") is None
    assert parse_run_at("") is None


def test_should_run_at_scheduled_time_once_a_day():
    monday = datetime(2026, 9, 7, tzinfo=timezone.utc)
    kwargs = {
        "enabled": True,
        "weekdays": [0],
        "interval_minutes": 15,
        "is_running": False,
        "mode": MODE_AT_TIME,
        "run_at": "03:00",
    }
    assert should_run_incremental(now=monday.replace(hour=2, minute=59), last_run=None, **kwargs) is False
    assert should_run_incremental(now=monday.replace(hour=3, minute=0), last_run=None, **kwargs) is True
    assert (
        should_run_incremental(
            now=monday.replace(hour=3, minute=1),
            last_run=monday.replace(hour=3, minute=0),
            **kwargs,
        )
        is False
    )
    assert (
        should_run_incremental(
            now=monday.replace(hour=3, minute=1),
            last_run=monday.replace(hour=1, minute=0),
            **kwargs,
        )
        is True
    )
    sunday = datetime(2026, 9, 6, 3, 0, tzinfo=timezone.utc)
    assert should_run_incremental(now=monday.replace(hour=3, minute=1), last_run=sunday, **kwargs) is True


def test_schedule_update_at_time_requires_clock():
    ok = SyncScheduleUpdate(enabled=True, mode="at_time", run_at="3:00", weekdays=[0, 1, 2, 3, 4])
    assert ok.run_at == "03:00"
    with pytest.raises(ValidationError):
        SyncScheduleUpdate(enabled=True, mode="at_time", run_at="", weekdays=[0])
