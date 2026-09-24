"""Field extractors aligned with live docs/odata-metadata.xml (test3_asil)."""

from __future__ import annotations

import re
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


def _optional_decimal(value: Any) -> Optional[Decimal]:
    if value is None or value == "":
        return None
    try:
        return as_decimal(value)
    except Exception:  # noqa: BLE001
        return None


def as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, dict):
        for key in ("Description", "Value", "value", "#value"):
            if key in value:
                return as_bool(value[key])
        return False
    text = str(value or "").strip().casefold()
    return text in {"1", "true", "да", "истина", "yes"}


def _kit_label(row: dict[str, Any], lookups: dict[str, dict[str, str]]) -> Optional[str]:
    nav = row.get("Комплект")
    if isinstance(nav, dict):
        for key in ("Артикул", "Code", "Description"):
            value = nav.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    desc = _nav_description(row, "Комплект")
    if desc:
        return desc
    key = _guid(_get(row, "Комплект_Key"))
    if not key:
        return None
    return lookups.get("kit", {}).get(key)


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
    appearance = resolve("ЮС_ВнешнийВид", "ЮС_ВнешнийВид_Key", "appearance")
    insert_category = resolve("КС_КатегорияВставок", "КС_КатегорияВставок_Key", "insert_category")
    default_characteristic = resolve(
        "ЮС_ХарактеристикаПоУмолчанию",
        "ЮС_ХарактеристикаПоУмолчанию_Key",
        "default_characteristic",
    )
    kit_article = _kit_label(row, lookups)
    article = normalize_article(_get(row, "Артикул", "Code"))
    name = _get(row, "Description", "НаименованиеПолное", "Наименование")
    model = _get(row, "Модель")
    insert = _get(row, "Вставка")
    comment = _get(row, "Комментарий")
    char_parts: list[str] = []
    if model:
        char_parts.append(f"Модель: {model}")
    if appearance:
        char_parts.append(f"Внешний вид: {appearance}")
    if insert_category:
        char_parts.append(f"Категория вставок: {insert_category}")
    if insert:
        char_parts.append(f"Вставка: {insert}")
    if comment:
        char_parts.append(str(comment))

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
        "weight": _optional_decimal(_get(row, "СреднийВес", "AverageWeight")),
        "characteristics": "; ".join(char_parts) or None,
        "direction": direction,
        "kit_article": kit_article,
        "card_created_at": parse_date(_get(row, "ЮС_ДатаСоздания")),
        "default_characteristic": default_characteristic,
        "is_promo": as_bool(_get(row, "Акция", "УчаствуетВАкции", default=False)),
        "is_weighted": as_bool(_get(row, "Весовой", default=False)),
        "modified_at": None,  # Modified absent in this config; DataVersion is opaque
    }


