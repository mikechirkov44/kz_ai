from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.domain.ai_rules import (
    IlliquidCandidate,
    PatternHit,
    PriceArbitrageAlert,
    article_price_gaps,
    build_recommendations_summary,
    compose_recommendation_items,
    dedupe_recommendations,
    is_recent_month,
    rank_recommendations,
)
from app.domain.articles import index_nomenclature_for_articles, lookup_nomenclature
from app.domain.dwell import dwell_bucket, months_without_sales
from app.domain.fact_shipments import quarter_bounds
from app.models import ClientSale, ClientStock, Counterparty, Nomenclature, QuarterlyPlan, Realization
from app.schemas import RecommendationItem, RecommendationsResponse
from app.services.counterparty_utils import (
    map_shops_to_promo_heads,
    rollup_averages_to_head,
    rollup_sums_to_head,
)


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
    ship_avg_by_article: Optional[dict[str, Decimal]] = None,
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
    prices_by_article: dict[str, list[Decimal]] = {}
    wear_by_article: dict[str, str] = {}
    for row in sales:
        nom = lookup_nomenclature(nom_index, row.article)
        wear = (_nom_dims(nom)[0] if nom else None) or "—"
        price = Decimal(row.price)
        wear_client.setdefault(wear, []).append(price)
        article_key = nom.article if nom and nom.article else row.article
        prices_by_article.setdefault(article_key, []).append(price)
        wear_by_article[article_key] = wear

    article_ship = ship_avg_by_article or {}
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
                articles=article_price_gaps(
                    wear_type=wear,
                    prices_by_article=prices_by_article,
                    ship_avg_by_article=article_ship,
                    wear_by_article=wear_by_article,
                ),
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
    to_head = map_shops_to_promo_heads(db, set(plan_map))
    doc_ids = set(to_head)
    facts = db.execute(
        select(Realization.counterparty_id, func.coalesce(func.sum(Realization.quantity), 0)).where(
            Realization.counterparty_id.in_(doc_ids),
            Realization.doc_date >= start,
            Realization.doc_date <= end,
        ).group_by(Realization.counterparty_id)
    ).all()
    fact_map = rollup_sums_to_head(
        ((cid, Decimal(str(qty))) for cid, qty in facts),
        to_head,
    )
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

    items_raw = []
    for source_id in sorted({cp.source_id for cp in cps}):
        items_raw.extend(_source_recommendations(db, [cp for cp in cps if cp.source_id == source_id], as_of))
    items_raw = rank_recommendations(items_raw)
    return RecommendationsResponse(
        generated_at=datetime.now(timezone.utc),
        items=[RecommendationItem(**item) for item in items_raw],
        summary=build_recommendations_summary(items_raw),
    )


def _source_recommendations(db: Session, cps: list[Counterparty], as_of: date) -> list[dict]:
    source_id = cps[0].source_id
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
        source_id=source_id,
    )
    to_head = map_shops_to_promo_heads(db, set(cp_ids))
    doc_ids = set(to_head) or set(cp_ids)
    ship_avg_rows = db.execute(
        select(
            Realization.counterparty_id,
            Nomenclature.wear_type,
            func.coalesce(func.sum(Realization.price), 0),
            func.count(),
        )
        .join(Nomenclature, Nomenclature.id == Realization.nomenclature_id)
        .where(
            Realization.counterparty_id.in_(doc_ids),
            Realization.price > 0,
            Nomenclature.wear_type.isnot(None),
        )
        .group_by(Realization.counterparty_id, Nomenclature.wear_type)
    ).all()
    ship_avg = rollup_averages_to_head(
        (
            (cp_id, str(wear), Decimal(str(total)), int(count))
            for cp_id, wear, total, count in ship_avg_rows
            if wear
        ),
        to_head,
    )
    ship_art_rows = db.execute(
        select(
            Realization.counterparty_id,
            Nomenclature.article,
            func.coalesce(func.sum(Realization.price), 0),
            func.count(),
        )
        .join(Nomenclature, Nomenclature.id == Realization.nomenclature_id)
        .where(
            Realization.counterparty_id.in_(doc_ids),
            Realization.price > 0,
            Nomenclature.article.isnot(None),
        )
        .group_by(Realization.counterparty_id, Nomenclature.article)
    ).all()
    ship_avg_article = rollup_averages_to_head(
        (
            (cp_id, str(article), Decimal(str(total)), int(count))
            for cp_id, article, total, count in ship_art_rows
            if article
        ),
        to_head,
    )

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
            ship_avg_by_article=ship_avg_article.get(cp.id, {}),
        )
        illiquid_items.extend(cp_illiquid)
        patterns.extend(cp_patterns)
        arbitrage.extend(cp_arb)

    items_raw = compose_recommendation_items(
        illiquid_items=illiquid_items,
        patterns=patterns,
        alerts=arbitrage,
        plan_percents=_plan_percents(db, cps, as_of),
        include_transfers=False,
    )
    article_items = _article_recommendations(
        db, cps, sales_by_cp, stocks_by_cp, illiquid_items, nom_index, as_of,
    )
    aged_keys = {
        (item["counterparty"], item["article"])
        for item in article_items if item["action"] in {"transfer", "return"}
    }
    items_raw = [
        item for item in items_raw
        if item["action"] != "return" or (item["counterparty"], item["article"]) not in aged_keys
    ] + article_items
    for item in items_raw:
        item["details"]["source_id"] = source_id
    return rank_recommendations(dedupe_recommendations(items_raw))


