from __future__ import annotations

from decimal import Decimal
from typing import Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.constants import DEFAULT_PRICE_MARKUP
from app.domain.motivation import calculate_line_bonus, normalize_work_type
from app.domain.turnover import next_quarter_plan, turnover_percent
from app.domain.fact_shipments import IlliquidCheckInput, include_in_fact, quarter_bounds
from app.models import (
    ClientOrder,
    ClientSale,
    ClientStock,
    Counterparty,
    Nomenclature,
    ProductionReceipt,
    PromoMotivation,
    QuarterlyPlan,
    Realization,
    ReturnDoc,
)
from app.schemas import (
    FactShipmentResult,
    MotivationItem,
    MotivationReport,
    QuarterlyClientRow,
    QuarterlyPlansReport,
    TurnoverReport,
    TurnoverRow,
)


def avg_realization_price(db: Session, counterparty_id: UUID, article: str) -> Optional[Decimal]:
    nom_ids = db.scalars(select(Nomenclature.id).where((Nomenclature.article == article) | (Nomenclature.barcode == article))).all()
    if not nom_ids:
        return None
    avg = db.scalar(
        select(func.avg(Realization.price)).where(
            Realization.counterparty_id == counterparty_id,
            Realization.nomenclature_id.in_(nom_ids),
            Realization.price > 0,
        )
    )
    return Decimal(avg) if avg is not None else None


def resolve_sale_price(db: Session, counterparty_id: UUID, article: str, price: Optional[Decimal]) -> Decimal:
    if price is not None:
        return Decimal(price)
    avg = avg_realization_price(db, counterparty_id, article)
    if avg is None:
        return Decimal(0)
    return (avg * Decimal(str(DEFAULT_PRICE_MARKUP))).quantize(Decimal("0.01"))


def build_motivation_report(
    db: Session,
    *,
    counterparty_id: UUID,
    year: int,
    month: int,
) -> MotivationReport:
    cp = db.get(Counterparty, counterparty_id)
    if not cp:
        raise ValueError("Counterparty not found")

    sales = db.scalars(
        select(ClientSale).where(
            ClientSale.head_counterparty_id == counterparty_id,
            ClientSale.period_year == year,
            ClientSale.period_month == month,
        )
    ).all()

    promo_articles = {
        p.article
        for p in db.scalars(select(PromoMotivation).where(PromoMotivation.counterparty_id == counterparty_id)).all()
    }

    items: list[MotivationItem] = []
    total = Decimal(0)
    for sale in sales:
        is_promo = sale.is_promo_motivation or sale.article in promo_articles
        bonus, grade, line_total = calculate_line_bonus(
            price=sale.price,
            quantity=sale.quantity,
            is_promo_motivation=is_promo,
        )
        total += line_total
        items.append(
            MotivationItem(
                article=sale.article,
                price=sale.price,
                quantity=sale.quantity,
                grade=grade,
                bonus_per_unit=bonus,
                total_bonus=line_total,
                is_promo_motivation=is_promo,
            )
        )

    return MotivationReport(
        counterparty=cp.name,
        period=f"{year:04d}-{month:02d}",
        items=items,
        total_bonus=total,
    )


