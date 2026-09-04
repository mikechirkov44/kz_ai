from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.config import settings
from app.constants import UserRole
from app.db import get_db
from app.deps import require_roles, write_audit
from app.models import Counterparty, SyncState, User
from app.odata.client import ODataClient, configured_sources
from app.schemas import CounterpartyPromoBulk, CounterpartyPromoUpdate, HealthResponse, SyncStateOut
from app.services.counterparty_utils import mark_counterparty_promo, mark_counterparties_promo
from app.services.sync import sync_all_enabled, sync_catalogs_only

router = APIRouter(prefix="/api/v1", tags=["admin"])


@router.get("/health", response_model=HealthResponse)
def health(db: Session = Depends(get_db)) -> HealthResponse:
    db_status = "ok"
    try:
        db.execute(text("SELECT 1"))
    except Exception:  # noqa: BLE001
        db_status = "error"

    redis_status = "ok"
    try:
        import redis

        r = redis.from_url(settings.redis_url)
        r.ping()
    except Exception:  # noqa: BLE001
        redis_status = "error"

    odata_status: dict[str, str] = {}
    for source in configured_sources():
        if not source.username:
            odata_status[source.source_id] = "unconfigured"
            continue
        with ODataClient(source) as client:
            odata_status[source.source_id] = client.health()

    status = "ok" if db_status == "ok" else "degraded"
    return HealthResponse(status=status, database=db_status, redis=redis_status, odata=odata_status)


@router.get("/sync/status", response_model=list[SyncStateOut])
def sync_status(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(UserRole.ADMIN)),
) -> list[SyncState]:
    return list(db.scalars(select(SyncState)).all())


@router.post("/sync/run")
def sync_run(
    full: bool = False,
    catalogs_only: bool = False,
    source_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(UserRole.ADMIN)),
) -> dict:
    if catalogs_only:
        result = {}
        for source in configured_sources():
            if not source.username:
                result[source.source_id] = {"skipped": "no credentials"}
                continue
            if source_id and source.source_id != source_id:
                continue
            result[source.source_id] = sync_catalogs_only(db, source)
        return result
    return sync_all_enabled(db, full=full, source_id=source_id)


@router.get("/counterparties")
def list_counterparties(
    promo_only: bool = False,
    source_id: Optional[str] = None,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(UserRole.ADMIN, UserRole.MANAGER, UserRole.ANALYTIC, UserRole.REGIONAL_DIRECTOR)),
) -> list[dict]:
    q = select(Counterparty).where(Counterparty.is_folder.is_(False))
    if promo_only:
        q = q.where(Counterparty.is_promo.is_(True))
    if source_id:
        q = q.where(Counterparty.source_id == source_id)
    rows = db.scalars(q.order_by(Counterparty.name)).all()
    return [
        {
            "id": str(r.id),
            "name": r.name,
            "source_id": r.source_id,
            "is_promo": r.is_promo,
            "work_type": r.work_type,
            "work_type_percent": float(r.work_type_percent or 0),
            "shops": r.shops or [],
        }
        for r in rows
    ]


@router.patch("/counterparties/{counterparty_id}/promo")
def set_counterparty_promo(
    counterparty_id: UUID,
    payload: CounterpartyPromoUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.ADMIN, UserRole.REGIONAL_DIRECTOR, UserRole.ANALYTIC)),
) -> dict:
    cp = db.get(Counterparty, counterparty_id)
    if not cp or cp.is_folder:
        raise HTTPException(status_code=404, detail="Counterparty not found")
    mark_counterparty_promo(db, counterparty_id, is_promo=payload.is_promo)
    write_audit(
        db,
        user_id=user.id,
        action="counterparty_promo",
        details={"counterparty_id": str(counterparty_id), "is_promo": payload.is_promo},
    )
    db.commit()
    return {"id": str(counterparty_id), "is_promo": payload.is_promo}


@router.post("/counterparties/promo/bulk")
def bulk_set_counterparty_promo(
    payload: CounterpartyPromoBulk,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.ADMIN, UserRole.REGIONAL_DIRECTOR, UserRole.ANALYTIC)),
) -> dict:
    updated = mark_counterparties_promo(db, set(payload.counterparty_ids), is_promo=payload.is_promo)
    write_audit(
        db,
        user_id=user.id,
        action="counterparty_promo_bulk",
        details={"count": updated, "is_promo": payload.is_promo},
    )
    db.commit()
    return {"updated": updated, "is_promo": payload.is_promo}
