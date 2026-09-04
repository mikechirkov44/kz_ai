"""Counterparty helpers: head resolution, promo flag."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
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


def counterparty_tree_ids(db: Session, root_id: UUID) -> set[UUID]:
    """Head + shops that point to this head."""
    ids = {root_id}
    ids.update(db.scalars(select(Counterparty.id).where(Counterparty.head_counterparty_id == root_id)).all())
    return ids


def map_shops_to_promo_heads(db: Session, promo_ids: set[UUID]) -> dict[UUID, UUID]:
    """Map document counterparty id to promo head (self or parent)."""
    mapping = {pid: pid for pid in promo_ids}
    if not promo_ids:
        return mapping
    for cid, head_id in db.execute(
        select(Counterparty.id, Counterparty.head_counterparty_id).where(
            Counterparty.head_counterparty_id.in_(promo_ids)
        )
    ):
        if head_id:
            mapping[cid] = head_id
    return mapping


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
