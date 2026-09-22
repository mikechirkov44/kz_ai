"""Scoped read-only queries for the data assistant."""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.domain.articles import find_nomenclature_by_article
from app.domain.assistant import TOOL_LABELS, attach_rank_change, months_in_quarter
from app.domain.fact_shipments import quarter_bounds
from app.domain.turnover import shift_quarter
from app.models import (
    ClientOrder,
    ClientSale,
    Counterparty,
    Nomenclature,
    Realization,
    User,
)
from app.services.ai import generate_recommendations
from app.services.counterparty_utils import counterparty_tree_ids, counterparty_trees
from app.services.reports import (
    build_motivation_report,
    build_quarterly_plans_report,
    compute_fact_shipments,
    list_fact_shipments,
)
from app.services.assistant_odata import query_odata_live
from app.services.scope import apply_counterparty_scope, resolve_allowed_counterparties

_Q = Decimal("0.01")


def _num(value: object) -> float:
    if value is None:
        return 0.0
    return float(Decimal(str(value)).quantize(_Q))


def _period_note(year: int, quarter: int, metric: str | None = None) -> str:
    source = ""
    if metric in {"sales_qty", "sales_amount"}:
        source = "продажи Excel"
    elif metric in {"shipment_qty", "shipment_amount"}:
        source = "отгрузки 1С"
    if source:
        return f"{year} Q{quarter}, {source}"
    return f"{year} Q{quarter}"


def _allowed_ids(db: Session, user: User) -> Optional[set[UUID]]:
    return resolve_allowed_counterparties(db, user)


def _find_counterparty(db: Session, user: User, name: str | None) -> Optional[Counterparty]:
    text = (name or "").strip()
    if not text:
        return None
    stmt = apply_counterparty_scope(
        select(Counterparty).where(
            Counterparty.is_folder.is_(False),
            Counterparty.name.ilike(f"%{text}%"),
        ),
        user,
    )
    rows = list(db.scalars(stmt.limit(12)).all())
    if not rows:
        return None
    exact = [row for row in rows if (row.name or "").strip().lower() == text.lower()]
    return (exact or rows)[0]


def _shipment_ids(db: Session, heads: Optional[set[UUID]], counterparty_id: Optional[UUID]) -> Optional[set[UUID]]:
    if counterparty_id:
        return counterparty_tree_ids(db, counterparty_id)
    if heads is None:
        return None
    if not heads:
        return set()
    trees = counterparty_trees(db, heads)
    ids: set[UUID] = set()
    for group in trees.values():
        ids |= group
    return ids


def run_tool(db: Session, user: User, name: str, args: dict[str, Any]) -> dict[str, Any]:
    year = int(args["year"])
    quarter = int(args["quarter"])
    limit = int(args.get("limit") or 5)
    allowed = _allowed_ids(db, user)
    counterparty = _find_counterparty(db, user, args.get("counterparty"))
    cp_id = counterparty.id if counterparty else None
    handlers = {
        "top_articles": lambda: top_articles(
            db,
            allowed=allowed,
            year=year,
            quarter=quarter,
            limit=limit,
            metric=str(args.get("metric") or "sales_qty"),
            counterparty_id=cp_id,
        ),
        "top_counterparties": lambda: top_counterparties(
            db,
            allowed=allowed,
            year=year,
            quarter=quarter,
            limit=limit,
            metric=str(args.get("metric") or "sales_qty"),
        ),
        "top_managers": lambda: top_managers(db, allowed=allowed, year=year, quarter=quarter, limit=limit),
        "lagging_plan": lambda: lagging_plan(db, allowed=allowed, year=year, quarter=quarter, limit=limit),
        "search_counterparties": lambda: search_counterparties(db, user, q=str(args.get("q") or args.get("counterparty") or "")),
        "recommendations": lambda: recommendations_digest(db, allowed=allowed, counterparty_id=cp_id),
        "motivation": lambda: motivation_digest(
            db,
            allowed=allowed,
            year=year,
            month=int(args.get("month") or months_in_quarter(quarter)[-1]),
            counterparty_id=cp_id,
        ),
        "fact_shipments": lambda: fact_digest(db, allowed=allowed, year=year, quarter=quarter, counterparty_id=cp_id),
        "orders": lambda: documents_digest(
            db,
            user,
            kind="order",
            year=year,
            quarter=quarter,
            counterparty_id=cp_id,
            q=str(args.get("q") or ""),
            limit=limit,
        ),
        "realizations": lambda: documents_digest(
            db,
            user,
            kind="realization",
            year=year,
            quarter=quarter,
            counterparty_id=cp_id,
            q=str(args.get("q") or ""),
            limit=limit,
        ),
        "nomenclature": lambda: nomenclature_digest(db, q=str(args.get("q") or args.get("article") or "")),
        "quarterly_plan": lambda: quarterly_digest(
            db, allowed=allowed, year=year, quarter=quarter, counterparty_id=cp_id, limit=limit
        ),
        "odata_live": lambda: query_odata_live(db, user, args),
    }
    handler = handlers.get(name)
    if not handler:
        return {"tool": name, "error": "Неизвестный запрос"}
    payload = handler()
    payload["tool"] = name
    payload["label"] = TOOL_LABELS.get(name, name)
    if counterparty:
        payload["counterparty"] = counterparty.name
    return payload


