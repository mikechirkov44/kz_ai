from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from typing import Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.constants import DEFAULT_PRICE_MARKUP
from app.domain.articles import find_nomenclature_by_article, normalize_article
from app.domain.motivation import (
    ClientMotivationTotal,
    add_client_sale,
    calculate_line_bonus,
    grade_sort_key,
    line_cost_metrics,
    normalize_work_type,
    sorted_client_totals,
    work_type_label,
)
from app.domain.turnover import next_quarter_plan, turnover_percent
from app.domain.fact_shipments import IlliquidCheckInput, cancelled_realization_ids, include_in_fact, quarter_bounds
from app.services.counterparty_utils import counterparty_tree_ids, map_shops_to_promo_heads
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
    User,
)
from app.schemas import (
    FactShipmentResult,
    MotivationClientRow,
    MotivationGroup,
    MotivationItem,
    MotivationReport,
    QuarterlyClientRow,
    QuarterlyPlansReport,
    QuarterlySlice,
    TurnoverReport,
    TurnoverRow,
)


def avg_realization_price(db: Session, counterparty_id: UUID, article: str) -> Optional[Decimal]:
    norm = normalize_article(article)
    if not norm:
        return None
    nom = find_nomenclature_by_article(db, norm)
    if not nom:
        return None
    tree = counterparty_tree_ids(db, counterparty_id)
    avg = db.scalar(
        select(func.avg(Realization.price)).where(
            Realization.counterparty_id.in_(tree),
            Realization.nomenclature_id == nom.id,
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


def _motivation_counterparties(
    db: Session,
    *,
    counterparty_id: Optional[UUID],
    source_id: Optional[str],
    allowed_ids: Optional[set[UUID]],
) -> list[Counterparty]:
    if counterparty_id:
        cp = db.get(Counterparty, counterparty_id)
        if not cp or cp.is_folder:
            raise ValueError("Counterparty not found")
        if allowed_ids is not None and counterparty_id not in allowed_ids:
            raise ValueError("Counterparty not found")
        return [cp]
    stmt = select(Counterparty).where(Counterparty.is_promo.is_(True), Counterparty.is_folder.is_(False))
    if source_id:
        stmt = stmt.where(Counterparty.source_id == source_id)
    if allowed_ids is not None:
        if not allowed_ids:
            return []
        stmt = stmt.where(Counterparty.id.in_(allowed_ids))
    return list(db.scalars(stmt.order_by(Counterparty.name)).all())


def _diff_percent(cost: Decimal, calculated: Decimal) -> Optional[Decimal]:
    if calculated == 0:
        return None
    return ((cost - calculated) / calculated * Decimal(100)).quantize(Decimal("0.01"))


def _group_motivation_items(items: list[MotivationItem]) -> list[MotivationGroup]:
    buckets: dict[str, list[MotivationItem]] = defaultdict(list)
    bonus_by_grade: dict[str, Decimal] = {}
    for item in items:
        buckets[item.grade].append(item)
        bonus_by_grade[item.grade] = item.bonus_per_unit
    groups: list[MotivationGroup] = []
    for grade in sorted(buckets.keys(), key=grade_sort_key):
        rows = sorted(buckets[grade], key=lambda r: ((r.name or "").lower(), r.article, float(r.price)))
        qty = sum((r.quantity for r in rows), Decimal(0))
        bonus = sum((r.total_bonus for r in rows), Decimal(0))
        cost = sum((r.cost_amount for r in rows), Decimal(0))
        calc = sum((r.calculated_amount or Decimal(0) for r in rows), Decimal(0))
        has_calc = any(r.calculated_amount is not None for r in rows)
        groups.append(
            MotivationGroup(
                grade=grade,
                bonus_per_unit=bonus_by_grade.get(grade, Decimal(0)),
                items=rows,
                quantity=qty,
                total_bonus=bonus,
                total_cost=cost,
                total_calculated_cost=calc if has_calc else Decimal(0),
                difference_percent=_diff_percent(cost, calc) if has_calc and calc else None,
            )
        )
    return groups


def build_motivation_report(
    db: Session,
    *,
    year: int,
    month: int,
    counterparty_id: Optional[UUID] = None,
    source_id: Optional[str] = None,
    allowed_ids: Optional[set[UUID]] = None,
) -> MotivationReport:
    counterparties = _motivation_counterparties(
        db, counterparty_id=counterparty_id, source_id=source_id, allowed_ids=allowed_ids
    )
    period = f"{year:04d}-{month:02d}"
    if not counterparties:
        return MotivationReport(
            counterparty="Все",
            counterparty_id=counterparty_id,
            period=period,
            items=[],
            clients=[],
            groups=[],
            total_bonus=Decimal(0),
        )

    cp_by_id = {cp.id: cp for cp in counterparties}
    sales = db.scalars(
        select(ClientSale).where(
            ClientSale.head_counterparty_id.in_(cp_by_id.keys()),
            ClientSale.period_year == year,
            ClientSale.period_month == month,
        )
    ).all()
    promo_rows = db.scalars(select(PromoMotivation).where(PromoMotivation.counterparty_id.in_(cp_by_id.keys()))).all()
    promo_by_cp: dict[UUID, set[str]] = {}
    for row in promo_rows:
        promo_by_cp.setdefault(row.counterparty_id, set()).add(row.article)

    nom_cache: dict[str, Optional[Nomenclature]] = {}
    avg_cache: dict[tuple[UUID, str], Optional[Decimal]] = {}
    items: list[MotivationItem] = []
    totals: dict[UUID, ClientMotivationTotal] = {}
    grand = Decimal(0)
    grand_cost = Decimal(0)
    grand_calc = Decimal(0)
    has_calc = False
    for sale in sales:
        cp = cp_by_id.get(sale.head_counterparty_id)
        if not cp:
            continue
        promo_articles = promo_by_cp.get(cp.id, set())
        is_promo = sale.is_promo_motivation or sale.article in promo_articles
        bonus, grade, line_total = calculate_line_bonus(
            price=sale.price,
            quantity=sale.quantity,
            is_promo_motivation=is_promo,
        )
        grand += line_total
        if sale.article not in nom_cache:
            nom_cache[sale.article] = find_nomenclature_by_article(db, sale.article)
        nom = nom_cache[sale.article]
        avg_key = (cp.id, sale.article)
        if avg_key not in avg_cache:
            avg_cache[avg_key] = avg_realization_price(db, cp.id, sale.article)
        cost_amount, calc_unit, calc_amount, diff = line_cost_metrics(
            price=sale.price,
            quantity=sale.quantity,
            avg_realization=avg_cache[avg_key],
        )
        grand_cost += cost_amount
        if calc_amount is not None:
            grand_calc += calc_amount
            has_calc = True
        items.append(
            MotivationItem(
                article=sale.article,
                price=sale.price,
                quantity=sale.quantity,
                grade=grade,
                bonus_per_unit=bonus,
                total_bonus=line_total,
                is_promo_motivation=is_promo,
                name=nom.name if nom else None,
                lts=nom.lts if nom else None,
                lts_date=nom.lts_date.isoformat() if nom and nom.lts_date else None,
                counterparty=cp.name,
                counterparty_id=cp.id,
                cost_amount=cost_amount,
                calculated_unit=calc_unit,
                calculated_amount=calc_amount,
                difference_percent=diff,
            )
        )
        add_client_sale(
            totals,
            counterparty_id=cp.id,
            counterparty=cp.name,
            quantity=sale.quantity,
            total_bonus=line_total,
            cost_amount=cost_amount,
            calculated_amount=calc_amount or Decimal(0),
        )

    items.sort(key=lambda r: (*grade_sort_key(r.grade), (r.name or "").lower(), r.article, float(r.price)))
    groups = _group_motivation_items(items)
    clients = [
        MotivationClientRow(
            counterparty_id=row.counterparty_id,
            counterparty=row.counterparty,
            quantity=row.quantity,
            lines=row.lines,
            total_bonus=row.total_bonus,
            total_cost=row.total_cost,
            total_calculated_cost=row.total_calculated_cost,
            difference_percent=_diff_percent(row.total_cost, row.total_calculated_cost)
            if row.total_calculated_cost
            else None,
        )
        for row in sorted_client_totals(totals)
    ]
    return MotivationReport(
        counterparty=counterparties[0].name if counterparty_id else "Все",
        counterparty_id=counterparty_id,
        period=period,
        items=items,
        clients=[] if counterparty_id else clients,
        groups=groups,
        total_bonus=grand,
        total_cost=grand_cost,
        total_calculated_cost=grand_calc if has_calc else Decimal(0),
        difference_percent=_diff_percent(grand_cost, grand_calc) if has_calc and grand_calc else None,
    )


def build_turnover_report(
    db: Session,
    *,
    view: str,
    year: int,
    month: int,
    counterparty_id: Optional[UUID] = None,
    manager_id: Optional[UUID] = None,
    allowed_ids: Optional[set[UUID]] = None,
) -> TurnoverReport:
    # Simplified MVP: aggregate client_sales + client_stocks for promo counterparties
    cps_q = select(Counterparty).where(Counterparty.is_promo.is_(True), Counterparty.is_folder.is_(False))
    if counterparty_id:
        cps_q = cps_q.where(Counterparty.id == counterparty_id)
    if allowed_ids is not None:
        if not allowed_ids:
            return TurnoverReport(period=f"{year:04d}-{month:02d}", view=view, data=[])
        cps_q = cps_q.where(Counterparty.id.in_(allowed_ids))
    elif manager_id:
        cps_q = cps_q.where(Counterparty.manager_id == manager_id)
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
                nom = find_nomenclature_by_article(db, article)
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
    tree_ids = counterparty_tree_ids(db, counterparty_id)

    realizations = db.scalars(
        select(Realization).where(
            Realization.counterparty_id.in_(tree_ids),
            Realization.doc_date >= start,
            Realization.doc_date <= end,
            Realization.ignore_turnover.is_(False),
        )
    ).all()
    returns = db.scalars(
        select(ReturnDoc).where(
            ReturnDoc.counterparty_id.in_(tree_ids),
            ReturnDoc.doc_date >= start,
            ReturnDoc.doc_date <= end,
            ReturnDoc.ignore_turnover.is_(False),
        )
    ).all()

    fact = Decimal(0)
    excluded = Decimal(0)
    cancelled = cancelled_realization_ids(realizations, returns)
    for r in realizations:
        if r.id in cancelled:
            continue
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

    return FactShipmentResult(
        counterparty_id=cp.id,
        counterparty=cp.name,
        year=year,
        quarter=quarter,
        fact_amount=fact,
        excluded_illiquid_amount=excluded,
    )


def list_fact_shipments(
    db: Session,
    *,
    year: int,
    quarter: int,
    allowed_ids: Optional[set[UUID]] = None,
) -> list[FactShipmentResult]:
    if allowed_ids is not None and not allowed_ids:
        return []
    promo_stmt = select(Counterparty).where(
        Counterparty.is_promo.is_(True),
        Counterparty.is_folder.is_(False),
    )
    if allowed_ids is not None:
        promo_stmt = promo_stmt.where(Counterparty.id.in_(allowed_ids))
    promo_cps = list(db.scalars(promo_stmt.order_by(Counterparty.name)).all())
    promo_ids = {c.id for c in promo_cps}
    if not promo_ids:
        return []
    to_promo = map_shops_to_promo_heads(db, promo_ids)
    doc_ids = set(to_promo)
    start, end = quarter_bounds(year, quarter)
    r_stmt = select(Realization).where(
        Realization.doc_date >= start,
        Realization.doc_date <= end,
        Realization.ignore_turnover.is_(False),
        Realization.counterparty_id.in_(doc_ids),
    )
    ret_stmt = select(ReturnDoc).where(
        ReturnDoc.doc_date >= start,
        ReturnDoc.doc_date <= end,
        ReturnDoc.ignore_turnover.is_(False),
        ReturnDoc.counterparty_id.in_(doc_ids),
    )
    realizations = list(db.scalars(r_stmt).all())
    returns = list(db.scalars(ret_stmt).all())

    nom_ids = {r.nomenclature_id for r in realizations if r.nomenclature_id}
    noms = (
        {n.id: n for n in db.scalars(select(Nomenclature).where(Nomenclature.id.in_(nom_ids))).all()}
        if nom_ids
        else {}
    )
    series = {r.series for r in realizations if r.series}
    receipts_by_series: dict[str, ProductionReceipt] = {}
    if series:
        for rec in db.scalars(select(ProductionReceipt).where(ProductionReceipt.series.in_(series))).all():
            receipts_by_series.setdefault(rec.series or "", rec)
    order_refs = {rec.client_order_onec_ref for rec in receipts_by_series.values() if rec.client_order_onec_ref}
    orders_by_ref: dict[str, ClientOrder] = {}
    if order_refs:
        for order in db.scalars(select(ClientOrder).where(ClientOrder.onec_ref.in_(order_refs))).all():
            orders_by_ref[order.onec_ref] = order

    fact_map: dict[UUID, Decimal] = defaultdict(lambda: Decimal(0))
    excl_map: dict[UUID, Decimal] = defaultdict(lambda: Decimal(0))
    reals_by_promo: dict[UUID, list[Realization]] = defaultdict(list)
    rets_by_promo: dict[UUID, list[ReturnDoc]] = defaultdict(list)
    for row in realizations:
        if not row.counterparty_id:
            continue
        promo_id = to_promo.get(row.counterparty_id)
        if promo_id:
            reals_by_promo[promo_id].append(row)
    for row in returns:
        if not row.counterparty_id:
            continue
        promo_id = to_promo.get(row.counterparty_id)
        if promo_id:
            rets_by_promo[promo_id].append(row)
    cancelled: set = set()
    for promo_id, real_rows in reals_by_promo.items():
        cancelled |= cancelled_realization_ids(real_rows, rets_by_promo.get(promo_id, []))

    for row in realizations:
        if not row.counterparty_id:
            continue
        promo_id = to_promo.get(row.counterparty_id)
        if not promo_id:
            continue
        if row.id in cancelled:
            continue
        nom = noms.get(row.nomenclature_id) if row.nomenclature_id else None
        order = None
        if row.series:
            receipt = receipts_by_series.get(row.series)
            if receipt and receipt.client_order_onec_ref:
                order = orders_by_ref.get(receipt.client_order_onec_ref)
        check = IlliquidCheckInput(
            lts=nom.lts if nom else None,
            lts_date=nom.lts_date if nom else None,
            order_date=order.doc_date if order else None,
            order_target_warehouse=order.target_warehouse if order else None,
            order_target_counterparty_ref=order.target_counterparty_onec_ref if order else None,
            realization_counterparty_ref=row.counterparty_onec_ref,
            amount=Decimal(row.amount),
        )
        if include_in_fact(check):
            fact_map[promo_id] += Decimal(row.amount)
        else:
            excl_map[promo_id] += Decimal(row.amount)

    items = [
        FactShipmentResult(
            counterparty_id=cp.id,
            counterparty=cp.name,
            year=year,
            quarter=quarter,
            fact_amount=fact_map[cp.id],
            excluded_illiquid_amount=excl_map[cp.id],
        )
        for cp in promo_cps
    ]
    items.sort(key=lambda item: item.counterparty.lower())
    return items


def _fulfillment_slice(name: str, rows: list[QuarterlyClientRow]) -> QuarterlySlice:
    plan = sum((Decimal(r.plan or 0) for r in rows), Decimal(0))
    fact = sum((Decimal(r.fact or 0) for r in rows), Decimal(0))
    percent = (fact / plan * 100) if plan else Decimal(0)
    fulfilled = sum(1 for r in rows if Decimal(r.percent or 0) >= 100)
    return QuarterlySlice(
        name=name,
        clients=len(rows),
        fulfilled=fulfilled,
        percent=percent.quantize(Decimal("0.01")),
    )


def build_quarterly_plans_report(
    db: Session,
    *,
    year: int,
    quarter: int,
    manager_id: Optional[UUID] = None,
    allowed_ids: Optional[set[UUID]] = None,
) -> QuarterlyPlansReport:
    stmt = select(QuarterlyPlan).where(QuarterlyPlan.year == year, QuarterlyPlan.quarter == quarter)
    if allowed_ids is not None:
        if not allowed_ids:
            return QuarterlyPlansReport(year=year, quarter=quarter, clients=[], slices=[])
        stmt = stmt.where(QuarterlyPlan.counterparty_id.in_(allowed_ids))
    elif manager_id:
        scoped_ids = select(Counterparty.id).where(Counterparty.manager_id == manager_id)
        stmt = stmt.where(QuarterlyPlan.counterparty_id.in_(scoped_ids))
    plans = db.scalars(stmt).all()
    clients: list[QuarterlyClientRow] = []
    prev_year, prev_q = (year - 1, 4) if quarter == 1 else (year, quarter - 1)

    manager_cache: dict[UUID, str] = {}
    for plan in plans:
        fact = compute_fact_shipments(db, counterparty_id=plan.counterparty_id, year=year, quarter=quarter)
        prev = compute_fact_shipments(db, counterparty_id=plan.counterparty_id, year=prev_year, quarter=prev_q)
        percent = (fact.fact_amount / plan.plan_value * 100) if plan.plan_value else Decimal(0)
        dynamics = None
        if prev.fact_amount:
            dynamics = (fact.fact_amount / prev.fact_amount).quantize(Decimal("0.01"))
        cp = db.get(Counterparty, plan.counterparty_id)
        mgr_id = cp.manager_id if cp else None
        mgr_name = None
        if mgr_id:
            if mgr_id not in manager_cache:
                mgr = db.get(User, mgr_id)
                manager_cache[mgr_id] = (mgr.full_name or mgr.email) if mgr else "—"
            mgr_name = manager_cache[mgr_id]
        clients.append(
            QuarterlyClientRow(
                counterparty=cp.name if cp else str(plan.counterparty_id),
                counterparty_id=plan.counterparty_id,
                plan=plan.plan_value,
                fact=fact.fact_amount,
                percent=percent.quantize(Decimal("0.01")),
                dynamics=dynamics,
                manager_id=mgr_id,
                manager_name=mgr_name,
                work_type=normalize_work_type(cp.work_type) if cp else None,
                work_type_label=work_type_label(cp.work_type) if cp else None,
                work_type_percent=cp.work_type_percent if cp else None,
            )
        )
    by_manager: dict[str, list[QuarterlyClientRow]] = defaultdict(list)
    for row in clients:
        by_manager[row.manager_name or "Без менеджера"].append(row)
    slices = [_fulfillment_slice("Всего", clients)]
    slices.extend(
        _fulfillment_slice(name, rows) for name, rows in sorted(by_manager.items(), key=lambda item: item[0].lower())
    )
    return QuarterlyPlansReport(year=year, quarter=quarter, clients=clients, slices=slices)
