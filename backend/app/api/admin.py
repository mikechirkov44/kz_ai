from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.config import settings
from app.constants import SOURCE_ASIL, SOURCE_MIAMOR, UserRole
from app.db import get_db
from app.deps import require_roles, write_audit
from app.models import Counterparty, SyncState, User
from app.odata.client import ODataClient, configured_sources
from app.schemas import (
    CounterpartyPromoBulk,
    CounterpartyPromoUpdate,
    DigestRunRequest,
    HealthResponse,
    ODataConnectionOut,
    ODataConnectionUpdate,
    SyncStateOut,
)
from app.services.counterparty_utils import mark_counterparties_promo, mark_counterparty_promo
from app.services.email_digest import build_digest_preview, send_weekly_digest
from app.services.odata_settings import (
    KNOWN_SOURCES,
    connection_public_view,
    ensure_odata_connections,
    get_connection_row,
    resolve_source,
    upsert_connection,
)
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
    for source_id, _ in KNOWN_SOURCES:
        src = resolve_source(db, source_id)
        if not src or not src.username:
            odata_status[source_id] = "unconfigured"
            continue
        with ODataClient(src) as client:
            odata_status[source_id] = client.health()

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
    background: bool = False,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.ADMIN)),
) -> dict:
    if background:
        from app.workers.tasks import sync_full, sync_incremental

        task = sync_full if full else sync_incremental
        async_result = task.delay(source_id=source_id)
        write_audit(
            db,
            user_id=user.id,
            action="sync_queued",
            details={"full": full, "source_id": source_id, "task_id": async_result.id},
        )
        db.commit()
        return {"queued": True, "task_id": async_result.id, "full": full, "source_id": source_id}

    if catalogs_only:
        result = {}
        for source in configured_sources(db):
            if not source.username:
                result[source.source_id] = {"skipped": "no credentials"}
                continue
            if source_id and source.source_id != source_id:
                continue
            result[source.source_id] = sync_catalogs_only(db, source)
        write_audit(db, user_id=user.id, action="sync_catalogs", details={"source_id": source_id})
        db.commit()
        return result

    result = sync_all_enabled(db, full=full, source_id=source_id)
    write_audit(db, user_id=user.id, action="sync_run", details={"full": full, "source_id": source_id})
    db.commit()
    return result


@router.get("/odata/connections", response_model=list[ODataConnectionOut])
def list_odata_connections(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(UserRole.ADMIN)),
) -> list[dict]:
    ensure_odata_connections(db)
    rows = []
    for source_id, _ in KNOWN_SOURCES:
        row = get_connection_row(db, source_id)
        if row:
            rows.append(connection_public_view(row))
    return rows


@router.put("/odata/connections/{source_id}", response_model=ODataConnectionOut)
def update_odata_connection(
    source_id: str,
    payload: ODataConnectionUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.ADMIN)),
) -> dict:
    if source_id not in {SOURCE_ASIL, SOURCE_MIAMOR}:
        raise HTTPException(status_code=404, detail="Unknown source_id")
    # Second base stays available in form but we don't force-enable until ready
    row = upsert_connection(
        db,
        source_id=source_id,
        base_url=payload.base_url,
        username=payload.username,
        password=payload.password,
        verify_ssl=payload.verify_ssl,
        enabled=payload.enabled,
        label=payload.label,
    )
    write_audit(
        db,
        user_id=user.id,
        action="odata_connection_update",
        details={"source_id": source_id, "enabled": payload.enabled, "base_url": payload.base_url},
    )
    db.commit()
    db.refresh(row)
    return connection_public_view(row)


@router.post("/odata/connections/{source_id}/test")
def test_odata_connection(
    source_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.ADMIN)),
) -> dict:
    from app.services.odata_settings import source_from_row

    row = get_connection_row(db, source_id)
    if row and row.base_url:
        src = source_from_row(row)
    else:
        src = resolve_source(db, source_id, include_disabled=True)
    if not src or not src.base_url:
        raise HTTPException(status_code=400, detail="Connection not configured")
    with ODataClient(src) as client:
        status = client.health()
    write_audit(db, user_id=user.id, action="odata_connection_test", details={"source_id": source_id, "status": status})
    db.commit()
    return {"source_id": source_id, "status": status}


@router.post("/digest/run")
def digest_run(
    payload: DigestRunRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.ADMIN, UserRole.REGIONAL_DIRECTOR)),
) -> dict:
    preview = build_digest_preview(db, year=payload.year, quarter=payload.quarter)
    if not payload.send:
        write_audit(
            db,
            user_id=user.id,
            action="digest_preview",
            details={"year": payload.year, "quarter": payload.quarter},
        )
        db.commit()
        return {"sent": False, "preview": preview}

    result = send_weekly_digest(db, year=payload.year, quarter=payload.quarter, force_send=True)
    write_audit(
        db,
        user_id=user.id,
        action="digest_send",
        details={"year": payload.year, "quarter": payload.quarter, "sent": result["sent"]},
    )
    db.commit()
    return result


@router.get("/counterparties")
def list_counterparties(
    promo_only: bool = False,
    source_id: Optional[str] = None,
    q: Optional[str] = None,
    db: Session = Depends(get_db),
    _: User = Depends(
        require_roles(UserRole.ADMIN, UserRole.MANAGER, UserRole.ANALYTIC, UserRole.REGIONAL_DIRECTOR)
    ),
) -> list[dict]:
    stmt = select(Counterparty).where(Counterparty.is_folder.is_(False))
    if promo_only:
        stmt = stmt.where(Counterparty.is_promo.is_(True))
    if source_id:
        stmt = stmt.where(Counterparty.source_id == source_id)
    if q:
        stmt = stmt.where(Counterparty.name.ilike(f"%{q.strip()}%"))
    rows = db.scalars(stmt.order_by(Counterparty.name).limit(2000)).all()
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
