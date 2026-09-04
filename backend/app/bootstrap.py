from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.constants import UserRole
from app.models import User
from app.security import hash_password
from app.services.llm_settings import ensure_llm_settings
from app.services.mail_settings import ensure_mail_settings
from app.services.odata_settings import ensure_odata_connections


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


def ensure_odata_settings(db: Session) -> None:
    ensure_odata_connections(db)
    ensure_llm_settings(db)
    ensure_mail_settings(db)
