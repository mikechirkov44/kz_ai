from __future__ import annotations

from decimal import Decimal


def turnover_percent(sales: Decimal, stock_begin: Decimal, stock_end: Decimal) -> Decimal:
    """Об-ть = (Продажи / ((Ост.нач + Ост.кон) / 2)) * 100%."""
    avg = (Decimal(stock_begin) + Decimal(stock_end)) / Decimal(2)
    if avg == 0:
        return Decimal(0)
    return (Decimal(sales) / avg) * Decimal(100)


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
