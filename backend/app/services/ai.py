from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.domain.ai_rules import (
    IlliquidCandidate,
    PatternHit,
    PriceArbitrageAlert,
    illiquid_recommendations,
    price_arbitrage_recommendations,
    successful_pattern_recommendations,
)
from app.domain.articles import find_nomenclature_by_article
from app.domain.dwell import months_without_sales
from app.models import ClientSale, ClientStock, Counterparty, Nomenclature, Realization
from app.schemas import RecommendationItem, RecommendationsResponse


def generate_recommendations(
    db: Session,
    *,
    counterparty_id: Optional[UUID] = None,
    manager_id: Optional[UUID] = None,
) -> RecommendationsResponse:
    as_of = datetime.now(timezone.utc).date()
    cps_q = select(Counterparty).where(
        Counterparty.is_promo.is_(True),
        Counterparty.is_folder.is_(False),
    )
    if counterparty_id:
        cps_q = cps_q.where(Counterparty.id == counterparty_id)
    if manager_id:
        cps_q = cps_q.where(Counterparty.manager_id == manager_id)
    cps = db.scalars(cps_q).all()

    illiquid_items: list[IlliquidCandidate] = []
    patterns: list[PatternHit] = []
    arbitrage: list[PriceArbitrageAlert] = []

    for cp in cps:
        sales = db.scalars(select(ClientSale).where(ClientSale.head_counterparty_id == cp.id)).all()
        stocks = db.scalars(select(ClientStock).where(ClientStock.head_counterparty_id == cp.id)).all()
        sales_by_article = {}
        last_sale: dict[str, tuple[int, int]] = {}
        for s in sales:
            sales_by_article.setdefault(s.article, Decimal(0))
            sales_by_article[s.article] += Decimal(s.quantity)
            prev = last_sale.get(s.article)
            key = (s.period_year, s.period_month)
            if prev is None or key > prev:
                last_sale[s.article] = key

        stock_by_article = {}
        first_stock: dict[str, date] = {}
        for st in stocks:
            stock_by_article.setdefault(st.article, Decimal(0))
            stock_by_article[st.article] += Decimal(st.quantity)
            prev_d = first_stock.get(st.article)
            if prev_d is None or st.stock_date < prev_d:
                first_stock[st.article] = st.stock_date

        pattern_bucket: dict[tuple[str, str, str], Decimal] = {}

        for article, stock_qty in stock_by_article.items():
            nom = find_nomenclature_by_article(db, article)
            sold = sales_by_article.get(article, Decimal(0))
            avg_turn = (sold / stock_qty * 100) if stock_qty else Decimal(0)
            ly, lm = last_sale.get(article, (None, None))
            months_without = months_without_sales(
                last_sale_year=ly,
                last_sale_month=lm,
                as_of=as_of,
                first_stock=first_stock.get(article),
            )
            illiquid_items.append(
                IlliquidCandidate(
                    counterparty=cp.name,
                    article=article,
                    wear_type=nom.wear_type if nom else None,
                    lts=nom.lts if nom else None,
                    metal_color=nom.metal_color if nom else None,
                    avg_turnover=avg_turn,
                    stock_qty=stock_qty,
                    months_without_sales=months_without,
                )
            )
            if nom and sold > 0:
                key = (nom.wear_type or "—", nom.lts or "—", nom.metal_color or "—")
                pattern_bucket[key] = pattern_bucket.get(key, Decimal(0)) + sold

        for (wear, lts, color), qty in pattern_bucket.items():
            patterns.append(PatternHit(cp.name, wear, lts, color, qty))

        # price arbitrage by wear_type
        wear_client: dict[str, list[Decimal]] = {}
        for s in sales:
            nom = find_nomenclature_by_article(db, s.article)
            wear = (nom.wear_type if nom else None) or "—"
            wear_client.setdefault(wear, []).append(Decimal(s.price))

        for wear, prices in wear_client.items():
            client_avg = sum(prices) / Decimal(len(prices))
            nom_ids = db.scalars(select(Nomenclature.id).where(Nomenclature.wear_type == wear)).all()
            ship_avg = db.scalar(
                select(func.avg(Realization.price)).where(
                    Realization.counterparty_id == cp.id,
                    Realization.nomenclature_id.in_(nom_ids) if nom_ids else False,
                    Realization.price > 0,
                )
            )
            if ship_avg:
                arbitrage.append(
                    PriceArbitrageAlert(
                        counterparty=cp.name,
                        wear_type=wear,
                        shipment_avg_price=Decimal(ship_avg),
                        client_avg_price=client_avg,
                    )
                )

    items_raw = (
        illiquid_recommendations(illiquid_items)
        + successful_pattern_recommendations(patterns)
        + price_arbitrage_recommendations(arbitrage)
    )
    items = [RecommendationItem(**x) for x in items_raw]
    return RecommendationsResponse(generated_at=datetime.now(timezone.utc), items=items)
