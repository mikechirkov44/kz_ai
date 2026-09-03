from datetime import date

from app.config import settings
from app.db import SessionLocal
from app.services.email_digest import send_weekly_digest
from app.services.sync import sync_all_enabled
from app.workers.celery_app import celery_app


@celery_app.task(name="app.workers.tasks.sync_incremental")
def sync_incremental() -> dict:
    if not settings.sync_enabled:
        return {"skipped": True, "reason": "SYNC_ENABLED=false"}
    db = SessionLocal()
    try:
        return sync_all_enabled(db, full=False, source_id="asil")
    finally:
        db.close()


@celery_app.task(name="app.workers.tasks.sync_full")
def sync_full() -> dict:
    if not settings.sync_enabled:
        return {"skipped": True, "reason": "SYNC_ENABLED=false"}
    db = SessionLocal()
    try:
        return sync_all_enabled(db, full=True)
    finally:
        db.close()


@celery_app.task(name="app.workers.tasks.weekly_digest")
def weekly_digest() -> dict:
    today = date.today()
    quarter = (today.month - 1) // 3 + 1
    db = SessionLocal()
    try:
        sent = send_weekly_digest(db, year=today.year, quarter=quarter)
        return {"sent": sent, "year": today.year, "quarter": quarter}
    finally:
        db.close()
