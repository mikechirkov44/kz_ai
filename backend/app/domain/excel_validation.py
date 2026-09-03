from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any, Optional


REQUIRED_COLUMNS_SALES = ("головной контрагент", "артикул", "магазин", "количество", "цена")
REQUIRED_COLUMNS_STOCKS = ("головной контрагент", "артикул", "магазин", "количество")


@dataclass
class RowError:
    row: int
    field: str
    message: str

    def as_dict(self) -> dict[str, Any]:
        return {"row": self.row, "field": self.field, "message": self.message}


@dataclass
class ParsedUploadRow:
    row_number: int
    head_counterparty_name: str
    article: str
    shop: Optional[str]
    quantity: Decimal
    price: Optional[Decimal] = None


@dataclass
class ValidationResult:
    rows: list[ParsedUploadRow] = field(default_factory=list)
    errors: list[RowError] = field(default_factory=list)

    @property
    def status(self) -> str:
        if not self.errors:
            return "success"
        if self.rows:
            return "partial"
        return "error"


def _norm_header(value: Any) -> str:
    text = str(value or "").strip().lower().replace("ё", "е")
    text = text.replace("/", " ").replace("\\", " ")
    while "  " in text:
        text = text.replace("  ", " ")
    return text


def map_headers(headers: list[Any]) -> dict[str, int]:
    mapping: dict[str, int] = {}
    for idx, raw in enumerate(headers):
        h = _norm_header(raw)
        if "головн" in h and "контрагент" in h:
            mapping["head"] = idx
        elif "артикул" in h or h in {"шк", "штрихкод"} or "штрих" in h:
            mapping["article"] = idx
        elif "магазин" in h:
            mapping["shop"] = idx
        elif "количество" in h or h == "кол-во":
            mapping["qty"] = idx
        elif "цена" in h:
            mapping["price"] = idx
    return mapping


def validate_upload_dataframe(
    records: list[dict[str, Any]],
    *,
    known_counterparties: dict[str, Any],
    known_articles: set[str],
    counterparty_shops: dict[str, set[str]],
    require_price: bool = False,
) -> ValidationResult:
    """
    Batch validation: collect all errors.
    `known_counterparties` maps normalized name -> id
    `known_articles` articles and barcodes
    """
    result = ValidationResult()
    if not records:
        result.errors.append(RowError(0, "file", "Файл пуст"))
        return result

    headers = list(records[0].keys())
    colmap = map_headers(headers)
    if "head" not in colmap or "article" not in colmap or "qty" not in colmap:
        result.errors.append(
            RowError(0, "file", "Не найдены обязательные колонки: Головной контрагент, Артикул/ШК, Количество")
        )
        return result

    head_names: list[str] = []
    for i, rec in enumerate(records, start=2):  # Excel-like row (header=1)
        values = list(rec.values())
        head = str(values[colmap["head"]] or "").strip()
        article = str(values[colmap["article"]] or "").strip()
        shop_raw = values[colmap["shop"]] if "shop" in colmap else None
        shop = str(shop_raw).strip() if shop_raw not in (None, "") else None
        qty_raw = values[colmap["qty"]]
        price_raw = values[colmap["price"]] if "price" in colmap else None

        row_ok = True
        if not head:
            result.errors.append(RowError(i, "head_counterparty", "Не заполнен головной контрагент"))
            row_ok = False
        elif head.lower() not in {k.lower(): k for k in known_counterparties}:
            # case-insensitive lookup
            found = next((k for k in known_counterparties if k.lower() == head.lower()), None)
            if not found:
                result.errors.append(
                    RowError(i, "head_counterparty", f"Контрагент «{head}» не существует в 1С")
                )
                row_ok = False
            else:
                head = found
        else:
            head = next(k for k in known_counterparties if k.lower() == head.lower())

        if head:
            head_names.append(head)

        if not article:
            result.errors.append(RowError(i, "article", "Не заполнен артикул/ШК"))
            row_ok = False
        elif article not in known_articles:
            result.errors.append(RowError(i, "article", f"Артикул «{article}» не найден в 1С"))
            row_ok = False

        if shop and head in counterparty_shops and shop not in counterparty_shops[head]:
            result.errors.append(
                RowError(i, "shop", f'Магазин "{shop}" не входит в список магазинов контрагента')
            )
            row_ok = False

        try:
            qty = Decimal(str(qty_raw).replace(",", ".").replace(" ", ""))
            if qty <= 0 or qty != qty.to_integral_value():
                raise InvalidOperation
        except (InvalidOperation, ValueError, TypeError):
            result.errors.append(RowError(i, "quantity", "Количество должно быть целым числом > 0"))
            row_ok = False
            qty = Decimal(0)

        price: Optional[Decimal] = None
        if price_raw not in (None, ""):
            try:
                price = Decimal(str(price_raw).replace(",", ".").replace(" ", "").replace("\xa0", ""))
            except (InvalidOperation, ValueError, TypeError):
                result.errors.append(RowError(i, "price", "Некорректная цена продажи"))
                row_ok = False
        elif require_price:
            result.errors.append(RowError(i, "price", "Не заполнена цена продажи"))
            row_ok = False

        if row_ok:
            result.rows.append(
                ParsedUploadRow(
                    row_number=i,
                    head_counterparty_name=head,
                    article=article,
                    shop=shop,
                    quantity=qty,
                    price=price,
                )
            )

    if head_names and len({h.lower() for h in head_names}) > 1:
        result.errors.insert(
            0,
            RowError(0, "head_counterparty", "Головной контрагент должен быть одинаков во всём файле"),
        )
        result.rows.clear()

    return result
