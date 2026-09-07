from celery import Celery
from celery.schedules import crontab

from app.config import settings

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
