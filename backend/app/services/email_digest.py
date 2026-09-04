from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.services.mail_settings import MailConfig, get_mail_config
from app.services.reports import build_quarterly_plans_report

logger = logging.getLogger(__name__)


def check_smtp_connection(config: MailConfig, *, smtp_cls: type[smtplib.SMTP] = smtplib.SMTP) -> dict:
    if not config.smtp_host:
        return {"status": "error", "detail": "Не указан SMTP-сервер"}
    try:
        with smtp_cls(config.smtp_host, config.smtp_port, timeout=15) as smtp:
            if config.use_tls:
                smtp.starttls()
            if config.smtp_user:
                smtp.login(config.smtp_user, config.smtp_password)
        return {"status": "ok", "detail": "SMTP доступен"}
    except Exception as exc:  # noqa: BLE001
        logger.warning("SMTP test failed: %s", exc)
        return {"status": "error", "detail": str(exc)}


def build_digest_preview(db: Session, *, year: int, quarter: int, config: Optional[MailConfig] = None) -> str:
    cfg = config or get_mail_config(db)
    sections: list[str] = []
    if cfg.include_quarterly or cfg.include_behind:
        report = build_quarterly_plans_report(db, year=year, quarter=quarter)
        if cfg.include_quarterly:
            lines = [f"План/факт {year} Q{quarter}", ""]
            if not report.clients:
                lines.append("Нет клиентов с выставленным планом.")
            else:
                for row in report.clients:
                    lines.append(
                        f"{row.counterparty}: план={row.plan} факт={row.fact} %={row.percent} динамика={row.dynamics}"
                    )
            sections.append("\n".join(lines))
        if cfg.include_behind:
            behind = [row for row in report.clients if float(row.percent or 0) < 100]
            lines = ["Отстающие (< 100%)", ""]
            if not behind:
                lines.append("Нет отстающих по плану.")
            else:
                for row in behind:
                    lines.append(f"{row.counterparty}: {row.percent}%")
            sections.append("\n".join(lines))
    if cfg.include_recommendations:
        from app.services.ai import generate_recommendations

        recs = generate_recommendations(db).items[:8]
        lines = ["Рекомендации", ""]
        if not recs:
            lines.append("Нет рекомендаций.")
        else:
            for item in recs:
                who = item.counterparty or ""
                prefix = f"{who}: " if who else ""
                lines.append(f"- {prefix}{item.message}")
        sections.append("\n".join(lines))
    if not sections:
        return "В настройках рассылки ничего не выбрано."
    return "\n\n".join(sections)


def send_weekly_digest(
    db: Session,
    *,
    year: int,
    quarter: int,
    force_send: bool = False,
    smtp_cls: type[smtplib.SMTP] = smtplib.SMTP,
) -> dict[str, Any]:
    config = get_mail_config(db)
    body = build_digest_preview(db, year=year, quarter=quarter, config=config)

    if not force_send and not config.enabled:
        return {"sent": False, "preview": body, "reason": "mail_disabled"}
    if not config.smtp_host:
        logger.info("SMTP not configured; mail preview:\n%s", body)
        return {"sent": False, "preview": body, "reason": "smtp_not_configured"}
    if not config.recipients:
        return {"sent": False, "preview": body, "reason": "recipients_empty"}

    msg = EmailMessage()
    msg["Subject"] = f"[Акции] План/Факт {year} Q{quarter}"
    msg["From"] = config.smtp_from or config.smtp_user or "noreply@example.com"
    msg["To"] = ", ".join(config.recipients)
    msg.set_content(body)

    with smtp_cls(config.smtp_host, config.smtp_port, timeout=30) as smtp:
        if config.use_tls:
            smtp.starttls()
        if config.smtp_user:
            smtp.login(config.smtp_user, config.smtp_password)
        smtp.send_message(msg)
    return {"sent": True, "preview": body}
