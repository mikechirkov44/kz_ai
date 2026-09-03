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

DIRECTION_FILTER = ("ИМПЕРИАЛ", "ИМПЕРИАЛ KZ", "БЕЛЛА", "МиАмор")
EXCLUDED_WAREHOUSES = ("ОК-бескаменка", "ОК с бриллиантами")
INTERNAL_WAREHOUSES = ("Mi Amor Склад", "Asil Tas Склад", "Asil Tas (Склад)")

MOTIVATION_GRADES: list[tuple[int | None, int, str]] = [
    # (max_inclusive_price, bonus, label) — price ranges per TZ
    (100_000, 1_500, "до 100к"),
    (200_000, 2_500, "100–200к"),
    (350_000, 4_000, "200–350к"),
    (500_000, 5_000, "350–500к"),
    (None, 6_000, "от 500к"),
]
PROMO_MOTIVATION_BONUS = 6_000
DEFAULT_PRICE_MARKUP = 1.70
