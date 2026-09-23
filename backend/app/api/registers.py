"""Registers of uploaded sales, stocks and extra motivation."""

from __future__ import annotations

from decimal import Decimal
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.constants import UserRole
from app.db import get_db
from app.deps import require_roles, write_audit
from app.models import User
from app.services.registers import (
    apply_register_edit,
    export_register,
    get_register_row,
    list_register,
    register_model,
)

router = APIRouter(prefix="/api/v1/registers", tags=["registers"])

_VIEW = (UserRole.ADMIN, UserRole.MANAGER, UserRole.ANALYTIC, UserRole.REGIONAL_DIRECTOR)
_EDIT = (UserRole.ADMIN, UserRole.MANAGER, UserRole.ANALYTIC)


class RegisterEdit(BaseModel):
    article: Optional[str] = None
    quantity: Optional[Decimal] = None
    shop: Optional[str] = None


def _kind_or_404(kind: str):
    try:
        register_model(kind)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{kind}.xlsx")
def download_register(
    kind: str,
    q: Optional[str] = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*_VIEW)),
) -> Response:
    _kind_or_404(kind)
    content, filename = export_register(db, kind, user, q=q)
    write_audit(db, user_id=user.id, action="export_register", details={"kind": kind})
    db.commit()
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{kind}")
def list_rows(
    kind: str,
    q: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*_VIEW)),
) -> dict:
    _kind_or_404(kind)
    return list_register(db, kind, user, q=q, page=page, page_size=page_size)


@router.patch("/{kind}/{row_id}")
def edit_row(
    kind: str,
    row_id: UUID,
    payload: RegisterEdit,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*_EDIT)),
) -> dict:
    _kind_or_404(kind)
    row = get_register_row(db, kind, row_id, user)
    if not row:
        raise HTTPException(status_code=404, detail="Строка не найдена")
    try:
        fields = payload.model_fields_set
        apply_register_edit(
            db,
            row,
            article=payload.article,
            quantity=payload.quantity,
            shop=payload.shop,
            shop_set="shop" in fields,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    write_audit(db, user_id=user.id, action="edit_register_row", entity_id=str(row_id), details={"kind": kind})
    db.commit()
    db.refresh(row)
    return {"id": str(row.id), "article": row.article, "quantity": float(row.quantity), "shop": row.shop}


@router.delete("/{kind}/{row_id}")
def delete_row(
    kind: str,
    row_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*_EDIT)),
) -> dict:
    _kind_or_404(kind)
    row = get_register_row(db, kind, row_id, user)
    if not row:
        raise HTTPException(status_code=404, detail="Строка не найдена")
    db.delete(row)
    write_audit(db, user_id=user.id, action="delete_register_row", entity_id=str(row_id), details={"kind": kind})
    db.commit()
    return {"deleted": True}
