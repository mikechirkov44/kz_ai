from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.sql import false

from app.constants import UserRole
from app.models import Counterparty, User


def is_scoped_manager(user: User) -> bool:
    return user.role == UserRole.MANAGER.value


def is_scoped_regional(user: User) -> bool:
    return user.role == UserRole.REGIONAL_DIRECTOR.value and bool((user.region or "").strip())


def effective_manager_id(user: User, requested: Optional[UUID] = None) -> Optional[UUID]:
    """Managers are locked to themselves; others may filter by manager_id."""
    if is_scoped_manager(user):
        return user.id
    return requested


def visible_counterparty_ids(db: Session, user: User) -> Optional[set[UUID]]:
    """None = all counterparties. Empty set = none assigned."""
    if is_scoped_manager(user):
        rows = db.scalars(select(Counterparty.id).where(Counterparty.manager_id == user.id)).all()
        return set(rows)
    if is_scoped_regional(user):
        region = (user.region or "").strip()
        rows = db.scalars(
            select(Counterparty.id).where(
                Counterparty.is_folder.is_(False),
                Counterparty.region == region,
            )
        ).all()
        return set(rows)
    return None


def resolve_allowed_counterparties(
    db: Session,
    user: User,
    *,
    manager_id: Optional[UUID] = None,
) -> Optional[set[UUID]]:
    """None = unrestricted. Empty set = nothing visible."""
    base = visible_counterparty_ids(db, user)
    mid = effective_manager_id(user, manager_id)
    if mid:
        managed = set(db.scalars(select(Counterparty.id).where(Counterparty.manager_id == mid)).all())
        if base is None:
            return managed
        return base & managed
    return base


def apply_counterparty_scope(stmt, user: User, *, manager_id: Optional[UUID] = None):
    """Apply manager / region filter to a query that already selects Counterparty."""
    scoped = effective_manager_id(user, manager_id)
    if scoped:
        return stmt.where(Counterparty.manager_id == scoped)
    if is_scoped_regional(user):
        return stmt.where(Counterparty.region == (user.region or "").strip())
    return stmt


def apply_allowed_ids(stmt, allowed_ids: Optional[set[UUID]], *, id_column=Counterparty.id):
    """Restrict query by resolved counterparty id set. None = no extra filter."""
    if allowed_ids is None:
        return stmt
    if not allowed_ids:
        return stmt.where(false())
    return stmt.where(id_column.in_(allowed_ids))


def constrain_counterparty_column(
    stmt,
    column,
    db: Session,
    user: User,
    *,
    counterparty_id: Optional[UUID] = None,
):
    """Restrict a document/report query by visible counterparties."""
    allowed = visible_counterparty_ids(db, user)
    if counterparty_id:
        if allowed is not None and counterparty_id not in allowed:
            return stmt.where(false())
        return stmt.where(column == counterparty_id)
    if allowed is not None:
        if not allowed:
            return stmt.where(false())
        return stmt.where(column.in_(allowed))
    return stmt


def assert_counterparty_access(db: Session, user: User, counterparty_id: UUID) -> Counterparty:
    cp = db.get(Counterparty, counterparty_id)
    if not cp or cp.is_folder:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Counterparty not found")
    if is_scoped_manager(user) and cp.manager_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Нет доступа к этому контрагенту")
    if is_scoped_regional(user):
        region = (user.region or "").strip()
        if (cp.region or "").strip() != region:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Нет доступа к этому контрагенту")
    return cp
