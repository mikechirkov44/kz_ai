"""Wipe synced and uploaded rows for one 1C organization."""

from __future__ import annotations

from pathlib import Path
from typing import Optional
from uuid import UUID

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from app.models import (
    ClientOrder,
    ClientSale,
    ClientStock,
    Counterparty,
    Nomenclature,
    ProductionReceipt,
    PromoMotivation,
    QuarterlyComment,
    QuarterlyPlan,
    Realization,
    ReturnDoc,
    SyncState,
    UploadLog,
)
from app.services.uploads import stored_upload_path


def remove_uploads_for_source(
    db: Session,
    source_id: str,
    *,
    user_id: Optional[UUID] = None,
    commit: bool = True,
) -> dict[str, int]:
    """Delete Excel/manual uploads tagged with this organization and their register rows."""
    stmt = select(UploadLog).where(UploadLog.source_id == source_id)
    if user_id is not None:
        stmt = stmt.where(UploadLog.user_id == user_id)
    uploads = list(db.scalars(stmt).all())
    removed_sales = 0
    removed_stocks = 0
    removed_promo = 0
    paths: list[Path] = []
    for upload in uploads:
        paths.append(stored_upload_path(upload.file_hash, upload.file_name))
        removed_sales += db.execute(delete(ClientSale).where(ClientSale.upload_id == upload.id)).rowcount or 0
        removed_stocks += db.execute(delete(ClientStock).where(ClientStock.upload_id == upload.id)).rowcount or 0
        removed_promo += (
            db.execute(delete(PromoMotivation).where(PromoMotivation.upload_id == upload.id)).rowcount or 0
        )
        db.delete(upload)
    if commit:
        db.commit()
        for path in paths:
            if path.is_file():
                path.unlink()
    return {
        "removed_uploads": len(uploads),
        "removed_sales": int(removed_sales),
        "removed_stocks": int(removed_stocks),
        "removed_promo": int(removed_promo),
    }


def clear_source_data(db: Session, source_id: str) -> dict[str, int]:
    """Remove 1C sync rows and related Excel data for one organization.

    Keeps the OData connection itself. Does not touch users or other bases.
    """
    cp_ids = list(db.scalars(select(Counterparty.id).where(Counterparty.source_id == source_id)).all())
    upload_paths: list[Path] = []
    upload_stmt = select(UploadLog).where(UploadLog.source_id == source_id)
    uploads = list(db.scalars(upload_stmt).all())
    removed_sales = 0
    removed_stocks = 0
    removed_promo = 0
    for upload in uploads:
        upload_paths.append(stored_upload_path(upload.file_hash, upload.file_name))
        removed_sales += db.execute(delete(ClientSale).where(ClientSale.upload_id == upload.id)).rowcount or 0
        removed_stocks += db.execute(delete(ClientStock).where(ClientStock.upload_id == upload.id)).rowcount or 0
        removed_promo += (
            db.execute(delete(PromoMotivation).where(PromoMotivation.upload_id == upload.id)).rowcount or 0
        )
        db.delete(upload)

    if cp_ids:
        removed_sales += (
            db.execute(delete(ClientSale).where(ClientSale.head_counterparty_id.in_(cp_ids))).rowcount or 0
        )
        removed_stocks += (
            db.execute(delete(ClientStock).where(ClientStock.head_counterparty_id.in_(cp_ids))).rowcount or 0
        )
        removed_promo += (
            db.execute(delete(PromoMotivation).where(PromoMotivation.counterparty_id.in_(cp_ids))).rowcount or 0
        )
        removed_plans = (
            db.execute(delete(QuarterlyPlan).where(QuarterlyPlan.counterparty_id.in_(cp_ids))).rowcount or 0
        )
        removed_comments = (
            db.execute(delete(QuarterlyComment).where(QuarterlyComment.counterparty_id.in_(cp_ids))).rowcount
            or 0
        )
        db.execute(
            update(Counterparty)
            .where(Counterparty.source_id == source_id)
            .values(head_counterparty_id=None)
        )
    else:
        removed_plans = 0
        removed_comments = 0

    removed_production = (
        db.execute(delete(ProductionReceipt).where(ProductionReceipt.source_id == source_id)).rowcount or 0
    )
    removed_realizations = db.execute(delete(Realization).where(Realization.source_id == source_id)).rowcount or 0
    removed_returns = db.execute(delete(ReturnDoc).where(ReturnDoc.source_id == source_id)).rowcount or 0
    removed_orders = db.execute(delete(ClientOrder).where(ClientOrder.source_id == source_id)).rowcount or 0
    removed_counterparties = (
        db.execute(delete(Counterparty).where(Counterparty.source_id == source_id)).rowcount or 0
    )
    removed_nomenclature = (
        db.execute(delete(Nomenclature).where(Nomenclature.source_id == source_id)).rowcount or 0
    )
    removed_sync_states = db.execute(delete(SyncState).where(SyncState.source_id == source_id)).rowcount or 0

    db.commit()
    for path in upload_paths:
        if path.is_file():
            path.unlink()

    return {
        "removed_uploads": len(uploads),
        "removed_sales": int(removed_sales),
        "removed_stocks": int(removed_stocks),
        "removed_promo": int(removed_promo),
        "removed_quarterly_plans": int(removed_plans),
        "removed_quarterly_comments": int(removed_comments),
        "removed_production_receipts": int(removed_production),
        "removed_realizations": int(removed_realizations),
        "removed_returns": int(removed_returns),
        "removed_orders": int(removed_orders),
        "removed_counterparties": int(removed_counterparties),
        "removed_nomenclature": int(removed_nomenclature),
        "removed_sync_states": int(removed_sync_states),
    }
