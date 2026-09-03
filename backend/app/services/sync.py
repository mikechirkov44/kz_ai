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
    CP_SELECT,
    NOM_EXPAND,
    NOM_SELECT,
    PRODUCTION_RECEIPT_ENTITY,
    as_bool,
    as_decimal,
    map_counterparty,
    map_nomenclature,
    map_shop,
    parse_date,
    _get,
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
                mapped = map_nomenclature(row, source.source_id)
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


def sync_realizations(db: Session, source: ODataSource, *, full: bool = False) -> int:
    state = _get_or_create_state(db, source.source_id, "realization")
    state.status = SyncStatus.RUNNING.value
    db.commit()
    count = 0
    try:
        with ODataClient(source) as client:
            filter_expr = "Date ge datetime'2023-01-01T00:00:00'"
            for row in client.iter_entity(
                "Document_РеализацияТоваровУслуг",
                filter_expr=filter_expr,
                expand="Товары",
                top=200,
            ):
                warehouse = str(_get(row, "Склад", "Warehouse", default="") or "")
                if any(w.lower() in warehouse.lower() for w in EXCLUDED_WAREHOUSES if warehouse):
                    continue
                ignore = as_bool(_get(row, "НеУчитыватьПриОборачиваемости", default=False))
                doc_ref = str(_get(row, "Ref_Key", default=""))
                doc_date = parse_date(_get(row, "Date")) or date(2023, 1, 1)
                doc_number = _get(row, "Number")
                cp_ref = str(_get(row, "Контрагент_Key", default="") or "") or None
                goods = _get(row, "Товары", default=[]) or []
                if isinstance(goods, dict):
                    goods = goods.get("results", [])
                for line in goods:
                    line_no = int(_get(line, "LineNumber", default=1) or 1)
                    nom_ref = str(_get(line, "Номенклатура_Key", default="") or "") or None
                    cp_id, nom_id = _resolve_ids(db, source.source_id, cp_ref, nom_ref)
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
                        "warehouse": warehouse or None,
                        "ignore_turnover": ignore,
                        "series": _get(line, "Серия", "Series"),
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
        state.status = SyncStatus.SUCCESS.value
        state.rows_synced = count
        state.last_error = None
        now = datetime.now(timezone.utc)
        state.last_incremental_at = now
        if full:
            state.last_full_at = now
        db.commit()
    except Exception as exc:  # noqa: BLE001
        logger.exception("sync_realizations failed")
        state.status = SyncStatus.FAILED.value
        state.last_error = str(exc)
        db.commit()
        raise
    return count


def sync_returns(db: Session, source: ODataSource, *, full: bool = False) -> int:
    state = _get_or_create_state(db, source.source_id, "return_doc")
    state.status = SyncStatus.RUNNING.value
    db.commit()
    count = 0
    try:
        with ODataClient(source) as client:
            filter_expr = "Date ge datetime'2023-01-01T00:00:00'"
            for row in client.iter_entity(
                "Document_ВозвратТоваровОтПокупателя",
                filter_expr=filter_expr,
                expand="Товары",
                top=200,
            ):
                ignore = as_bool(_get(row, "НеУчитыватьПриОборачиваемости", default=False))
                doc_ref = str(_get(row, "Ref_Key", default=""))
                doc_date = parse_date(_get(row, "Date")) or date(2023, 1, 1)
                doc_number = _get(row, "Number")
                cp_ref = str(_get(row, "Контрагент_Key", default="") or "") or None
                warehouse = str(_get(row, "Склад", default="") or "") or None
                goods = _get(row, "Товары", default=[]) or []
                if isinstance(goods, dict):
                    goods = goods.get("results", [])
                for line in goods:
                    line_no = int(_get(line, "LineNumber", default=1) or 1)
                    nom_ref = str(_get(line, "Номенклатура_Key", default="") or "") or None
                    cp_id, nom_id = _resolve_ids(db, source.source_id, cp_ref, nom_ref)
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
                        "warehouse": warehouse,
                        "ignore_turnover": ignore,
                        "series": _get(line, "Серия", "Series"),
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
        state.status = SyncStatus.SUCCESS.value
        state.rows_synced = count
        state.last_error = None
        now = datetime.now(timezone.utc)
        state.last_incremental_at = now
        if full:
            state.last_full_at = now
        db.commit()
    except Exception as exc:  # noqa: BLE001
        logger.exception("sync_returns failed")
        state.status = SyncStatus.FAILED.value
        state.last_error = str(exc)
        db.commit()
        raise
    return count


