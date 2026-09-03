from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.constants import UserRole
from app.models import User
from app.security import hash_password


def ensure_admin_user(db: Session) -> None:
    existing = db.scalar(select(User).where(User.email == settings.admin_email.lower()))
    if existing:
        return
    db.add(
        User(
            email=settings.admin_email.lower(),
            password_hash=hash_password(settings.admin_password),
            role=UserRole.ADMIN.value,
            full_name="Administrator",
            active=True,
        )
    )
    db.commit()
