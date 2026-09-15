from datetime import date

from app.config import settings
from app.db import SessionLocal
from app.domain.sync_run import normalize_sync_items
from app.services.email_digest import send_weekly_digest
from app.services.sync import sync_all_enabled
from app.services.sync_schedule import due_incremental, mark_dispatched
from app.workers.celery_app import celery_app


def _run_sync(
    *,
    full: bool,
    source_id: str | None = None,
    entities: list[str] | None = None,
    items: list[dict] | None = None,
) -> dict:
    """Run a sync queued from admin. SYNC_ENABLED only gates the schedule tick."""
    db = SessionLocal()
    try:
        return sync_all_enabled(
            db,
            full=full,
            source_id=source_id,
            entities=entities,
            items=normalize_sync_items(items) or None,
        )
    finally:
        db.close()


@celery_app.task(name="app.workers.tasks.sync_incremental")
def sync_incremental(
    source_id: str | None = None,
    entities: list[str] | None = None,
    items: list[dict] | None = None,
) -> dict:
    """Incremental sync for all configured sources (or one source_id / selected objects)."""
    return _run_sync(full=False, source_id=source_id, entities=entities, items=items)


@celery_app.task(name="app.workers.tasks.sync_full")
def sync_full(
    source_id: str | None = None,
    entities: list[str] | None = None,
    items: list[dict] | None = None,
) -> dict:
    """Full sync including client orders and production receipts. Manual only."""
    return _run_sync(full=True, source_id=source_id, entities=entities, items=items)


@celery_app.task(name="app.workers.tasks.tick_scheduled_sync")
def tick_scheduled_sync() -> dict:
    """Fire incremental sync when the admin schedule is due. Full sync stays manual."""
    if not settings.sync_enabled:
        return {"skipped": True, "reason": "SYNC_ENABLED=false"}
    db = SessionLocal()
    try:
        if not due_incremental(db):
            return {"skipped": True, "reason": "not due"}
        mark_dispatched(db)
        return sync_all_enabled(db, full=False)
    finally:
        db.close()


@celery_app.task(name="app.workers.tasks.weekly_digest")
def weekly_digest(year: int | None = None, quarter: int | None = None) -> dict:
    today = date.today()
    y = year or today.year
    q = quarter or ((today.month - 1) // 3 + 1)
    db = SessionLocal()
    try:
        result = send_weekly_digest(db, year=y, quarter=q)
        return {"sent": result["sent"], "year": y, "quarter": q, "preview": result["preview"][:500]}
    finally:
        db.close()
