from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.constants import DIRECTION_FILTER, EXCLUDED_WAREHOUSES, SyncStatus
from app.models import ClientOrder, Counterparty, Nomenclature, ProductionReceipt, Realization, ReturnDoc, SyncState
from app.odata.client import ODataClient, ODataSource, configured_sources
from app.odata.mapping import (
    ASSAY_CATALOG,
    CLIENT_ORDER_ENTITY,
    CP_SELECT,
    DIRECTION_CATALOG,
    DOC_MIN_DATE_DEFAULT,
    LTS_CATALOG,
    LTS_HISTORY_REGISTER,
    METAL_COLOR_CATALOG,
    NOM_EXPAND,
    NOM_SELECT,
    PRODUCTION_RECEIPT_ENTITY,
    REALIZATION_ENTITY,
    RETURN_ENTITY,
    WAREHOUSE_CATALOG,
    WEAR_TYPE_CATALOG,
    as_bool,
    as_decimal,
    line_series,
    map_counterparty,
    map_nomenclature,
    map_shop,
    parse_date,
    _get,
    _guid,
)

logger = logging.getLogger(__name__)


def _get_or_create_state(db: Session, source_id: str, entity: str) -> SyncState:
    state = db.scalar(select(SyncState).where(SyncState.source_id == source_id, SyncState.entity == entity))
    if not state:
        state = SyncState(source_id=source_id, entity=entity, status=SyncStatus.IDLE.value)
        db.add(state)
        db.flush()
    return state


def sync_nomenclature(
    db: Session, source: ODataSource, *, full: bool = False, max_pages: int = 10_000
) -> int:
    state = _get_or_create_state(db, source.source_id, "nomenclature")
    state.status = SyncStatus.RUNNING.value
    db.commit()
    count = 0
    skipped = 0
    cache: dict[str, Nomenclature] = {}
    try:
        with ODataClient(source) as client:
            lookups = {
                "direction": client.catalog_name_map(DIRECTION_CATALOG),
                "wear_type": client.catalog_name_map(WEAR_TYPE_CATALOG),
                "assay": client.catalog_name_map(ASSAY_CATALOG),
                "metal_color": client.catalog_name_map(METAL_COLOR_CATALOG),
                "lts": client.catalog_name_map(LTS_CATALOG),
            }
            logger.info(
                "nomenclature lookups loaded direction=%s wear=%s assay=%s color=%s lts=%s",
                len(lookups["direction"]),
                len(lookups["wear_type"]),
                len(lookups["assay"]),
                len(lookups["metal_color"]),
                len(lookups["lts"]),
            )
            for row in client.iter_entity(
                "Catalog_Номенклатура",
                select=NOM_SELECT,
                expand=NOM_EXPAND,
                top=200,
                order_by="Ref_Key",
                max_pages=max_pages,
            ):
                if as_bool(row.get("IsFolder")) or as_bool(row.get("DeletionMark")):
                    skipped += 1
                    continue
                mapped = map_nomenclature(row, source.source_id, lookups=lookups)
                ref = mapped["onec_ref"]
                if not ref:
                    continue
                direction = mapped.get("direction") or ""
                if direction and direction not in DIRECTION_FILTER:
                    skipped += 1
                    continue
                existing = cache.get(ref)
                if existing is None:
                    existing = db.scalar(
                        select(Nomenclature).where(
                            Nomenclature.source_id == source.source_id,
                            Nomenclature.onec_ref == ref,
                        )
                    )
                if existing:
                    for k, v in mapped.items():
                        # Keep values filled by lts_history (or prior enrichers) when OData has none.
                        if v is None and k in ("lts", "lts_date"):
                            continue
                        setattr(existing, k, v)
                    cache[ref] = existing
                else:
                    obj = Nomenclature(**mapped)
                    db.add(obj)
                    cache[ref] = obj
                count += 1
                if count % 200 == 0:
                    db.commit()
                    logger.info("nomenclature synced=%s skipped=%s", count, skipped)
        state.status = SyncStatus.SUCCESS.value
        state.rows_synced = count
        state.last_error = None
        now = datetime.now(timezone.utc)
        state.last_incremental_at = now
        if full:
            state.last_full_at = now
        db.commit()
        logger.info("nomenclature done synced=%s skipped=%s", count, skipped)
    except Exception as exc:  # noqa: BLE001
        logger.exception("sync_nomenclature failed")
        db.rollback()
        state = _get_or_create_state(db, source.source_id, "nomenclature")
        state.status = SyncStatus.FAILED.value
        state.last_error = str(exc)
        db.commit()
        raise
    return count


