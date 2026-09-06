from __future__ import annotations

from datetime import date
from typing import Any, Iterable, Optional

from app.constants import UploadType

MANUAL_UPLOAD_TYPES = frozenset(
    {
        UploadType.SALES.value,
        UploadType.STOCKS.value,
        UploadType.BOTH.value,
        UploadType.PROMO_MOTIVATION.value,
    }
)
MANUAL_FILE_NAME = "Ручной ввод"
MAX_MANUAL_ROWS = 500


def records_from_manual_rows(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Map JSON rows to the same column names as the Excel sales template."""
    records: list[dict[str, Any]] = []
    for row in rows:
        records.append(
            {
                "Головной контрагент": row.get("counterparty"),
                "Артикул": row.get("article"),
                "Магазин": row.get("shop") or None,
                "Количество": row.get("quantity"),
                "Цена продажи": row.get("price"),
            }
        )
    return records


def require_manual_period(
    upload_type: str,
    *,
    period_year: Optional[int],
    period_month: Optional[int],
    stock_date: Optional[date],
) -> None:
    if upload_type not in MANUAL_UPLOAD_TYPES:
        raise ValueError("Для ручного ввода доступны продажи, остатки и доп. мотивация")
    if upload_type in {UploadType.SALES.value, UploadType.BOTH.value} and (
        period_year is None or period_month is None
    ):
        raise ValueError("Для продаж нужны год и месяц")
    if upload_type in {UploadType.STOCKS.value, UploadType.BOTH.value} and stock_date is None:
        raise ValueError("Для остатков нужна дата остатков")
