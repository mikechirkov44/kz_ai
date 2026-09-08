from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.domain.ai_rules import (
    IlliquidCandidate,
    PatternHit,
    PriceArbitrageAlert,
    apply_plan_boost,
    build_recommendations_summary,
    dedupe_recommendations,
    illiquid_recommendations,
    is_recent_month,
    mix_imbalance_recommendations,
    price_arbitrage_recommendations,
    rank_recommendations,
    successful_pattern_recommendations,
    transfer_recommendations,
)
from app.domain.articles import index_nomenclature_for_articles, lookup_nomenclature
from app.domain.dwell import months_without_sales
from app.domain.fact_shipments import quarter_bounds
from app.models import ClientSale, ClientStock, Counterparty, Nomenclature, QuarterlyPlan, Realization
from app.schemas import RecommendationItem, RecommendationsResponse


def _nom_dims(nom: Any) -> tuple[Optional[str], Optional[str], Optional[str]]:
    if nom is None:
        return None, None, None
    return nom.wear_type, nom.lts, nom.metal_color


def collect_client_signals(
    *,
    counterparty: str,
    sales: list[Any],
    stocks: list[Any],
    nom_index: dict,
    as_of: date,
    ship_avg_by_wear: dict[str, Decimal],
) -> tuple[list[IlliquidCandidate], list[PatternHit], list[PriceArbitrageAlert]]:
    sales_by_article: dict[str, Decimal] = {}
    recent_by_article: dict[str, Decimal] = {}
    last_sale: dict[str, tuple[int, int]] = {}
    for row in sales:
        qty = Decimal(row.quantity)
        sales_by_article.setdefault(row.article, Decimal(0))
        sales_by_article[row.article] += qty
        if is_recent_month(row.period_year, row.period_month, as_of):
            recent_by_article.setdefault(row.article, Decimal(0))
            recent_by_article[row.article] += qty
        prev = last_sale.get(row.article)
        key = (row.period_year, row.period_month)
        if prev is None or key > prev:
            last_sale[row.article] = key

    stock_by_article: dict[str, Decimal] = {}
    first_stock: dict[str, date] = {}
    for row in stocks:
        stock_by_article.setdefault(row.article, Decimal(0))
        stock_by_article[row.article] += Decimal(row.quantity)
        prev_d = first_stock.get(row.article)
        if prev_d is None or row.stock_date < prev_d:
            first_stock[row.article] = row.stock_date

    illiquid_items: list[IlliquidCandidate] = []
    pattern_bucket: dict[tuple[str, str, str], Decimal] = {}
    stock_bucket: dict[tuple[str, str, str], Decimal] = {}

    for article, stock_qty in stock_by_article.items():
        nom = lookup_nomenclature(nom_index, article)
        sold = sales_by_article.get(article, Decimal(0))
        avg_turn = (sold / stock_qty * 100) if stock_qty else Decimal(0)
        ly, lm = last_sale.get(article, (None, None))
        months_without = months_without_sales(
            last_sale_year=ly,
            last_sale_month=lm,
            as_of=as_of,
            first_stock=first_stock.get(article),
        )
        wear, lts, color = _nom_dims(nom)
        illiquid_items.append(
            IlliquidCandidate(
                counterparty=counterparty,
                article=article,
                wear_type=wear,
                lts=lts,
                metal_color=color,
                avg_turnover=avg_turn,
                stock_qty=stock_qty,
                months_without_sales=months_without,
            )
        )
        recent_sold = recent_by_article.get(article, Decimal(0))
        if wear or lts or color:
            bundle = (wear or "—", lts or "—", color or "—")
            stock_bucket[bundle] = stock_bucket.get(bundle, Decimal(0)) + stock_qty
            if recent_sold > 0:
                pattern_bucket[bundle] = pattern_bucket.get(bundle, Decimal(0)) + recent_sold

    for article, recent_sold in recent_by_article.items():
        if article in stock_by_article or recent_sold <= 0:
            continue
        nom = lookup_nomenclature(nom_index, article)
        wear, lts, color = _nom_dims(nom)
        if not (wear or lts or color):
            continue
        bundle = (wear or "—", lts or "—", color or "—")
        pattern_bucket[bundle] = pattern_bucket.get(bundle, Decimal(0)) + recent_sold

    patterns = [
        PatternHit(
            counterparty,
            wear,
            lts,
            color,
            qty,
            stock_bucket.get((wear, lts, color), Decimal(0)),
            recent_sales=qty,
        )
        for (wear, lts, color), qty in pattern_bucket.items()
    ]

    wear_client: dict[str, list[Decimal]] = {}
    for row in sales:
        nom = lookup_nomenclature(nom_index, row.article)
        wear = (_nom_dims(nom)[0] if nom else None) or "—"
        wear_client.setdefault(wear, []).append(Decimal(row.price))

    arbitrage: list[PriceArbitrageAlert] = []
    for wear, prices in wear_client.items():
        if wear == "—" or not wear or len(prices) < 3:
            continue
        ship_avg = ship_avg_by_wear.get(wear)
        if not ship_avg:
            continue
        client_avg = sum(prices) / Decimal(len(prices))
        arbitrage.append(
            PriceArbitrageAlert(
                counterparty=counterparty,
                wear_type=wear,
                shipment_avg_price=Decimal(ship_avg),
                client_avg_price=client_avg,
                sample_count=len(prices),
            )
        )
    return illiquid_items, patterns, arbitrage


