"""Плоский отчёт «Итоги квартала» — все акционные клиенты, 15 колонок."""

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.motivation import normalize_work_type, work_type_label
from app.domain.quarterly import fulfillment_percent, promo_scope_ids, quarterly_results_labels
from app.domain.turnover import dynamics_trend, sales_dynamics_percent, shift_quarter
from app.models import ClientSale, Counterparty, QuarterlyComment, QuarterlyPlan, User
from app.schemas import FactShipmentResult
from app.services.reports import list_fact_shipments_by_periods

_Q = Decimal("0.01")


def _q(value: Decimal | None) -> float:
    if value is None:
        return 0.0
    return float(Decimal(value).quantize(_Q))


def _months_in_quarter(year: int, quarter: int) -> list[tuple[int, int]]:
    start_month = (quarter - 1) * 3 + 1
    return [(year, start_month), (year, start_month + 1), (year, start_month + 2)]


def _facts_for_periods(
    db: Session, *, periods: list[tuple[int, int]], allowed_ids: set[UUID]
) -> dict[tuple[int, int], dict[UUID, FactShipmentResult]]:
    grouped = list_fact_shipments_by_periods(db, periods=periods, allowed_ids=allowed_ids)
    return {period: {item.counterparty_id: item for item in items} for period, items in grouped.items()}


def _zero_fact(cp: Counterparty, year: int, quarter: int) -> FactShipmentResult:
    return FactShipmentResult(
        counterparty_id=cp.id,
        counterparty=cp.name,
        year=year,
        quarter=quarter,
        fact_amount=Decimal(0),
        excluded_illiquid_amount=Decimal(0),
    )


def filter_results_clients(
    clients: list[dict],
    *,
    query: str = "",
    work_type: str = "",
    manager: str = "",
) -> list[dict]:
    q = (query or "").strip().casefold()
    work = (work_type or "").strip().casefold()
    mgr = (manager or "").strip().casefold()
    out: list[dict] = []
    for client in clients:
        name = str(client.get("counterparty") or "").casefold()
        work_val = str(client.get("work_type_label") or client.get("work_type") or "").casefold()
        mgr_val = str(client.get("manager_name") or "").casefold()
        if q and q not in name:
            continue
        if work and work not in work_val:
            continue
        if mgr and mgr not in mgr_val:
            continue
        out.append(client)
    return out


def _promo_counterparties(
    db: Session,
    *,
    allowed_ids: Optional[set[UUID]],
    counterparty_id: Optional[UUID],
    manager_id: Optional[UUID],
) -> list[Counterparty]:
    stmt = select(Counterparty).where(Counterparty.is_promo.is_(True), Counterparty.is_folder.is_(False))
    if counterparty_id:
        stmt = stmt.where(Counterparty.id == counterparty_id)
    if allowed_ids is not None:
        stmt = stmt.where(Counterparty.id.in_(allowed_ids))
    elif manager_id:
        stmt = stmt.where(Counterparty.manager_id == manager_id)
    rows = list(db.scalars(stmt.order_by(Counterparty.name)).all())
    scoped = promo_scope_ids({cp.id for cp in rows}, allowed_ids=allowed_ids, counterparty_id=counterparty_id)
    return [cp for cp in rows if cp.id in scoped]


