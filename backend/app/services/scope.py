from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.sql import false

from app.constants import UserRole
from app.domain.managers import counterparty_belongs_to_manager, user_manager_name
from app.models import Counterparty, User


def is_scoped_manager(user: User) -> bool:
    return user.role == UserRole.MANAGER.value


def is_scoped_regional(user: User) -> bool:
    return user.role == UserRole.REGIONAL_DIRECTOR.value and bool((user.region or "").strip())


def effective_manager_id(user: User, requested: Optional[UUID] = None) -> Optional[UUID]:
    """Managers are locked to themselves; others may filter by manager user id."""
    if is_scoped_manager(user):
        return user.id
    return requested


def _ids_for_manager_user(db: Session, manager: User) -> set[UUID]:
    label = user_manager_name(manager)
    rows = db.scalars(select(Counterparty)).all()
    if not label:
        return {row.id for row in rows if row.manager_id == manager.id}
    return {row.id for row in rows if counterparty_belongs_to_manager(row, manager)}


def visible_counterparty_ids(db: Session, user: User) -> Optional[set[UUID]]:
    """None = all counterparties. Empty set = none assigned."""
    if is_scoped_manager(user):
        return _ids_for_manager_user(db, user)
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
        mgr = db.get(User, mid)
        managed = _ids_for_manager_user(db, mgr) if mgr else set()
        if base is None:
            return managed
        return base & managed
    return base


def apply_counterparty_scope(stmt, db: Session, user: User, *, manager_id: Optional[UUID] = None):
    """Apply manager / region filter to a query that already selects Counterparty."""
    allowed = resolve_allowed_counterparties(db, user, manager_id=manager_id)
    if allowed is None:
        return stmt
    if not allowed:
        return stmt.where(false())
    return stmt.where(Counterparty.id.in_(allowed))


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
    if is_scoped_manager(user) and not counterparty_belongs_to_manager(cp, user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Нет доступа к этому контрагенту")
    if is_scoped_regional(user):
        region = (user.region or "").strip()
        if (cp.region or "").strip() != region:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Нет доступа к этому контрагенту")
    return cp