def _empty_report() -> RecommendationsResponse:
    return RecommendationsResponse(
        generated_at=datetime.now(timezone.utc),
        items=[],
        summary=build_recommendations_summary([]),
    )


def _plan_percents(db: Session, cps: list[Counterparty], as_of: date) -> dict[str, Decimal]:
    if not cps:
        return {}
    year, quarter = as_of.year, (as_of.month - 1) // 3 + 1
    start, end = quarter_bounds(year, quarter)
    ids = [cp.id for cp in cps]
    plans = db.execute(
        select(QuarterlyPlan.counterparty_id, QuarterlyPlan.plan_value).where(
            QuarterlyPlan.year == year,
            QuarterlyPlan.quarter == quarter,
            QuarterlyPlan.counterparty_id.in_(ids),
            QuarterlyPlan.plan_value > 0,
        )
    ).all()
    plan_map = {cid: Decimal(str(value)) for cid, value in plans if value}
    if not plan_map:
        return {}
    facts = db.execute(
        select(Realization.counterparty_id, func.coalesce(func.sum(Realization.quantity), 0)).where(
            Realization.counterparty_id.in_(list(plan_map)),
            Realization.doc_date >= start,
            Realization.doc_date <= end,
        ).group_by(Realization.counterparty_id)
    ).all()
    fact_map = {cid: Decimal(str(qty)) for cid, qty in facts}
    names = {cp.id: cp.name for cp in cps}
    out: dict[str, Decimal] = {}
    for cid, plan in plan_map.items():
        name = names.get(cid)
        if not name:
            continue
        out[name] = fact_map.get(cid, Decimal(0)) / plan * 100
    return out


def generate_recommendations(
    db: Session,
    *,
    counterparty_id: Optional[UUID] = None,
    manager_id: Optional[UUID] = None,
    allowed_ids: Optional[set[UUID]] = None,
) -> RecommendationsResponse:
    as_of = datetime.now(timezone.utc).date()
    cps_q = select(Counterparty).where(
        Counterparty.is_promo.is_(True),
        Counterparty.is_folder.is_(False),
    )
    if counterparty_id:
        cps_q = cps_q.where(Counterparty.id == counterparty_id)
    if allowed_ids is not None:
        if not allowed_ids:
            return _empty_report()
        cps_q = cps_q.where(Counterparty.id.in_(allowed_ids))
    elif manager_id:
        cps_q = cps_q.where(Counterparty.manager_id == manager_id)
    cps = db.scalars(cps_q).all()
    if not cps:
        return _empty_report()

    cp_ids = [cp.id for cp in cps]
    sales_by_cp: dict[UUID, list[ClientSale]] = defaultdict(list)
    for row in db.scalars(select(ClientSale).where(ClientSale.head_counterparty_id.in_(cp_ids))).all():
        sales_by_cp[row.head_counterparty_id].append(row)
    stocks_by_cp: dict[UUID, list[ClientStock]] = defaultdict(list)
    for row in db.scalars(select(ClientStock).where(ClientStock.head_counterparty_id.in_(cp_ids))).all():
        stocks_by_cp[row.head_counterparty_id].append(row)

    nom_index = index_nomenclature_for_articles(
        db,
        {row.article for rows in sales_by_cp.values() for row in rows}
        | {row.article for rows in stocks_by_cp.values() for row in rows},
    )
    ship_avg_rows = db.execute(
        select(Realization.counterparty_id, Nomenclature.wear_type, func.avg(Realization.price))
        .join(Nomenclature, Nomenclature.id == Realization.nomenclature_id)
        .where(
            Realization.counterparty_id.in_(cp_ids),
            Realization.price > 0,
            Nomenclature.wear_type.isnot(None),
        )
        .group_by(Realization.counterparty_id, Nomenclature.wear_type)
    ).all()
    ship_avg: dict[UUID, dict[str, Decimal]] = defaultdict(dict)
    for cp_id, wear, avg_price in ship_avg_rows:
        if not cp_id or not wear or avg_price is None:
            continue
        ship_avg[cp_id][str(wear)] = Decimal(str(avg_price))

    illiquid_items: list[IlliquidCandidate] = []
    patterns: list[PatternHit] = []
    arbitrage: list[PriceArbitrageAlert] = []
    for cp in cps:
        cp_illiquid, cp_patterns, cp_arb = collect_client_signals(
            counterparty=cp.name,
            sales=sales_by_cp.get(cp.id, []),
            stocks=stocks_by_cp.get(cp.id, []),
            nom_index=nom_index,
            as_of=as_of,
            ship_avg_by_wear=ship_avg.get(cp.id, {}),
        )
        illiquid_items.extend(cp_illiquid)
        patterns.extend(cp_patterns)
        arbitrage.extend(cp_arb)

    items_raw = rank_recommendations(
        apply_plan_boost(
            dedupe_recommendations(
                illiquid_recommendations(illiquid_items)
                + successful_pattern_recommendations(patterns)
                + price_arbitrage_recommendations(arbitrage)
                + mix_imbalance_recommendations(patterns, illiquid_items)
                + transfer_recommendations(patterns, illiquid_items)
            ),
            _plan_percents(db, cps, as_of),
        )
    )
    items = [RecommendationItem(**x) for x in items_raw]
    return RecommendationsResponse(
        generated_at=datetime.now(timezone.utc),
        items=items,
        summary=build_recommendations_summary(items_raw),
    )
