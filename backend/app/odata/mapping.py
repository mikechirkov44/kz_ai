"""Field extractors aligned with live docs/odata-metadata.xml (test3_asil)."""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Optional

from app.domain.articles import normalize_article

EMPTY_GUID = "00000000-0000-0000-0000-000000000000"


def _get(row: dict[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        if key in row and row[key] not in (None, ""):
            value = row[key]
            if isinstance(value, str) and not value.strip():
                continue
            return value
    return default


def _guid(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value)
    if not text or text == EMPTY_GUID:
        return None
    return text


def _nav_description(row: dict[str, Any], *nav_keys: str) -> Optional[str]:
    for key in nav_keys:
        nav = row.get(key)
        if isinstance(nav, dict):
            desc = nav.get("Description")
            if desc:
                return str(desc)
        # sometimes already flattened
        flat = row.get(key)
        if isinstance(flat, str) and flat and flat != EMPTY_GUID:
            return flat
    return None


def parse_datetime(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    text = str(value).replace("Z", "+00:00")
    if text.startswith("/Date("):
        ms = int(text[6:].split(")")[0].split("+")[0].split("-")[0])
        return datetime.fromtimestamp(ms / 1000.0, tz=timezone.utc)
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def parse_date(value: Any) -> Optional[date]:
    dt = parse_datetime(value)
    if dt:
        return dt.date()
    if isinstance(value, date):
        return value
    return None


def as_decimal(value: Any, default: str = "0") -> Decimal:
    if value is None or value == "":
        return Decimal(default)
    return Decimal(str(value).replace(",", ".").replace(" ", "").replace("\xa0", ""))


def as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value in (1, "1", "true", "True", "Да", "да"):
        return True
    return False


def map_nomenclature(
    row: dict[str, Any],
    source_id: str,
    *,
    lookups: Optional[dict[str, dict[str, str]]] = None,
) -> dict[str, Any]:
    """Map nomenclature row; resolve *_Key via catalog lookups when $expand is empty."""
    lookups = lookups or {}

    def resolve(nav_name: str, key_name: str, lookup_key: str, *fallback_nav: str) -> Optional[str]:
        desc = _nav_description(row, nav_name, *fallback_nav)
        if desc:
            return desc
        key = _guid(_get(row, key_name))
        if not key:
            return None
        return lookups.get(lookup_key, {}).get(key)

    assay = resolve("Проба", "Проба_Key", "assay") or _get(row, "Металл")
    metal_color = resolve("ЮС_ЦветМеталла", "ЮС_ЦветМеталла_Key", "metal_color", "ГруппаЦвета")
    wear_type = resolve("ТипИзделия", "ТипИзделия_Key", "wear_type")
    lts = resolve("ЮС_ЖЦТ", "ЮС_ЖЦТ_Key", "lts")
    direction = resolve("КС_Направление", "КС_Направление_Key", "direction")
    article = normalize_article(_get(row, "Артикул", "Code"))
    name = _get(row, "Description", "НаименованиеПолное", "Наименование")

    return {
        "source_id": source_id,
        "onec_ref": str(_get(row, "Ref_Key", "Ref", default="")),
        "article": article,
        "barcode": normalize_article(_get(row, "Штрихкод", "Barcode")),
        "name": name.strip() if isinstance(name, str) else name,
        "assay": assay,
        "metal_color": metal_color,
        "wear_type": wear_type,
        "lts": lts,
        "lts_date": parse_date(_get(row, "ДатаИзмененияЖЦТ", "LTSDate")),
        "weight": None,
        "characteristics": None,
        "direction": direction,
        "is_promo": as_bool(_get(row, "Акция", "УчаствуетВАкции", default=False)),
        "is_weighted": as_bool(_get(row, "Весовой", default=False)),
        "modified_at": None,  # Modified absent in this config; DataVersion is opaque
    }


def map_counterparty(row: dict[str, Any], source_id: str) -> dict[str, Any]:
    work_type = _get(row, "ТипРаботыКонтрагента", "ТипРаботы", "WorkType")
    return {
        "source_id": source_id,
        "onec_ref": str(_get(row, "Ref_Key", "Ref", default="")),
        "name": str(_get(row, "Description", "НаименованиеПолное", "Наименование", default="")),
        "head_counterparty_onec_ref": _guid(_get(row, "ГоловнойКонтрагент_Key")),
        "parent_onec_ref": _guid(_get(row, "Parent_Key")),
        "is_folder": as_bool(_get(row, "IsFolder", default=False)),
        # promo flag not on catalog in this base; filled later from actions / manual
        "is_promo": as_bool(_get(row, "УчаствуетВАкции", default=False)),
        "work_type": work_type,
        "work_type_percent": as_decimal(_get(row, "ПроцентТипаРаботы", default=0), "0"),
        "shops": [],
    }


def map_shop(row: dict[str, Any]) -> tuple[Optional[str], str]:
    """Return (owner_counterparty_ref, shop_name)."""
    owner = _guid(_get(row, "Owner_Key"))
    name = str(_get(row, "Description", "Code", default="") or "")
    return owner, name


NOM_SELECT = (
    "Ref_Key,Description,Артикул,Акция,Весовой,Code,IsFolder,DeletionMark,"
    "КС_Направление_Key,ЮС_ЖЦТ_Key,ЮС_ЦветМеталла_Key,ТипИзделия_Key,Проба_Key,Металл"
)
# $expand on these nav props returns null Description on live publication — resolve via catalogs.
NOM_EXPAND = None

# Target catalogs from $metadata associations (plural entity names).
DIRECTION_CATALOG = "Catalog_КС_Направления"
WEAR_TYPE_CATALOG = "Catalog_ТипыИзделий"
ASSAY_CATALOG = "Catalog_Пробы"
METAL_COLOR_CATALOG = "Catalog_ЮС_ЦветМеталла"
LTS_CATALOG = "Catalog_ЮС_ЖЦТ"

CP_SELECT = (
    "Ref_Key,Description,IsFolder,DeletionMark,ГоловнойКонтрагент_Key,Parent_Key,"
    "ТипРаботыКонтрагента,ПроцентТипаРаботы,НаименованиеПолное"
)

# Real entity name in this configuration (not ПоступлениеИзПроизводства)
PRODUCTION_RECEIPT_ENTITY = "Document_ПоступлениеПродукцииИзПроизводства"

REALIZATION_ENTITY = "Document_РеализацияТоваровУслуг"
RETURN_ENTITY = "Document_ВозвратТоваровОтПокупателя"
CLIENT_ORDER_ENTITY = "Document_ЗаказКлиента"
WAREHOUSE_CATALOG = "Catalog_Склады"
LTS_HISTORY_REGISTER = "InformationRegister_ИсторияИзмененияЖЦТ"

# Date $filter is rejected by this publication — filter client-side.
DOC_MIN_DATE_DEFAULT = date(2023, 1, 1)


def line_series(row: dict[str, Any]) -> Optional[str]:
    """Series GUID/name from tabular line (СерияНоменклатуры_Key on live metadata)."""
    value = _get(row, "СерияНоменклатуры_Key", "СерияНоменклатуры", "Серия", "Series")
    return _guid(value) or (str(value) if value else None)
