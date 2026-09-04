"""Counterparty helpers: head resolution, promo flag."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.models import Counterparty


def resolve_head_counterparty_id(db: Session, counterparty_id: UUID) -> UUID:
    """Return head counterparty id (self if already head)."""
    cp = db.get(Counterparty, counterparty_id)
    if not cp:
        return counterparty_id
    if cp.head_counterparty_id:
        return cp.head_counterparty_id
    return cp.id


def mark_counterparty_promo(db: Session, counterparty_id: UUID, *, is_promo: bool = True) -> None:
    cp = db.get(Counterparty, counterparty_id)
    if cp and cp.is_promo != is_promo:
        cp.is_promo = is_promo


def mark_counterparties_promo(db: Session, counterparty_ids: set[UUID], *, is_promo: bool = True) -> int:
    updated = 0
    for cp_id in counterparty_ids:
        cp = db.get(Counterparty, cp_id)
        if cp and cp.is_promo != is_promo:
            cp.is_promo = is_promo
            updated += 1
    return updated
