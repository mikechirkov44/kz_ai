"""Multi-month turnover matrices matching Excel sample layouts."""

from __future__ import annotations

from calendar import monthrange
from datetime import date
from decimal import Decimal
from typing import Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.domain.articles import find_nomenclature_by_article
from app.domain.motivation import normalize_work_type
from app.domain.turnover import next_quarter_plan, turnover_percent
from app.models import ClientSale, ClientStock, Counterparty, Nomenclature, Realization, ReturnDoc


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
) -> dict:
    months = _month_iter(year_from, month_from, year_to, month_to)
    month_keys = [f"{y:04d}-{m:02d}" for y, m in months]

    cps_q = select(Counterparty).where(Counterparty.is_promo.is_(True), Counterparty.is_folder.is_(False))
    if counterparty_id:
        cps_q = cps_q.where(Counterparty.id == counterparty_id)
    if manager_id:
        cps_q = cps_q.where(Counterparty.manager_id == manager_id)
    counterparties = db.scalars(cps_q.order_by(Counterparty.name)).all()

    dim_attr = {
        "main": None,
        "lts": "lts",
        "wear_type": "wear_type",
        "metal_color": "metal_color",
        "counterparty": None,
    }.get(view)

    rows_out: list[dict] = []

    for cp in counterparties:
        if view == "counterparty" or view == "main" and dim_attr is None and view != "main":
            pass

        # Per-month totals for counterparty
        months_data: dict[str, dict] = {}
        for y, m in months:
            key = f"{y:04d}-{m:02d}"
            start, end = _month_bounds(y, m)
            sales_qty = db.scalar(
                select(func.coalesce(func.sum(ClientSale.quantity), 0)).where(
                    ClientSale.head_counterparty_id == cp.id,
                    ClientSale.period_year == y,
                    ClientSale.period_month == m,
                )
            ) or 0
            stock_end = db.scalar(
                select(func.coalesce(func.sum(ClientStock.quantity), 0)).where(
                    ClientStock.head_counterparty_id == cp.id,
                    ClientStock.stock_date == end,
                )
            ) or 0
            stock_begin = db.scalar(
                select(func.coalesce(func.sum(ClientStock.quantity), 0)).where(
                    ClientStock.head_counterparty_id == cp.id,
                    ClientStock.stock_date < start,
                )
            )
            if stock_begin is None:
                stock_begin = stock_end
            sales_d = Decimal(sales_qty)
            begin_d = Decimal(stock_begin or 0)
            end_d = Decimal(stock_end or 0)
            turn = turnover_percent(sales_d, begin_d, end_d)
            months_data[key] = {
                "stock_begin": float(begin_d),
                "stock_end": float(end_d),
                "sales": float(sales_d),
                "turnover_percent": float(turn.quantize(Decimal("0.01"))),
            }

        proposal = None
        if months:
            last_key = month_keys[-1]
            last_sales = Decimal(str(months_data[last_key]["sales"]))
            proposal = float(
                next_quarter_plan(
                    last_sales, normalize_work_type(cp.work_type), cp.work_type_percent
                ).quantize(Decimal("0.01"))
            )

        if view == "counterparty":
            rows_out.append(
                {
                    "counterparty": cp.name,
                    "counterparty_id": str(cp.id),
                    "dimension": None,
                    "work_type": normalize_work_type(cp.work_type),
                    "work_type_percent": float(cp.work_type_percent or 0),
                    "months": months_data,
                    "proposal": proposal,
                }
            )
            continue

        if view == "main":
            # SKU detail rows
            sales_all = db.scalars(
                select(ClientSale).where(
                    ClientSale.head_counterparty_id == cp.id,
                    ClientSale.period_year >= year_from,
                    ClientSale.period_year <= year_to,
                )
            ).all()
            stocks_all = db.scalars(
                select(ClientStock).where(ClientStock.head_counterparty_id == cp.id)
            ).all()
            articles = sorted({s.article for s in sales_all} | {s.article for s in stocks_all})
            # counterparty header row
            rows_out.append(
                {
                    "row_type": "counterparty",
                    "counterparty": cp.name,
                    "counterparty_id": str(cp.id),
                    "article": None,
                    "wear_type": None,
                    "metal_color": None,
                    "lts": None,
                    "lts_days": None,
                    "months": months_data,
                }
            )
            for article in articles[:500]:
                nom = find_nomenclature_by_article(db, article)
                art_months: dict[str, dict] = {}
                for y, m in months:
                    key = f"{y:04d}-{m:02d}"
                    start, end = _month_bounds(y, m)
                    sq = sum(
                        (Decimal(s.quantity) for s in sales_all if s.article == article and s.period_year == y and s.period_month == m),
                        Decimal(0),
                    )
                    se = sum(
                        (Decimal(s.quantity) for s in stocks_all if s.article == article and s.stock_date == end),
                        Decimal(0),
                    )
                    sb_rows = [s for s in stocks_all if s.article == article and s.stock_date < start]
                    sb = sum((Decimal(s.quantity) for s in sb_rows), Decimal(0)) if sb_rows else se
                    # realizations / returns for article in month
                    nom_id = nom.id if nom else None
                    real_qty = Decimal(0)
                    ret_qty = Decimal(0)
                    if nom_id:
                        real_qty = db.scalar(
                            select(func.coalesce(func.sum(Realization.quantity), 0)).where(
                                Realization.counterparty_id == cp.id,
                                Realization.nomenclature_id == nom_id,
                                Realization.doc_date >= start,
                                Realization.doc_date <= end,
                            )
                        ) or 0
                        ret_qty = db.scalar(
                            select(func.coalesce(func.sum(ReturnDoc.quantity), 0)).where(
                                ReturnDoc.counterparty_id == cp.id,
                                ReturnDoc.nomenclature_id == nom_id,
                                ReturnDoc.doc_date >= start,
                                ReturnDoc.doc_date <= end,
                            )
                        ) or 0
                    art_months[key] = {
                        "stock_begin": float(sb),
                        "stock_end": float(se),
                        "sales": float(sq),
                        "realization": float(real_qty),
                        "return_qty": float(ret_qty),
                        "turnover_percent": float(turnover_percent(sq, sb, se).quantize(Decimal("0.01"))),
                    }
                lts_days = None
                if nom and nom.lts_date:
                    lts_days = (date.today() - nom.lts_date).days
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
                        "lts_date": nom.lts_date.isoformat() if nom and nom.lts_date else None,
                        "lts_days": lts_days,
                        "months": art_months,
                    }
                )
            continue

        # dimension views: lts / wear_type / metal_color
        if dim_attr:
            buckets: dict[str, dict[str, dict]] = {}
            for y, m in months:
                key = f"{y:04d}-{m:02d}"
                start, end = _month_bounds(y, m)
                sales = db.scalars(
                    select(ClientSale).where(
                        ClientSale.head_counterparty_id == cp.id,
                        ClientSale.period_year == y,
                        ClientSale.period_month == m,
                    )
                ).all()
                stocks_end = db.scalars(
                    select(ClientStock).where(
                        ClientStock.head_counterparty_id == cp.id, ClientStock.stock_date == end
                    )
                ).all()
                stocks_begin = db.scalars(
                    select(ClientStock).where(
                        ClientStock.head_counterparty_id == cp.id, ClientStock.stock_date < start
                    )
                ).all()

                def dim_of(article: str) -> str:
                    nom = find_nomenclature_by_article(db, article)
                    return (getattr(nom, dim_attr, None) if nom else None) or "—"

                sales_by: dict[str, Decimal] = {}
                end_by: dict[str, Decimal] = {}
                begin_by: dict[str, Decimal] = {}
                for s in sales:
                    d = dim_of(s.article)
                    sales_by[d] = sales_by.get(d, Decimal(0)) + Decimal(s.quantity)
                for s in stocks_end:
                    d = dim_of(s.article)
                    end_by[d] = end_by.get(d, Decimal(0)) + Decimal(s.quantity)
                for s in stocks_begin:
                    d = dim_of(s.article)
                    begin_by[d] = begin_by.get(d, Decimal(0)) + Decimal(s.quantity)

                dims = set(sales_by) | set(end_by) | set(begin_by)
                for d in dims:
                    buckets.setdefault(d, {})
                    sb = begin_by.get(d)
                    se = end_by.get(d, Decimal(0))
                    if sb is None:
                        sb = se
                    sq = sales_by.get(d, Decimal(0))
                    buckets[d][key] = {
                        "stock_begin": float(sb),
                        "stock_end": float(se),
                        "sales": float(sq),
                        "turnover_percent": float(turnover_percent(sq, sb, se).quantize(Decimal("0.01"))),
                    }

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
                # fill missing months
                for key in month_keys:
                    md.setdefault(key, {"stock_begin": 0, "stock_end": 0, "sales": 0, "turnover_percent": 0})
                rows_out.append(
                    {
                        "row_type": "dimension",
                        "counterparty": cp.name,
                        "dimension": dim,
                        "months": md,
                    }
                )

    return {
        "view": view,
        "months": month_keys,
        "year_from": year_from,
        "month_from": month_from,
        "year_to": year_to,
        "month_to": month_to,
        "rows": rows_out,
    }