def _article_recommendations(
    db: Session,
    cps: list[Counterparty],
    sales_by_cp: dict,
    stocks_by_cp: dict,
    illiquid: list[IlliquidCandidate],
    nom_index: dict,
    as_of: date,
) -> list[dict]:
    previous_month = as_of.replace(day=1) - timedelta(days=1)
    stocks = {}
    demand = {}
    monthly = {}
    for cp in cps:
        stock = defaultdict(Decimal)
        latest_by_shop = {}
        for row in stocks_by_cp[cp.id]:
            latest_by_shop[row.shop] = max(row.stock_date, latest_by_shop.get(row.shop, row.stock_date))
        for row in stocks_by_cp[cp.id]:
            if row.stock_date != latest_by_shop[row.shop]:
                continue
            nom = lookup_nomenclature(nom_index, row.article)
            stock[nom.article if nom and nom.article else row.article] += row.quantity
        stocks[cp.name] = {article: qty for article, qty in stock.items() if qty > 0}
        demand[cp.name] = defaultdict(Decimal)
        monthly[cp.name] = defaultdict(Decimal)
        for row in sales_by_cp[cp.id]:
            nom = lookup_nomenclature(nom_index, row.article)
            article = nom.article if nom and nom.article else row.article
            if is_recent_month(row.period_year, row.period_month, previous_month):
                demand[cp.name][article] += row.quantity
            if (row.period_year, row.period_month) == (previous_month.year, previous_month.month):
                monthly[cp.name][article] += row.quantity

    def signature(article):
        nom = lookup_nomenclature(nom_index, article)
        if nom and nom.wear_type and nom.metal_color:
            return nom.wear_type.strip().casefold(), nom.metal_color.strip().casefold()
        return None

    items = []

    def add(kind, action, client, article, title, **details):
        items.append({
            "type": kind, "action": action, "severity": "medium", "score": 60,
            "counterparty": client, "article": article, "title": title,
            "message": title, "details": details,
        })

    aged = {}
    for candidate in illiquid:
        if candidate.stock_qty <= 0 or dwell_bucket(candidate.months_without_sales) != "dead":
            continue
        client = candidate.counterparty
        nom = lookup_nomenclature(nom_index, candidate.article)
        article = nom.article if nom and nom.article else candidate.article
        key = (client, article)
        quantity = stocks[client].get(article)
        if quantity:
            aged[key] = quantity, max(aged.get(key, (quantity, 0))[1], candidate.months_without_sales)

    assigned_stock = set()
    for (client, article), (quantity, dwell) in sorted(aged.items()):
        match = signature(article)
        recipients = []
        if match:
            for other, sales in demand.items():
                if other != client and article not in stocks[other] and (other, article) not in assigned_stock:
                    volume = sum(qty for sku, qty in sales.items() if qty > 0 and sku != article and signature(sku) == match)
                    if volume:
                        recipients.append((volume, other))
        if recipients:
            _, recipient = min(recipients, key=lambda pair: (-pair[0], pair[1]))
            assigned_stock.add((recipient, article))
            add("transfer", "transfer", client, article, f"Передать {article} клиенту «{recipient}»",
                to_counterparty=recipient, suggest_qty=str(quantity), months_without_sales=dwell)
        else:
            replacements = sorted(
                (sku for sku, qty in demand[client].items() if sku != article and qty > 0),
                key=lambda sku: (signature(sku) != match, -demand[client][sku], sku),
            )[:3]
            title = f"Вернуть {article}"
            if replacements:
                title += f" и подсортировать: {', '.join(replacements)}"
            add("aged_return", "return", client, article, title, replacement_articles=replacements,
                suggest_qty=str(quantity), months_without_sales=dwell)

    kit_articles = {nom.kit_article for nom in nom_index.values() if nom.kit_article}
    catalog = db.scalars(select(Nomenclature).where(
        Nomenclature.source_id == cps[0].source_id,
        Nomenclature.kit_article.in_(kit_articles),
        Nomenclature.article.isnot(None),
    ))
    kits = defaultdict(set)
    for nom in catalog:
        wear = (nom.wear_type or "").strip().casefold()
        if wear in {"кольцо", "серьги"}:
            kits[nom.kit_article, wear].add(nom.article)
    for client, sold in monthly.items():
        if not sold:
            continue
        for article, qty in sorted(sold.items()):
            if qty > 0:
                add("monthly_restock", "restock", client, article,
                    f"Пополнить {article}: продано {qty:g} шт. за прошлый месяц", suggest_qty=str(qty))
        for article in sorted(stocks[client]):
            nom = lookup_nomenclature(nom_index, article)
            if not nom or not nom.kit_article:
                continue
            wear = (nom.wear_type or "").strip().casefold()
            opposite = {"кольцо": "серьги", "серьги": "кольцо"}.get(wear)
            if not opposite:
                continue
            options = kits[nom.kit_article, opposite]
            if options and not options.intersection(stocks[client]):
                partner = min(options, key=lambda sku: (-demand[client][sku], sku))
                add("kit_restock", "restock", client, partner, f"Доукомплектовать {article} артикулом {partner}",
                    kit_article=nom.kit_article, existing_article=article, suggest_qty="1")
    return items
