from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Iterable, Optional, Sequence

ALLOWED_INTERVAL_MINUTES = (15, 30, 60, 180, 360, 720, 1440)
DEFAULT_INTERVAL_MINUTES = 15
ALL_WEEKDAYS = (0, 1, 2, 3, 4, 5, 6)
MODE_INTERVAL = "interval"
MODE_AT_TIME = "at_time"
DEFAULT_RUN_AT = "03:00"


def parse_weekdays(raw: Optional[str]) -> list[int]:
    if not raw or not str(raw).strip():
        return list(ALL_WEEKDAYS)
    days: list[int] = []
    for part in str(raw).split(","):
        token = part.strip()
        if not token:
            continue
        try:
            day = int(token)
        except ValueError:
            continue
        if day in ALL_WEEKDAYS and day not in days:
            days.append(day)
    return days or list(ALL_WEEKDAYS)


def serialize_weekdays(days: Sequence[int]) -> str:
    cleaned = sorted({int(day) for day in days if int(day) in ALL_WEEKDAYS})
    if not cleaned:
        cleaned = list(ALL_WEEKDAYS)
    return ",".join(str(day) for day in cleaned)


def normalize_interval_minutes(minutes: int) -> int:
    if minutes in ALLOWED_INTERVAL_MINUTES:
        return minutes
    return DEFAULT_INTERVAL_MINUTES


def normalize_mode(raw: Optional[str]) -> str:
    if (raw or "").strip() == MODE_AT_TIME:
        return MODE_AT_TIME
    return MODE_INTERVAL


def parse_run_at(raw: Optional[str]) -> Optional[str]:
    if not raw or not str(raw).strip():
        return None
    parts = str(raw).strip().split(":")
    if len(parts) < 2:
        return None
    try:
        hour = int(parts[0])
        minute = int(parts[1])
    except ValueError:
        return None
    if hour < 0 or hour > 23 or minute < 0 or minute > 59:
        return None
    return f"{hour:02d}:{minute:02d}"


def _as_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _scheduled_today(local: datetime, run_at: str) -> datetime:
    hour, minute = (int(part) for part in run_at.split(":", 1))
    return local.replace(hour=hour, minute=minute, second=0, microsecond=0)


def should_run_incremental(
    *,
    enabled: bool,
    weekdays: Iterable[int],
    interval_minutes: int,
    now: datetime,
    last_run: Optional[datetime],
    is_running: bool,
    mode: str = MODE_INTERVAL,
    run_at: Optional[str] = None,
) -> bool:
    if not enabled or is_running:
        return False
    allowed = {int(day) for day in weekdays if int(day) in ALL_WEEKDAYS}
    if not allowed:
        return False
    local = _as_aware(now)
    if local.weekday() not in allowed:
        return False
    if normalize_mode(mode) == MODE_AT_TIME:
        parsed = parse_run_at(run_at)
        if not parsed:
            return False
        scheduled = _scheduled_today(local, parsed)
        if local < scheduled:
            return False
        if last_run is None:
            return True
        last_local = _as_aware(last_run).astimezone(local.tzinfo)
        return not (last_local.date() == local.date() and last_local >= scheduled)
    if last_run is None:
        return True
    elapsed = local - _as_aware(last_run).astimezone(local.tzinfo)
    return elapsed >= timedelta(minutes=normalize_interval_minutes(interval_minutes))
