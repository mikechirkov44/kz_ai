"""Document journals: realizations, returns, client orders, production."""

from __future__ import annotations

from datetime import date
from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.constants import UserRole
from app.db import get_db
from app.deps import require_roles
from app.models import ClientOrder, Counterparty, Nomenclature, ProductionReceipt, Realization, ReturnDoc, User

router = APIRouter(prefix="/api/v1/documents", tags=["documents"])


def _page_params(page: int, page_size: int) -> tuple[int, int]:
    return (page - 1) * page_size, page_size


@router.get("/realizations")
def list_realizations(
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    counterparty_id: Optional[UUID] = None,
    source_id: Optional[str] = None,
    doc_number: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(UserRole.ADMIN, UserRole.MANAGER, UserRole.ANALYTIC, UserRole.REGIONAL_DIRECTOR)),
) -> dict:
    # Aggregate by document (source_id + onec_ref)
    stmt = (
        select(
            Realization.source_id,
            Realization.onec_ref,
            Realization.doc_number,
            func.min(Realization.doc_date).label("doc_date"),
            Realization.counterparty_id,
            func.count().label("lines"),
            func.coalesce(func.sum(Realization.quantity), 0).label("quantity"),
            func.coalesce(func.sum(Realization.amount), 0).label("amount"),
            func.max(Realization.warehouse).label("warehouse"),
        )
        .group_by(
            Realization.source_id,
            Realization.onec_ref,
            Realization.doc_number,
            Realization.counterparty_id,
        )
    )
    if date_from:
        stmt = stmt.where(Realization.doc_date >= date_from)
    if date_to:
        stmt = stmt.where(Realization.doc_date <= date_to)
    if counterparty_id:
        stmt = stmt.where(Realization.counterparty_id == counterparty_id)
    if source_id:
        stmt = stmt.where(Realization.source_id == source_id)
    if doc_number:
        stmt = stmt.where(Realization.doc_number.ilike(f"%{doc_number.strip()}%"))

    sub = stmt.subquery()
    total = db.scalar(select(func.count()).select_from(sub)) or 0
    offset, limit = _page_params(page, page_size)
    rows = db.execute(
        select(sub).order_by(sub.c.doc_date.desc(), sub.c.onec_ref).offset(offset).limit(limit)
    ).all()

    cp_ids = {r.counterparty_id for r in rows if r.counterparty_id}
    cps = {c.id: c.name for c in db.scalars(select(Counterparty).where(Counterparty.id.in_(cp_ids))).all()} if cp_ids else {}

    items = [
        {
            "source_id": r.source_id,
            "onec_ref": r.onec_ref,
            "doc_number": r.doc_number,
            "doc_date": r.doc_date.isoformat() if r.doc_date else None,
            "counterparty_id": str(r.counterparty_id) if r.counterparty_id else None,
            "counterparty": cps.get(r.counterparty_id),
            "lines": r.lines,
            "quantity": float(r.quantity),
            "amount": float(r.amount),
            "warehouse": r.warehouse,
        }
        for r in rows
    ]
    return {"total": total, "page": page, "page_size": page_size, "items": items}


@router.get("/realizations/{source_id}/{onec_ref}")
def realization_detail(
    source_id: str,
    onec_ref: str,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(UserRole.ADMIN, UserRole.MANAGER, UserRole.ANALYTIC, UserRole.REGIONAL_DIRECTOR)),
) -> dict:
    lines = db.scalars(
        select(Realization)
        .where(Realization.source_id == source_id, Realization.onec_ref == onec_ref)
        .order_by(Realization.line_number)
    ).all()
    if not lines:
        raise HTTPException(status_code=404, detail="Document not found")
    return _doc_detail_realization(db, lines)


