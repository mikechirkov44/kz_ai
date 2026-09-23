"""Live read-only OData queries for the 1C assistant mode."""

from __future__ import annotations

import logging
from typing import Any, Callable, Optional
from uuid import UUID

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.assistant import ODATA_ENTITY_KEYS, extract_onec_search
from app.domain.fact_shipments import quarter_bounds
from app.models import Counterparty, User
from app.odata.client import ODataClient, ODataSource, configured_sources
from app.odata.mapping import (
    CLIENT_ORDER_ENTITY,
    PRODUCTION_RECEIPT_ENTITY,
    REALIZATION_ENTITY,
    RETURN_ENTITY,
    _guid,
    as_bool,
    parse_date,
)
from app.services.odata_settings import get_connection_row
from app.services.scope import apply_counterparty_scope, resolve_allowed_counterparties

logger = logging.getLogger(__name__)

ODATA_TIMEOUT = 20.0
ODATA_PAGE_SIZE = 40
ODATA_MAX_PAGES = 1

ClientFactory = Callable[[ODataSource], ODataClient]

ODATA_ENTITIES: dict[str, dict[str, Any]] = {
    "realization": {
        "set": REALIZATION_ENTITY,
        "kind": "document",
        "select": "Ref_Key,Number,Date,Posted,DeletionMark,Контрагент_Key",
        "has_counterparty": True,
        "label": "Реализации 1С",
    },
    "return_doc": {
        "set": RETURN_ENTITY,
        "kind": "document",
        "select": "Ref_Key,Number,Date,Posted,DeletionMark,Контрагент_Key",
        "has_counterparty": True,
        "label": "Возвраты 1С",
    },
    "client_order": {
        "set": CLIENT_ORDER_ENTITY,
        "kind": "document",
        "select": "Ref_Key,Number,Date,Posted,DeletionMark,Контрагент_Key",
        "has_counterparty": True,
        "label": "Заказы 1С",
    },
    "production_receipt": {
        "set": PRODUCTION_RECEIPT_ENTITY,
        "kind": "document",
        "select": "Ref_Key,Number,Date,Posted,DeletionMark",
        "has_counterparty": False,
        "label": "Поступления из производства",
    },
    "nomenclature": {
        "set": "Catalog_Номенклатура",
        "kind": "catalog",
        "select": "Ref_Key,Description,Артикул,DeletionMark,IsFolder",
        "has_counterparty": False,
        "label": "Номенклатура 1С",
    },
    "counterparty": {
        "set": "Catalog_Контрагенты",
        "kind": "catalog",
        "select": "Ref_Key,Description,Code,DeletionMark,IsFolder",
        "has_counterparty": False,
        "label": "Контрагенты 1С",
    },
}

_SOURCE_LABELS = {"asil": "Асыл", "miamor": "МиАмор"}


def escape_odata_literal(value: str) -> str:
    return (value or "").replace("'", "''")


def is_guid(value: str) -> bool:
    try:
        UUID(str(value))
        return True
    except (TypeError, ValueError):
        return False


def build_odata_filter(
    entity: str,
    *,
    counterparty_ref: Optional[str] = None,
    q: Optional[str] = None,
) -> str:
    """Server-built $filter. Date predicates are omitted: this publication rejects them."""
    spec = ODATA_ENTITIES[entity]
    parts: list[str] = []
    if spec["kind"] == "document":
        parts.append("Posted eq true")
        if spec.get("has_counterparty") and counterparty_ref and is_guid(counterparty_ref):
            parts.append(f"Контрагент_Key eq guid'{counterparty_ref}'")
    else:
        # DeletionMark/IsFolder $filter is ignored or inverted on this publication.
        text = (q or "").strip()[:80]
        if text:
            safe = escape_odata_literal(text)
            if entity == "nomenclature":
                parts.append(
                    f"(substringof('{safe}',Description) eq true or substringof('{safe}',Артикул) eq true)"
                )
            else:
                parts.append(f"substringof('{safe}',Description) eq true")
    return " and ".join(parts)


def _source_label(db: Session, source_id: str) -> str:
    row = get_connection_row(db, source_id)
    if row and (row.label or "").strip():
        return row.label.strip()
    return _SOURCE_LABELS.get(source_id, source_id)


def _pick_sources(db: Session, source_arg: str) -> list[ODataSource]:
    sources = configured_sources(db)
    if source_arg in {"asil", "miamor"}:
        return [item for item in sources if item.source_id == source_arg]
    return sources


def _find_counterparty(db: Session, user: User, name: str | None) -> Optional[Counterparty]:
    text = (name or "").strip()
    if not text:
        return None
    stmt = apply_counterparty_scope(
        select(Counterparty).where(
            Counterparty.is_folder.is_(False),
            Counterparty.name.ilike(f"%{text}%"),
        ),
        db,
        user,
    )
    rows = list(db.scalars(stmt.limit(12)).all())
    if not rows:
        return None
    exact = [row for row in rows if (row.name or "").strip().lower() == text.lower()]
    return (exact or rows)[0]


