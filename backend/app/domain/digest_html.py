"""HTML-тело письма квартальных отчётов (ТЗ: HTML + Excel)."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from html import escape
from typing import Any, Iterable, Sequence

from app.domain.turnover import join_value_and_trend

TABLE = "border-collapse:collapse;width:100%;font-family:Arial,sans-serif;font-size:13px;margin:0 0 18px;"
TH = "border:1px solid #d0d7de;background:#f3f4f6;padding:6px 8px;text-align:left;white-space:nowrap;"
TD = "border:1px solid #d0d7de;padding:6px 8px;"
H2 = "font-size:15px;margin:0 0 8px;font-family:Arial,sans-serif;"

PROGRESS_HEADERS = (
    "Головной контрагент",
    "Менеджер",
    "Тип работы",
    "% типа работы",
    "План на квартал",
    "Факт квартал",
    "% выполнения",
    "Динамика",
)

SLICE_HEADERS = ("Срез", "Клиентов", "Выполнен план", "%")

DEFAULT_RESULTS_HEADERS = (
    "Головной контрагент",
    "Менеджер",
    "Тип работы",
    "% типа работы",
    "План отгрузок последний квартал",
    "Факт отгрузок последний",
    "% выполнения",
    "Факт отгрузок пред. кв.",
    "Факт отгрузок предпред. кв.",
    "Динамика отгрузок",
    "Продажи последний кв.",
    "Продажи пред. кв.",
    "Продажи предпред. кв.",
    "Динамика продаж",
    "Комментарий",
)


def _attr(row: Any, key: str, default: object = None) -> object:
    if isinstance(row, dict):
        return row.get(key, default)
    return getattr(row, key, default)


def format_digest_number(value: object | None, *, places: int = 2) -> str:
    if value is None or value == "":
        return "—"
    try:
        number = value if isinstance(value, Decimal) else Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return "—"
    if not number.is_finite():
        return "—"
    text = f"{number:.{places}f}"
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text.replace(".", ",")


def format_digest_with_trend(value: object | None, trend: object | None = None, *, places: int = 2) -> str:
    number = format_digest_number(value, places=places)
    joined = join_value_and_trend(None if number == "—" else number, str(trend) if trend else None)
    return "—" if joined is None or joined == "" else str(joined)


def html_table(headers: Sequence[str], rows: Iterable[Sequence[object]], *, caption: str = "") -> str:
    head = "".join(f'<th style="{TH}">{escape(str(header))}</th>' for header in headers)
    body_parts: list[str] = []
    for row in rows:
        cells = "".join(f'<td style="{TD}">{escape(str(cell))}</td>' for cell in row)
        body_parts.append(f"<tr>{cells}</tr>")
    body = "".join(body_parts) or (
        f'<tr><td style="{TD}" colspan="{max(len(headers), 1)}">Нет данных.</td></tr>'
    )
    cap = f'<h2 style="{H2}">{escape(caption)}</h2>' if caption else ""
    return f'{cap}<table style="{TABLE}"><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>'


def progress_client_rows(clients: Sequence[Any]) -> list[tuple[str, ...]]:
    rows: list[tuple[str, ...]] = []
    for row in clients:
        rows.append(
            (
                str(_attr(row, "counterparty") or ""),
                str(_attr(row, "manager_name") or "—"),
                str(_attr(row, "work_type_label") or _attr(row, "work_type") or "—"),
                format_digest_number(_attr(row, "work_type_percent")),
                format_digest_number(_attr(row, "plan")),
                format_digest_number(_attr(row, "fact")),
                format_digest_number(_attr(row, "percent")),
                format_digest_with_trend(_attr(row, "dynamics"), _attr(row, "dynamics_trend")),
            )
        )
    return rows


def slice_rows(slices: Sequence[Any]) -> list[tuple[str, ...]]:
    rows: list[tuple[str, ...]] = []
    for item in slices:
        rows.append(
            (
                str(_attr(item, "name") or ""),
                str(_attr(item, "clients") or 0),
                str(_attr(item, "fulfilled") or 0),
                format_digest_number(_attr(item, "percent")),
            )
        )
    return rows


def render_progress_html(year: int, quarter: int, clients: Sequence[Any], slices: Sequence[Any] = ()) -> str:
    parts = [
        html_table(
            PROGRESS_HEADERS,
            progress_client_rows(clients),
            caption=f"Промежуточные итоги {year} Q{quarter}",
        )
    ]
    if slices:
        parts.append(html_table(SLICE_HEADERS, slice_rows(slices), caption="Срезы"))
    return "".join(parts)


def render_behind_html(clients: Sequence[Any]) -> str:
    behind = [row for row in clients if _percent(row) < 100]
    rows = [
        (
            str(_attr(row, "counterparty") or ""),
            str(_attr(row, "manager_name") or "—"),
            format_digest_number(_attr(row, "percent")),
        )
        for row in behind
    ]
    return html_table(
        ("Головной контрагент", "Менеджер", "% выполнения"),
        rows,
        caption="Отстающие (< 100%)",
    )


def results_headers(labels: dict[str, str] | None = None) -> tuple[str, ...]:
    labels = labels or {}
    return (
        "Головной контрагент",
        "Менеджер",
        "Тип работы",
        "% типа работы",
        labels.get("plan") or DEFAULT_RESULTS_HEADERS[4],
        labels.get("shipment_fact") or DEFAULT_RESULTS_HEADERS[5],
        labels.get("shipment_percent") or DEFAULT_RESULTS_HEADERS[6],
        labels.get("shipment_prev") or DEFAULT_RESULTS_HEADERS[7],
        labels.get("shipment_prev2") or DEFAULT_RESULTS_HEADERS[8],
        labels.get("shipment_dynamics") or DEFAULT_RESULTS_HEADERS[9],
        labels.get("sales") or DEFAULT_RESULTS_HEADERS[10],
        labels.get("sales_prev") or DEFAULT_RESULTS_HEADERS[11],
        labels.get("sales_prev2") or DEFAULT_RESULTS_HEADERS[12],
        labels.get("sales_dynamics") or DEFAULT_RESULTS_HEADERS[13],
        "Комментарий",
    )


def results_client_rows(clients: Sequence[Any]) -> list[tuple[str, ...]]:
    rows: list[tuple[str, ...]] = []
    for row in clients:
        rows.append(
            (
                str(_attr(row, "counterparty") or ""),
                str(_attr(row, "manager_name") or "—"),
                str(_attr(row, "work_type_label") or _attr(row, "work_type") or "—"),
                format_digest_number(_attr(row, "work_type_percent")),
                format_digest_number(_attr(row, "plan")),
                format_digest_number(_attr(row, "shipment_fact")),
                format_digest_number(_attr(row, "shipment_percent")),
                format_digest_number(_attr(row, "shipment_prev_quarter")),
                format_digest_number(_attr(row, "shipment_prev2_quarter")),
                format_digest_with_trend(
                    _attr(row, "shipment_dynamics_percent"), _attr(row, "shipment_dynamics_trend")
                ),
                format_digest_number(_attr(row, "sales_total")),
                format_digest_number(_attr(row, "sales_prev_quarter")),
                format_digest_number(_attr(row, "sales_prev2_quarter")),
                format_digest_with_trend(_attr(row, "dynamics_percent"), _attr(row, "dynamics_trend")),
                str(_attr(row, "comment") or ""),
            )
        )
    return rows


def render_results_html(year: int, quarter: int, clients: Sequence[Any], labels: dict[str, str] | None = None) -> str:
    return html_table(
        results_headers(labels),
        results_client_rows(clients),
        caption=f"Итоги квартала {year} Q{quarter}",
    )


def render_recommendations_html(items: Sequence[Any]) -> str:
    lines: list[str] = []
    for item in items:
        who = str(_attr(item, "counterparty") or "").strip()
        message = str(_attr(item, "message") or "").strip()
        if not message:
            continue
        prefix = f"{who}: " if who else ""
        lines.append(f"<li>{escape(prefix + message)}</li>")
    body = "".join(lines) or "<li>Нет рекомендаций.</li>"
    return f'<h2 style="{H2}">Рекомендации</h2><ul style="margin:0 0 18px;padding-left:18px;">{body}</ul>'


def wrap_digest_html(title: str, sections: Sequence[str]) -> str:
    inner = "".join(section for section in sections if section) or "<p>В настройках рассылки ничего не выбрано.</p>"
    return (
        "<!DOCTYPE html><html><head><meta charset=\"utf-8\">"
        f"<title>{escape(title)}</title></head>"
        '<body style="margin:0;padding:16px;background:#f8fafc;color:#111827;font-family:Arial,sans-serif;">'
        '<div style="max-width:1100px;margin:0 auto;background:#fff;padding:20px;border:1px solid #e5e7eb;">'
        f'<h1 style="font-size:18px;margin:0 0 16px;">{escape(title)}</h1>'
        f"{inner}</div></body></html>"
    )


def _percent(row: Any) -> float:
    try:
        return float(_attr(row, "percent") or 0)
    except (TypeError, ValueError):
        return 0.0
