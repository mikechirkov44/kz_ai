from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage
from typing import Any

from sqlalchemy.orm import Session

from app.config import settings
from app.services.reports import build_quarterly_plans_report

logger = logging.getLogger(__name__)


def build_digest_preview(db: Session, *, year: int, quarter: int) -> str:
    report = build_quarterly_plans_report(db, year=year, quarter=quarter)
    lines = [f"Квартальные планы {year} Q{quarter}", ""]
    for row in report.clients:
        lines.append(
            f"{row.counterparty}: план={row.plan} факт={row.fact} %={row.percent} динамика={row.dynamics}"
        )
    if not report.clients:
        lines.append("Нет клиентов с выставленным планом.")
    return "\n".join(lines)


def send_weekly_digest(db: Session, *, year: int, quarter: int, force_send: bool = False) -> dict[str, Any]:
    body = build_digest_preview(db, year=year, quarter=quarter)

    if not settings.smtp_host:
        logger.info("SMTP not configured; digest preview:\n%s", body)
        return {"sent": False, "preview": body, "reason": "smtp_not_configured"}

    if not force_send and not settings.digest_email:
        return {"sent": False, "preview": body, "reason": "digest_email_empty"}

    msg = EmailMessage()
    msg["Subject"] = f"[Акции] План/Факт {year} Q{quarter}"
    msg["From"] = settings.smtp_from
    msg["To"] = settings.digest_email
    msg.set_content(body)

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as smtp:
        smtp.starttls()
        if settings.smtp_user:
            smtp.login(settings.smtp_user, settings.smtp_password)
        smtp.send_message(msg)
    return {"sent": True, "preview": body}