def _doc_detail_realization(db: Session, lines: list[Realization]) -> dict:
    first = lines[0]
    cp = db.get(Counterparty, first.counterparty_id) if first.counterparty_id else None
    nom_ids = {x.nomenclature_id for x in lines if x.nomenclature_id}
    noms = {
        n.id: n
        for n in db.scalars(select(Nomenclature).where(Nomenclature.id.in_(nom_ids))).all()
    } if nom_ids else {}
    return {
        "type": "realization",
        "source_id": first.source_id,
        "onec_ref": first.onec_ref,
        "doc_number": first.doc_number,
        "doc_date": first.doc_date.isoformat(),
        "counterparty": cp.name if cp else None,
        "counterparty_id": str(first.counterparty_id) if first.counterparty_id else None,
        "warehouse": first.warehouse,
        "lines": [
            {
                "line_number": x.line_number,
                "article": noms[x.nomenclature_id].article if x.nomenclature_id in noms else None,
                "name": noms[x.nomenclature_id].name if x.nomenclature_id in noms else None,
                "nomenclature_id": str(x.nomenclature_id) if x.nomenclature_id else None,
                "quantity": float(x.quantity),
                "price": float(x.price),
                "amount": float(x.amount),
                "series": x.series,
                "warehouse": x.warehouse,
            }
            for x in lines
        ],
        "total_amount": float(sum((x.amount or 0) for x in lines)),
        "total_quantity": float(sum((x.quantity or 0) for x in lines)),
    }


@router.get("/returns")
def list_returns(
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    counterparty_id: Optional[UUID] = None,
    source_id: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(UserRole.ADMIN, UserRole.MANAGER, UserRole.ANALYTIC, UserRole.REGIONAL_DIRECTOR)),
) -> dict:
    stmt = (
        select(
            ReturnDoc.source_id,
            ReturnDoc.onec_ref,
            ReturnDoc.doc_number,
            func.min(ReturnDoc.doc_date).label("doc_date"),
            ReturnDoc.counterparty_id,
            func.count().label("lines"),
            func.coalesce(func.sum(ReturnDoc.quantity), 0).label("quantity"),
            func.coalesce(func.sum(ReturnDoc.amount), 0).label("amount"),
        )
        .group_by(ReturnDoc.source_id, ReturnDoc.onec_ref, ReturnDoc.doc_number, ReturnDoc.counterparty_id)
    )
    if date_from:
        stmt = stmt.where(ReturnDoc.doc_date >= date_from)
    if date_to:
        stmt = stmt.where(ReturnDoc.doc_date <= date_to)
    if counterparty_id:
        stmt = stmt.where(ReturnDoc.counterparty_id == counterparty_id)
    if source_id:
        stmt = stmt.where(ReturnDoc.source_id == source_id)
    sub = stmt.subquery()
    total = db.scalar(select(func.count()).select_from(sub)) or 0
    offset, limit = _page_params(page, page_size)
    rows = db.execute(select(sub).order_by(sub.c.doc_date.desc()).offset(offset).limit(limit)).all()
    cp_ids = {r.counterparty_id for r in rows if r.counterparty_id}
    cps = {c.id: c.name for c in db.scalars(select(Counterparty).where(Counterparty.id.in_(cp_ids))).all()} if cp_ids else {}
    items = [
        {
            "source_id": r.source_id,
            "onec_ref": r.onec_ref,
            "doc_number": r.doc_number,
            "doc_date": r.doc_date.isoformat() if r.doc_date else None,
            "counterparty_id": str(r.counterparty_id) if r.counterparty_id else None,
            "counterparty": cps.get(r.counterparty_id),
            "lines": r.lines,
            "quantity": float(r.quantity),
            "amount": float(r.amount),
        }
        for r in rows
    ]
    return {"total": total, "page": page, "page_size": page_size, "items": items}


