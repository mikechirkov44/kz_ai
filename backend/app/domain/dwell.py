from __future__ import annotations

from datetime import date


def months_without_sales(
    *,
    last_sale_year: int | None,
    last_sale_month: int | None,
    as_of: date,
    first_stock: date | None = None,
) -> int:
    """Months since last sale (or since first stock if never sold)."""
    if last_sale_year and last_sale_month:
        return max(0, (as_of.year - last_sale_year) * 12 + (as_of.month - last_sale_month))
    if first_stock:
        return max(1, (as_of.year - first_stock.year) * 12 + (as_of.month - first_stock.month))
    return 12


def dwell_bucket(months: int) -> str:
    if months <= 1:
        return "fresh"
    if months <= 3:
        return "warm"
    if months <= 6:
        return "stale"
    return "dead"