def _allowed_refs(db: Session, user: User, source_id: str) -> Optional[set[str]]:
    allowed = resolve_allowed_counterparties(db, user)
    if allowed is None:
        return None
    if not allowed:
        return set()
    refs = db.scalars(
        select(Counterparty.onec_ref).where(
            Counterparty.id.in_(allowed),
            Counterparty.source_id == source_id,
            Counterparty.onec_ref.is_not(None),
        )
    ).all()
    return {str(ref) for ref in refs if ref}


def _name_map(db: Session, source_id: str, refs: set[str]) -> dict[str, str]:
    if not refs:
        return {}
    rows = db.execute(
        select(Counterparty.onec_ref, Counterparty.name).where(
            Counterparty.source_id == source_id,
            Counterparty.onec_ref.in_(refs),
        )
    ).all()
    return {str(row.onec_ref): row.name for row in rows if row.onec_ref}


def _default_client(source: ODataSource) -> ODataClient:
    return ODataClient(source, timeout=ODATA_TIMEOUT)


def _page_skip(client: ODataClient, spec: dict[str, Any], filter_expr: str, order: str, *, pages: int = 1) -> int:
    """Natural 1C order is oldest-first. Date $orderby is ignored on this publication."""
    if order == "oldest" or not hasattr(client, "entity_count"):
        return 0
    try:
        total = client.entity_count(spec["set"], filter_expr=filter_expr or None)
    except Exception:  # noqa: BLE001
        return 0
    if not total or total <= ODATA_PAGE_SIZE:
        return 0
    return max(0, int(total) - ODATA_PAGE_SIZE * pages)


def _usable_catalog_row(row: dict[str, Any]) -> bool:
    return not as_bool(row.get("DeletionMark")) and not as_bool(row.get("IsFolder"))


def _fetch_rows(
    client: ODataClient,
    spec: dict[str, Any],
    filter_expr: str,
    *,
    order: str = "latest",
) -> list[dict[str, Any]]:
    catalog = spec["kind"] == "catalog"
    pages = 20 if catalog else ODATA_MAX_PAGES
    start_skip = _page_skip(client, spec, filter_expr, order, pages=8 if catalog and order == "latest" else 1)
    try:
        rows = client.fetch_all(
            spec["set"],
            select=spec["select"],
            filter_expr=filter_expr or None,
            top=ODATA_PAGE_SIZE,
            max_pages=pages,
            start_skip=start_skip,
        )
    except httpx.HTTPStatusError:
        fallback = "Posted eq true" if spec["kind"] == "document" else ""
        start_skip = _page_skip(client, spec, fallback, order, pages=8 if catalog else 1)
        rows = client.fetch_all(
            spec["set"],
            select=spec["select"],
            filter_expr=fallback or None,
            top=ODATA_PAGE_SIZE,
            max_pages=pages,
            start_skip=start_skip,
        )
    if catalog:
        return [row for row in rows if _usable_catalog_row(row)]
    return rows