def top_articles(
    db: Session,
    *,
    allowed: Optional[set[UUID]],
    year: int,
    quarter: int,
    limit: int,
    metric: str,
    counterparty_id: Optional[UUID],
) -> dict[str, Any]:
    if metric in {"shipment_qty", "shipment_amount"}:
        rows = _top_articles_shipments(
            db,
            allowed=allowed,
            year=year,
            quarter=quarter,
            limit=limit,
            by_amount=metric == "shipment_amount",
            counterparty_id=counterparty_id,
        )
        prev_y, prev_q = shift_quarter(year, quarter, -1)
        previous = _top_articles_shipments(
            db,
            allowed=allowed,
            year=prev_y,
            quarter=prev_q,
            limit=max(limit * 4, 20),
            by_amount=metric == "shipment_amount",
            counterparty_id=counterparty_id,
        )
        rows = attach_rank_change(rows, previous, key="article")
    else:
        rows = _top_articles_sales(
            db,
            allowed=allowed,
            year=year,
            quarter=quarter,
            limit=limit,
            by_amount=metric == "sales_amount",
            counterparty_id=counterparty_id,
        )
        prev_y, prev_q = shift_quarter(year, quarter, -1)
        previous = _top_articles_sales(
            db,
            allowed=allowed,
            year=prev_y,
            quarter=prev_q,
            limit=max(limit * 4, 20),
            by_amount=metric == "sales_amount",
            counterparty_id=counterparty_id,
        )
        rows = attach_rank_change(rows, previous, key="article")
    return {
        "period": _period_note(year, quarter, metric),
        "metric": metric,
        "rows": rows,
    }


def _top_articles_sales(
    db: Session,
    *,
    allowed: Optional[set[UUID]],
    year: int,
    quarter: int,
    limit: int,
    by_amount: bool,
    counterparty_id: Optional[UUID],
) -> list[dict[str, Any]]:
    qty = func.sum(ClientSale.quantity)
    amount = func.sum(ClientSale.quantity * ClientSale.price)
    stmt = (
        select(ClientSale.article, qty.label("quantity"), amount.label("amount"))
        .where(ClientSale.period_year == year, ClientSale.period_month.in_(months_in_quarter(quarter)))
        .group_by(ClientSale.article)
        .order_by((amount if by_amount else qty).desc())
        .limit(limit)
    )
    if counterparty_id:
        stmt = stmt.where(ClientSale.head_counterparty_id == counterparty_id)
    elif allowed is not None:
        stmt = stmt.where(ClientSale.head_counterparty_id.in_(allowed or {UUID(int=0)}))
    return [
        {"article": row.article, "quantity": _num(row.quantity), "amount": _num(row.amount)}
        for row in db.execute(stmt).all()
    ]


