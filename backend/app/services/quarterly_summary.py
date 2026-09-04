"""Итоговый отчёт по кварталу — матрица цвет / ЖЦТ / тип изделия (ТЗ лист 6)."""

from __future__ import annotations

from calendar import monthrange
from collections import defaultdict
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.ai_rules import (
    IlliquidCandidate,
    PatternHit,
    PriceArbitrageAlert,
    illiquid_recommendations,
    price_arbitrage_recommendations,
    successful_pattern_recommendations,
)
from app.domain.articles import index_nomenclature, lookup_nomenclature
from app.domain.dwell import months_without_sales
from app.domain.motivation import normalize_work_type, work_type_label
from app.domain.quarterly import (
    BLOCK_KEYS,
    BLOCK_LABELS,
    TOTAL_DIMENSION,
    dim_metrics,
    recommendations_digest,
    zip_block_rows,
)
from app.domain.turnover import next_quarter_plan, sales_dynamics_percent, shift_quarter
from app.models import (
    ClientSale,
    ClientStock,
    Counterparty,
    Nomenclature,
    QuarterlyComment,
    QuarterlyPlan,
    Realization,
    User,
)
from app.services.reports import compute_fact_shipments

_Q = Decimal("0.01")


def _q(value: Decimal | None) -> float:
    if value is None:
        return 0.0
    return float(Decimal(value).quantize(_Q))


def _months_in_quarter(year: int, quarter: int) -> list[tuple[int, int]]:
    start_month = (quarter - 1) * 3 + 1
    return [(year, start_month), (year, start_month + 1), (year, start_month + 2)]


def _month_end(year: int, month: int) -> date:
    return date(year, month, monthrange(year, month)[1])


def _prev_month(year: int, month: int) -> tuple[int, int]:
    if month == 1:
        return year - 1, 12
    return year, month - 1


def _nom_dim(nom: Nomenclature | None, attr: str) -> str:
    if nom is None:
        return "—"
    return getattr(nom, attr, None) or "—"


def _stock_on_date(by_date: dict[date, Decimal], as_of: date) -> Decimal:
    dates = [d for d in by_date if d <= as_of]
    if not dates:
        return Decimal(0)
    return by_date[max(dates)]


def _metrics_payload(sales: Decimal, begins: list[Decimal], ends: list[Decimal], dimension: str) -> dict:
    m = dim_metrics(sales, begins, ends)
    return {
        "dimension": dimension,
        "avg_stock": _q(m["avg_stock"]),
        "sales_total": _q(m["sales_total"]),
        "quarter_turnover_percent": _q(m["quarter_turnover_percent"]),
        "avg_month_turnover_percent": _q(m["avg_month_turnover_percent"]),
    }