def _aggregate_counterparties(rows: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    counts: dict[str, dict[str, Any]] = {}
    for row in rows:
        name = str(row.get("counterparty") or "без контрагента").strip()
        bucket = counts.setdefault(name, {"title": name, "counterparty": name, "quantity": 0, "hint": row.get("source")})
        bucket["quantity"] = int(bucket["quantity"]) + 1
    ranked = sorted(counts.values(), key=lambda item: int(item["quantity"]), reverse=True)
    return ranked[:limit]


def _map_document(
    row: dict[str, Any],
    *,
    source_id: str,
    source_label: str,
    names: dict[str, str],
) -> Optional[dict[str, Any]]:
    if as_bool(row.get("DeletionMark")):
        return None
    number = str(row.get("Number") or "").strip()
    ref = str(row.get("Ref_Key") or "").strip()
    doc_date = parse_date(row.get("Date"))
    cp_ref = _guid(row.get("Контрагент_Key"))
    title = number or ref[:8]
    if not title:
        return None
    return {
        "title": title,
        "number": number or None,
        "date": doc_date.isoformat() if doc_date else None,
        "counterparty": names.get(cp_ref or ""),
        "source": source_label,
        "source_id": source_id,
        "hint": source_label,
    }


def _map_catalog(row: dict[str, Any], *, source_id: str, source_label: str, entity: str) -> Optional[dict[str, Any]]:
    if as_bool(row.get("DeletionMark")) or as_bool(row.get("IsFolder")):
        return None
    name = str(row.get("Description") or "").strip()
    article = str(row.get("Артикул") or "").strip()
    code = str(row.get("Code") or "").strip()
    title = article or name or code
    if not title:
        return None
    return {
        "title": title,
        "name": name or None,
        "article": article or None,
        "counterparty": name if entity == "counterparty" else None,
        "source": source_label,
        "source_id": source_id,
        "hint": name if article else (code or source_label),
    }


def query_odata_live(
    db: Session,
    user: User,
    args: dict[str, Any],
    *,
    client_factory: Optional[ClientFactory] = None,
) -> dict[str, Any]:
    entity = str(args.get("entity") or "realization").strip()
    if entity not in ODATA_ENTITY_KEYS:
        entity = "realization"
    spec = ODATA_ENTITIES[entity]
    year = int(args["year"])
    quarter = int(args["quarter"])
    limit = max(1, min(int(args.get("limit") or 15), 30))
    source_arg = str(args.get("source") or "all").strip().lower()
    start, end = quarter_bounds(year, quarter)
    factory = client_factory or _default_client
    sources = _pick_sources(db, source_arg)
    period = f"{year} Q{quarter}, живая 1С"
    label = spec["label"]
    if not sources:
        return {
            "tool": "odata_live",
            "label": label,
            "entity": entity,
            "period": period,
            "error": "Нет включённых подключений 1С. Включите OData в админке.",
            "rows": [],
        }

    order = "oldest" if str(args.get("order") or "") == "oldest" else "latest"
    aggregate = str(args.get("aggregate") or "")
    raw_needle = str(args.get("q") or args.get("article") or args.get("counterparty") or "").strip()
    needle = extract_onec_search(raw_needle) or ""
    if raw_needle and not needle and len(raw_needle) <= 40:
        needle = raw_needle
    named = _find_counterparty(db, user, needle) if spec.get("has_counterparty") and needle else None
    mapped: list[dict[str, Any]] = []
    warnings: list[str] = []

    for source in sources:
        allowed = _allowed_refs(db, user, source.source_id) if spec.get("has_counterparty") else None
        if allowed is not None and not allowed:
            warnings.append(f"{_source_label(db, source.source_id)}: нет доступных контрагентов")
            continue
        cp_ref = None
        if named and named.source_id == source.source_id:
            cp_ref = named.onec_ref
            if allowed is not None and cp_ref not in allowed:
                continue
        elif named and named.source_id != source.source_id:
            continue
        filter_expr = build_odata_filter(entity, counterparty_ref=cp_ref, q=needle if spec["kind"] == "catalog" else None)
        try:
            with factory(source) as client:
                raw = _fetch_rows(client, spec, filter_expr, order=order)
        except httpx.TimeoutException:
            warnings.append(f"{_source_label(db, source.source_id)}: таймаут OData")
            continue
        except Exception as exc:  # noqa: BLE001
            logger.warning("assistant odata %s %s failed: %s", source.source_id, entity, exc)
            warnings.append(f"{_source_label(db, source.source_id)}: не удалось прочитать 1С")
            continue

        refs = {_guid(row.get("Контрагент_Key")) for row in raw}
        refs.discard(None)
        names = _name_map(db, source.source_id, {str(ref) for ref in refs if ref})
        source_label = _source_label(db, source.source_id)
        for row in raw:
            if spec["kind"] == "document":
                if allowed is not None:
                    cp_key = _guid(row.get("Контрагент_Key"))
                    if not cp_key or cp_key not in allowed:
                        continue
                item = _map_document(row, source_id=source.source_id, source_label=source_label, names=names)
                if item:
                    doc_date = parse_date(row.get("Date"))
                    item["_in_quarter"] = bool(doc_date and start <= doc_date <= end)
            else:
                item = _map_catalog(row, source_id=source.source_id, source_label=source_label, entity=entity)
            if item:
                mapped.append(item)

    if spec["kind"] == "document" and order != "oldest":
        quarter_rows = [row for row in mapped if row.get("_in_quarter")]
        if quarter_rows:
            mapped = quarter_rows
        elif mapped:
            period = "последние документы 1С"
    elif spec["kind"] == "document" and order == "oldest":
        period = "самые ранние документы 1С"
    elif spec["kind"] == "catalog" and order == "oldest":
        period = "самые ранние карточки 1С"
    for row in mapped:
        row.pop("_in_quarter", None)
    if spec["kind"] == "document":
        mapped.sort(key=lambda item: item.get("date") or "", reverse=(order != "oldest"))
    if aggregate == "counterparties":
        mapped = _aggregate_counterparties(mapped, limit)
        label = "Клиенты по последним реализациям"
    else:
        mapped = mapped[:limit]
    payload: dict[str, Any] = {
        "tool": "odata_live",
        "label": label,
        "entity": entity,
        "period": period,
        "order": order,
        "rows": mapped,
    }
    if aggregate == "counterparties":
        payload["aggregate"] = "counterparties"
    if named:
        payload["counterparty"] = named.name
    if warnings and not mapped:
        payload["error"] = "; ".join(warnings)
    elif warnings:
        payload["warnings"] = warnings
    elif not mapped:
        if spec["kind"] == "catalog" and needle:
            payload["error"] = f"В справочнике 1С нет карточек по запросу «{needle}»."
        elif spec["kind"] == "catalog":
            payload["error"] = "В справочнике 1С нет карточек в доступе."
        else:
            payload["error"] = "Подключение к 1С есть, но подходящих документов не нашлось."
    return payload