def sync_counterparties(
    db: Session, source: ODataSource, *, full: bool = False, max_pages: int = 10_000
) -> int:
    state = _get_or_create_state(db, source.source_id, "counterparty")
    state.status = SyncStatus.RUNNING.value
    db.commit()
    count = 0
    cache: dict[str, Counterparty] = {}
    try:
        with ODataClient(source) as client:
            for row in client.iter_entity(
                "Catalog_Контрагенты",
                select=CP_SELECT,
                top=500,
                order_by="Ref_Key",
                max_pages=max_pages,
            ):
                if as_bool(row.get("DeletionMark")):
                    continue
                mapped = map_counterparty(row, source.source_id)
                if not mapped["onec_ref"]:
                    continue
                existing = cache.get(mapped["onec_ref"])
                if existing is None:
                    existing = db.scalar(
                        select(Counterparty).where(
                            Counterparty.source_id == source.source_id,
                            Counterparty.onec_ref == mapped["onec_ref"],
                        )
                    )
                if existing:
                    for k, v in mapped.items():
                        if k == "shops":
                            continue
                        setattr(existing, k, v)
                    cache[mapped["onec_ref"]] = existing
                else:
                    obj = Counterparty(**mapped)
                    db.add(obj)
                    cache[mapped["onec_ref"]] = obj
                count += 1
                if count % 200 == 0:
                    db.commit()

            # shops: Catalog_МагазиныКонтрагентов.Owner_Key -> counterparty
            shops_by_owner: dict[str, list[str]] = {}
            for row in client.iter_entity(
                "Catalog_МагазиныКонтрагентов", top=500, order_by="Ref_Key", max_pages=max_pages
            ):
                if as_bool(row.get("DeletionMark")):
                    continue
                owner, name = map_shop(row)
                if owner and name:
                    shops_by_owner.setdefault(owner, []).append(name)
            if shops_by_owner:
                rows = db.scalars(
                    select(Counterparty).where(Counterparty.source_id == source.source_id)
                ).all()
                for cp in rows:
                    if cp.onec_ref in shops_by_owner:
                        cp.shops = sorted(set(shops_by_owner[cp.onec_ref]))

        # Resolve head_counterparty_id
        rows = db.scalars(select(Counterparty).where(Counterparty.source_id == source.source_id)).all()
        by_ref = {r.onec_ref: r for r in rows}
        for row in rows:
            if row.head_counterparty_onec_ref and row.head_counterparty_onec_ref in by_ref:
                row.head_counterparty_id = by_ref[row.head_counterparty_onec_ref].id
        state.status = SyncStatus.SUCCESS.value
        state.rows_synced = count
        state.last_error = None
        now = datetime.now(timezone.utc)
        state.last_incremental_at = now
        if full:
            state.last_full_at = now
        db.commit()
    except Exception as exc:  # noqa: BLE001
        logger.exception("sync_counterparties failed")
        db.rollback()
        state = _get_or_create_state(db, source.source_id, "counterparty")
        state.status = SyncStatus.FAILED.value
        state.last_error = str(exc)
        db.commit()
        raise
    return count


