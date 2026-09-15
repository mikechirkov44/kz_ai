from datetime import datetime, timezone

from app.constants import (
    STALE_SYNC_AFTER_SECONDS,
    SYNC_DOCUMENT_ENTITIES,
    SYNC_ENTITIES,
    SyncStatus,
)


def ordered_entities(selected: list[str] | None) -> list[str]:
    """Keep the catalog → documents order; ignore unknown names."""
    if not selected:
        return list(SYNC_ENTITIES)
    wanted = {name for name in selected if name in SYNC_ENTITIES}
    return [name for name in SYNC_ENTITIES if name in wanted]


def normalize_sync_items(items: list[dict] | None) -> list[tuple[str, str]]:
    """Deduped (source_id, entity) pairs in first-seen order."""
    if not items:
        return []
    out: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for item in items:
        source_id = str(item.get("source_id") or "").strip()
        entity = str(item.get("entity") or "").strip()
        if not source_id or entity not in SYNC_ENTITIES:
            continue
        key = (source_id, entity)
        if key in seen:
            continue
        seen.add(key)
        out.append(key)
    return out


def sync_progress_percent(done: int, expected: int, status: str) -> int | None:
    """Share of last-run size. Running stays below 100% until the job finishes."""
    if status == SyncStatus.SUCCESS.value:
        return 100
    if expected <= 0:
        return None
    pct = int(max(0, done) * 100 / expected)
    if status in {SyncStatus.RUNNING.value, SyncStatus.QUEUED.value} and pct >= 100:
        return 99
    return min(100, pct)


def queued_idle_status(rows_synced: int) -> str:
    return SyncStatus.SUCCESS.value if rows_synced else SyncStatus.IDLE.value


def sync_count_unit(entity: str) -> str:
    """Documents for journals, records for catalogs and registers."""
    return "документов" if entity in SYNC_DOCUMENT_ENTITIES else "записей"


def is_stale_sync_status(
    status: str,
    updated_at: datetime | None,
    *,
    now: datetime,
    stale_after_seconds: int = STALE_SYNC_AFTER_SECONDS,
) -> bool:
    """True when a running row has no heartbeat for too long."""
    if status != SyncStatus.RUNNING.value:
        return False
    if updated_at is None:
        return True
    stamp = updated_at if updated_at.tzinfo else updated_at.replace(tzinfo=timezone.utc)
    moment = now if now.tzinfo else now.replace(tzinfo=timezone.utc)
    return (moment - stamp).total_seconds() >= stale_after_seconds


def should_report_sync_progress(*, done: int, seen: int = 0, lines: int = 0) -> bool:
    """Heartbeat while scanning 1C pages, not only after used documents."""
    if done and done % 20 == 0:
        return True
    if seen and seen % 100 == 0:
        return True
    if lines and lines % 200 == 0:
        return True
    return False