def build_turnover_report(
    db: Session,
    *,
    view: str,
    year: int,
    month: int,
    counterparty_id: Optional[UUID] = None,
) -> TurnoverReport:
    # Simplified MVP: aggregate client_sales + client_stocks for promo counterparties
    cps_q = select(Counterparty).where(Counterparty.is_promo.is_(True), Counterparty.is_folder.is_(False))
    if counterparty_id:
        cps_q = cps_q.where(Counterparty.id == counterparty_id)
    counterparties = db.scalars(cps_q).all()

    # stocks: begin = last day prev month snapshot or earliest in month; end = stock_date in month
    from calendar import monthrange

    last_day = monthrange(year, month)[1]
    start = __import__("datetime").date(year, month, 1)
    end = __import__("datetime").date(year, month, last_day)

    data: list[TurnoverRow] = []

    if view == "counterparty":
        for cp in counterparties:
            sales_qty = db.scalar(
                select(func.coalesce(func.sum(ClientSale.quantity), 0)).where(
                    ClientSale.head_counterparty_id == cp.id,
                    ClientSale.period_year == year,
                    ClientSale.period_month == month,
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
            avg = (begin_d + end_d) / Decimal(2)
            turn = turnover_percent(sales_d, begin_d, end_d)
            proposal = next_quarter_plan(sales_d, normalize_work_type(cp.work_type), cp.work_type_percent)
            data.append(
                TurnoverRow(
                    counterparty=cp.name,
                    work_type=normalize_work_type(cp.work_type),
                    work_type_percent=cp.work_type_percent,
                    sales=sales_d,
                    stock_begin=begin_d,
                    stock_end=end_d,
                    stock_avg=avg,
                    turnover_percent=turn.quantize(Decimal("0.01")),
                    proposal=proposal.quantize(Decimal("0.01")),
                )
            )
    else:
        # main / lts / wear_type / metal_color — dimension from nomenclature joined via article
        dim_attr = {
            "main": None,
            "lts": "lts",
            "wear_type": "wear_type",
            "metal_color": "metal_color",
        }.get(view, None)

        for cp in counterparties:
            sales = db.scalars(
                select(ClientSale).where(
                    ClientSale.head_counterparty_id == cp.id,
                    ClientSale.period_year == year,
                    ClientSale.period_month == month,
                )
            ).all()
            stocks_end = db.scalars(
                select(ClientStock).where(ClientStock.head_counterparty_id == cp.id, ClientStock.stock_date == end)
            ).all()
            stocks_begin_rows = db.scalars(
                select(ClientStock).where(ClientStock.head_counterparty_id == cp.id, ClientStock.stock_date < start)
            ).all()

            def nom_dim(article: str) -> str:
                if not dim_attr:
                    return ""
                nom = db.scalar(
                    select(Nomenclature).where(
                        (Nomenclature.article == article) | (Nomenclature.barcode == article)
                    )
                )
                return getattr(nom, dim_attr, None) or "—" if nom else "—"

            buckets: dict[str, dict[str, Decimal]] = {}

            def bucket(key: str) -> dict[str, Decimal]:
                if key not in buckets:
                    buckets[key] = {
                        "sales": Decimal(0),
                        "begin": Decimal(0),
                        "end": Decimal(0),
                    }
                return buckets[key]

            # total row
            total_key = "__total__"
            for s in sales:
                key = nom_dim(s.article) if dim_attr else total_key
                bucket(key)["sales"] += Decimal(s.quantity)
                bucket(total_key)["sales"] += Decimal(s.quantity)
            for st in stocks_end:
                key = nom_dim(st.article) if dim_attr else total_key
                bucket(key)["end"] += Decimal(st.quantity)
                bucket(total_key)["end"] += Decimal(st.quantity)
            for st in stocks_begin_rows:
                key = nom_dim(st.article) if dim_attr else total_key
                bucket(key)["begin"] += Decimal(st.quantity)
                bucket(total_key)["begin"] += Decimal(st.quantity)

            # ensure begin fallback
            for b in buckets.values():
                if b["begin"] == 0 and b["end"] != 0:
                    b["begin"] = b["end"]

            # counterparty total first
            tot = buckets.get(total_key, {"sales": Decimal(0), "begin": Decimal(0), "end": Decimal(0)})
            avg = (tot["begin"] + tot["end"]) / Decimal(2)
            turn = turnover_percent(tot["sales"], tot["begin"], tot["end"])
            data.append(
                TurnoverRow(
                    counterparty=cp.name,
                    dimension=None,
                    work_type=normalize_work_type(cp.work_type) if view == "main" else None,
                    work_type_percent=cp.work_type_percent if view == "main" else None,
                    sales=tot["sales"],
                    stock_begin=tot["begin"],
                    stock_end=tot["end"],
                    stock_avg=avg,
                    turnover_percent=turn.quantize(Decimal("0.01")),
                    proposal=next_quarter_plan(tot["sales"], normalize_work_type(cp.work_type), cp.work_type_percent)
                    if view == "main"
                    else None,
                )
            )
            if dim_attr:
                for dim, vals in buckets.items():
                    if dim == total_key:
                        continue
                    avg = (vals["begin"] + vals["end"]) / Decimal(2)
                    turn = turnover_percent(vals["sales"], vals["begin"], vals["end"])
                    data.append(
                        TurnoverRow(
                            counterparty=None,
                            dimension=dim,
                            sales=vals["sales"],
                            stock_begin=vals["begin"],
                            stock_end=vals["end"],
                            stock_avg=avg,
                            turnover_percent=turn.quantize(Decimal("0.01")),
                        )
                    )

    return TurnoverReport(period=f"{year:04d}-{month:02d}", view=view, data=data)


def compute_fact_shipments(
    db: Session,
    *,
    counterparty_id: UUID,
    year: int,
    quarter: int,
) -> FactShipmentResult:
    cp = db.get(Counterparty, counterparty_id)
    if not cp:
        raise ValueError("Counterparty not found")
    start, end = quarter_bounds(year, quarter)

    realizations = db.scalars(
        select(Realization).where(
            Realization.counterparty_id == counterparty_id,
            Realization.doc_date >= start,
            Realization.doc_date <= end,
            Realization.ignore_turnover.is_(False),
        )
    ).all()
    returns = db.scalars(
        select(ReturnDoc).where(
            ReturnDoc.counterparty_id == counterparty_id,
            ReturnDoc.doc_date >= start,
            ReturnDoc.doc_date <= end,
            ReturnDoc.ignore_turnover.is_(False),
        )
    ).all()

    fact = Decimal(0)
    excluded = Decimal(0)
    for r in realizations:
        nom = db.get(Nomenclature, r.nomenclature_id) if r.nomenclature_id else None
        order = None
        if r.series:
            receipt = db.scalar(
                select(ProductionReceipt).where(ProductionReceipt.series == r.series).limit(1)
            )
            if receipt and receipt.client_order_onec_ref:
                order = db.scalar(
                    select(ClientOrder).where(ClientOrder.onec_ref == receipt.client_order_onec_ref).limit(1)
                )
        check = IlliquidCheckInput(
            lts=nom.lts if nom else None,
            lts_date=nom.lts_date if nom else None,
            order_date=order.doc_date if order else None,
            order_target_warehouse=order.target_warehouse if order else None,
            order_target_counterparty_ref=order.target_counterparty_onec_ref if order else None,
            realization_counterparty_ref=r.counterparty_onec_ref,
            amount=Decimal(r.amount),
        )
        if include_in_fact(check):
            fact += Decimal(r.amount)
        else:
            excluded += Decimal(r.amount)

    ret_sum = sum((Decimal(x.amount) for x in returns), Decimal(0))
    fact -= ret_sum

    return FactShipmentResult(
        counterparty_id=cp.id,
        counterparty=cp.name,
        year=year,
        quarter=quarter,
        fact_amount=fact,
        excluded_illiquid_amount=excluded,
    )


def build_quarterly_plans_report(db: Session, *, year: int, quarter: int) -> QuarterlyPlansReport:
    plans = db.scalars(
        select(QuarterlyPlan).where(QuarterlyPlan.year == year, QuarterlyPlan.quarter == quarter)
    ).all()
    clients: list[QuarterlyClientRow] = []
    prev_year, prev_q = (year - 1, 4) if quarter == 1 else (year, quarter - 1)

    for plan in plans:
        fact = compute_fact_shipments(db, counterparty_id=plan.counterparty_id, year=year, quarter=quarter)
        prev = compute_fact_shipments(db, counterparty_id=plan.counterparty_id, year=prev_year, quarter=prev_q)
        percent = (fact.fact_amount / plan.plan_value * 100) if plan.plan_value else Decimal(0)
        dynamics = None
        if prev.fact_amount:
            dynamics = (fact.fact_amount / prev.fact_amount).quantize(Decimal("0.01"))
        cp = db.get(Counterparty, plan.counterparty_id)
        clients.append(
            QuarterlyClientRow(
                counterparty=cp.name if cp else str(plan.counterparty_id),
                counterparty_id=plan.counterparty_id,
                plan=plan.plan_value,
                fact=fact.fact_amount,
                percent=percent.quantize(Decimal("0.01")),
                dynamics=dynamics,
            )
        )
    return QuarterlyPlansReport(year=year, quarter=quarter, clients=clients)
