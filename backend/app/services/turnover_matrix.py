"""Multi-month turnover matrices matching Excel sample layouts."""

from __future__ import annotations

from calendar import monthrange
from collections import defaultdict
from datetime import date
from decimal import Decimal
from typing import Optional
from uuid import UUID

from sqlalchemy import select, tuple_
from sqlalchemy.orm import Session

from app.constants import is_excluded_turnover_warehouse
from app.domain.articles import index_nomenclature_for_articles
from app.domain.turnover_matrix import assemble_turnover_rows
from app.models import ClientSale, ClientStock, Counterparty, Realization, ReturnDoc
from app.services.counterparty_utils import map_shops_to_promo_heads


def _month_iter(year_from: int, month_from: int, year_to: int, month_to: int) -> list[tuple[int, int]]:
    y, m = year_from, month_from
    out: list[tuple[int, int]] = []
    while (y, m) <= (year_to, month_to):
        out.append((y, m))
        m += 1
        if m > 12:
            m = 1
            y += 1
        if len(out) > 24:
            break
    return out


def _month_bounds(year: int, month: int) -> tuple[date, date]:
    return date(year, month, 1), date(year, month, monthrange(year, month)[1])


def _empty_report(view: str, month_keys: list[str], year_from: int, month_from: int, year_to: int, month_to: int) -> dict:
    return {
        "view": view,
        "months": month_keys,
        "year_from": year_from,
        "month_from": month_from,
        "year_to": year_to,
        "month_to": month_to,
        "rows": [],
    }


def _load_sales(
    db: Session,
    cp_ids: list[UUID],
    months: list[tuple[int, int]],
    *,
    view: str,
    year_from: int,
    year_to: int,
) -> list[ClientSale]:
    if not cp_ids:
        return []
    stmt = select(ClientSale).where(ClientSale.head_counterparty_id.in_(cp_ids))
    if view == "main":
        stmt = stmt.where(ClientSale.period_year >= year_from, ClientSale.period_year <= year_to)
    else:
        stmt = stmt.where(tuple_(ClientSale.period_year, ClientSale.period_month).in_(months))
    return list(db.scalars(stmt).all())


def _load_stocks(db: Session, cp_ids: list[UUID]) -> list[ClientStock]:
    if not cp_ids:
        return []
    return list(db.scalars(select(ClientStock).where(ClientStock.head_counterparty_id.in_(cp_ids))).all())


def _load_movements(
    db: Session,
    cp_ids: list[UUID],
    nom_ids: set[UUID],
    start: date,
    end: date,
) -> dict[tuple[UUID, UUID, int, int], tuple[Decimal, Decimal]]:
    if not cp_ids or not nom_ids:
        return {}
    to_promo = map_shops_to_promo_heads(db, set(cp_ids))
    shop_ids = set(to_promo) or set(cp_ids)
    reals = db.scalars(
        select(Realization).where(
            Realization.counterparty_id.in_(shop_ids),
            Realization.nomenclature_id.in_(nom_ids),
            Realization.doc_date >= start,
            Realization.doc_date <= end,
            Realization.ignore_turnover.is_(False),
        )
    ).all()
    rets = db.scalars(
        select(ReturnDoc).where(
            ReturnDoc.counterparty_id.in_(shop_ids),
            ReturnDoc.nomenclature_id.in_(nom_ids),
            ReturnDoc.doc_date >= start,
            ReturnDoc.doc_date <= end,
            ReturnDoc.ignore_turnover.is_(False),
        )
    ).all()
    real_qty: dict[tuple[UUID, UUID, int, int], Decimal] = defaultdict(lambda: Decimal(0))
    ret_qty: dict[tuple[UUID, UUID, int, int], Decimal] = defaultdict(lambda: Decimal(0))
    for row in reals:
        if row.counterparty_id is None or row.nomenclature_id is None:
            continue
        if is_excluded_turnover_warehouse(row.warehouse):
            continue
        head_id = to_promo.get(row.counterparty_id)
        if not head_id:
            continue
        key = (head_id, row.nomenclature_id, row.doc_date.year, row.doc_date.month)
        real_qty[key] += Decimal(row.quantity or 0)
    for row in rets:
        if row.counterparty_id is None or row.nomenclature_id is None:
            continue
        if is_excluded_turnover_warehouse(row.warehouse):
            continue
        head_id = to_promo.get(row.counterparty_id)
        if not head_id:
            continue
        key = (head_id, row.nomenclature_id, row.doc_date.year, row.doc_date.month)
        ret_qty[key] += Decimal(row.quantity or 0)
    keys = set(real_qty) | set(ret_qty)
    return {key: (real_qty[key], ret_qty[key]) for key in keys}


def build_turnover_matrix(
    db: Session,
    *,
    view: str,
    year_from: int,
    month_from: int,
    year_to: int,
    month_to: int,
    counterparty_id: Optional[UUID] = None,
    manager_id: Optional[UUID] = None,
    allowed_ids: Optional[set[UUID]] = None,
) -> dict:
    months = _month_iter(year_from, month_from, year_to, month_to)
    month_keys = [f"{y:04d}-{m:02d}" for y, m in months]
    empty = _empty_report(view, month_keys, year_from, month_from, year_to, month_to)
    if not months:
        return empty
    bounds = [(f"{y:04d}-{m:02d}", *_month_bounds(y, m)) for y, m in months]

    cps_q = select(Counterparty).where(Counterparty.is_promo.is_(True), Counterparty.is_folder.is_(False))
    if counterparty_id:
        cps_q = cps_q.where(Counterparty.id == counterparty_id)
    if allowed_ids is not None:
        if not allowed_ids:
            return empty
        cps_q = cps_q.where(Counterparty.id.in_(allowed_ids))
    elif manager_id:
        cps_q = cps_q.where(Counterparty.manager_id == manager_id)
    counterparties = list(db.scalars(cps_q.order_by(Counterparty.name)).all())
    if not counterparties:
        return empty

    cp_ids = [cp.id for cp in counterparties]
    sales = _load_sales(db, cp_ids, months, view=view, year_from=year_from, year_to=year_to)
    stocks = _load_stocks(db, cp_ids)
    articles = {row.article for row in sales} | {row.article for row in stocks}
    noms = index_nomenclature_for_articles(db, articles)
    movements = None
    nom_ids = {nom.id for nom in noms.values() if getattr(nom, "id", None)}
    if nom_ids:
        first_start, last_end = bounds[0][1], bounds[-1][2]
        movements = _load_movements(db, cp_ids, nom_ids, first_start, last_end)

    rows = assemble_turnover_rows(
        view=view,
        month_bounds=bounds,
        counterparties=counterparties,
        sales=sales,
        stocks=stocks,
        noms=noms,
        movements=movements,
    )
    return {
        "view": view,
        "months": month_keys,
        "year_from": year_from,
        "month_from": month_from,
        "year_to": year_to,
        "month_to": month_to,
        "rows": rows,
    }