def _optional_text(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text == EMPTY_GUID or text.startswith("0001-01-01"):
        return None
    return text


LEGAL_STATUS_LABELS = {
    "ФизЛицо": "Физ. лицо",
    "ЮрЛицо": "Юр. лицо",
    "ФизическоеЛицо": "Физ. лицо",
    "ЮридическоеЛицо": "Юр. лицо",
}


def legal_status_label(value: Any) -> Optional[str]:
    text = _optional_text(value)
    if not text:
        return None
    return LEGAL_STATUS_LABELS.get(text, text)


MANAGER_KEY_FIELDS = (
    "ОсновнойМенеджер_Key",
    "Ответственный_Key",
    "Менеджер_Key",
    "ЮС_Менеджер_Key",
)
MANAGER_TEXT_FIELDS = ("ОсновнойМенеджер", "Ответственный", "Менеджер")


def _is_guid(value: str) -> bool:
    hexed = value.strip().replace("-", "")
    return len(hexed) == 32 and all(char in "0123456789abcdefABCDEF" for char in hexed)


_MANAGER_NAME_NEEDLES = ("менедж", "ответств", "manager")


def _is_manager_field_name(name: str) -> bool:
    folded = name.casefold()
    return any(needle in folded for needle in _MANAGER_NAME_NEEDLES)


def _user_key(value: str) -> str:
    return value.strip().replace("-", "").lower()


def _user_index(users: Optional[dict[str, str]]) -> dict[str, str]:
    indexed: dict[str, str] = {}
    for key, name in (users or {}).items():
        text = str(name or "").strip()
        if not key or not text:
            continue
        indexed[_user_key(str(key))] = text
    return indexed


def manager_name_from_row(row: dict[str, Any], users: Optional[dict[str, str]] = None) -> Optional[str]:
    """Responsible manager from a counterparty row, as text or a user-catalog ref."""
    indexed = _user_index(users)
    for field, value in row.items():
        if not _is_manager_field_name(str(field)) or str(field).endswith("_Key"):
            continue
        text = _optional_text(value)
        if text and not _is_guid(text):
            return text
    for field, value in row.items():
        if not _is_manager_field_name(str(field)):
            continue
        key = _guid(value)
        if key and _is_guid(key):
            name = indexed.get(_user_key(key))
            if name:
                return name
    return None


def manager_name_from_properties(
    extra: Optional[dict[str, Any]],
    users: Optional[dict[str, str]] = None,
) -> Optional[str]:
    """Extra property whose name contains «менеджер» or «ответствен»."""
    if not extra:
        return None
    indexed = _user_index(users)
    for label, value in extra.items():
        if not _is_manager_field_name(str(label)):
            continue
        text = str(value or "").strip()
        if not text or text.casefold() in {"да", "нет"}:
            continue
        if _is_guid(text):
            return indexed.get(_user_key(text))
        return text
    return None


def manager_fields_from_metadata(xml: str) -> list[str]:
    """Manager properties published on Catalog_Контрагенты."""
    type_match = re.search(
        r'<EntitySet\b[^>]*\bName="Catalog_Контрагенты"[^>]*\bEntityType="([^"]+)"',
        xml,
    )
    if not type_match:
        type_match = re.search(
            r'<EntitySet\b[^>]*\bEntityType="([^"]+)"[^>]*\bName="Catalog_Контрагенты"',
            xml,
        )
    type_name = type_match.group(1).split(".")[-1] if type_match else "Catalog_Контрагенты"
    block_match = re.search(
        rf'<EntityType\b[^>]*\bName="{re.escape(type_name)}"[^>]*>(.*?)</EntityType>',
        xml,
        flags=re.DOTALL,
    )
    if not block_match:
        return []
    block = block_match.group(1)
    found: list[str] = []
    for name in re.findall(r'<Property\b[^>]*\bName="([^"]+)"', block):
        if _is_manager_field_name(name):
            found.append(name)
    for name in re.findall(r'<NavigationProperty\b[^>]*\bName="([^"]+)"', block):
        if not _is_manager_field_name(name):
            continue
        found.append(name if name.endswith("_Key") else f"{name}_Key")
    return list(dict.fromkeys(found))


def map_counterparty(
    row: dict[str, Any],
    source_id: str,
    *,
    lookups: Optional[dict[str, dict[str, str]]] = None,
) -> dict[str, Any]:
    work_type = _get(row, "ТипРаботыКонтрагента", "ТипРаботы", "WorkType")
    lookups = lookups or {}
    contact_key = _guid(_get(row, "ОсновноеКонтактноеЛицо_Key"))
    director_name = lookups.get("contacts", {}).get(contact_key) if contact_key else None
    return {
        "source_id": source_id,
        "onec_ref": str(_get(row, "Ref_Key", "Ref", default="")),
        "name": str(_get(row, "Description", "НаименованиеПолное", "Наименование", default="")),
        "head_counterparty_onec_ref": _guid(_get(row, "ГоловнойКонтрагент_Key")),
        "parent_onec_ref": _guid(_get(row, "Parent_Key")),
        "is_folder": as_bool(_get(row, "IsFolder", default=False)),
        # promo flag is extra property «Участвует в акции», not a catalog attribute
        "is_promo": as_bool(_get(row, "УчаствуетВАкции", default=False)),
        "work_type": work_type,
        "work_type_percent": as_decimal(_get(row, "ПроцентТипаРаботы", default=0), "0"),
        "shops": [],
        "code": _optional_text(_get(row, "Code")),
        "full_name": _optional_text(_get(row, "НаименованиеПолное")),
        "legal_status": legal_status_label(_get(row, "ЮрФизЛицо")),
        "is_buyer": as_bool(_get(row, "Покупатель", default=False)),
        "is_supplier": as_bool(_get(row, "Поставщик", default=False)),
        "iin": _optional_text(_get(row, "ИдентификационныйКодЛичности")),
        "identity_document": _optional_text(_get(row, "ДокументУдостоверяющийЛичность")),
        "rnn": _optional_text(_get(row, "РНН")),
        "sik": _optional_text(_get(row, "СИК")),
        "okpo": _optional_text(_get(row, "КодПоОКПО")),
        "kbe": _optional_text(_get(row, "КБЕ")),
        "work_schedule": _optional_text(_get(row, "РасписаниеРаботыСтрокой")),
        "comment": _optional_text(_get(row, "Комментарий")),
        "director_name": director_name,
        "onec_manager_name": manager_name_from_row(row, lookups.get("users")),
    }


def map_shop(row: dict[str, Any]) -> tuple[Optional[str], str]:
    """Return (owner_counterparty_ref, shop_name)."""
    owner = _guid(_get(row, "Owner_Key"))
    name = str(_get(row, "Description", "Code", default="") or "")
    return owner, name


NOM_SELECT = (
    "Ref_Key,Description,Артикул,Акция,Весовой,СреднийВес,Модель,Вставка,Комментарий,"
    "Code,IsFolder,DeletionMark,Комплект_Key,ЮС_ДатаСоздания,ЮС_ХарактеристикаПоУмолчанию_Key,"
    "КС_Направление_Key,ЮС_ЖЦТ_Key,ЮС_ЦветМеталла_Key,ТипИзделия_Key,Проба_Key,Металл,"
    "ЮС_ВнешнийВид_Key,КС_КатегорияВставок_Key"
)
APPEARANCE_CATALOG = "Catalog_ЮС_ВнешнийВид"
INSERT_CATEGORY_CATALOG = "Catalog_КС_КатегорииВставок"
KIT_CATALOG = "Catalog_Комплекты"
DEFAULT_CHAR_CATALOG = "Catalog_ХарактеристикиНоменклатуры"
# $expand on these nav props returns null Description on live publication — resolve via catalogs.
NOM_EXPAND = None

# Target catalogs from $metadata associations (plural entity names).
DIRECTION_CATALOG = "Catalog_КС_Направления"
WEAR_TYPE_CATALOG = "Catalog_ТипыИзделий"
ASSAY_CATALOG = "Catalog_Пробы"
METAL_COLOR_CATALOG = "Catalog_ЮС_ЦветМеталла"
LTS_CATALOG = "Catalog_ЮС_ЖЦТ"

CP_SELECT = (
    "Ref_Key,Description,IsFolder,DeletionMark,Code,ГоловнойКонтрагент_Key,Parent_Key,"
    "ТипРаботыКонтрагента,ПроцентТипаРаботы,НаименованиеПолное,ЮрФизЛицо,Покупатель,Поставщик,"
    "ИдентификационныйКодЛичности,ДокументУдостоверяющийЛичность,РНН,СИК,КодПоОКПО,КБЕ,"
    "РасписаниеРаботыСтрокой,Комментарий,ОсновноеКонтактноеЛицо_Key"
)
CONTACT_PERSON_CATALOG = "Catalog_КонтактныеЛица"
PROPERTY_VALUE_CATALOG = "Catalog_ЗначенияСвойствОбъектов"

# Real entity name in this configuration (not ПоступлениеИзПроизводства)
PRODUCTION_RECEIPT_ENTITY = "Document_ПоступлениеПродукцииИзПроизводства"

REALIZATION_ENTITY = "Document_РеализацияТоваровУслуг"
RETURN_ENTITY = "Document_ВозвратТоваровОтПокупателя"
CLIENT_ORDER_ENTITY = "Document_ЗаказКлиента"
# Asil OData has no КонтрагентПолучатель on this document; recipient falls back to Контрагент_Key.
CLIENT_ORDER_SELECT = (
    "Ref_Key,Number,Date,Posted,DeletionMark,Контрагент_Key,Склад_Key"
)
WAREHOUSE_CATALOG = "Catalog_Склады"
LTS_HISTORY_REGISTER = "InformationRegister_ИсторияИзмененияЖЦТ"
OBJECT_PROPERTIES_CHART = "ChartOfCharacteristicTypes_СвойстваОбъектов"
OBJECT_PROPERTY_VALUES_REGISTER = "InformationRegister_ЗначенияСвойствОбъектов"
IGNORE_TURNOVER_PROPERTY_NAME = "Не учитывать при оборачиваемости"
IGNORE_TURNOVER_PROPERTY_CODE = "00125"
PROMO_PARTICIPATION_PROPERTY_NAME = "Участвует в акции"

# Date $filter is rejected by this publication — filter client-side.
DOC_MIN_DATE_DEFAULT = date(2023, 1, 1)


def is_ignore_turnover_property(description: Any, code: Any = None) -> bool:
    name = str(description or "").strip()
    if name == IGNORE_TURNOVER_PROPERTY_NAME:
        return True
    return str(code or "").strip() == IGNORE_TURNOVER_PROPERTY_CODE


def is_promo_participation_property(description: Any, code: Any = None) -> bool:
    return str(description or "").strip() == PROMO_PARTICIPATION_PROPERTY_NAME


def classify_property_object(object_type: Any) -> Optional[str]:
    """Map 1C Объект_Type to realization / return / counterparty / nomenclature."""
    text = str(object_type or "")
    if "РеализацияТоваровУслуг" in text:
        return "realization"
    if "ВозвратТоваровОтПокупателя" in text:
        return "return"
    if "Catalog_Контрагенты" in text or text.endswith("Контрагенты"):
        return "counterparty"
    if "Номенклатура" in text:
        return "nomenclature"
    return None


def find_property_key_by_name(
    rows: Any, name: str, *, code: Optional[str] = None
) -> Optional[str]:
    expected = name.strip()
    expected_code = (code or "").strip()
    for row in rows:
        desc = str(_get(row, "Description") or "").strip()
        row_code = str(_get(row, "Code") or "").strip()
        if desc == expected or (expected_code and row_code == expected_code):
            return _guid(_get(row, "Ref_Key"))
    return None


def find_ignore_turnover_property_key(rows: Any) -> Optional[str]:
    return find_property_key_by_name(
        rows, IGNORE_TURNOVER_PROPERTY_NAME, code=IGNORE_TURNOVER_PROPERTY_CODE
    )


def collect_true_object_refs(rows: Any, property_key: str) -> dict[str, set[str]]:
    """True-valued property rows grouped by object kind."""
    buckets: dict[str, set[str]] = {
        "realization": set(),
        "return": set(),
        "counterparty": set(),
        "nomenclature": set(),
    }
    for row in rows:
        if _guid(_get(row, "Свойство_Key")) != property_key:
            continue
        if not as_bool(_get(row, "Значение", default=False)):
            continue
        obj_ref = _guid(_get(row, "Объект"))
        if not obj_ref:
            continue
        kind = classify_property_object(_get(row, "Объект_Type"))
        if kind in buckets:
            buckets[kind].add(obj_ref)
    return buckets


def collect_ignore_turnover_refs(
    rows: Any, property_key: str
) -> tuple[set[str], set[str]]:
    """True-valued property rows → (realization refs, return refs)."""
    buckets = collect_true_object_refs(rows, property_key)
    return buckets["realization"], buckets["return"]


SKIP_COUNTERPARTY_EXTRA_PROPERTIES = frozenset({PROMO_PARTICIPATION_PROPERTY_NAME})


def property_chart_names(rows: Any) -> dict[str, str]:
    names: dict[str, str] = {}
    for row in rows:
        key = _guid(_get(row, "Ref_Key"))
        label = _optional_text(_get(row, "Description"))
        if key and label:
            names[key] = label
    return names


def object_property_text(value: Any, lookups: Optional[dict[str, str]] = None) -> Optional[str]:
    lookups = lookups or {}
    if value is None:
        return None
    if isinstance(value, bool):
        return "да" if value else None
    if isinstance(value, (int, float, Decimal)):
        if value == 0:
            return None
        if float(value).is_integer():
            return str(int(value))
        return str(value)
    text = _optional_text(value)
    if not text:
        return None
    guid = _guid(text)
    if guid and guid in lookups:
        return lookups[guid]
    lowered = text.lower()
    if lowered in {"false", "нет", "0"}:
        return None
    return text


def collect_counterparty_extra_properties(
    rows: Any,
    *,
    property_names: dict[str, str],
    value_names: Optional[dict[str, str]] = None,
    skip_names: frozenset[str] = SKIP_COUNTERPARTY_EXTRA_PROPERTIES,
) -> dict[str, dict[str, str]]:
    """Filled extra properties on counterparties, keyed by onec_ref then label."""
    result: dict[str, dict[str, str]] = {}
    for row in rows:
        if classify_property_object(_get(row, "Объект_Type")) != "counterparty":
            continue
        prop_key = _guid(_get(row, "Свойство_Key"))
        label = property_names.get(prop_key or "")
        if not label or label in skip_names:
            continue
        text = object_property_text(_get(row, "Значение"), value_names)
        if not text:
            continue
        obj_ref = _guid(_get(row, "Объект"))
        if not obj_ref:
            continue
        result.setdefault(obj_ref, {})[label] = text
    return result


def line_series(row: dict[str, Any]) -> Optional[str]:
    """Series GUID/name from tabular line (СерияНоменклатуры_Key on live metadata)."""
    value = _get(row, "СерияНоменклатуры_Key", "СерияНоменклатуры", "Серия", "Series")
    return _guid(value) or (str(value) if value else None)