def build_quarterly_summary(
    db: Session,
    *,
    year: int,
    quarter: int,
    counterparty_id: Optional[UUID] = None,
    manager_id: Optional[UUID] = None,
    allowed_ids: Optional[set[UUID]] = None,
) -> dict:
    months = _months_in_quarter(year, quarter)
    month_nums = [m for _, m in months]
    prev_y, prev_q = shift_quarter(year, quarter, -1)
    prev2_y, prev2_q = shift_quarter(year, quarter, -2)
    prev_months = _months_in_quarter(prev_y, prev_q)
    prev2_months = _months_in_quarter(prev2_y, prev2_q)

    cps_q = select(Counterparty).where(
        Counterparty.is_promo.is_(True),
        Counterparty.is_folder.is_(False),
    )
    if counterparty_id:
        cps_q = cps_q.where(Counterparty.id == counterparty_id)
    if allowed_ids is not None:
        if not allowed_ids:
            return {
                "year": year,
                "quarter": quarter,
                "labels": _period_labels(year, quarter, prev_q, prev2_q),
                "clients": [],
            }
        cps_q = cps_q.where(Counterparty.id.in_(allowed_ids))
    elif manager_id:
        cps_q = cps_q.where(Counterparty.manager_id == manager_id)
    counterparties = db.scalars(cps_q.order_by(Counterparty.name)).all()
    allowed_ids = {cp.id for cp in counterparties}
    if not allowed_ids:
        return {
            "year": year,
            "quarter": quarter,
            "labels": _period_labels(year, quarter, prev_q, prev2_q),
            "clients": [],
        }

    all_sales = [
        s
        for s in db.scalars(
            select(ClientSale).where(
                ClientSale.head_counterparty_id.in_(allowed_ids),
                ClientSale.period_year.in_({year, prev_y, prev2_y}),
            )
        ).all()
        if s.head_counterparty_id in allowed_ids
    ]
    stocks = db.scalars(select(ClientStock).where(ClientStock.head_counterparty_id.in_(allowed_ids))).all()
    noms = index_nomenclature(db.scalars(select(Nomenclature)).all())

    plans = {
        p.counterparty_id: p.plan_value
        for p in db.scalars(
            select(QuarterlyPlan).where(
                QuarterlyPlan.year == year,
                QuarterlyPlan.quarter == quarter,
                QuarterlyPlan.counterparty_id.in_(allowed_ids),
            )
        ).all()
    }
    comments = db.scalars(
        select(QuarterlyComment)
        .where(
            QuarterlyComment.year == year,
            QuarterlyComment.quarter == quarter,
            QuarterlyComment.counterparty_id.in_(allowed_ids),
        )
        .order_by(QuarterlyComment.created_at.desc())
    ).all()
    latest_comment: dict[UUID, QuarterlyComment] = {}
    for comment in comments:
        latest_comment.setdefault(comment.counterparty_id, comment)

    sales_by_cp: dict[UUID, list[ClientSale]] = defaultdict(list)
    for s in all_sales:
        sales_by_cp[s.head_counterparty_id].append(s)
    stocks_by_cp: dict[UUID, list[ClientStock]] = defaultdict(list)
    for st in stocks:
        stocks_by_cp[st.head_counterparty_id].append(st)

    realizations = db.scalars(
        select(Realization).where(Realization.counterparty_id.in_(allowed_ids), Realization.price > 0)
    ).all()
    real_by_cp: dict[UUID, list[Realization]] = defaultdict(list)
    for r in realizations:
        if r.counterparty_id:
            real_by_cp[r.counterparty_id].append(r)

    month_ends = [_month_end(y, m) for y, m in months]
    month_begins = [_month_end(*_prev_month(y, m)) for y, m in months]
    as_of = month_ends[-1]

    clients_out: list[dict] = []
    for cp in counterparties:
        cp_sales = sales_by_cp.get(cp.id, [])
        q_sales = [s for s in cp_sales if s.period_year == year and s.period_month in month_nums]
        cp_stocks = stocks_by_cp.get(cp.id, [])

        article_sales: dict[str, Decimal] = defaultdict(lambda: Decimal(0))
        last_sale: dict[str, tuple[int, int]] = {}
        for s in q_sales:
            article_sales[s.article] += Decimal(s.quantity)
            key = (s.period_year, s.period_month)
            prev = last_sale.get(s.article)
            if prev is None or key > prev:
                last_sale[s.article] = key

        article_stock_dates: dict[str, dict[date, Decimal]] = defaultdict(lambda: defaultdict(lambda: Decimal(0)))
        first_stock: dict[str, date] = {}
        for st in cp_stocks:
            article_stock_dates[st.article][st.stock_date] += Decimal(st.quantity)
            prev_d = first_stock.get(st.article)
            if prev_d is None or st.stock_date < prev_d:
                first_stock[st.article] = st.stock_date

        articles = set(article_sales) | set(article_stock_dates)
        dim_sales: dict[str, dict[str, Decimal]] = {attr: defaultdict(lambda: Decimal(0)) for attr in BLOCK_KEYS}
        dim_begin: dict[str, dict[str, list[Decimal]]] = {
            attr: defaultdict(lambda: [Decimal(0)] * 3) for attr in BLOCK_KEYS
        }
        dim_end: dict[str, dict[str, list[Decimal]]] = {
            attr: defaultdict(lambda: [Decimal(0)] * 3) for attr in BLOCK_KEYS
        }
        total_begin = [Decimal(0)] * 3
        total_end = [Decimal(0)] * 3
        total_sales = sum(article_sales.values(), Decimal(0))

        illiquid_items: list[IlliquidCandidate] = []
        pattern_bucket: dict[tuple[str, str, str], Decimal] = defaultdict(lambda: Decimal(0))
        wear_client_prices: dict[str, list[Decimal]] = defaultdict(list)

        for article in articles:
            nom = lookup_nomenclature(noms, article)
            sold = article_sales.get(article, Decimal(0))
            by_date = article_stock_dates.get(article, {})
            art_begins = [_stock_on_date(by_date, d) for d in month_begins]
            art_ends = [_stock_on_date(by_date, d) for d in month_ends]
            for i in range(3):
                total_begin[i] += art_begins[i]
                total_end[i] += art_ends[i]
            for attr in BLOCK_KEYS:
                dim = _nom_dim(nom, attr)
                dim_sales[attr][dim] += sold
                for i in range(3):
                    dim_begin[attr][dim][i] += art_begins[i]
                    dim_end[attr][dim][i] += art_ends[i]
            art_metrics = dim_metrics(sold, art_begins, art_ends)
            prev_sale = last_sale.get(article)
            ly = prev_sale[0] if prev_sale else None
            lm = prev_sale[1] if prev_sale else None
            dwell = months_without_sales(
                last_sale_year=ly,
                last_sale_month=lm,
                as_of=as_of,
                first_stock=first_stock.get(article),
            )
            stock_now = art_ends[-1]
            if stock_now > 0:
                illiquid_items.append(
                    IlliquidCandidate(
                        counterparty=cp.name,
                        article=article,
                        wear_type=nom.wear_type if nom else None,
                        lts=nom.lts if nom else None,
                        metal_color=nom.metal_color if nom else None,
                        avg_turnover=art_metrics["avg_month_turnover_percent"],
                        stock_qty=stock_now,
                        months_without_sales=dwell,
                    )
                )
            if nom and sold > 0:
                pattern_bucket[
                    (nom.wear_type or "—", nom.lts or "—", nom.metal_color or "—")
                ] += sold

        for s in q_sales:
            nom = lookup_nomenclature(noms, s.article)
            wear = (nom.wear_type if nom else None) or "—"
            wear_client_prices[wear].append(Decimal(s.price))

        block_rows: dict[str, list[dict]] = {}
        for attr in BLOCK_KEYS:
            dims = sorted(set(dim_sales[attr]) | set(dim_begin[attr]) | set(dim_end[attr]))
            rows = []
            for dim in dims:
                sales_d = dim_sales[attr].get(dim, Decimal(0))
                begins = dim_begin[attr].get(dim, [Decimal(0)] * 3)
                ends = dim_end[attr].get(dim, [Decimal(0)] * 3)
                if sales_d == 0 and all(v == 0 for v in begins) and all(v == 0 for v in ends):
                    continue
                rows.append(_metrics_payload(sales_d, begins, ends, dim))
            block_rows[attr] = rows

        total_row = _metrics_payload(total_sales, total_begin, total_end, TOTAL_DIMENSION)
        matrix: list[dict] = []
        for parts in zip_block_rows(*(block_rows[attr] for attr in BLOCK_KEYS)):
            matrix.append({attr: parts[i] for i, attr in enumerate(BLOCK_KEYS)})
        matrix.append({attr: total_row for attr in BLOCK_KEYS} | {"is_total": True})

        prev_sales = sum(
            (Decimal(s.quantity) for s in cp_sales if (s.period_year, s.period_month) in prev_months),
            Decimal(0),
        )
        prev2_sales = sum(
            (Decimal(s.quantity) for s in cp_sales if (s.period_year, s.period_month) in prev2_months),
            Decimal(0),
        )
        dynamics = sales_dynamics_percent(total_sales, prev_sales)
        wt = normalize_work_type(cp.work_type)
        plan_next = next_quarter_plan(total_sales, wt, cp.work_type_percent)

        rec_items = _client_recommendations(
            illiquid_items=illiquid_items,
            patterns=[
                PatternHit(cp.name, wear, lts, color, qty) for (wear, lts, color), qty in pattern_bucket.items()
            ],
            wear_client_prices=wear_client_prices,
            realizations=real_by_cp.get(cp.id, []),
            noms=noms,
        )
        comment = latest_comment.get(cp.id)
        shipment = compute_fact_shipments(db, counterparty_id=cp.id, year=year, quarter=quarter)
        shipment_prev = compute_fact_shipments(db, counterparty_id=cp.id, year=prev_y, quarter=prev_q)
        shipment_prev2 = compute_fact_shipments(db, counterparty_id=cp.id, year=prev2_y, quarter=prev2_q)
        plan_value = plans.get(cp.id, Decimal(0))
        shipment_percent = (shipment.fact_amount / plan_value * 100) if plan_value else Decimal(0)
        shipment_dyn = sales_dynamics_percent(shipment.fact_amount, shipment_prev.fact_amount)
        mgr_name = None
        if cp.manager_id:
            mgr = db.get(User, cp.manager_id)
            mgr_name = (mgr.full_name or mgr.email) if mgr else None
        clients_out.append(
            {
                "counterparty_id": str(cp.id),
                "counterparty": cp.name,
                "manager_name": mgr_name,
                "work_type": wt,
                "work_type_label": work_type_label(cp.work_type),
                "work_type_percent": _q(cp.work_type_percent or Decimal(0)),
                "plan": _q(plan_value),
                "shipment_fact": _q(shipment.fact_amount),
                "shipment_percent": _q(shipment_percent),
                "shipment_prev_quarter": _q(shipment_prev.fact_amount),
                "shipment_prev2_quarter": _q(shipment_prev2.fact_amount),
                "shipment_dynamics_percent": _q(shipment_dyn) if shipment_dyn is not None else None,
                "sales_total": _q(total_sales),
                "sales_prev_quarter": _q(prev_sales),
                "sales_prev2_quarter": _q(prev2_sales),
                "dynamics_percent": _q(dynamics) if dynamics is not None else None,
                "comment": comment.text if comment else None,
                "comment_id": str(comment.id) if comment else None,
                "next_quarter_plan": _q(plan_next),
                "recommendations": rec_items,
                "recommendations_text": recommendations_digest(rec_items),
                "blocks": {BLOCK_LABELS[k]: block_rows[k] for k in BLOCK_KEYS},
                "matrix": matrix,
                "total": total_row,
            }
        )

    return {
        "year": year,
        "quarter": quarter,
        "labels": _period_labels(year, quarter, prev_q, prev2_q),
        "clients": clients_out,
    }


