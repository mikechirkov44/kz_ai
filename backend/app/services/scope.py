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


def effective_manager_id(user: User, requested: Optional[UUID] = None) -> Optional[UUID]:
    """Managers are locked to themselves; others may filter by manager_id."""
    if is_scoped_manager(user):
        return user.id
    return requested


def visible_counterparty_ids(db: Session, user: User) -> Optional[set[UUID]]:
    """None = all counterparties. Empty set = none assigned."""
    if not is_scoped_manager(user):
        return None
    rows = db.scalars(select(Counterparty.id).where(Counterparty.manager_id == user.id)).all()
    return set(rows)


def apply_counterparty_scope(stmt, user: User, *, manager_id: Optional[UUID] = None):
    """Apply manager filter to a query that already selects Counterparty."""
    scoped = effective_manager_id(user, manager_id)
    if scoped:
        return stmt.where(Counterparty.manager_id == scoped)
    return stmt


def constrain_counterparty_column(
    stmt,
    column,
    db: Session,
    user: User,
    *,
    counterparty_id: Optional[UUID] = None,
):
    """Restrict a document/report query by Counterparty.manager_id for managers."""
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
    return cp