def _resolve_ids(db: Session, source_id: str, cp_ref: Optional[str], nom_ref: Optional[str]):
    cp_id = None
    nom_id = None
    if cp_ref:
        cp = db.scalar(
            select(Counterparty).where(Counterparty.source_id == source_id, Counterparty.onec_ref == cp_ref)
        )
        cp_id = cp.id if cp else None
    if nom_ref:
        nom = db.scalar(
            select(Nomenclature).where(Nomenclature.source_id == source_id, Nomenclature.onec_ref == nom_ref)
        )
        nom_id = nom.id if nom else None
    return cp_id, nom_id


def _warehouse_name(warehouses: dict[str, str], *keys: Optional[str]) -> Optional[str]:
    for key in keys:
        if not key:
            continue
        return warehouses.get(key) or key
    return None


def _is_excluded_warehouse(warehouse: Optional[str]) -> bool:
    if not warehouse:
        return False
    lower = warehouse.lower()
    return any(w.lower() in lower for w in EXCLUDED_WAREHOUSES)


def _finish_state(state: SyncState, db: Session, count: int, *, full: bool) -> None:
    state.status = SyncStatus.SUCCESS.value
    state.rows_synced = count
    state.last_error = None
    now = datetime.now(timezone.utc)
    state.last_incremental_at = now
    if full:
        state.last_full_at = now
    db.commit()


def _fail_state(state: SyncState, db: Session, exc: Exception) -> None:
    state.status = SyncStatus.FAILED.value
    state.last_error = str(exc)
    db.commit()


