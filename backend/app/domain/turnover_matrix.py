"""Pure helpers for the multi-month turnover matrix (no DB)."""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from decimal import Decimal
from typing import Any, Iterable, Optional, Sequence

from app.domain.articles import lookup_nomenclature
from app.domain.motivation import work_type_label
from app.domain.turnover import turnover_percent

SKU_ROW_LIMIT = 500
CHILD_ROW_TYPES = frozenset({"dimension", "sku"})


def _dec(value: Any) -> Decimal:
    if value is None:
        return Decimal(0)
    return Decimal(value)


def month_cell(
    sales: Decimal,
    stock_begin: Decimal,
    stock_end: Decimal,
    *,
    realization: Optional[Decimal] = None,
    return_qty: Optional[Decimal] = None,
) -> dict:
    sales_d = _dec(sales)
    begin_d = _dec(stock_begin)
    end_d = _dec(stock_end)
    avg = (begin_d + end_d) / Decimal(2)
    cell: dict[str, float] = {
        "stock_begin": float(begin_d),
        "stock_end": float(end_d),
        "stock_avg": float(avg),
        "sales": float(sales_d),
        "turnover_percent": float(turnover_percent(sales_d, begin_d, end_d).quantize(Decimal("0.01"))),
    }
    if realization is not None:
        cell["realization"] = float(_dec(realization))
    if return_qty is not None:
        cell["return_qty"] = float(_dec(return_qty))
    return cell


def empty_month_cell(*, main: bool = False) -> dict:
    if main:
        return month_cell(Decimal(0), Decimal(0), Decimal(0), realization=Decimal(0), return_qty=Decimal(0))
    return {"stock_begin": 0, "stock_end": 0, "sales": 0, "turnover_percent": 0}


def header_stock_begin(qty_before_start: Decimal) -> Decimal:
    """Header uses SQL coalesce(sum, 0) — empty history is 0, not end-of-month."""
    return _dec(qty_before_start)


def article_stock_begin(qty_before_start: Decimal, has_begin_rows: bool, stock_end: Decimal) -> Decimal:
    if has_begin_rows:
        return _dec(qty_before_start)
    return _dec(stock_end)


def is_empty_month_cell(cell: Optional[dict]) -> bool:
    if not cell:
        return True
    keys = ("stock_begin", "stock_end", "sales", "realization", "return_qty")
    return all(_dec(cell.get(key) or 0) == 0 for key in keys)


def is_empty_turnover_row(row: dict) -> bool:
    months = row.get("months") or {}
    if not months:
        return True
    return all(is_empty_month_cell(cell) for cell in months.values())


def filter_empty_turnover_rows(rows: Sequence[dict]) -> list[dict]:
    """Drop all-zero leaf rows; drop a client group if parent and children are empty."""
    out: list[dict] = []
    idx = 0
    while idx < len(rows):
        row = rows[idx]
        if row.get("row_type") == "counterparty":
            children: list[dict] = []
            nxt = idx + 1
            while nxt < len(rows) and rows[nxt].get("row_type") in CHILD_ROW_TYPES:
                children.append(rows[nxt])
                nxt += 1
            kept = [child for child in children if not is_empty_turnover_row(child)]
            if kept or not is_empty_turnover_row(row):
                out.append(row)
                out.extend(kept)
            idx = nxt
            continue
        if not is_empty_turnover_row(row):
            out.append(row)
        idx += 1
    return out


def _sum_before(by_date: dict[date, Decimal], start: date) -> tuple[Decimal, bool]:
    total = Decimal(0)
    found = False
    for snap_date, qty in by_date.items():
        if snap_date < start:
            total += qty
            found = True
    return total, found


