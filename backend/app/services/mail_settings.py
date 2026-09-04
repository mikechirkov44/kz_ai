"""Admin mail / weekly digest settings (encrypted SMTP password)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.domain.mail import parse_recipients
from app.models import MailSettings
from app.security import decrypt_secret, encrypt_secret

DEFAULT_SLUG = "default"
DEFAULT_PORT = 587


@dataclass(frozen=True)
class MailConfig:
    enabled: bool
    smtp_host: str
    smtp_port: int
    smtp_user: str
    smtp_password: str
    smtp_from: str
    use_tls: bool
    recipients: list[str]
    include_quarterly: bool
    include_behind: bool
    include_recommendations: bool


def ensure_mail_settings(db: Session) -> MailSettings:
    row = db.scalar(select(MailSettings).where(MailSettings.slug == DEFAULT_SLUG))
    if row:
        return row
    password = settings.smtp_password or ""
    row = MailSettings(
        slug=DEFAULT_SLUG,
        enabled=bool(settings.smtp_host and settings.digest_email),
        smtp_host=settings.smtp_host or "",
        smtp_port=int(settings.smtp_port or DEFAULT_PORT),
        smtp_user=settings.smtp_user or "",
        smtp_password_encrypted=encrypt_secret(password) if password else "",
        smtp_from=settings.smtp_from or "",
        use_tls=True,
        recipients=settings.digest_email or "",
        include_quarterly=True,
        include_behind=True,
        include_recommendations=False,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def get_mail_row(db: Session) -> MailSettings:
    return ensure_mail_settings(db)


def settings_public_view(row: MailSettings) -> dict:
    return {
        "enabled": bool(row.enabled),
        "smtp_host": row.smtp_host or "",
        "smtp_port": int(row.smtp_port or DEFAULT_PORT),
        "smtp_user": row.smtp_user or "",
        "password_set": bool(row.smtp_password_encrypted),
        "smtp_from": row.smtp_from or "",
        "use_tls": bool(row.use_tls),
        "recipients": row.recipients or "",
        "include_quarterly": bool(row.include_quarterly),
        "include_behind": bool(row.include_behind),
        "include_recommendations": bool(row.include_recommendations),
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def get_mail_config(db: Session) -> MailConfig:
    row = get_mail_row(db)
    password = decrypt_secret(row.smtp_password_encrypted) if row.smtp_password_encrypted else ""
    return MailConfig(
        enabled=bool(row.enabled),
        smtp_host=(row.smtp_host or "").strip(),
        smtp_port=int(row.smtp_port or DEFAULT_PORT),
        smtp_user=(row.smtp_user or "").strip(),
        smtp_password=password,
        smtp_from=(row.smtp_from or "").strip(),
        use_tls=bool(row.use_tls),
        recipients=parse_recipients(row.recipients or ""),
        include_quarterly=bool(row.include_quarterly),
        include_behind=bool(row.include_behind),
        include_recommendations=bool(row.include_recommendations),
    )


def upsert_mail_settings(
    db: Session,
    *,
    enabled: bool,
    smtp_host: str,
    smtp_port: int,
    smtp_user: str,
    smtp_password: Optional[str],
    smtp_from: str,
    use_tls: bool,
    recipients: str,
    include_quarterly: bool,
    include_behind: bool,
    include_recommendations: bool,
) -> MailSettings:
    row = get_mail_row(db)
    row.enabled = enabled
    row.smtp_host = (smtp_host or "").strip()
    row.smtp_port = smtp_port
    row.smtp_user = (smtp_user or "").strip()
    row.smtp_from = (smtp_from or "").strip()
    row.use_tls = use_tls
    row.recipients = (recipients or "").strip()
    row.include_quarterly = include_quarterly
    row.include_behind = include_behind
    row.include_recommendations = include_recommendations
    if smtp_password is not None and smtp_password != "":
        row.smtp_password_encrypted = encrypt_secret(smtp_password)
    db.flush()
    return row
