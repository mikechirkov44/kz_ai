from datetime import date
from enum import StrEnum


class UserRole(StrEnum):
    ADMIN = "admin"
    REGIONAL_DIRECTOR = "regional_director"
    MANAGER = "manager"
    ANALYTIC = "analytic"


class WorkType(StrEnum):
    HOLD = "hold"  # Удержание
    GROWTH = "growth"  # Рост / Прирост
    DECLINE = "decline"  # Падение


class UploadType(StrEnum):
    SALES = "sales"
    STOCKS = "stocks"
    BOTH = "both"
    PROMO_MOTIVATION = "promo_motivation"
    QUARTERLY_PLANS = "quarterly_plans"


class UploadStatus(StrEnum):
    SUCCESS = "success"
    PARTIAL = "partial"
    ERROR = "error"


class SyncStatus(StrEnum):
    IDLE = "idle"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"


SOURCE_ASIL = "asil"
SOURCE_MIAMOR = "miamor"

# Excel «Перенос в ИИ»: номенклатура только по направлениям своей базы.
DIRECTION_FILTER_BY_SOURCE: dict[str, frozenset[str]] = {
    SOURCE_ASIL: frozenset({"ИМПЕРИАЛ", "ИМПЕРИАЛ KZ"}),
    SOURCE_MIAMOR: frozenset({"БЕЛЛА", "МиАмор"}),
}
DIRECTION_FILTER = frozenset().union(*DIRECTION_FILTER_BY_SOURCE.values())


def allowed_directions_for_source(source_id: str) -> frozenset[str]:
    """Per-base allowlist; unknown source_id → union of all known directions."""
    return DIRECTION_FILTER_BY_SOURCE.get(source_id, DIRECTION_FILTER)

EXCLUDED_WAREHOUSES = ("ОК-бескаменка", "ОК с бриллиантами")
INTERNAL_WAREHOUSES = ("Mi Amor Склад", "Asil Tas Склад", "Asil Tas (Склад)")
# Excel «Перенос в ИИ»: контрагенты только из папки «Покупатели» (и вложенные).
BUYERS_FOLDER_NAME = "Покупатели"

# OData objects tracked in sync_state (placeholder rows so dates can be set before first run).
SYNC_ENTITIES: tuple[str, ...] = (
    "nomenclature",
    "counterparty",
    "lts_history",
    "realization",
    "return_doc",
    "client_order",
    "production_receipt",
    "object_properties",
)

# Client-side date cutoff (1C $filter by Date is rejected). Empty since_date = no cutoff.
SYNC_DATE_FILTER_ENTITIES: frozenset[str] = frozenset(
    {
        "realization",
        "return_doc",
        "client_order",
        "production_receipt",
        "lts_history",
    }
)

SYNC_SINCE_DEFAULTS: dict[str, date] = {
    "realization": date(2023, 1, 1),
    "return_doc": date(2023, 1, 1),
    "client_order": date(2023, 1, 1),
    "production_receipt": date(2025, 1, 1),
    "lts_history": date(2023, 1, 1),
}


def default_since_date(entity: str) -> date | None:
    return SYNC_SINCE_DEFAULTS.get(entity)


def effective_since(min_date: date | None, state_since: date | None) -> date | None:
    """Explicit caller override wins; otherwise the stored admin date (None = no cutoff)."""
    return min_date if min_date is not None else state_since


def is_before_since(value: date | None, since: date | None) -> bool:
    """Skip rows with a missing date, or earlier than the cutoff. None cutoff keeps dated rows."""
    if value is None:
        return True
    if since is None:
        return False
    return value < since


MOTIVATION_GRADES: list[tuple[int | None, int, str]] = [
    # (max_inclusive_price, bonus, label) — как в отчёте 1С «Мотивационные акции»
    (100_000, 1_500, "1 — 100 000"),
    (200_000, 2_500, "100 001 — 200 000"),
    (350_000, 4_000, "200 001 — 350 000"),
    (500_000, 5_000, "350 001 — 500 000"),
    (None, 6_000, "500 001 — 999 999 999"),
]
PROMO_MOTIVATION_BONUS = 6_000
PROMO_MOTIVATION_GRADE = "Доп. мотивация"
DEFAULT_PRICE_MARKUP = 1.70