@router.get("/returns/{source_id}/{onec_ref}")
def return_detail(
    source_id: str,
    onec_ref: str,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(UserRole.ADMIN, UserRole.MANAGER, UserRole.ANALYTIC, UserRole.REGIONAL_DIRECTOR)),
) -> dict:
    lines = db.scalars(
        select(ReturnDoc)
        .where(ReturnDoc.source_id == source_id, ReturnDoc.onec_ref == onec_ref)
        .order_by(ReturnDoc.line_number)
    ).all()
    if not lines:
        raise HTTPException(status_code=404, detail="Document not found")
    first = lines[0]
    cp = db.get(Counterparty, first.counterparty_id) if first.counterparty_id else None
    nom_ids = {x.nomenclature_id for x in lines if x.nomenclature_id}
    noms = {
        n.id: n for n in db.scalars(select(Nomenclature).where(Nomenclature.id.in_(nom_ids))).all()
    } if nom_ids else {}
    return {
        "type": "return",
        "source_id": first.source_id,
        "onec_ref": first.onec_ref,
        "doc_number": first.doc_number,
        "doc_date": first.doc_date.isoformat(),
        "counterparty": cp.name if cp else None,
        "lines": [
            {
                "line_number": x.line_number,
                "article": noms[x.nomenclature_id].article if x.nomenclature_id in noms else None,
                "name": noms[x.nomenclature_id].name if x.nomenclature_id in noms else None,
                "quantity": float(x.quantity),
                "price": float(x.price),
                "amount": float(x.amount),
            }
            for x in lines
        ],
        "total_amount": float(sum((x.amount or 0) for x in lines)),
    }


@router.get("/orders/{source_id}/{onec_ref}")
def order_detail(
    source_id: str,
    onec_ref: str,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(UserRole.ADMIN, UserRole.MANAGER, UserRole.ANALYTIC, UserRole.REGIONAL_DIRECTOR)),
) -> dict:
    lines = db.scalars(
        select(ClientOrder)
        .where(ClientOrder.source_id == source_id, ClientOrder.onec_ref == onec_ref)
        .order_by(ClientOrder.line_number)
    ).all()
    if not lines:
        raise HTTPException(status_code=404, detail="Document not found")
    first = lines[0]
    cp = db.get(Counterparty, first.counterparty_id) if first.counterparty_id else None
    nom_ids = {x.nomenclature_id for x in lines if x.nomenclature_id}
    noms = {
        n.id: n for n in db.scalars(select(Nomenclature).where(Nomenclature.id.in_(nom_ids))).all()
    } if nom_ids else {}
    return {
        "type": "order",
        "source_id": first.source_id,
        "onec_ref": first.onec_ref,
        "doc_date": first.doc_date.isoformat(),
        "counterparty": cp.name if cp else None,
        "target_warehouse": first.target_warehouse,
        "lines": [
            {
                "line_number": x.line_number,
                "article": noms[x.nomenclature_id].article if x.nomenclature_id in noms else None,
                "name": noms[x.nomenclature_id].name if x.nomenclature_id in noms else None,
                "quantity": float(x.quantity),
                "series": x.series,
            }
            for x in lines
        ],
        "total_quantity": float(sum((x.quantity or 0) for x in lines)),
    }


@router.get("/production/{source_id}/{onec_ref}")
def production_detail(
    source_id: str,
    onec_ref: str,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(UserRole.ADMIN, UserRole.MANAGER, UserRole.ANALYTIC, UserRole.REGIONAL_DIRECTOR)),
) -> dict:
    lines = db.scalars(
        select(ProductionReceipt)
        .where(ProductionReceipt.source_id == source_id, ProductionReceipt.onec_ref == onec_ref)
        .order_by(ProductionReceipt.line_number)
    ).all()
    if not lines:
        raise HTTPException(status_code=404, detail="Document not found")
    first = lines[0]
    nom_ids = {x.nomenclature_id for x in lines if x.nomenclature_id}
    noms = {
        n.id: n for n in db.scalars(select(Nomenclature).where(Nomenclature.id.in_(nom_ids))).all()
    } if nom_ids else {}
    return {
        "type": "production",
        "source_id": first.source_id,
        "onec_ref": first.onec_ref,
        "doc_date": first.doc_date.isoformat(),
        "doc_type": first.doc_type,
        "lines": [
            {
                "line_number": x.line_number,
                "article": noms[x.nomenclature_id].article if x.nomenclature_id in noms else None,
                "name": noms[x.nomenclature_id].name if x.nomenclature_id in noms else None,
                "series": x.series,
                "client_order_onec_ref": x.client_order_onec_ref,
            }
            for x in lines
        ],
    }


