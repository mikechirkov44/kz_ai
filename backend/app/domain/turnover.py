from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal


def rolled_stock_end(
    stock_begin: Decimal,
    *,
    sales: Decimal = Decimal(0),
    realization: Decimal = Decimal(0),
    return_qty: Decimal = Decimal(0),
) -> Decimal:
    """Конец месяца = начало + реализации − возвраты − продажи клиента (ТЗ лист 4)."""
    return Decimal(stock_begin) + Decimal(realization) - Decimal(return_qty) - Decimal(sales)


def turnover_percent(sales: Decimal, stock_begin: Decimal, stock_end: Decimal) -> Decimal:
    """Об-ть = (Продажи / ((Ост.нач + Ост.кон) / 2)) * 100%."""
    avg = month_avg_stock(stock_begin, stock_end)
    if avg == 0:
        return Decimal(0)
    return (Decimal(sales) / avg) * Decimal(100)


def month_avg_stock(stock_begin: Decimal, stock_end: Decimal) -> Decimal:
    """Ср. месячный остаток = (нач. + кон.) / 2."""
    return (Decimal(stock_begin) + Decimal(stock_end)) / Decimal(2)


def quarter_avg_stock(monthly_avgs: Sequence[Decimal], months: int = 3) -> Decimal:
    """Средний остаток на квартал — среднее ср. месячных остатков."""
    vals = [Decimal(v) for v in monthly_avgs]
    while len(vals) < months:
        vals.append(Decimal(0))
    return sum(vals[:months], Decimal(0)) / Decimal(months)


def quarter_turnover(sales_quarter: Decimal, avg_stock_quarter: Decimal) -> Decimal:
    if avg_stock_quarter == 0:
        return Decimal(0)
    return (Decimal(sales_quarter) / Decimal(avg_stock_quarter)) * Decimal(100)


def avg_quarter_turnover(quarter_turnover_value: Decimal) -> Decimal:
    return Decimal(quarter_turnover_value) / Decimal(3)


def next_quarter_plan(sales: Decimal, work_type: str | None, percent: Decimal | None) -> Decimal:
    base = Decimal(sales)
    pct = Decimal(percent or 0) / Decimal(100)
    wt = (work_type or "hold").lower()
    if wt in {"growth", "рост", "прирост"}:
        return base + base * pct
    if wt in {"decline", "падение"}:
        return base - base * pct
    return base


def shift_quarter(year: int, quarter: int, delta: int = -1) -> tuple[int, int]:
    idx = year * 4 + (quarter - 1) + delta
    return idx // 4, idx % 4 + 1


def sales_dynamics_percent(current: Decimal, previous: Decimal) -> Decimal | None:
    """Динамика Q / Q-1 = текущие продажи / предыдущие × 100. None, если предыдущих нет."""
    prev = Decimal(previous)
    if prev == 0:
        return None
    return (Decimal(current) / prev) * Decimal(100)


def sales_dynamics_qty(current: Decimal, previous: Decimal) -> Decimal:
    """Динамика в штуках: продажи квартала минус продажи предыдущего."""
    return Decimal(current) - Decimal(previous)


TREND_GROWTH = "Рост"
TREND_DECLINE = "Падение"
TREND_HOLD = "Удержание"
TREND_UNSTABLE = "Нестабильный"


def _has_quarter_fact(value: Decimal | None) -> bool:
    if value is None:
        return False
    return Decimal(value) != 0


def _cmp_trend(current: Decimal, previous: Decimal) -> str:
    cur, prev = Decimal(current), Decimal(previous)
    if cur > prev:
        return TREND_GROWTH
    if cur < prev:
        return TREND_DECLINE
    return TREND_HOLD


def dynamics_trend(
    current: Decimal,
    previous: Decimal,
    previous2: Decimal | None = None,
) -> str | None:
    """ТЗ: Рост / Падение / Удержание / Нестабильный. Нужны факты минимум двух кварталов."""
    if not _has_quarter_fact(previous):
        return None
    recent = _cmp_trend(current, previous)
    if previous2 is None or not _has_quarter_fact(previous2):
        return recent
    older = _cmp_trend(previous, previous2)
    if older != recent:
        return TREND_UNSTABLE
    return recent


def join_value_and_trend(value: object | None, trend: str | None) -> object:
    """Число как есть, подпись тренда рядом. Пустое число → только тренд."""
    if not trend:
        return value
    if value is None or value == "":
        return trend
    return f"{value} {trend}"
