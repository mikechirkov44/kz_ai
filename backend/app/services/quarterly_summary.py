"""Quarterly summary report (§5.4 TZ): blocks by metal_color / lts / wear_type."""

from __future__ import annotations

from calendar import monthrange
from datetime import date
from decimal import Decimal
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.articles import find_nomenclature_by_article
from app.domain.fact_shipments import quarter_bounds
from app.domain.motivation import normalize_work_type
from app.domain.turnover import avg_quarter_turnover, next_quarter_plan, quarter_turnover
from app.models import ClientSale, ClientStock, Counterparty


def _months_in_quarter(year: int, quarter: int) -> list[tuple[int, int]]:
    start_month = (quarter - 1) * 3 + 1
    return [(year, start_month), (year, start_month + 1), (year, start_month + 2)]


def _month_end(year: int, month: int) -> date:
    return date(year, month, monthrange(year, month)[1])


def build_quarterly_summary(
    db: Session,
    *,
    year: int,
    quarter: int,
    counterparty_id: Optional[UUID] = None,
) -> dict:
    """
    Metrics per block (metal_color / lts / wear_type) and per dimension value:
    - avg_stock (mean of monthly end stocks)
    - sales_total
    - quarter_turnover_pct
    - avg_month_turnover_pct (= quarter_turnover / 3)
    - next_plan (by work type)
    """
    months = _months_in_quarter(year, quarter)
    start, end = quarter_bounds(year, quarter)

    cps_q = select(Counterparty).where(Counterparty.is_promo.is_(True), Counterparty.is_folder.is_(False))
    if counterparty_id:
        cps_q = cps_q.where(Counterparty.id == counterparty_id)
    counterparties = db.scalars(cps_q.order_by(Counterparty.name)).all()

    blocks = ("metal_color", "lts", "wear_type")
    block_labels = {
        "metal_color": "Цвет металла",
        "lts": "ЖЦТ",
        "wear_type": "Тип изделия",
    }

    clients_out: list[dict] = []

    for cp in counterparties:
        sales = db.scalars(
            select(ClientSale).where(
                ClientSale.head_counterparty_id == cp.id,
                ClientSale.period_year == year,
                ClientSale.period_month.in_([m for _, m in months]),
            )
        ).all()
        stocks = db.scalars(
            select(ClientStock).where(
                ClientStock.head_counterparty_id == cp.id,
                ClientStock.stock_date >= start,
                ClientStock.stock_date <= end,
            )
        ).all()

        # total sales for plan
        total_sales_all = sum((Decimal(s.quantity) for s in sales), Decimal(0))
        plan_next = next_quarter_plan(
            total_sales_all, normalize_work_type(cp.work_type), cp.work_type_percent
        )

        client_blocks: dict[str, list[dict]] = {}
        for attr in blocks:
            # dim -> {month_key: stock_end, sales}
            dim_sales: dict[str, Decimal] = {}
            dim_stock_months: dict[str, list[Decimal]] = {}

            for s in sales:
                nom = find_nomenclature_by_article(db, s.article)
                dim = (getattr(nom, attr, None) if nom else None) or "—"
                dim_sales[dim] = dim_sales.get(dim, Decimal(0)) + Decimal(s.quantity)

            for y, m in months:
                mend = _month_end(y, m)
                month_stocks: dict[str, Decimal] = {}
                for st in stocks:
                    if st.stock_date != mend:
                        continue
                    nom = find_nomenclature_by_article(db, st.article)
                    dim = (getattr(nom, attr, None) if nom else None) or "—"
                    month_stocks[dim] = month_stocks.get(dim, Decimal(0)) + Decimal(st.quantity)
                for dim, qty in month_stocks.items():
                    dim_stock_months.setdefault(dim, []).append(qty)
                # ensure dims with sales but no stock still get a 0 for avg calc? optional

            dims = sorted(set(dim_sales) | set(dim_stock_months))
            rows = []
            for dim in dims:
                stock_vals = dim_stock_months.get(dim, [])
                # pad to 3 months with 0 if missing for average of monthly stocks
                while len(stock_vals) < 3:
                    stock_vals.append(Decimal(0))
                avg_stock = sum(stock_vals, Decimal(0)) / Decimal(3)
                sales_q = dim_sales.get(dim, Decimal(0))
                q_turn = quarter_turnover(sales_q, avg_stock)
                avg_turn = avg_quarter_turnover(q_turn)
                rows.append(
                    {
                        "dimension": dim,
                        "avg_stock": float(avg_stock.quantize(Decimal("0.01"))),
                        "sales_total": float(sales_q.quantize(Decimal("0.01"))),
                        "quarter_turnover_percent": float(q_turn.quantize(Decimal("0.01"))),
                        "avg_month_turnover_percent": float(avg_turn.quantize(Decimal("0.01"))),
                    }
                )
            client_blocks[attr] = rows

        clients_out.append(
            {
                "counterparty_id": str(cp.id),
                "counterparty": cp.name,
                "work_type": normalize_work_type(cp.work_type),
                "work_type_percent": float(cp.work_type_percent or 0),
                "sales_total": float(total_sales_all.quantize(Decimal("0.01"))),
                "next_quarter_plan": float(plan_next.quantize(Decimal("0.01"))),
                "blocks": {
                    block_labels[k]: client_blocks[k]
                    for k in blocks
                },
            }
        )

    return {
        "year": year,
        "quarter": quarter,
        "period_start": start.isoformat(),
        "period_end": end.isoformat(),
        "clients": clients_out,
    }
