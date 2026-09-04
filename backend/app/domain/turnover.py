from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal


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
