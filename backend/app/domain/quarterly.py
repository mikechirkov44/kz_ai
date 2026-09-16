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


SKIP_DIMENSIONS = frozenset({TOTAL_DIMENSION, "—", "", "без характеристик 1С"})
_BUNDLE_DETAIL_KEYS = ("bundle", "strong_bundle", "weak_bundle")
_DIM_DETAIL_KEYS = ("wear_type", "lts", "metal_color")
ACTION_VERBS = {
    "return": "Верните",
    "restock": "Довезите",
    "transfer": "Переложите",
    "reprice": "Снизьте цену",
}


def is_matchable_dimension(value: object) -> bool:
    text = str(value or "").strip()
    return bool(text) and text not in SKIP_DIMENSIONS


def _as_number(raw: object) -> float | None:
    if isinstance(raw, bool):
        return None
    if isinstance(raw, (int, float)):
        return float(raw)
    if isinstance(raw, str):
        try:
            return float(raw.replace(" ", "").replace(",", ".").replace("%", ""))
        except ValueError:
            return None
    return None


def _money_short(value: float) -> str:
    return f"{int(round(value)):,}".replace(",", " ") + " ₸"


def _details_map(item: Mapping) -> Mapping:
    details = item.get("details") or {}
    return details if isinstance(details, Mapping) else {}


def _article_gap_bits(details: Mapping) -> list[str]:
    bits: list[str] = []
    raw = details.get("articles") or []
    if not isinstance(raw, list):
        return bits
    for row in raw[:3]:
        if not isinstance(row, Mapping):
            continue
        article = str(row.get("article") or "").strip()
        if not article:
            continue
        gap = _as_number(row.get("gap_percent"))
        bits.append(f"{article} (−{gap:.0f}%)" if gap is not None else article)
    return bits


def compact_recommendation_line(item: Mapping) -> str:
    comment = str(item.get("llm_comment") or "").strip()
    if comment:
        return comment
    facts = fact_recommendation_line(item)
    if facts:
        return facts
    return str(item.get("title") or item.get("message") or "").strip()


def fact_recommendation_line(item: Mapping) -> str:
    details = _details_map(item)
    action = str(item.get("action") or "")
    wear = str(details.get("wear_type") or "").strip()
    if wear and not is_matchable_dimension(wear):
        wear = ""
    article = str(item.get("article") or "").strip()
    if action == "reprice":
        gap = _as_number(details.get("gap_percent"))
        ceiling = _as_number(details.get("client_avg_price"))
        arts = _article_gap_bits(details)
        parts: list[str] = []
        who = f"«{wear}»" if wear else "товар"
        if gap is not None:
            parts.append(f"Клиент продаёт {who} на {gap:.0f}% дешевле отгрузки.")
        else:
            parts.append(f"Снизьте цену отгрузки ({wear})." if wear else "Снизьте цену отгрузки.")
        if ceiling is not None:
            parts.append(f"Следующие отгрузки — не выше {_money_short(ceiling)}.")
        if arts:
            parts.append(f"Сильнее всего: {', '.join(arts)}.")
        elif article:
            parts.append(f"Артикул {article}.")
        return " ".join(parts)
    title = str(item.get("title") or "").strip()
    extra: list[str] = []
    turn = _as_number(details.get("avg_turnover"))
    if turn is not None:
        extra.append(f"оборачиваемость {turn:.0f}%")
    months = _as_number(details.get("months_without_sales"))
    if months and months > 0:
        extra.append(f"{int(months)} мес. без продаж")
    dest = str(details.get("to_counterparty") or "").strip()
    if dest:
        extra.append(f"переложить на {dest}")
    plan = _as_number(details.get("plan_percent"))
    if plan is not None:
        extra.append(f"план {plan:.0f}%")
    if extra:
        body = ", ".join(extra)
        return f"{title}: {body}." if title else f"{body[0].upper()}{body[1:]}."
    return ""


def _unique_detail_values(group: Sequence[Mapping], key: str) -> list[str]:
    seen: list[str] = []
    for item in group:
        details = _details_map(item)
        raw = details.get(key)
        if not is_matchable_dimension(raw):
            continue
        text = str(raw).strip()
        if text not in seen:
            seen.append(text)
    return seen


