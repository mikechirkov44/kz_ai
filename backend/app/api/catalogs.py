"""Catalog browse APIs: nomenclature and counterparties."""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.config import settings
from app.constants import UserRole
from app.db import get_db
from app.deps import require_roles, write_audit
from app.models import Counterparty, Nomenclature, User
from app.services.export_xlsx import counterparties_workbook, nomenclature_workbook, workbook_bytes
from app.services.scope import apply_counterparty_scope, assert_counterparty_access

router = APIRouter(prefix="/api/v1/catalogs", tags=["catalogs"])


def _xlsx_response(content: bytes, filename: str) -> Response:
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _nom_dict(n: Nomenclature) -> dict:
    return {
        "id": str(n.id),
        "source_id": n.source_id,
        "onec_ref": n.onec_ref,
        "article": n.article,
        "barcode": n.barcode,
        "name": n.name,
        "assay": n.assay,
        "metal_color": n.metal_color,
        "wear_type": n.wear_type,
        "lts": n.lts,
        "lts_date": n.lts_date.isoformat() if n.lts_date else None,
        "direction": n.direction,
        "is_promo": n.is_promo,
        "is_weighted": n.is_weighted,
        "weight": float(n.weight) if n.weight is not None else None,
        "characteristics": n.characteristics,
    }


def _cp_dict(c: Counterparty, *, head_name: Optional[str] = None, manager_name: Optional[str] = None) -> dict:
    return {
        "id": str(c.id),
        "source_id": c.source_id,
        "onec_ref": c.onec_ref,
        "name": c.name,
        "is_promo": c.is_promo,
        "is_folder": c.is_folder,
        "work_type": c.work_type,
        "work_type_percent": float(c.work_type_percent or 0),
        "shops": c.shops or [],
        "region": c.region,
        "head_counterparty_id": str(c.head_counterparty_id) if c.head_counterparty_id else None,
        "head_name": head_name,
        "manager_id": str(c.manager_id) if c.manager_id else None,
        "manager_name": manager_name,
    }


def _manager_labels(db: Session, rows: list[Counterparty]) -> dict:
    ids = {c.manager_id for c in rows if c.manager_id}
    if not ids:
        return {}
    users = db.scalars(select(User).where(User.id.in_(ids))).all()
    return {u.id: (u.full_name or u.email) for u in users}


@router.get("/nomenclature")
def list_nomenclature(
    q: Optional[str] = None,
    source_id: Optional[str] = None,
    lts: Optional[str] = None,
    wear_type: Optional[str] = None,
    metal_color: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(UserRole.ADMIN, UserRole.MANAGER, UserRole.ANALYTIC, UserRole.REGIONAL_DIRECTOR)),
) -> dict:
    stmt = select(Nomenclature)
    if source_id:
        stmt = stmt.where(Nomenclature.source_id == source_id)
    if lts:
        stmt = stmt.where(Nomenclature.lts == lts)
    if wear_type:
        stmt = stmt.where(Nomenclature.wear_type == wear_type)
    if metal_color:
        stmt = stmt.where(Nomenclature.metal_color == metal_color)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(
                Nomenclature.article.ilike(like),
                Nomenclature.barcode.ilike(like),
                Nomenclature.name.ilike(like),
            )
        )
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(
        stmt.order_by(Nomenclature.article.nulls_last(), Nomenclature.name).offset((page - 1) * page_size).limit(page_size)
    ).all()
    return {"total": total, "page": page, "page_size": page_size, "items": [_nom_dict(n) for n in rows]}


