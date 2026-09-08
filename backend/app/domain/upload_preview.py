from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Mapping, Sequence

PREVIEW_ROW_LIMIT = 200


def preview_cell(value: Any) -> str | int | float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if value != value or value in {float("inf"), float("-inf")}:
            return None
        if value.is_integer():
            return int(value)
        return round(value, 6)
    if isinstance(value, Decimal):
        if not value.is_finite():
            return None
        as_int = value.to_integral_value()
        if as_int == value:
            return int(as_int)
        return float(value)
    if isinstance(value, datetime):
        return value.isoformat(sep=" ", timespec="seconds")
    if isinstance(value, date):
        return value.isoformat()
    text = str(value).strip()
    if not text or text.lower() in {"nan", "nat", "none", "null"}:
        return None
    return text


def normalize_upload_errors(raw: object) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    items: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        try:
            row = int(item.get("row") or 0)
        except (TypeError, ValueError):
            row = 0
        items.append(
            {
                "row": row,
                "field": str(item.get("field") or "").strip(),
                "message": str(item.get("message") or "").strip(),
            }
        )
    return items


def spreadsheet_preview(
    columns: Sequence[Any],
    records: Sequence[Mapping[Any, Any]],
    *,
    limit: int = PREVIEW_ROW_LIMIT,
) -> dict[str, Any]:
    cols = [str(col) for col in columns]
    cap = max(int(limit), 0)
    shown = list(records)[:cap]
    rows = [{col: preview_cell(row.get(col)) for col in cols} for row in shown]
    return {
        "columns": cols,
        "rows": rows,
        "total_rows": len(records),
        "shown_rows": len(rows),
    }
