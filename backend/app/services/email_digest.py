from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage

from sqlalchemy.orm import Session

from app.config import settings
from app.services.reports import build_quarterly_plans_report

logger = logging.getLogger(__name__)


def send_weekly_digest(db: Session, *, year: int, quarter: int) -> bool:
    report = build_quarterly_plans_report(db, year=year, quarter=quarter)
    lines = [f"Квартальные планы {year} Q{quarter}", ""]
    for row in report.clients:
        lines.append(
            f"{row.counterparty}: план={row.plan} факт={row.fact} %={row.percent} динамика={row.dynamics}"
        )
    body = "\n".join(lines) if report.clients else "Нет клиентов с выставленным планом."

    if not settings.smtp_host:
        logger.info("SMTP not configured; digest preview:\n%s", body)
        return False

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
    return True