def _top_articles_shipments(
    db: Session,
    *,
    allowed: Optional[set[UUID]],
    year: int,
    quarter: int,
    limit: int,
    by_amount: bool,
    counterparty_id: Optional[UUID],
) -> list[dict[str, Any]]:
    start, end = quarter_bounds(year, quarter)
    qty = func.sum(Realization.quantity)
    amount = func.sum(Realization.amount)
    stmt = (
        select(
            Nomenclature.article,
            func.max(Nomenclature.name).label("name"),
            qty.label("quantity"),
            amount.label("amount"),
        )
        .join(Nomenclature, Nomenclature.id == Realization.nomenclature_id)
        .where(
            Realization.doc_date >= start,
            Realization.doc_date <= end,
            Realization.ignore_turnover.is_(False),
            Nomenclature.article.is_not(None),
        )
        .group_by(Nomenclature.article)
        .order_by((amount if by_amount else qty).desc())
        .limit(limit)
    )
    scope = _shipment_ids(db, allowed, counterparty_id)
    if scope is not None:
        stmt = stmt.where(Realization.counterparty_id.in_(scope or {UUID(int=0)}))
    return [
        {
            "article": row.article,
            "name": row.name,
            "quantity": _num(row.quantity),
            "amount": _num(row.amount),
        }
        for row in db.execute(stmt).all()
    ]


def top_counterparties(
    db: Session,
    *,
    allowed: Optional[set[UUID]],
    year: int,
    quarter: int,
    limit: int,
    metric: str,
) -> dict[str, Any]:
    if metric in {"shipment_qty", "shipment_amount"}:
        rows = _top_counterparties_shipments(
            db, allowed=allowed, year=year, quarter=quarter, limit=limit, by_amount=metric != "shipment_qty"
        )
        prev_y, prev_q = shift_quarter(year, quarter, -1)
        previous = _top_counterparties_shipments(
            db, allowed=allowed, year=prev_y, quarter=prev_q, limit=max(limit * 4, 20), by_amount=metric != "shipment_qty"
        )
        rows = attach_rank_change(rows, previous, key="counterparty")
    else:
        rows = _top_counterparties_sales(
            db, allowed=allowed, year=year, quarter=quarter, limit=limit, by_amount=metric == "sales_amount"
        )
        prev_y, prev_q = shift_quarter(year, quarter, -1)
        previous = _top_counterparties_sales(
            db, allowed=allowed, year=prev_y, quarter=prev_q, limit=max(limit * 4, 20), by_amount=metric == "sales_amount"
        )
        rows = attach_rank_change(rows, previous, key="counterparty")
    return {"period": _period_note(year, quarter, metric), "metric": metric, "rows": rows}


def _top_counterparties_sales(
    db: Session,
    *,
    allowed: Optional[set[UUID]],
    year: int,
    quarter: int,
    limit: int,
    by_amount: bool,
) -> list[dict[str, Any]]:
    qty = func.sum(ClientSale.quantity)
    amount = func.sum(ClientSale.quantity * ClientSale.price)
    stmt = (
        select(
            ClientSale.head_counterparty_id,
            Counterparty.name,
            qty.label("quantity"),
            amount.label("amount"),
        )
        .join(Counterparty, Counterparty.id == ClientSale.head_counterparty_id)
        .where(ClientSale.period_year == year, ClientSale.period_month.in_(months_in_quarter(quarter)))
        .group_by(ClientSale.head_counterparty_id, Counterparty.name)
        .order_by((amount if by_amount else qty).desc())
        .limit(limit)
    )
    if allowed is not None:
        stmt = stmt.where(ClientSale.head_counterparty_id.in_(allowed or {UUID(int=0)}))
    return [
        {"counterparty": row.name, "quantity": _num(row.quantity), "amount": _num(row.amount)}
        for row in db.execute(stmt).all()
    ]


def _top_counterparties_shipments(
    db: Session,
    *,
    allowed: Optional[set[UUID]],
    year: int,
    quarter: int,
    limit: int,
    by_amount: bool,
) -> list[dict[str, Any]]:
    facts = list_fact_shipments(db, year=year, quarter=quarter, allowed_ids=allowed)
    facts = sorted(facts, key=lambda item: item.fact_amount, reverse=True)[:limit]
    if not by_amount:
        facts = facts[:limit]
    return [
        {"counterparty": item.counterparty, "amount": _num(item.fact_amount)}
        for item in facts
    ]


