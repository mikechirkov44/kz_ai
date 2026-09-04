from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.dwell import months_without_sales
from app.domain.turnover import turnover_percent
from app.models import ClientSale, ClientStock, Counterparty


def build_dwell_heatmap(
    db: Session,
    *,
    as_of: Optional[date] = None,
    manager_id: Optional[UUID] = None,
    max_counterparties: int = 15,
    max_articles: int = 12,
) -> dict:
    """Client × SKU dwell heatmap from latest stocks and sales periods."""
    as_of = as_of or date.today()
    cps_q = select(Counterparty).where(Counterparty.is_promo.is_(True), Counterparty.is_folder.is_(False))
    if manager_id:
        cps_q = cps_q.where(Counterparty.manager_id == manager_id)
    counterparties = db.scalars(cps_q.order_by(Counterparty.name)).all()

    scored: list[tuple[Decimal, Counterparty, list[dict]]] = []
    for cp in counterparties:
        stocks = db.scalars(select(ClientStock).where(ClientStock.head_counterparty_id == cp.id)).all()
        stock_by_article: dict[str, Decimal] = {}
        first_stock: dict[str, date] = {}
        for st in stocks:
            stock_by_article[st.article] = stock_by_article.get(st.article, Decimal(0)) + Decimal(st.quantity)
            prev = first_stock.get(st.article)
            if prev is None or st.stock_date < prev:
                first_stock[st.article] = st.stock_date

        sales = db.scalars(select(ClientSale).where(ClientSale.head_counterparty_id == cp.id)).all()
        sales_qty: dict[str, Decimal] = {}
        last_sale: dict[str, tuple[int, int]] = {}
        for s in sales:
            sales_qty[s.article] = sales_qty.get(s.article, Decimal(0)) + Decimal(s.quantity)
            prev = last_sale.get(s.article)
            key = (s.period_year, s.period_month)
            if prev is None or key > prev:
                last_sale[s.article] = key

        cells: list[dict] = []
        total_stock = Decimal(0)
        for article, qty in stock_by_article.items():
            if qty <= 0:
                continue
            total_stock += qty
            ly, lm = last_sale.get(article, (None, None))
            dwell = months_without_sales(
                last_sale_year=ly,
                last_sale_month=lm,
                as_of=as_of,
                first_stock=first_stock.get(article),
            )
            sold = sales_qty.get(article, Decimal(0))
            cells.append(
                {
                    "counterparty_id": str(cp.id),
                    "counterparty": cp.name,
                    "article": article,
                    "months_without_sales": dwell,
                    "stock_qty": float(qty),
                    "sales_qty": float(sold),
                    "turnover_percent": float(turnover_percent(sold, qty, qty)),
                }
            )
        if cells:
            scored.append((total_stock, cp, cells))

    scored.sort(key=lambda x: x[0], reverse=True)
    top = scored[:max_counterparties]
    article_stock: dict[str, Decimal] = {}
    for _, _, cells in top:
        for cell in cells:
            art = cell["article"]
            article_stock[art] = article_stock.get(art, Decimal(0)) + Decimal(str(cell["stock_qty"]))
    top_articles = [
        a for a, _ in sorted(article_stock.items(), key=lambda kv: kv[1], reverse=True)[:max_articles]
    ]
    article_set = set(top_articles)

    out_cells: list[dict] = []
    names: list[str] = []
    for _, cp, cells in top:
        names.append(cp.name)
        for cell in cells:
            if cell["article"] in article_set:
                out_cells.append(cell)

    return {
        "as_of": as_of.isoformat(),
        "counterparties": names,
        "articles": top_articles,
        "cells": out_cells,
    }
