from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any

from app.domain.excel_validation import RowError, _norm_header, normalize_counterparty_name


@dataclass
class ParsedPlanRow:
    row_number: int
    head_counterparty_name: str
    year: int
    quarter: int
    plan_value: Decimal


@dataclass
class PlanUploadResult:
    rows: list[ParsedPlanRow] = field(default_factory=list)
    errors: list[RowError] = field(default_factory=list)

    @property
    def status(self) -> str:
        if not self.errors:
            return "success"
        if self.rows:
            return "partial"
        return "error"


def map_plan_headers(headers: list[Any]) -> dict[str, int]:
    mapping: dict[str, int] = {}
    for idx, raw in enumerate(headers):
        h = _norm_header(raw)
        if "контрагент" in h:
            mapping["head"] = idx
        elif h == "год":
            mapping["year"] = idx
        elif "квартал" in h:
            mapping["quarter"] = idx
        elif "штук" in h or "количество" in h or "кол-во" in h or "план" in h:
            mapping.setdefault("qty", idx)
    return mapping


def parse_quarterly_plan_records(
    records: list[dict[str, Any]],
    *,
    known_counterparties: dict[str, Any],
) -> PlanUploadResult:
    result = PlanUploadResult()
    if not records:
        result.errors.append(RowError(0, "file", "Файл пуст"))
        return result
    headers = list(records[0].keys())
    colmap = map_plan_headers(headers)
    missing = [name for name in ("head", "year", "quarter", "qty") if name not in colmap]
    if missing:
        result.errors.append(
            RowError(0, "file", "Нужны колонки: Головной контрагент, Год, Квартал, Кол-во штук")
        )
        return result

    known_lower = {k.lower(): k for k in known_counterparties}
    for i, rec in enumerate(records, start=2):
        values = list(rec.values())
        head = normalize_counterparty_name(values[colmap["head"]])
        year_raw = values[colmap["year"]]
        quarter_raw = values[colmap["quarter"]]
        qty_raw = values[colmap["qty"]]
        row_ok = True
        if not head:
            result.errors.append(RowError(i, "head_counterparty", "Не заполнен головной контрагент"))
            row_ok = False
        else:
            canonical = known_lower.get(head.lower())
            if not canonical:
                result.errors.append(
                    RowError(i, "head_counterparty", f"Контрагент «{head}» не существует в 1С")
                )
                row_ok = False
            else:
                head = canonical
        try:
            year = int(year_raw)
        except (TypeError, ValueError):
            result.errors.append(RowError(i, "year", "Некорректный год"))
            row_ok = False
            year = 0
        try:
            quarter = int(quarter_raw)
        except (TypeError, ValueError):
            result.errors.append(RowError(i, "quarter", "Некорректный квартал"))
            row_ok = False
            quarter = 0
        if quarter and quarter not in {1, 2, 3, 4}:
            result.errors.append(RowError(i, "quarter", "Квартал должен быть 1–4"))
            row_ok = False
        try:
            qty = Decimal(str(qty_raw).replace(",", ".").replace(" ", "").replace("\xa0", ""))
        except (InvalidOperation, TypeError, AttributeError):
            result.errors.append(RowError(i, "plan_value", "Некорректное количество"))
            row_ok = False
            qty = Decimal(0)
        if qty < 0:
            result.errors.append(RowError(i, "plan_value", "Количество не может быть отрицательным"))
            row_ok = False
        if row_ok:
            result.rows.append(
                ParsedPlanRow(
                    row_number=i,
                    head_counterparty_name=head,
                    year=year,
                    quarter=quarter,
                    plan_value=qty,
                )
            )
    return result