def sync_realizations(
    db: Session,
    source: ODataSource,
    *,
    full: bool = False,
    max_pages: int = 10_000,
    start_skip: int = 0,
    min_date: date = DOC_MIN_DATE_DEFAULT,
) -> int:
    """Sync realization lines. Date filter and $expand=Товары unavailable on live OData."""
    state = _get_or_create_state(db, source.source_id, "realization")
    state.status = SyncStatus.RUNNING.value
    db.commit()
    count = 0
    docs_seen = 0
    docs_used = 0
    try:
        with ODataClient(source) as client:
            warehouses = client.catalog_name_map(WAREHOUSE_CATALOG)
            for row in client.iter_entity(
                REALIZATION_ENTITY,
                filter_expr="Posted eq true",
                select="Ref_Key,Number,Date,Posted,DeletionMark,Контрагент_Key,Склад_Key",
                order_by="Ref_Key",
                top=100,
                max_pages=max_pages,
                start_skip=start_skip,
            ):
                docs_seen += 1
                if as_bool(row.get("DeletionMark")):
                    continue
                doc_date = parse_date(_get(row, "Date"))
                if not doc_date or doc_date < min_date:
                    continue
                docs_used += 1
                doc_ref = str(_get(row, "Ref_Key", default="") or "")
                if not doc_ref:
                    continue
                wh_key = _guid(_get(row, "Склад_Key"))
                warehouse = _warehouse_name(warehouses, wh_key)
                if _is_excluded_warehouse(warehouse):
                    continue
                ignore = as_bool(_get(row, "НеУчитыватьПриОборачиваемости", default=False))
                doc_number = _get(row, "Number")
                cp_ref = _guid(_get(row, "Контрагент_Key"))
                for line in client.iter_nav_collection(REALIZATION_ENTITY, doc_ref, "Товары", top=200):
                    line_no = int(_get(line, "LineNumber", default=1) or 1)
                    nom_ref = _guid(_get(line, "Номенклатура_Key"))
                    cp_id, nom_id = _resolve_ids(db, source.source_id, cp_ref, nom_ref)
                    line_wh = _warehouse_name(warehouses, _guid(_get(line, "Склад_Key")), wh_key)
                    payload = {
                        "source_id": source.source_id,
                        "onec_ref": doc_ref,
                        "line_number": line_no,
                        "doc_date": doc_date,
                        "doc_number": doc_number,
                        "counterparty_id": cp_id,
                        "nomenclature_id": nom_id,
                        "counterparty_onec_ref": cp_ref,
                        "nomenclature_onec_ref": nom_ref,
                        "quantity": as_decimal(_get(line, "Количество", default=0)),
                        "price": as_decimal(_get(line, "Цена", default=0)),
                        "amount": as_decimal(_get(line, "Сумма", default=0)),
                        "warehouse": line_wh or warehouse,
                        "ignore_turnover": ignore,
                        "series": line_series(line),
                    }
                    existing = db.scalar(
                        select(Realization).where(
                            Realization.source_id == source.source_id,
                            Realization.onec_ref == doc_ref,
                            Realization.line_number == line_no,
                        )
                    )
                    if existing:
                        for k, v in payload.items():
                            setattr(existing, k, v)
                    else:
                        db.add(Realization(**payload))
                    count += 1
                if count and count % 200 == 0:
                    db.commit()
                    logger.info(
                        "realization lines=%s docs_used=%s docs_seen=%s",
                        count,
                        docs_used,
                        docs_seen,
                    )
        _finish_state(state, db, count, full=full)
        logger.info(
            "realization done lines=%s docs_used=%s docs_seen=%s",
            count,
            docs_used,
            docs_seen,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("sync_realizations failed")
        _fail_state(state, db, exc)
        raise
    return count


def sync_returns(
    db: Session,
    source: ODataSource,
    *,
    full: bool = False,
    max_pages: int = 10_000,
    start_skip: int = 0,
    min_date: date = DOC_MIN_DATE_DEFAULT,
) -> int:
    """Sync return document lines (same live OData quirks as realizations)."""
    state = _get_or_create_state(db, source.source_id, "return_doc")
    state.status = SyncStatus.RUNNING.value
    db.commit()
    count = 0
    docs_seen = 0
    docs_used = 0
    try:
        with ODataClient(source) as client:
            warehouses = client.catalog_name_map(WAREHOUSE_CATALOG)
            for row in client.iter_entity(
                RETURN_ENTITY,
                filter_expr="Posted eq true",
                select="Ref_Key,Number,Date,Posted,DeletionMark,Контрагент_Key,СкладОрдер_Key",
                order_by="Ref_Key",
                top=100,
                max_pages=max_pages,
                start_skip=start_skip,
            ):
                docs_seen += 1
                if as_bool(row.get("DeletionMark")):
                    continue
                doc_date = parse_date(_get(row, "Date"))
                if not doc_date or doc_date < min_date:
                    continue
                docs_used += 1
                doc_ref = str(_get(row, "Ref_Key", default="") or "")
                if not doc_ref:
                    continue
                wh_key = _guid(_get(row, "СкладОрдер_Key"))
                warehouse = _warehouse_name(warehouses, wh_key)
                if _is_excluded_warehouse(warehouse):
                    continue
                ignore = as_bool(_get(row, "НеУчитыватьПриОборачиваемости", default=False))
                doc_number = _get(row, "Number")
                cp_ref = _guid(_get(row, "Контрагент_Key"))
                for line in client.iter_nav_collection(RETURN_ENTITY, doc_ref, "Товары", top=200):
                    line_no = int(_get(line, "LineNumber", default=1) or 1)
                    nom_ref = _guid(_get(line, "Номенклатура_Key"))
                    cp_id, nom_id = _resolve_ids(db, source.source_id, cp_ref, nom_ref)
                    line_wh = _warehouse_name(warehouses, _guid(_get(line, "Склад_Key")), wh_key)
                    payload = {
                        "source_id": source.source_id,
                        "onec_ref": doc_ref,
                        "line_number": line_no,
                        "doc_date": doc_date,
                        "doc_number": doc_number,
                        "counterparty_id": cp_id,
                        "nomenclature_id": nom_id,
                        "counterparty_onec_ref": cp_ref,
                        "nomenclature_onec_ref": nom_ref,
                        "quantity": as_decimal(_get(line, "Количество", default=0)),
                        "price": as_decimal(_get(line, "Цена", default=0)),
                        "amount": as_decimal(_get(line, "Сумма", default=0)),
                        "warehouse": line_wh or warehouse,
                        "ignore_turnover": ignore,
                        "series": line_series(line),
                    }
                    existing = db.scalar(
                        select(ReturnDoc).where(
                            ReturnDoc.source_id == source.source_id,
                            ReturnDoc.onec_ref == doc_ref,
                            ReturnDoc.line_number == line_no,
                        )
                    )
                    if existing:
                        for k, v in payload.items():
                            setattr(existing, k, v)
                    else:
                        db.add(ReturnDoc(**payload))
                    count += 1
                if count and count % 200 == 0:
                    db.commit()
                    logger.info(
                        "return_doc lines=%s docs_used=%s docs_seen=%s",
                        count,
                        docs_used,
                        docs_seen,
                    )
        _finish_state(state, db, count, full=full)
        logger.info(
            "return_doc done lines=%s docs_used=%s docs_seen=%s",
            count,
            docs_used,
            docs_seen,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("sync_returns failed")
        _fail_state(state, db, exc)
        raise
    return count


def sync_client_orders(
    db: Session,
    source: ODataSource,
    *,
    full: bool = False,
    max_pages: int = 10_000,
    start_skip: int = 0,
    min_date: date = DOC_MIN_DATE_DEFAULT,
) -> int:
    state = _get_or_create_state(db, source.source_id, "client_order")
    state.status = SyncStatus.RUNNING.value
    db.commit()
    count = 0
    try:
        with ODataClient(source) as client:
            warehouses = client.catalog_name_map(WAREHOUSE_CATALOG)
            for row in client.iter_entity(
                CLIENT_ORDER_ENTITY,
                filter_expr="Posted eq true",
                select="Ref_Key,Number,Date,Posted,DeletionMark,Контрагент_Key,Склад_Key",
                order_by="Ref_Key",
                top=100,
                max_pages=max_pages,
                start_skip=start_skip,
            ):
                if as_bool(row.get("DeletionMark")):
                    continue
                doc_date = parse_date(_get(row, "Date"))
                if not doc_date or doc_date < min_date:
                    continue
                doc_ref = str(_get(row, "Ref_Key", default="") or "")
                if not doc_ref:
                    continue
                cp_ref = _guid(_get(row, "Контрагент_Key"))
                target_wh = _warehouse_name(warehouses, _guid(_get(row, "Склад_Key")))
                target_cp = _guid(_get(row, "КонтрагентПолучатель_Key")) or cp_ref
                lines = list(client.iter_nav_collection(CLIENT_ORDER_ENTITY, doc_ref, "Товары", top=200))
                if not lines:
                    lines = [{}]
                for line in lines:
                    line_no = int(_get(line, "LineNumber", default=1) or 1)
                    nom_ref = _guid(_get(line, "Номенклатура_Key"))
                    cp_id, nom_id = _resolve_ids(db, source.source_id, cp_ref, nom_ref)
                    payload = {
                        "source_id": source.source_id,
                        "onec_ref": doc_ref,
                        "line_number": line_no,
                        "doc_date": doc_date,
                        "counterparty_id": cp_id,
                        "nomenclature_id": nom_id,
                        "counterparty_onec_ref": cp_ref,
                        "nomenclature_onec_ref": nom_ref,
                        "target_warehouse": target_wh,
                        "target_counterparty_onec_ref": target_cp,
                        "quantity": as_decimal(_get(line, "Количество", default=0)),
                        "series": line_series(line),
                    }
                    existing = db.scalar(
                        select(ClientOrder).where(
                            ClientOrder.source_id == source.source_id,
                            ClientOrder.onec_ref == doc_ref,
                            ClientOrder.line_number == line_no,
                        )
                    )
                    if existing:
                        for k, v in payload.items():
                            setattr(existing, k, v)
                    else:
                        db.add(ClientOrder(**payload))
                    count += 1
                if count and count % 200 == 0:
                    db.commit()
        _finish_state(state, db, count, full=full)
    except Exception as exc:  # noqa: BLE001
        logger.exception("sync_client_orders failed")
        _fail_state(state, db, exc)
        raise
    return count


def sync_production_receipts(
    db: Session,
    source: ODataSource,
    *,
    full: bool = False,
    max_pages: int = 10_000,
    start_skip: int = 0,
    min_date: date = date(2025, 1, 1),
) -> int:
    state = _get_or_create_state(db, source.source_id, "production_receipt")
    state.status = SyncStatus.RUNNING.value
    db.commit()
    count = 0
    entities = (
        (PRODUCTION_RECEIPT_ENTITY, "production"),
        ("Document_ПоступлениеТоваровУслуг", "goods"),
    )
    try:
        with ODataClient(source) as client:
            for entity_set, doc_type in entities:
                for row in client.iter_entity(
                    entity_set,
                    filter_expr="Posted eq true",
                    select="Ref_Key,Number,Date,Posted,DeletionMark",
                    order_by="Ref_Key",
                    top=100,
                    max_pages=max_pages,
                    start_skip=start_skip,
                ):
                    if as_bool(row.get("DeletionMark")):
                        continue
                    doc_date = parse_date(_get(row, "Date"))
                    if not doc_date or doc_date < min_date:
                        continue
                    doc_ref = str(_get(row, "Ref_Key", default="") or "")
                    if not doc_ref:
                        continue
                    for line in client.iter_nav_collection(entity_set, doc_ref, "Товары", top=200):
                        line_no = int(_get(line, "LineNumber", default=1) or 1)
                        nom_ref = _guid(_get(line, "Номенклатура_Key"))
                        _, nom_id = _resolve_ids(db, source.source_id, None, nom_ref)
                        order_ref = _guid(_get(line, "ЗаказКлиента_Key")) or _guid(
                            _get(row, "ЗаказКлиента_Key")
                        )
                        order_id = None
                        if order_ref:
                            order = db.scalar(
                                select(ClientOrder)
                                .where(
                                    ClientOrder.source_id == source.source_id,
                                    ClientOrder.onec_ref == order_ref,
                                )
                                .limit(1)
                            )
                            order_id = order.id if order else None
                        payload = {
                            "source_id": source.source_id,
                            "onec_ref": doc_ref,
                            "line_number": line_no,
                            "doc_date": doc_date,
                            "nomenclature_id": nom_id,
                            "nomenclature_onec_ref": nom_ref,
                            "series": line_series(line),
                            "client_order_id": order_id,
                            "client_order_onec_ref": order_ref,
                            "doc_type": doc_type,
                        }
                        existing = db.scalar(
                            select(ProductionReceipt).where(
                                ProductionReceipt.source_id == source.source_id,
                                ProductionReceipt.onec_ref == doc_ref,
                                ProductionReceipt.line_number == line_no,
                            )
                        )
                        if existing:
                            for k, v in payload.items():
                                setattr(existing, k, v)
                        else:
                            db.add(ProductionReceipt(**payload))
                        count += 1
                    if count and count % 200 == 0:
                        db.commit()
        _finish_state(state, db, count, full=full)
    except Exception as exc:  # noqa: BLE001
        logger.exception("sync_production_receipts failed")
        _fail_state(state, db, exc)
        raise
    return count


def sync_lts_history(
    db: Session,
    source: ODataSource,
    *,
    full: bool = False,
    max_pages: int = 10_000,
) -> int:
    """
    Fill nomenclature.lts_date (and lts name) from InformationRegister_ИсторияИзмененияЖЦТ.

    For each Номенклатура_Key keep the latest Period and its Значение_Key
    (resolved via Catalog_ЮС_ЖЦТ).
    """
    state = _get_or_create_state(db, source.source_id, "lts_history")
    state.status = SyncStatus.RUNNING.value
    db.commit()
    updated = 0
    rows_seen = 0
    try:
        with ODataClient(source) as client:
            lts_names = client.catalog_name_map(LTS_CATALOG)
            latest: dict[str, tuple[date, Optional[str]]] = {}
            for row in client.iter_entity(
                LTS_HISTORY_REGISTER,
                select="Period,Номенклатура_Key,Значение_Key",
                order_by="Period",
                top=500,
                max_pages=max_pages,
            ):
                rows_seen += 1
                nom_ref = _guid(_get(row, "Номенклатура_Key"))
                period = parse_date(_get(row, "Period"))
                if not nom_ref or not period:
                    continue
                value_key = _guid(_get(row, "Значение_Key"))
                lts_name = lts_names.get(value_key) if value_key else None
                prev = latest.get(nom_ref)
                if prev is None or period >= prev[0]:
                    latest[nom_ref] = (period, lts_name)

            if not latest:
                _finish_state(state, db, 0, full=full)
                logger.info("lts_history empty rows_seen=%s", rows_seen)
                return 0

            noms = db.scalars(
                select(Nomenclature).where(Nomenclature.source_id == source.source_id)
            ).all()
            by_ref = {n.onec_ref: n for n in noms}
            for nom_ref, (period, lts_name) in latest.items():
                nom = by_ref.get(nom_ref)
                if not nom:
                    continue
                nom.lts_date = period
                if lts_name:
                    nom.lts = lts_name
                updated += 1
            db.commit()
        _finish_state(state, db, updated, full=full)
        logger.info(
            "lts_history done updated=%s unique_noms=%s rows_seen=%s",
            updated,
            len(latest),
            rows_seen,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("sync_lts_history failed")
        _fail_state(state, db, exc)
        raise
    return updated


def sync_source(db: Session, source: ODataSource, *, full: bool = False) -> dict[str, int]:
    result = {
        "nomenclature": sync_nomenclature(db, source, full=full),
        "counterparty": sync_counterparties(db, source, full=full),
        "lts_history": sync_lts_history(db, source, full=full),
        "realization": sync_realizations(db, source, full=full),
        "return_doc": sync_returns(db, source, full=full),
    }
    if full:
        result["client_order"] = sync_client_orders(db, source, full=full)
        result["production_receipt"] = sync_production_receipts(db, source, full=full)
    return result


def sync_catalogs_only(
    db: Session, source: ODataSource, *, max_pages: int = 10_000
) -> dict[str, int]:
    """Trial path: only nomenclature + counterparties (+ shops)."""
    return {
        "nomenclature": sync_nomenclature(db, source, full=True, max_pages=max_pages),
        "counterparty": sync_counterparties(db, source, full=True, max_pages=max_pages),
    }


def sync_documents_trial(
    db: Session,
    source: ODataSource,
    *,
    max_pages: int = 20,
    realization_start_skip: int = 4500,
    return_start_skip: int = 0,
    min_date: date = DOC_MIN_DATE_DEFAULT,
) -> dict[str, int]:
    """Limited realization/return sync for live smoke tests."""
    return {
        "realization": sync_realizations(
            db,
            source,
            full=True,
            max_pages=max_pages,
            start_skip=realization_start_skip,
            min_date=min_date,
        ),
        "return_doc": sync_returns(
            db,
            source,
            full=True,
            max_pages=max_pages,
            start_skip=return_start_skip,
            min_date=min_date,
        ),
    }


def sync_all_enabled(db: Session, *, full: bool = False, source_id: Optional[str] = None) -> dict:
    result = {}
    for source in configured_sources():
        if not source.username:
            result[source.source_id] = {"skipped": "no credentials"}
            continue
        if source_id and source.source_id != source_id:
            continue
        result[source.source_id] = sync_source(db, source, full=full)
    return result