@router.get("/orders")
def list_orders(
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    source_id: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(UserRole.ADMIN, UserRole.MANAGER, UserRole.ANALYTIC, UserRole.REGIONAL_DIRECTOR)),
) -> dict:
    stmt = (
        select(
            ClientOrder.source_id,
            ClientOrder.onec_ref,
            func.min(ClientOrder.doc_date).label("doc_date"),
            ClientOrder.counterparty_id,
            func.count().label("lines"),
            func.coalesce(func.sum(ClientOrder.quantity), 0).label("quantity"),
            func.max(ClientOrder.target_warehouse).label("target_warehouse"),
        )
        .group_by(ClientOrder.source_id, ClientOrder.onec_ref, ClientOrder.counterparty_id)
    )
    if date_from:
        stmt = stmt.where(ClientOrder.doc_date >= date_from)
    if date_to:
        stmt = stmt.where(ClientOrder.doc_date <= date_to)
    if source_id:
        stmt = stmt.where(ClientOrder.source_id == source_id)
    sub = stmt.subquery()
    total = db.scalar(select(func.count()).select_from(sub)) or 0
    offset, limit = _page_params(page, page_size)
    rows = db.execute(select(sub).order_by(sub.c.doc_date.desc()).offset(offset).limit(limit)).all()
    cp_ids = {r.counterparty_id for r in rows if r.counterparty_id}
    cps = {c.id: c.name for c in db.scalars(select(Counterparty).where(Counterparty.id.in_(cp_ids))).all()} if cp_ids else {}
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [
            {
                "source_id": r.source_id,
                "onec_ref": r.onec_ref,
                "doc_date": r.doc_date.isoformat() if r.doc_date else None,
                "counterparty": cps.get(r.counterparty_id),
                "lines": r.lines,
                "quantity": float(r.quantity),
                "target_warehouse": r.target_warehouse,
            }
            for r in rows
        ],
    }


@router.get("/production")
def list_production(
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    source_id: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(UserRole.ADMIN, UserRole.MANAGER, UserRole.ANALYTIC, UserRole.REGIONAL_DIRECTOR)),
) -> dict:
    stmt = (
        select(
            ProductionReceipt.source_id,
            ProductionReceipt.onec_ref,
            func.min(ProductionReceipt.doc_date).label("doc_date"),
            ProductionReceipt.doc_type,
            func.count().label("lines"),
        )
        .group_by(ProductionReceipt.source_id, ProductionReceipt.onec_ref, ProductionReceipt.doc_type)
    )
    if date_from:
        stmt = stmt.where(ProductionReceipt.doc_date >= date_from)
    if date_to:
        stmt = stmt.where(ProductionReceipt.doc_date <= date_to)
    if source_id:
        stmt = stmt.where(ProductionReceipt.source_id == source_id)
    sub = stmt.subquery()
    total = db.scalar(select(func.count()).select_from(sub)) or 0
    offset, limit = _page_params(page, page_size)
    rows = db.execute(select(sub).order_by(sub.c.doc_date.desc()).offset(offset).limit(limit)).all()
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [
            {
                "source_id": r.source_id,
                "onec_ref": r.onec_ref,
                "doc_date": r.doc_date.isoformat() if r.doc_date else None,
                "doc_type": r.doc_type,
                "lines": r.lines,
            }
            for r in rows
        ],
    }
