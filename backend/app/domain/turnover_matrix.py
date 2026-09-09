"""Pure helpers for the multi-month turnover matrix (no DB)."""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from decimal import Decimal
from typing import Any, Iterable, Optional, Sequence

from app.domain.articles import lookup_nomenclature
from app.domain.motivation import work_type_label
from app.domain.turnover import rolled_stock_end, turnover_percent

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


def _qty_in_range(by_date: dict[date, Decimal], start: date, end: date) -> tuple[Decimal, bool]:
    total = Decimal(0)
    found = False
    for snap_date, qty in by_date.items():
        if start <= snap_date <= end:
            total += qty
            found = True
    return total, found


def opening_stock(
    by_date: dict[date, Decimal],
    start: date,
    end: date,
    prev_end: Decimal | None,
) -> Decimal:
    """Начало месяца: конец прошлого, иначе снимок до месяца, иначе первая загрузка в месяце."""
    if prev_end is not None:
        return prev_end
    before, has_before = _sum_before(by_date, start)
    if has_before:
        return before
    in_month, has_in = _qty_in_range(by_date, start, end)
    if has_in:
        return in_month
    return Decimal(0)


def _movement_ym(
    movements: Optional[dict[tuple[Any, Any, int, int], tuple[Decimal, Decimal]]],
    cp_id: Any,
    nom_id: Any = None,
) -> tuple[dict[tuple[int, int], Decimal], dict[tuple[int, int], Decimal]]:
    real_ym: dict[tuple[int, int], Decimal] = defaultdict(lambda: Decimal(0))
    ret_ym: dict[tuple[int, int], Decimal] = defaultdict(lambda: Decimal(0))
    if not movements:
        return real_ym, ret_ym
    for (c_id, n_id, year, month), (real, ret) in movements.items():
        if c_id != cp_id:
            continue
        if nom_id is not None and n_id != nom_id:
            continue
        real_ym[(year, month)] += _dec(real)
        ret_ym[(year, month)] += _dec(ret)
    return real_ym, ret_ym


def rolled_month_cells(
    *,
    by_date: dict[date, Decimal],
    month_bounds: Sequence[tuple[str, date, date]],
    sales_ym: dict[tuple[int, int], Decimal],
    real_ym: Optional[dict[tuple[int, int], Decimal]] = None,
    ret_ym: Optional[dict[tuple[int, int], Decimal]] = None,
    with_movements: bool = False,
) -> dict[str, dict]:
    """Остаток конца месяца = начало + реализации − возвраты − продажи."""
    real_map = real_ym or {}
    ret_map = ret_ym or {}
    prev_end: Decimal | None = None
    chained = False
    out: dict[str, dict] = {}
    for key, start, end_d in month_bounds:
        year, month = int(key[:4]), int(key[5:7])
        sales_qty = sales_ym.get((year, month), Decimal(0))
        real = real_map.get((year, month), Decimal(0))
        ret = ret_map.get((year, month), Decimal(0))
        has_flow = bool(by_date) or real != 0 or ret != 0
        extra: dict[str, Decimal] = {}
        if with_movements:
            extra = {"realization": real, "return_qty": ret}
        if not has_flow and not chained:
            out[key] = month_cell(sales_qty, Decimal(0), Decimal(0), **extra)
            continue
        begin = opening_stock(by_date, start, end_d, prev_end if chained else None)
        end_qty = rolled_stock_end(begin, sales=sales_qty, realization=real, return_qty=ret)
        chained = True
        prev_end = end_qty
        out[key] = month_cell(sales_qty, begin, end_qty, **extra)
    return out


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
        real_ym, ret_ym = _movement_ym(movements, cp.id)
        months_data = rolled_month_cells(
            by_date=cp_stock_dates,
            month_bounds=month_bounds,
            sales_ym=cp_sales_month,
            real_ym=real_ym,
            ret_ym=ret_ym,
        )

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
                nom_id = getattr(nom, "id", None) if nom else None
                art_real, art_ret = _movement_ym(movements, cp.id, nom_id)
                art_sales: dict[tuple[int, int], Decimal] = defaultdict(lambda: Decimal(0))
                for ym, by_art in cp_sales_art.items():
                    art_sales[ym] = by_art.get(article, Decimal(0))
                art_months = rolled_month_cells(
                    by_date=cp_art_dates.get(article, {}),
                    month_bounds=month_bounds,
                    sales_ym=art_sales,
                    real_ym=art_real,
                    ret_ym=art_ret,
                    with_movements=True,
                )
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

            dim_articles: dict[str, set[str]] = defaultdict(set)
            for article in articles_by_cp.get(cp.id, ()):
                dim_articles[dim_of(article)].add(article)

            for dim, arts in dim_articles.items():
                dim_dates: dict[date, Decimal] = defaultdict(lambda: Decimal(0))
                dim_sales: dict[tuple[int, int], Decimal] = defaultdict(lambda: Decimal(0))
                dim_real: dict[tuple[int, int], Decimal] = defaultdict(lambda: Decimal(0))
                dim_ret: dict[tuple[int, int], Decimal] = defaultdict(lambda: Decimal(0))
                for article in arts:
                    for snap_date, qty in cp_art_dates.get(article, {}).items():
                        dim_dates[snap_date] += qty
                    for ym, by_art in cp_sales_art.items():
                        dim_sales[ym] += by_art.get(article, Decimal(0))
                    nom = lookup_nomenclature(noms, article)
                    nom_id = getattr(nom, "id", None) if nom else None
                    art_real, art_ret = _movement_ym(movements, cp.id, nom_id)
                    for ym, qty in art_real.items():
                        dim_real[ym] += qty
                    for ym, qty in art_ret.items():
                        dim_ret[ym] += qty
                buckets[dim] = rolled_month_cells(
                    by_date=dim_dates,
                    month_bounds=month_bounds,
                    sales_ym=dim_sales,
                    real_ym=dim_real,
                    ret_ym=dim_ret,
                )

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