def build_quarterly_results(
    db: Session,
    *,
    year: int,
    quarter: int,
    counterparty_id: Optional[UUID] = None,
    manager_id: Optional[UUID] = None,
    allowed_ids: Optional[set[UUID]] = None,
) -> dict:
    prev_y, prev_q = shift_quarter(year, quarter, -1)
    prev2_y, prev2_q = shift_quarter(year, quarter, -2)
    labels = quarterly_results_labels(quarter, prev_q, prev2_q)
    empty = {"year": year, "quarter": quarter, "labels": labels, "clients": []}
    if allowed_ids is not None and not allowed_ids:
        return empty

    counterparties = _promo_counterparties(
        db, allowed_ids=allowed_ids, counterparty_id=counterparty_id, manager_id=manager_id
    )
    if not counterparties:
        return empty

    allowed = {cp.id for cp in counterparties}
    months = _months_in_quarter(year, quarter)
    prev_months = set(_months_in_quarter(prev_y, prev_q))
    prev2_months = set(_months_in_quarter(prev2_y, prev2_q))
    month_nums = {m for _, m in months}

    all_sales = list(
        db.scalars(
            select(ClientSale).where(
                ClientSale.head_counterparty_id.in_(allowed),
                ClientSale.period_year.in_({year, prev_y, prev2_y}),
            )
        ).all()
    )
    sales_by_cp: dict[UUID, list[ClientSale]] = defaultdict(list)
    for sale in all_sales:
        if sale.head_counterparty_id in allowed:
            sales_by_cp[sale.head_counterparty_id].append(sale)

    plans = {
        p.counterparty_id: p.plan_value
        for p in db.scalars(
            select(QuarterlyPlan).where(
                QuarterlyPlan.year == year,
                QuarterlyPlan.quarter == quarter,
                QuarterlyPlan.counterparty_id.in_(allowed),
            )
        ).all()
    }
    comments = db.scalars(
        select(QuarterlyComment)
        .where(
            QuarterlyComment.year == year,
            QuarterlyComment.quarter == quarter,
            QuarterlyComment.counterparty_id.in_(allowed),
        )
        .order_by(QuarterlyComment.created_at.desc())
    ).all()
    latest_comment: dict[UUID, QuarterlyComment] = {}
    for comment in comments:
        latest_comment.setdefault(comment.counterparty_id, comment)

    facts = _facts_for_periods(
        db,
        periods=[(year, quarter), (prev_y, prev_q), (prev2_y, prev2_q)],
        allowed_ids=allowed,
    )
    fact_cur = facts.get((year, quarter), {})
    fact_prev = facts.get((prev_y, prev_q), {})
    fact_prev2 = facts.get((prev2_y, prev2_q), {})

    mgr_ids = {cp.manager_id for cp in counterparties if cp.manager_id}
    managers = {
        u.id: (u.full_name or u.email)
        for u in db.scalars(select(User).where(User.id.in_(mgr_ids))).all()
    } if mgr_ids else {}

    clients_out: list[dict] = []
    for cp in counterparties:
        cp_sales = sales_by_cp.get(cp.id, [])
        plan_value = plans.get(cp.id, Decimal(0))
        shipment = fact_cur.get(cp.id) or _zero_fact(cp, year, quarter)
        shipment_prev = fact_prev.get(cp.id) or _zero_fact(cp, prev_y, prev_q)
        shipment_prev2 = fact_prev2.get(cp.id) or _zero_fact(cp, prev2_y, prev2_q)
        comment = latest_comment.get(cp.id)
        total_sales = sum(
            (Decimal(s.quantity) for s in cp_sales if s.period_year == year and s.period_month in month_nums),
            Decimal(0),
        )
        prev_sales = sum(
            (Decimal(s.quantity) for s in cp_sales if (s.period_year, s.period_month) in prev_months),
            Decimal(0),
        )
        prev2_sales = sum(
            (Decimal(s.quantity) for s in cp_sales if (s.period_year, s.period_month) in prev2_months),
            Decimal(0),
        )
        shipment_dyn = sales_dynamics_percent(shipment.fact_amount, shipment_prev.fact_amount)
        dynamics = sales_dynamics_percent(total_sales, prev_sales)
        shipment_trend = dynamics_trend(
            shipment.fact_amount, shipment_prev.fact_amount, shipment_prev2.fact_amount
        )
        sales_trend = dynamics_trend(total_sales, prev_sales, prev2_sales)
        mgr_name = managers.get(cp.manager_id) if cp.manager_id else None
        clients_out.append(
            {
                "counterparty_id": str(cp.id),
                "counterparty": cp.name,
                "manager_name": mgr_name,
                "work_type": normalize_work_type(cp.work_type),
                "work_type_label": work_type_label(cp.work_type),
                "work_type_percent": _q(cp.work_type_percent or Decimal(0)),
                "plan": _q(plan_value),
                "shipment_fact": _q(shipment.fact_amount),
                "shipment_percent": _q(fulfillment_percent(shipment.fact_amount, plan_value)),
                "shipment_prev_quarter": _q(shipment_prev.fact_amount),
                "shipment_prev2_quarter": _q(shipment_prev2.fact_amount),
                "shipment_dynamics_percent": _q(shipment_dyn) if shipment_dyn is not None else None,
                "shipment_dynamics_trend": shipment_trend,
                "sales_total": _q(total_sales),
                "sales_prev_quarter": _q(prev_sales),
                "sales_prev2_quarter": _q(prev2_sales),
                "dynamics_percent": _q(dynamics) if dynamics is not None else None,
                "dynamics_trend": sales_trend,
                "comment": comment.text if comment else None,
                "comment_id": str(comment.id) if comment else None,
            }
        )

    return {
        "year": year,
        "quarter": quarter,
        "labels": labels,
        "clients": clients_out,
    }
