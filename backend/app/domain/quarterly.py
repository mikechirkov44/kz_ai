"""Итоговый отчёт по кварталу (ТЗ лист 6): блоки цвет / ЖЦТ / тип изделия."""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal

from app.domain.turnover import (
    avg_quarter_turnover,
    month_avg_stock,
    quarter_avg_stock,
    quarter_turnover,
)

BLOCK_KEYS = ("metal_color", "lts", "wear_type")
BLOCK_LABELS = {
    "metal_color": "Цвет металла",
    "lts": "ЖЦТ",
    "wear_type": "Тип изделия",
}
TOTAL_DIMENSION = "Итого"


def dim_metrics(
    sales: Decimal,
    month_begins: Sequence[Decimal],
    month_ends: Sequence[Decimal],
) -> dict[str, Decimal]:
    """Метрики одного измерения: ср. остаток, продажи, об-ть кв, ср. об-ть / 3."""
    begins = [Decimal(v) for v in month_begins]
    ends = [Decimal(v) for v in month_ends]
    n = max(len(begins), len(ends), 3)
    while len(begins) < n:
        begins.append(Decimal(0))
    while len(ends) < n:
        ends.append(Decimal(0))
    monthly = [month_avg_stock(begins[i], ends[i]) for i in range(3)]
    avg_stock = quarter_avg_stock(monthly)
    sales_q = Decimal(sales)
    q_turn = quarter_turnover(sales_q, avg_stock)
    return {
        "avg_stock": avg_stock,
        "sales_total": sales_q,
        "quarter_turnover_percent": q_turn,
        "avg_month_turnover_percent": avg_quarter_turnover(q_turn),
    }


def zip_block_rows(*blocks: list[dict]) -> list[tuple[dict | None, ...]]:
    """Строки матрицы: категории блоков идут параллельно, короткие блоки дополняются пустыми ячейками."""
    n = max((len(b) for b in blocks), default=0)
    rows: list[tuple[dict | None, ...]] = []
    for i in range(n):
        rows.append(tuple(b[i] if i < len(b) else None for b in blocks))
    return rows


def should_include_summary_client(
    *,
    has_quarter_sales: bool,
    include_empty: bool = False,
    has_empty_anchor: bool = False,
) -> bool:
    """ТЗ: все, у кого были продажи за квартал, даже без плана. Только остатки — нет."""
    if has_quarter_sales:
        return True
    return bool(include_empty and has_empty_anchor)


def summary_counterparty_ids(
    sale_ids: set,
    extra_ids: set | None = None,
    *,
    include_empty: bool = False,
) -> set:
    if include_empty:
        return set(sale_ids) | set(extra_ids or ())
    return set(sale_ids)


def promo_scope_ids(
    promo_ids: set,
    *,
    allowed_ids: set | None = None,
    counterparty_id=None,
) -> set:
    """Отчёт «Итоги квартала»: все акционные клиенты в зоне доступа."""
    ids = set(promo_ids)
    if allowed_ids is not None:
        ids &= set(allowed_ids)
    if counterparty_id is not None:
        ids &= {counterparty_id}
    return ids


def fulfillment_percent(fact: Decimal, plan: Decimal) -> Decimal:
    """% выполнения = факт / план × 100. Нет плана — 0."""
    plan_n = Decimal(plan)
    if plan_n == 0:
        return Decimal(0)
    return (Decimal(fact) / plan_n * Decimal(100)).quantize(Decimal("0.01"))


def quarterly_results_labels(quarter: int, prev_q: int, prev2_q: int) -> dict[str, str]:
    """Подписи колонок плоского отчёта «Итоги квартала»."""
    return {
        "plan": f"План отгрузок на {quarter} квартал",
        "shipment_fact": f"Факт отгрузок {quarter} квартал",
        "shipment_percent": "% выполнения",
        "shipment_prev": f"Факт отгрузок {prev_q} квартал",
        "shipment_prev2": f"Факт отгрузок {prev2_q} квартал",
        "shipment_dynamics": "Динамика отгрузок",
        "sales": f"Продажи {quarter} кв.",
        "sales_prev": f"Продажи {prev_q} кв.",
        "sales_prev2": f"Продажи {prev2_q} кв.",
        "sales_dynamics": "Динамика продаж",
    }


def recommendations_digest(items: Sequence[dict], limit: int | None = None) -> str:
    lines: list[str] = []
    for item in items:
        text = str(item.get("title") or item.get("message") or "").strip()
        if not text:
            continue
        lines.append(text)
        if limit is not None and len(lines) >= limit:
            break
    return " · ".join(lines)
