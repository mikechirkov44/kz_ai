"""Manual counterparty removal from the service catalog."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    ClientOrder,
    ClientSale,
    ClientStock,
    Counterparty,
    PromoMotivation,
    QuarterlyComment,
    QuarterlyPlan,
    Realization,
    ReturnDoc,
)


class CounterpartyDeleteError(ValueError):
    """Raised when the counterparty cannot be removed."""


def _count(db: Session, stmt) -> int:
    return int(db.scalar(stmt) or 0)


def counterparty_usage(db: Session, counterparty_id: UUID) -> dict[str, int]:
    """How many linked rows block deletion."""
    return {
        "realizations": _count(
            db, select(func.count()).select_from(Realization).where(Realization.counterparty_id == counterparty_id)
        ),
        "returns": _count(
            db, select(func.count()).select_from(ReturnDoc).where(ReturnDoc.counterparty_id == counterparty_id)
        ),
        "orders": _count(
            db, select(func.count()).select_from(ClientOrder).where(ClientOrder.counterparty_id == counterparty_id)
        ),
        "sales": _count(
            db, select(func.count()).select_from(ClientSale).where(ClientSale.head_counterparty_id == counterparty_id)
        ),
        "stocks": _count(
            db, select(func.count()).select_from(ClientStock).where(ClientStock.head_counterparty_id == counterparty_id)
        ),
        "promo": _count(
            db,
            select(func.count()).select_from(PromoMotivation).where(PromoMotivation.counterparty_id == counterparty_id),
        ),
        "plans": _count(
            db, select(func.count()).select_from(QuarterlyPlan).where(QuarterlyPlan.counterparty_id == counterparty_id)
        ),
        "comments": _count(
            db,
            select(func.count())
            .select_from(QuarterlyComment)
            .where(QuarterlyComment.counterparty_id == counterparty_id),
        ),
        "subordinates": _count(
            db,
            select(func.count())
            .select_from(Counterparty)
            .where(Counterparty.head_counterparty_id == counterparty_id),
        ),
    }


def delete_counterparty(db: Session, counterparty_id: UUID) -> dict[str, str]:
    """Delete a catalog row when nothing references it."""
    row = db.get(Counterparty, counterparty_id)
    if not row:
        raise CounterpartyDeleteError("Контрагент не найден")
    usage = counterparty_usage(db, counterparty_id)
    blocking = {key: value for key, value in usage.items() if value}
    if blocking:
        parts = ", ".join(f"{key}={value}" for key, value in blocking.items())
        raise CounterpartyDeleteError(
            "Нельзя удалить: есть связанные данные ("
            f"{parts}). Сначала уберите реализации, загрузки, планы или подчинённых."
        )
    payload = {
        "id": str(row.id),
        "source_id": row.source_id,
        "name": row.name or "",
        "onec_ref": row.onec_ref or "",
        "code": row.code or "",
    }
    db.delete(row)
    db.flush()
    return payload