def assemble_turnover_rows(
    *,
    view: str,
    month_bounds: Sequence[tuple[str, date, date]],
    counterparties: Sequence[Any],
    sales: Iterable[Any],
    stocks: Iterable[Any],
    noms: dict[str, Any],
    movements: Optional[dict[tuple[Any, Any, int, int], tuple[Decimal, Decimal]]] = None,
) -> list[dict]:
    """Build matrix rows from already-loaded sales, stocks and nomenclature."""
    month_keys = [key for key, _start, _end in month_bounds]
    sales_month: dict[Any, dict[tuple[int, int], Decimal]] = defaultdict(lambda: defaultdict(lambda: Decimal(0)))
    sales_art: dict[Any, dict[tuple[int, int], dict[str, Decimal]]] = defaultdict(
        lambda: defaultdict(lambda: defaultdict(lambda: Decimal(0)))
    )
    articles_by_cp: dict[Any, set[str]] = defaultdict(set)
    for sale in sales:
        qty = _dec(sale.quantity)
        cp_id = sale.head_counterparty_id
        ym = (sale.period_year, sale.period_month)
        sales_month[cp_id][ym] += qty
        sales_art[cp_id][ym][sale.article] += qty
        articles_by_cp[cp_id].add(sale.article)

    stock_date_total: dict[Any, dict[date, Decimal]] = defaultdict(lambda: defaultdict(lambda: Decimal(0)))
    stock_art_date: dict[Any, dict[str, dict[date, Decimal]]] = defaultdict(
        lambda: defaultdict(lambda: defaultdict(lambda: Decimal(0)))
    )
    for stock in stocks:
        qty = _dec(stock.quantity)
        cp_id = stock.head_counterparty_id
        stock_date_total[cp_id][stock.stock_date] += qty
        stock_art_date[cp_id][stock.article][stock.stock_date] += qty
        articles_by_cp[cp_id].add(stock.article)

    dim_attr = {
        "main": None,
        "lts": "lts",
        "wear_type": "wear_type",
        "metal_color": "metal_color",
        "counterparty": None,
    }.get(view)
    rows_out: list[dict] = []

    for cp in counterparties:
        cp_sales_month = sales_month[cp.id]
        cp_stock_dates = stock_date_total[cp.id]
        months_data: dict[str, dict] = {}
        for key, start, end in month_bounds:
            y, m = (int(key[:4]), int(key[5:7]))
            sales_qty = cp_sales_month[(y, m)]
            stock_end = cp_stock_dates.get(end, Decimal(0))
            begin_qty, _found = _sum_before(cp_stock_dates, start)
            months_data[key] = month_cell(sales_qty, header_stock_begin(begin_qty), stock_end)

        if view == "counterparty":
            rows_out.append(
                {
                    "counterparty": cp.name,
                    "counterparty_id": str(cp.id),
                    "dimension": None,
                    "months": months_data,
                }
            )
            continue

        if view == "main":
            articles = sorted(articles_by_cp.get(cp.id, ()))[:SKU_ROW_LIMIT]
            rows_out.append(
                {
                    "row_type": "counterparty",
                    "counterparty": cp.name,
                    "counterparty_id": str(cp.id),
                    "article": None,
                    "wear_type": None,
                    "metal_color": None,
                    "lts": None,
                    "work_type": work_type_label(cp.work_type),
                    "work_type_percent": float(cp.work_type_percent or 0),
                    "months": months_data,
                }
            )
            cp_sales_art = sales_art[cp.id]
            cp_art_dates = stock_art_date[cp.id]
            for article in articles:
                nom = lookup_nomenclature(noms, article)
                art_dates = cp_art_dates.get(article, {})
                art_months: dict[str, dict] = {}
                for key, start, end in month_bounds:
                    y, m = (int(key[:4]), int(key[5:7]))
                    sq = cp_sales_art[(y, m)].get(article, Decimal(0))
                    se = art_dates.get(end, Decimal(0))
                    begin_qty, has_begin = _sum_before(art_dates, start)
                    sb = article_stock_begin(begin_qty, has_begin, se)
                    real_qty = Decimal(0)
                    ret_qty = Decimal(0)
                    nom_id = getattr(nom, "id", None) if nom else None
                    if nom_id is not None and movements:
                        real_qty, ret_qty = movements.get((cp.id, nom_id, y, m), (Decimal(0), Decimal(0)))
                    art_months[key] = month_cell(sq, sb, se, realization=real_qty, return_qty=ret_qty)
                rows_out.append(
                    {
                        "row_type": "sku",
                        "counterparty": cp.name,
                        "counterparty_id": str(cp.id),
                        "article": article,
                        "name": nom.name if nom else None,
                        "wear_type": nom.wear_type if nom else None,
                        "metal_color": nom.metal_color if nom else None,
                        "lts": nom.lts if nom else None,
                        "lts_date": nom.lts_date.isoformat() if nom and getattr(nom, "lts_date", None) else None,
                        "work_type": work_type_label(cp.work_type),
                        "work_type_percent": float(cp.work_type_percent or 0),
                        "months": art_months,
                    }
                )
            continue

        if dim_attr:
            buckets: dict[str, dict[str, dict]] = {}
            cp_sales_art = sales_art[cp.id]
            cp_art_dates = stock_art_date[cp.id]
            dim_cache: dict[str, str] = {}

            def dim_of(article: str) -> str:
                found = dim_cache.get(article)
                if found is None:
                    found = _dim_of(noms, article, dim_attr)
                    dim_cache[article] = found
                return found

            for key, start, end in month_bounds:
                y, m = (int(key[:4]), int(key[5:7]))
                sales_by: dict[str, Decimal] = defaultdict(lambda: Decimal(0))
                end_by: dict[str, Decimal] = defaultdict(lambda: Decimal(0))
                begin_by: dict[str, Decimal] = defaultdict(lambda: Decimal(0))
                begin_found: set[str] = set()
                for article, qty in cp_sales_art[(y, m)].items():
                    sales_by[dim_of(article)] += qty
                for article, by_date in cp_art_dates.items():
                    dim = dim_of(article)
                    if end in by_date:
                        end_by[dim] += by_date[end]
                    bq, found = _sum_before(by_date, start)
                    if found:
                        begin_by[dim] += bq
                        begin_found.add(dim)
                dims = set(sales_by) | set(end_by) | set(begin_by)
                for dim in dims:
                    se = end_by.get(dim, Decimal(0))
                    sb = begin_by.get(dim, Decimal(0)) if dim in begin_found else se
                    buckets.setdefault(dim, {})[key] = month_cell(sales_by.get(dim, Decimal(0)), sb, se)

            rows_out.append(
                {
                    "row_type": "counterparty",
                    "counterparty": cp.name,
                    "counterparty_id": str(cp.id),
                    "dimension": None,
                    "months": months_data,
                }
            )
            for dim, md in sorted(buckets.items()):
                for key in month_keys:
                    md.setdefault(key, empty_month_cell())
                rows_out.append(
                    {
                        "row_type": "dimension",
                        "counterparty": cp.name,
                        "counterparty_id": str(cp.id),
                        "dimension": dim,
                        "months": md,
                    }
                )

    return rows_out


def _dim_of(noms: dict[str, Any], article: str, dim_attr: str) -> str:
    nom = lookup_nomenclature(noms, article)
    return (getattr(nom, dim_attr, None) if nom else None) or "—"