@router.get("/nomenclature.xlsx")
def export_nomenclature(
    q: Optional[str] = None,
    source_id: Optional[str] = None,
    lts: Optional[str] = None,
    wear_type: Optional[str] = None,
    metal_color: Optional[str] = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.ADMIN, UserRole.MANAGER, UserRole.ANALYTIC, UserRole.REGIONAL_DIRECTOR)),
) -> Response:
    stmt = select(Nomenclature)
    if source_id:
        stmt = stmt.where(Nomenclature.source_id == source_id)
    if lts:
        stmt = stmt.where(Nomenclature.lts == lts)
    if wear_type:
        stmt = stmt.where(Nomenclature.wear_type == wear_type)
    if metal_color:
        stmt = stmt.where(Nomenclature.metal_color == metal_color)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(
                Nomenclature.article.ilike(like),
                Nomenclature.barcode.ilike(like),
                Nomenclature.name.ilike(like),
            )
        )
    rows = db.scalars(
        stmt.order_by(Nomenclature.article.nulls_last(), Nomenclature.name).limit(settings.export_max_rows)
    ).all()
    write_audit(db, user_id=user.id, action="export_nomenclature", details={"rows": len(rows)})
    db.commit()
    return _xlsx_response(
        workbook_bytes(nomenclature_workbook(_nom_dict(n) for n in rows)),
        "nomenclature.xlsx",
    )


@router.get("/nomenclature/{item_id}")
def get_nomenclature(
    item_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(UserRole.ADMIN, UserRole.MANAGER, UserRole.ANALYTIC, UserRole.REGIONAL_DIRECTOR)),
) -> dict:
    n = db.get(Nomenclature, item_id)
    if not n:
        raise HTTPException(status_code=404, detail="Not found")
    return _nom_dict(n)


@router.get("/counterparties")
def list_counterparties_catalog(
    q: Optional[str] = None,
    source_id: Optional[str] = None,
    promo_only: bool = False,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.ADMIN, UserRole.MANAGER, UserRole.ANALYTIC, UserRole.REGIONAL_DIRECTOR)),
) -> dict:
    stmt = select(Counterparty).where(Counterparty.is_folder.is_(False))
    stmt = apply_counterparty_scope(stmt, user)
    if source_id:
        stmt = stmt.where(Counterparty.source_id == source_id)
    if promo_only:
        stmt = stmt.where(Counterparty.is_promo.is_(True))
    if q:
        stmt = stmt.where(Counterparty.name.ilike(f"%{q.strip()}%"))
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(stmt.order_by(Counterparty.name).offset((page - 1) * page_size).limit(page_size)).all()
    labels = _manager_labels(db, rows)
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [_cp_dict(c, manager_name=labels.get(c.manager_id)) for c in rows],
    }


@router.get("/counterparties.xlsx")
def export_counterparties(
    q: Optional[str] = None,
    source_id: Optional[str] = None,
    promo_only: bool = False,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.ADMIN, UserRole.MANAGER, UserRole.ANALYTIC, UserRole.REGIONAL_DIRECTOR)),
) -> Response:
    stmt = select(Counterparty).where(Counterparty.is_folder.is_(False))
    stmt = apply_counterparty_scope(stmt, user)
    if source_id:
        stmt = stmt.where(Counterparty.source_id == source_id)
    if promo_only:
        stmt = stmt.where(Counterparty.is_promo.is_(True))
    if q:
        stmt = stmt.where(Counterparty.name.ilike(f"%{q.strip()}%"))
    rows = db.scalars(stmt.order_by(Counterparty.name).limit(settings.export_max_rows)).all()
    labels = _manager_labels(db, rows)
    write_audit(db, user_id=user.id, action="export_counterparties", details={"rows": len(rows)})
    db.commit()
    return _xlsx_response(
        workbook_bytes(
            counterparties_workbook(_cp_dict(c, manager_name=labels.get(c.manager_id)) for c in rows)
        ),
        "counterparties.xlsx",
    )


@router.get("/counterparties/{item_id}")
def get_counterparty(
    item_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.ADMIN, UserRole.MANAGER, UserRole.ANALYTIC, UserRole.REGIONAL_DIRECTOR)),
) -> dict:
    c = db.get(Counterparty, item_id)
    if not c:
        raise HTTPException(status_code=404, detail="Not found")
    assert_counterparty_access(db, user, item_id)
    head_name = None
    if c.head_counterparty_id:
        head = db.get(Counterparty, c.head_counterparty_id)
        head_name = head.name if head else None
    manager_name = None
    if c.manager_id:
        mgr = db.get(User, c.manager_id)
        manager_name = (mgr.full_name or mgr.email) if mgr else None
    return _cp_dict(c, head_name=head_name, manager_name=manager_name)
