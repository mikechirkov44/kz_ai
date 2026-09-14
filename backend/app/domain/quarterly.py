"""Итоговый отчёт по кварталу (ТЗ лист 6): блоки цвет / ЖЦТ / тип изделия."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

from app.domain.fact_shipments import quarter_bounds
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


TWOPLACES = Decimal("0.01")


@dataclass(frozen=True)
class QuarterWeek:
    """Календарная неделя пн–вс, обрезанная границами квартала."""

    index: int
    start: date
    end: date
    days: int


@dataclass(frozen=True)
class WeeklyPlanFact:
    week_index: int
    week_start: date
    week_end: date
    days: int
    plan: Decimal
    fact: Decimal
    percent: Decimal
    is_current: bool


def monday_of(day: date) -> date:
    return day - timedelta(days=day.weekday())


def quarter_weeks(year: int, quarter: int) -> list[QuarterWeek]:
    """Недели, пересекающие квартал. Неполные первая и последняя — короче."""
    q_start, q_end = quarter_bounds(year, quarter)
    cursor = monday_of(q_start)
    weeks: list[QuarterWeek] = []
    index = 1
    while cursor <= q_end:
        week_end = cursor + timedelta(days=6)
        start = max(cursor, q_start)
        end = min(week_end, q_end)
        if start <= end:
            days = (end - start).days + 1
            weeks.append(QuarterWeek(index=index, start=start, end=end, days=days))
            index += 1
        cursor += timedelta(days=7)
    return weeks


def allocate_weekly_plan(total: Decimal, day_counts: Sequence[int]) -> list[Decimal]:
    """Делит квартальный план пропорционально дням недели; сумма равна плану."""
    days_list = [max(0, int(count)) for count in day_counts]
    n = len(days_list)
    if n == 0:
        return []
    total_n = Decimal(total or 0)
    total_days = sum(days_list)
    if total_n == 0 or total_days <= 0:
        return [Decimal("0.00")] * n
    allocated: list[Decimal] = []
    used = Decimal("0.00")
    last = n - 1
    for i, days in enumerate(days_list):
        if i == last:
            part = (total_n - used).quantize(TWOPLACES)
        else:
            part = (total_n * Decimal(days) / Decimal(total_days)).quantize(TWOPLACES, rounding=ROUND_HALF_UP)
            used += part
        allocated.append(part)
    return allocated


def week_index_for_date(doc_date: date | None, weeks: Sequence[QuarterWeek]) -> int | None:
    if doc_date is None:
        return None
    for week in weeks:
        if week.start <= doc_date <= week.end:
            return week.index
    return None


def fact_amounts_by_week(
    weeks: Sequence[QuarterWeek],
    items: Sequence[tuple[date | None, Decimal]],
) -> dict[int, Decimal]:
    totals: dict[int, Decimal] = {week.index: Decimal(0) for week in weeks}
    for doc_date, amount in items:
        index = week_index_for_date(doc_date, weeks)
        if index is None:
            continue
        totals[index] += Decimal(amount or 0)
    return totals


def build_weekly_plan_fact(
    weeks: Sequence[QuarterWeek],
    quarter_plan: Decimal,
    fact_by_index: Mapping[int, Decimal],
    as_of: date,
) -> list[WeeklyPlanFact]:
    plans = allocate_weekly_plan(quarter_plan, [week.days for week in weeks])
    rows: list[WeeklyPlanFact] = []
    for week, plan in zip(weeks, plans, strict=True):
        fact = Decimal(fact_by_index.get(week.index, 0) or 0)
        rows.append(
            WeeklyPlanFact(
                week_index=week.index,
                week_start=week.start,
                week_end=week.end,
                days=week.days,
                plan=plan,
                fact=fact.quantize(TWOPLACES),
                percent=fulfillment_percent(fact, plan),
                is_current=week.start <= as_of <= week.end,
            )
        )
    return rows


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
