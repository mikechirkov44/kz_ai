"""Admin settings for incremental auto-sync schedule."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.constants import SyncStatus
from app.domain.sync_schedule import (
    DEFAULT_INTERVAL_MINUTES,
    DEFAULT_RUN_AT,
    MODE_INTERVAL,
    normalize_interval_minutes,
    normalize_mode,
    parse_run_at,
    parse_weekdays,
    serialize_weekdays,
    should_run_incremental,
)
from app.models import SyncSchedule, SyncState

DEFAULT_SLUG = "default"
DEFAULT_WEEKDAYS = "0,1,2,3,4,5,6"


def ensure_sync_schedule(db: Session) -> SyncSchedule:
    row = db.scalar(select(SyncSchedule).where(SyncSchedule.slug == DEFAULT_SLUG))
    if row:
        return row
    row = SyncSchedule(
        slug=DEFAULT_SLUG,
        enabled=True,
        interval_minutes=DEFAULT_INTERVAL_MINUTES,
        mode=MODE_INTERVAL,
        weekdays=DEFAULT_WEEKDAYS,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def get_sync_schedule_row(db: Session) -> SyncSchedule:
    return ensure_sync_schedule(db)


def settings_public_view(row: SyncSchedule) -> dict:
    mode = normalize_mode(getattr(row, "mode", None))
    return {
        "enabled": bool(row.enabled),
        "mode": mode,
        "interval_minutes": normalize_interval_minutes(int(row.interval_minutes or DEFAULT_INTERVAL_MINUTES)),
        "run_at": parse_run_at(getattr(row, "run_at", None)) or DEFAULT_RUN_AT,
        "weekdays": parse_weekdays(row.weekdays),
        "timezone": settings.timezone,
        "env_sync_enabled": bool(settings.sync_enabled),
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def upsert_sync_schedule(
    db: Session,
    *,
    enabled: bool,
    interval_minutes: int,
    weekdays: list[int],
    mode: str = MODE_INTERVAL,
    run_at: Optional[str] = None,
) -> SyncSchedule:
    row = ensure_sync_schedule(db)
    row.enabled = bool(enabled)
    row.mode = normalize_mode(mode)
    row.interval_minutes = normalize_interval_minutes(interval_minutes)
    row.run_at = parse_run_at(run_at) or DEFAULT_RUN_AT
    row.weekdays = serialize_weekdays(weekdays)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def sync_is_running(db: Session) -> bool:
    return db.scalar(select(SyncState.id).where(SyncState.status == SyncStatus.RUNNING.value).limit(1)) is not None


def latest_incremental_at(db: Session) -> Optional[datetime]:
    return db.scalar(select(func.max(SyncState.last_incremental_at)))


def local_now(now: Optional[datetime] = None) -> datetime:
    tz = ZoneInfo(settings.timezone)
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    return current.astimezone(tz)


def due_incremental(db: Session, now: Optional[datetime] = None) -> bool:
    row = ensure_sync_schedule(db)
    current = local_now(now)
    last_run = row.last_dispatched_at
    state_run = latest_incremental_at(db)
    if state_run and (last_run is None or state_run > last_run):
        last_run = state_run
    return should_run_incremental(
        enabled=bool(row.enabled),
        weekdays=parse_weekdays(row.weekdays),
        interval_minutes=int(row.interval_minutes or DEFAULT_INTERVAL_MINUTES),
        now=current,
        last_run=last_run,
        is_running=sync_is_running(db),
        mode=normalize_mode(getattr(row, "mode", None)),
        run_at=parse_run_at(getattr(row, "run_at", None)),
    )


def mark_dispatched(db: Session, when: Optional[datetime] = None) -> None:
    row = ensure_sync_schedule(db)
    row.last_dispatched_at = when or datetime.now(timezone.utc)
    db.add(row)
    db.commit()
