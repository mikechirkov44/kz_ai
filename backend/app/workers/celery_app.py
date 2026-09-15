import logging

from celery import Celery
from celery.schedules import crontab
from celery.signals import worker_ready

from app.config import settings

log = logging.getLogger(__name__)

celery_app = Celery("kz_ai", broker=settings.redis_url, backend=settings.redis_url)
celery_app.conf.timezone = settings.timezone
celery_app.conf.beat_schedule = {
    "sync-schedule-tick": {
        "task": "app.workers.tasks.tick_scheduled_sync",
        "schedule": crontab(minute="*"),
        "options": {"expires": 50},
    },
    "weekly-digest": {
        "task": "app.workers.tasks.weekly_digest",
        "schedule": crontab(minute=0, hour=8, day_of_week=1),
    },
}
celery_app.autodiscover_tasks(["app.workers"])


@worker_ready.connect
def recover_stale_sync_on_worker_ready(**_kwargs) -> None:
    from app.db import SessionLocal
    from app.services.sync import recover_stale_sync_states

    db = SessionLocal()
    try:
        recover_stale_sync_states(db)
    except Exception:
        log.exception("stale sync recover on worker ready failed")
    finally:
        db.close()