def _group_articles(group: Sequence[Mapping]) -> list[str]:
    seen: list[str] = []
    for item in group:
        article = str(item.get("article") or "").strip()
        if article and article not in seen:
            seen.append(article)
        for bit in _article_gap_bits(_details_map(item)):
            name = bit.split(" ", 1)[0]
            if name and name not in seen:
                seen.append(name)
    return seen[:3]


def _merge_action_line(action: str, group: Sequence[Mapping]) -> str:
    if action == "reprice":
        parts = [compact_recommendation_line(item) for item in group]
        return " · ".join(part for part in parts if part)
    head = f"{ACTION_VERBS[action]} {len(group)} SKU"
    wears = _unique_detail_values(group, "wear_type")
    if wears:
        head = f"{head} ({', '.join(wears)})"
    arts = _group_articles(group)
    if arts:
        return f"{head}: {', '.join(arts)}."
    return f"{head}."


def compact_recommendation_lines(items: Sequence[Mapping]) -> list[str]:
    """Понятные фразы для таблицы: что сделать и почему, без телеграфных обрывков."""
    lines: list[str] = []
    bucket_action: str | None = None
    bucket: list[Mapping] = []

    def flush() -> None:
        nonlocal bucket_action, bucket
        if not bucket:
            return
        if bucket_action in ACTION_VERBS and len(bucket) > 1:
            lines.append(_merge_action_line(bucket_action, bucket))
        else:
            for item in bucket:
                text = compact_recommendation_line(item)
                if text:
                    lines.append(text)
        bucket_action = None
        bucket = []

    for item in items:
        if item.get("llm_comment"):
            flush()
            text = compact_recommendation_line(item)
            if text and text not in lines:
                lines.append(text)
            continue
        action = str(item.get("action") or "")
        if action not in ACTION_VERBS:
            flush()
            text = compact_recommendation_line(item)
            if text:
                lines.append(text)
            continue
        if bucket_action is None or action != bucket_action:
            flush()
            bucket_action = action
            bucket = [item]
        else:
            bucket.append(item)
    flush()
    return lines


def recommendations_digest(items: Sequence[Mapping], limit: int | None = None) -> str:
    lines = compact_recommendation_lines(items)
    if limit is not None:
        lines = lines[:limit]
    return " · ".join(lines)


def recommendation_dimension_values(item: Mapping) -> set[str]:
    details = item.get("details") or {}
    if not isinstance(details, Mapping):
        details = {}
    values: set[str] = set()
    for key in _DIM_DETAIL_KEYS:
        raw = details.get(key)
        if is_matchable_dimension(raw):
            values.add(str(raw).strip())
    for key in _BUNDLE_DETAIL_KEYS:
        raw = details.get(key)
        if not raw:
            continue
        for part in str(raw).split(" / "):
            if is_matchable_dimension(part):
                values.add(part.strip())
    return values


def matrix_row_dimensions(row: Mapping) -> set[str]:
    values: set[str] = set()
    for key in BLOCK_KEYS:
        cell = row.get(key) or {}
        if not isinstance(cell, Mapping):
            continue
        dim = cell.get("dimension")
        if is_matchable_dimension(dim):
            values.add(str(dim).strip())
    return values


def assign_matrix_recommendations(matrix: list[dict], items: Sequence[Mapping]) -> None:
    """Раскладывает рекомендации по строкам матрицы: совпала любая из трёх категорий — в ячейку.

    Строка «Итого» получает только то, что ни к одной категории не привязалось.
    Одна рекомендация может стоять в нескольких строках, без дублей внутри ячейки.
    """
    rec_dims = [(item, recommendation_dimension_values(item)) for item in items]
    placed: set[int] = set()
    for row in matrix:
        if row.get("is_total"):
            continue
        row_dims = matrix_row_dimensions(row)
        matched: list[Mapping] = []
        seen: set[int] = set()
        for item, dims in rec_dims:
            if not dims or not row_dims or not (dims & row_dims):
                continue
            ident = id(item)
            if ident in seen:
                continue
            seen.add(ident)
            matched.append(item)
            placed.add(ident)
        row["recommendations"] = matched
        row["recommendations_text"] = recommendations_digest(matched)
    leftover = [item for item, _ in rec_dims if id(item) not in placed]
    leftover_text = recommendations_digest(leftover)
    for row in matrix:
        if not row.get("is_total"):
            continue
        row["recommendations"] = leftover
        row["recommendations_text"] = leftover_text
