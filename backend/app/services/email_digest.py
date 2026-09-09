from __future__ import annotations

import logging
import smtplib
from collections import defaultdict
from email.message import EmailMessage
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.domain.digest_html import (
    render_behind_html,
    render_progress_html,
    render_recommendations_html,
    render_results_html,
    wrap_digest_html,
)
from app.services.export_xlsx import quarterly_plans_workbook, quarterly_results_workbook, workbook_bytes
from app.services.mail_settings import MailConfig, get_mail_config
from app.services.quarterly_results import build_quarterly_results
from app.services.reports import build_quarterly_plans_report

logger = logging.getLogger(__name__)

XLSX_SUBTYPE = "vnd.openxmlformats-officedocument.spreadsheetml.sheet"


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


def _managers_section(report) -> str:
    by_manager: dict[str, list] = defaultdict(list)
    for row in report.clients:
        key = row.manager_name or "Без менеджера"
        by_manager[key].append(row)
    lines = ["По менеджерам", ""]
    if not by_manager:
        lines.append("Нет данных.")
        return "\n".join(lines)
    for name in sorted(by_manager.keys(), key=str.lower):
        rows = by_manager[name]
        plan = sum((float(r.plan or 0) for r in rows), 0.0)
        fact = sum((float(r.fact or 0) for r in rows), 0.0)
        pct = (fact / plan * 100) if plan else 0.0
        behind = sum(1 for r in rows if float(r.percent or 0) < 100)
        lines.append(
            f"{name}: клиентов={len(rows)} план={plan:.0f} факт={fact:.0f} %={pct:.1f} отстающих={behind}"
        )
    return "\n".join(lines)


def _progress_text(year: int, quarter: int, report) -> str:
    lines = [f"Промежуточные итоги {year} Q{quarter}", ""]
    if not report.clients:
        lines.append("Нет клиентов с выставленным планом.")
    else:
        for row in report.clients:
            lines.append(
                f"{row.counterparty}: план={row.plan} факт={row.fact} %={row.percent} динамика={row.dynamics}"
            )
    return "\n".join(lines)


def _behind_text(report) -> str:
    behind = [row for row in report.clients if float(row.percent or 0) < 100]
    lines = ["Отстающие (< 100%)", ""]
    if not behind:
        lines.append("Нет отстающих по плану.")
    else:
        for row in behind:
            mgr = f" [{row.manager_name}]" if row.manager_name else ""
            lines.append(f"{row.counterparty}{mgr}: {row.percent}%")
    return "\n".join(lines)


def _results_text(year: int, quarter: int, report: dict) -> str:
    lines = [f"Итоги квартала {year} Q{quarter}", ""]
    clients = report.get("clients") or []
    if not clients:
        lines.append("Нет акционных клиентов.")
        return "\n".join(lines)
    for row in clients:
        lines.append(
            f"{row.get('counterparty')}: план={row.get('plan')} факт={row.get('shipment_fact')} "
            f"%={row.get('shipment_percent')} продажи={row.get('sales_total')}"
        )
    return "\n".join(lines)


def build_digest_parts(db: Session, *, year: int, quarter: int, config: Optional[MailConfig] = None) -> dict[str, Any]:
    cfg = config or get_mail_config(db)
    text_sections: list[str] = []
    html_sections: list[str] = []
    attachments: list[tuple[str, bytes]] = []
    title = f"Квартальные отчёты {year} Q{quarter}"

    progress = None
    if cfg.include_quarterly or cfg.include_behind:
        progress = build_quarterly_plans_report(db, year=year, quarter=quarter)
    if cfg.include_quarterly and progress is not None:
        text_sections.append(_progress_text(year, quarter, progress))
        text_sections.append(_managers_section(progress))
        html_sections.append(render_progress_html(year, quarter, progress.clients, progress.slices))
        attachments.append(
            (f"quarterly_progress_{year}_Q{quarter}.xlsx", workbook_bytes(quarterly_plans_workbook(progress)))
        )
        results = build_quarterly_results(db, year=year, quarter=quarter)
        text_sections.append(_results_text(year, quarter, results))
        html_sections.append(render_results_html(year, quarter, results.get("clients") or [], results.get("labels")))
        attachments.append(
            (f"quarterly_results_{year}_Q{quarter}.xlsx", workbook_bytes(quarterly_results_workbook(results)))
        )
    if cfg.include_behind and progress is not None:
        text_sections.append(_behind_text(progress))
        html_sections.append(render_behind_html(progress.clients))
    if cfg.include_recommendations:
        from app.services.ai import generate_recommendations

        recs = generate_recommendations(db).items[:8]
        rec_lines = ["Рекомендации", ""]
        if not recs:
            rec_lines.append("Нет рекомендаций.")
        else:
            for item in recs:
                who = item.counterparty or ""
                prefix = f"{who}: " if who else ""
                rec_lines.append(f"- {prefix}{item.message}")
        text_sections.append("\n".join(rec_lines))
        html_sections.append(render_recommendations_html(recs))

    if not text_sections:
        text = "В настройках рассылки ничего не выбрано."
        html = wrap_digest_html(title, [])
    else:
        text = "\n\n".join(section for section in text_sections if section)
        html = wrap_digest_html(title, html_sections)
    return {"title": title, "text": text, "html": html, "attachments": attachments}


def build_digest_preview(db: Session, *, year: int, quarter: int, config: Optional[MailConfig] = None) -> str:
    return str(build_digest_parts(db, year=year, quarter=quarter, config=config)["text"])


def send_weekly_digest(
    db: Session,
    *,
    year: int,
    quarter: int,
    force_send: bool = False,
    smtp_cls: type[smtplib.SMTP] = smtplib.SMTP,
) -> dict[str, Any]:
    config = get_mail_config(db)
    parts = build_digest_parts(db, year=year, quarter=quarter, config=config)
    body = parts["text"]

    if not force_send and not config.enabled:
        return {"sent": False, "preview": body, "reason": "mail_disabled"}
    if not config.smtp_host:
        logger.info("SMTP not configured; mail preview:\n%s", body)
        return {"sent": False, "preview": body, "reason": "smtp_not_configured"}
    if not config.recipients:
        return {"sent": False, "preview": body, "reason": "recipients_empty"}

    msg = EmailMessage()
    msg["Subject"] = f"[Акции] {parts['title']}"
    msg["From"] = config.smtp_from or config.smtp_user or "noreply@example.com"
    msg["To"] = ", ".join(config.recipients)
    msg.set_content(body)
    msg.add_alternative(parts["html"], subtype="html")
    for filename, data in parts["attachments"]:
        msg.add_attachment(data, maintype="application", subtype=XLSX_SUBTYPE, filename=filename)

    with smtp_cls(config.smtp_host, config.smtp_port, timeout=30) as smtp:
        if config.use_tls:
            smtp.starttls()
        if config.smtp_user:
            smtp.login(config.smtp_user, config.smtp_password)
        smtp.send_message(msg)
    return {
        "sent": True,
        "preview": body,
        "attachments": [name for name, _ in parts["attachments"]],
    }
