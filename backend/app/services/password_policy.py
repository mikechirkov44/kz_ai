from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.config import settings
from app.models import User


def password_must_change(user: User, *, now: datetime | None = None) -> bool:
    """True if password older than PASSWORD_MAX_AGE_DAYS (0 = disabled)."""
    max_days = settings.password_max_age_days
    if max_days <= 0:
        return False
    changed = user.password_changed_at
    if changed is None:
        return True
    if changed.tzinfo is None:
        changed = changed.replace(tzinfo=timezone.utc)
    current = now or datetime.now(timezone.utc)
    return changed + timedelta(days=max_days) <= current