def top_managers(
    db: Session,
    *,
    allowed: Optional[set[UUID]],
    year: int,
    quarter: int,
    limit: int,
) -> dict[str, Any]:
    qty = func.sum(ClientSale.quantity)
    amount = func.sum(ClientSale.quantity * ClientSale.price)
    stmt = (
        select(
            Counterparty.manager_id,
            User.full_name,
            User.email,
            qty.label("quantity"),
            amount.label("amount"),
        )
        .join(Counterparty, Counterparty.id == ClientSale.head_counterparty_id)
        .join(User, User.id == Counterparty.manager_id)
        .where(
            ClientSale.period_year == year,
            ClientSale.period_month.in_(months_in_quarter(quarter)),
            Counterparty.manager_id.is_not(None),
        )
        .group_by(Counterparty.manager_id, User.full_name, User.email)
        .order_by(qty.desc())
        .limit(limit)
    )
    if allowed is not None:
        stmt = stmt.where(ClientSale.head_counterparty_id.in_(allowed or {UUID(int=0)}))
    rows = [
        {
            "manager": row.full_name or row.email,
            "quantity": _num(row.quantity),
            "amount": _num(row.amount),
        }
        for row in db.execute(stmt).all()
    ]
    return {"period": _period_note(year, quarter, "sales_qty"), "rows": rows}


def lagging_plan(
    db: Session,
    *,
    allowed: Optional[set[UUID]],
    year: int,
    quarter: int,
    limit: int,
) -> dict[str, Any]:
    report = build_quarterly_plans_report(db, year=year, quarter=quarter, allowed_ids=allowed)
    ranked = sorted(report.clients, key=lambda row: float(row.percent or 0))[:limit]
    return {
        "period": _period_note(year, quarter),
        "rows": [
            {
                "counterparty": row.counterparty,
                "plan": _num(row.plan),
                "fact": _num(row.fact),
                "percent": _num(row.percent),
            }
            for row in ranked
        ],
    }


def search_counterparties(db: Session, user: User, *, q: str) -> dict[str, Any]:
    text = q.strip()
    stmt = apply_counterparty_scope(
        select(Counterparty).where(Counterparty.is_folder.is_(False)),
        user,
    )
    if text:
        stmt = stmt.where(Counterparty.name.ilike(f"%{text}%"))
    rows = list(db.scalars(stmt.order_by(Counterparty.name).limit(8)).all())
    mgr_ids = {row.manager_id for row in rows if row.manager_id}
    managers = {
        item.id: (item.full_name or item.email)
        for item in db.scalars(select(User).where(User.id.in_(mgr_ids))).all()
    } if mgr_ids else {}
    return {
        "rows": [
            {
                "name": row.name,
                "promo": bool(row.is_promo),
                "manager": managers.get(row.manager_id) if row.manager_id else None,
                "source_id": row.source_id,
            }
            for row in rows
        ]
    }


def recommendations_digest(
    db: Session,
    *,
    allowed: Optional[set[UUID]],
    counterparty_id: Optional[UUID],
) -> dict[str, Any]:
    report = generate_recommendations(db, counterparty_id=counterparty_id, allowed_ids=allowed)
    items = []
    for item in report.items[:8]:
        items.append(
            {
                "type": item.type,
                "counterparty": item.counterparty,
                "article": item.article,
                "title": item.title,
                "message": item.message,
            }
        )
    return {"count": len(report.items), "rows": items}


def motivation_digest(
    db: Session,
    *,
    allowed: Optional[set[UUID]],
    year: int,
    month: int,
    counterparty_id: Optional[UUID],
) -> dict[str, Any]:
    report = build_motivation_report(
        db,
        year=year,
        month=month,
        counterparty_id=counterparty_id,
        allowed_ids=allowed,
        include_detail=bool(counterparty_id),
    )
    clients = [
        {"counterparty": row.counterparty, "bonus": _num(row.total_bonus), "quantity": _num(row.quantity)}
        for row in (report.clients or [])[:8]
    ]
    payload: dict[str, Any] = {
        "period": f"{year}-{month:02d}",
        "total_bonus": _num(report.total_bonus),
        "clients": clients,
    }
    if report.items:
        payload["items"] = [
            {"article": item.article, "quantity": _num(item.quantity), "bonus": _num(item.total_bonus)}
            for item in report.items[:12]
        ]
    return payload