def _period_labels(year: int, quarter: int, prev_q: int, prev2_q: int) -> dict[str, str]:
    next_y, next_q = shift_quarter(year, quarter, 1)
    return {
        "plan": f"План отгрузки на {quarter} квартал",
        "sales": f"итого продажи {quarter} кв",
        "turnover": f"Об-ть {quarter} кв",
        "avg_turnover": f"Ср. об-ть за {quarter} кв",
        "sales_prev": f"итого продажи {prev_q} кв.",
        "sales_prev2": f"итого продажи {prev2_q} кв.",
        "dynamics": f"Динамика {quarter} кв. / {prev_q} кв.",
        "next_plan": f"План работы на {next_q} кв (шт)",
        "next_year": next_y,
        "next_quarter": str(next_q),
    }


def _client_recommendations(
    *,
    illiquid_items: list[IlliquidCandidate],
    patterns: list[PatternHit],
    wear_client_prices: dict[str, list[Decimal]],
    realizations: list[Realization],
    noms: dict[str, Nomenclature],
) -> list[dict]:
    nom_by_id = {n.id: n for n in noms.values()}
    wear_ship: dict[str, list[Decimal]] = defaultdict(list)
    for row in realizations:
        nom = nom_by_id.get(row.nomenclature_id) if row.nomenclature_id else None
        wear = (nom.wear_type if nom else None) or "—"
        wear_ship[wear].append(Decimal(row.price))
    alerts: list[PriceArbitrageAlert] = []
    for wear, prices in wear_client_prices.items():
        if not prices:
            continue
        client_avg = sum(prices, Decimal(0)) / Decimal(len(prices))
        ship = wear_ship.get(wear) or []
        if not ship:
            continue
        ship_avg = sum(ship, Decimal(0)) / Decimal(len(ship))
        alerts.append(
            PriceArbitrageAlert(
                counterparty=illiquid_items[0].counterparty if illiquid_items else "",
                wear_type=wear,
                shipment_avg_price=ship_avg,
                client_avg_price=client_avg,
            )
        )
    ranked_patterns = [p for p in patterns if p.sales > 0]
    return (
        illiquid_recommendations(illiquid_items)
        + successful_pattern_recommendations(ranked_patterns, top_n=3)
        + price_arbitrage_recommendations(alerts)
    )


def add_quarterly_comment(
    db: Session,
    *,
    year: int,
    quarter: int,
    counterparty_id: UUID,
    text: str,
    author: User | None,
) -> QuarterlyComment:
    comment = QuarterlyComment(
        year=year,
        quarter=quarter,
        counterparty_id=counterparty_id,
        text=text.strip(),
        author_id=author.id if author else None,
        created_at=datetime.now(timezone.utc),
    )
    db.add(comment)
    db.flush()
    return comment


def list_quarterly_comments(
    db: Session,
    *,
    year: int,
    quarter: int,
    counterparty_id: UUID,
) -> list[QuarterlyComment]:
    return list(
        db.scalars(
            select(QuarterlyComment)
            .where(
                QuarterlyComment.year == year,
                QuarterlyComment.quarter == quarter,
                QuarterlyComment.counterparty_id == counterparty_id,
            )
            .order_by(QuarterlyComment.created_at.desc())
        ).all()
    )
