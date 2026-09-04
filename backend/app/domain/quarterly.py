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


def recommendations_digest(items: Sequence[dict], limit: int = 5) -> str:
    messages = [str(item.get("message") or "").strip() for item in items]
    messages = [m for m in messages if m][:limit]
    return " ".join(messages)
