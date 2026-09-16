"""Counterparty helpers: head resolution, promo flag."""

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from typing import Iterable, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Counterparty


def counterparty_group_id(cp: Counterparty | None) -> UUID | None:
    """Head id if set, otherwise the row itself."""
    if not cp:
        return None
    return cp.head_counterparty_id or cp.id


def resolve_head_counterparty_id(db: Session, counterparty_id: UUID) -> UUID:
    """Return head counterparty id (self if already head)."""
    cp = db.get(Counterparty, counterparty_id)
    if not cp:
        return counterparty_id
    return counterparty_group_id(cp) or counterparty_id


def counterparty_tree_ids(db: Session, root_id: UUID) -> set[UUID]:
    """Head + shops that point to this head."""
    return counterparty_trees(db, [root_id]).get(root_id, {root_id})


def counterparty_trees(db: Session, root_ids: Iterable[UUID]) -> dict[UUID, set[UUID]]:
    """Head → {head + shops} for many counterparties in one query."""
    trees = {root_id: {root_id} for root_id in root_ids}
    if not trees:
        return trees
    for shop_id, head_id in db.execute(
        select(Counterparty.id, Counterparty.head_counterparty_id).where(
            Counterparty.head_counterparty_id.in_(trees.keys())
        )
    ):
        if head_id in trees:
            trees[head_id].add(shop_id)
    return trees


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


def rollup_sums_to_head(
    rows: Iterable[tuple[Optional[UUID], Decimal]],
    to_head: dict[UUID, UUID],
) -> dict[UUID, Decimal]:
    """Sum values from head and shop counterparties onto the report head."""
    totals: dict[UUID, Decimal] = defaultdict(lambda: Decimal(0))
    for cp_id, value in rows:
        if not cp_id:
            continue
        head_id = to_head.get(cp_id)
        if not head_id:
            continue
        totals[head_id] += value
    return dict(totals)


def rollup_averages_to_head(
    rows: Iterable[tuple[Optional[UUID], str, Decimal, int]],
    to_head: dict[UUID, UUID],
) -> dict[UUID, dict[str, Decimal]]:
    """Weighted average by head: shop lines are added to the parent."""
    acc: dict[tuple[UUID, str], list[Decimal | int]] = defaultdict(lambda: [Decimal(0), 0])
    for cp_id, key, total, count in rows:
        if not cp_id or not key or count <= 0:
            continue
        head_id = to_head.get(cp_id)
        if not head_id:
            continue
        slot = acc[(head_id, key)]
        slot[0] += total
        slot[1] += count
    out: dict[UUID, dict[str, Decimal]] = defaultdict(dict)
    for (head_id, key), (total, count) in acc.items():
        if count:
            out[head_id][key] = total / Decimal(count)
    return out


def group_rows_by_head(
    rows: Iterable,
    to_head: dict[UUID, UUID],
    *,
    counterparty_id_of,
) -> dict[UUID, list]:
    """Attach 1C document rows to the head used in reports."""
    grouped: dict[UUID, list] = defaultdict(list)
    for row in rows:
        cp_id = counterparty_id_of(row)
        if not cp_id:
            continue
        head_id = to_head.get(cp_id)
        if head_id:
            grouped[head_id].append(row)
    return grouped


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