def sync_client_orders(db: Session, source: ODataSource, *, full: bool = False) -> int:
    state = _get_or_create_state(db, source.source_id, "client_order")
    state.status = SyncStatus.RUNNING.value
    db.commit()
    count = 0
    try:
        with ODataClient(source) as client:
            for row in client.iter_entity("Document_ЗаказКлиента", expand="Товары", top=200):
                doc_ref = str(_get(row, "Ref_Key", default=""))
                doc_date = parse_date(_get(row, "Date")) or date(2023, 1, 1)
                cp_ref = str(_get(row, "Контрагент_Key", default="") or "") or None
                target_wh = str(_get(row, "Склад", "Warehouse", default="") or "") or None
                target_cp = str(_get(row, "КонтрагентПолучатель_Key", default="") or "") or cp_ref
                goods = _get(row, "Товары", default=[]) or []
                if isinstance(goods, dict):
                    goods = goods.get("results", [])
                if not goods:
                    goods = [{}]
                for line in goods:
                    line_no = int(_get(line, "LineNumber", default=1) or 1)
                    nom_ref = str(_get(line, "Номенклатура_Key", default="") or "") or None
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
                        "series": _get(line, "Серия", "Series"),
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
        state.status = SyncStatus.SUCCESS.value
        state.rows_synced = count
        state.last_error = None
        now = datetime.now(timezone.utc)
        state.last_incremental_at = now
        if full:
            state.last_full_at = now
        db.commit()
    except Exception as exc:  # noqa: BLE001
        logger.exception("sync_client_orders failed")
        state.status = SyncStatus.FAILED.value
        state.last_error = str(exc)
        db.commit()
        raise
    return count


def sync_production_receipts(db: Session, source: ODataSource, *, full: bool = False) -> int:
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
                filter_expr = "Date ge datetime'2025-01-01T00:00:00'"
                for row in client.iter_entity(entity_set, filter_expr=filter_expr, expand="Товары", top=200):
                    doc_ref = str(_get(row, "Ref_Key", default=""))
                    doc_date = parse_date(_get(row, "Date")) or date(2025, 1, 1)
                    order_ref = str(_get(row, "ЗаказКлиента_Key", default="") or "") or None
                    goods = _get(row, "Товары", default=[]) or []
                    if isinstance(goods, dict):
                        goods = goods.get("results", [])
                    for line in goods:
                        line_no = int(_get(line, "LineNumber", default=1) or 1)
                        nom_ref = str(_get(line, "Номенклатура_Key", default="") or "") or None
                        _, nom_id = _resolve_ids(db, source.source_id, None, nom_ref)
                        order_id = None
                        if order_ref:
                            order = db.scalar(
                                select(ClientOrder).where(
                                    ClientOrder.source_id == source.source_id,
                                    ClientOrder.onec_ref == order_ref,
                                ).limit(1)
                            )
                            order_id = order.id if order else None
                        payload = {
                            "source_id": source.source_id,
                            "onec_ref": doc_ref,
                            "line_number": line_no,
                            "doc_date": doc_date,
                            "nomenclature_id": nom_id,
                            "nomenclature_onec_ref": nom_ref,
                            "series": _get(line, "Серия", "Series"),
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
        state.status = SyncStatus.SUCCESS.value
        state.rows_synced = count
        state.last_error = None
        now = datetime.now(timezone.utc)
        state.last_incremental_at = now
        if full:
            state.last_full_at = now
        db.commit()
    except Exception as exc:  # noqa: BLE001
        logger.exception("sync_production_receipts failed")
        state.status = SyncStatus.FAILED.value
        state.last_error = str(exc)
        db.commit()
        raise
    return count


def sync_source(db: Session, source: ODataSource, *, full: bool = False) -> dict[str, int]:
    result = {
        "nomenclature": sync_nomenclature(db, source, full=full),
        "counterparty": sync_counterparties(db, source, full=full),
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
    """Trial / stage-0→1 path: only nomenclature + counterparties (+ shops)."""
    return {
        "nomenclature": sync_nomenclature(db, source, full=True, max_pages=max_pages),
        "counterparty": sync_counterparties(db, source, full=True, max_pages=max_pages),
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