def fact_digest(
    db: Session,
    *,
    allowed: Optional[set[UUID]],
    year: int,
    quarter: int,
    counterparty_id: Optional[UUID],
) -> dict[str, Any]:
    if counterparty_id:
        item = compute_fact_shipments(db, counterparty_id=counterparty_id, year=year, quarter=quarter)
        rows = [{"counterparty": item.counterparty, "amount": _num(item.fact_amount)}]
    else:
        listed = sorted(
            list_fact_shipments(db, year=year, quarter=quarter, allowed_ids=allowed),
            key=lambda row: row.fact_amount,
            reverse=True,
        )[:8]
        rows = [{"counterparty": row.counterparty, "amount": _num(row.fact_amount)} for row in listed]
    return {"period": _period_note(year, quarter, "shipment_amount"), "rows": rows}


def documents_digest(
    db: Session,
    user: User,
    *,
    kind: str,
    year: int,
    quarter: int,
    counterparty_id: Optional[UUID],
    q: str,
    limit: int,
) -> dict[str, Any]:
    start, end = quarter_bounds(year, quarter)
    model = ClientOrder if kind == "order" else Realization
    qty_col = model.quantity
    amount_col = model.amount
    stmt = (
        select(
            model.source_id,
            model.onec_ref,
            func.min(model.doc_date).label("doc_date"),
            func.max(getattr(model, "doc_number", model.onec_ref)).label("doc_number"),
            func.count().label("lines"),
            func.coalesce(func.sum(qty_col), 0).label("quantity"),
            func.sum(amount_col).label("amount"),
            model.counterparty_id,
        )
        .where(model.doc_date >= start, model.doc_date <= end)
        .group_by(model.source_id, model.onec_ref, model.counterparty_id)
        .order_by(func.min(model.doc_date).desc())
        .limit(max(limit, 8))
    )
    allowed = _allowed_ids(db, user)
    if counterparty_id:
        tree = counterparty_tree_ids(db, counterparty_id)
        stmt = stmt.where(model.counterparty_id.in_(tree))
    elif allowed is not None:
        stmt = stmt.where(model.counterparty_id.in_(allowed or {UUID(int=0)}))
    if q.strip() and hasattr(model, "doc_number"):
        stmt = stmt.where(
            or_(model.doc_number.ilike(f"%{q.strip()}%"), model.onec_ref.ilike(f"%{q.strip()}%"))
        )
    rows = db.execute(stmt).all()
    cp_ids = {row.counterparty_id for row in rows if row.counterparty_id}
    names = {
        item.id: item.name
        for item in db.scalars(select(Counterparty).where(Counterparty.id.in_(cp_ids))).all()
    } if cp_ids else {}
    return {
        "period": _period_note(year, quarter),
        "rows": [
            {
                "date": row.doc_date.isoformat() if row.doc_date else None,
                "number": row.doc_number,
                "counterparty": names.get(row.counterparty_id),
                "quantity": _num(row.quantity),
                "amount": _num(row.amount) if row.amount is not None else None,
                "lines": int(row.lines),
            }
            for row in rows
        ],
    }


def nomenclature_digest(db: Session, *, q: str) -> dict[str, Any]:
    text = q.strip()
    if not text:
        return {"rows": []}
    found = find_nomenclature_by_article(db, text)
    items = [found] if found else list(
        db.scalars(
            select(Nomenclature)
            .where(
                or_(
                    Nomenclature.article.ilike(f"%{text}%"),
                    Nomenclature.name.ilike(f"%{text}%"),
                    Nomenclature.barcode.ilike(f"%{text}%"),
                )
            )
            .limit(8)
        ).all()
    )
    return {
        "rows": [
            {
                "article": item.article,
                "name": item.name,
                "wear_type": item.wear_type,
                "lts": item.lts,
                "source_id": item.source_id,
            }
            for item in items
            if item is not None
        ]
    }


def quarterly_digest(
    db: Session,
    *,
    allowed: Optional[set[UUID]],
    year: int,
    quarter: int,
    counterparty_id: Optional[UUID],
    limit: int,
) -> dict[str, Any]:
    report = build_quarterly_plans_report(db, year=year, quarter=quarter, allowed_ids=allowed)
    clients = report.clients
    if counterparty_id:
        clients = [row for row in clients if row.counterparty_id == counterparty_id]
    clients = clients[: max(limit, 8)]
    return {
        "period": _period_note(year, quarter),
        "rows": [
            {
                "counterparty": row.counterparty,
                "plan": _num(row.plan),
                "fact": _num(row.fact),
                "percent": _num(row.percent),
            }
            for row in clients
        ],
    }
