from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any, Optional

from app.domain.articles import normalize_article


REQUIRED_COLUMNS_SALES = ("головной контрагент", "артикул", "магазин", "количество", "цена")
REQUIRED_COLUMNS_STOCKS = ("головной контрагент", "артикул", "магазин", "количество")


@dataclass
class RowError:
    row: int
    field: str
    message: str
    counterparty: str | None = None

    def as_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"row": self.row, "field": self.field, "message": self.message}
        if self.counterparty:
            payload["counterparty"] = self.counterparty
        return payload


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


def _is_blank(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str) and not value.strip():
        return True
    return False


def _is_nan_like(value: Any) -> bool:
    if isinstance(value, Decimal):
        return not value.is_finite()
    if isinstance(value, float):
        return value != value or value in {float("inf"), float("-inf")}
    text = str(value).strip().lower().replace(",", ".")
    return text in {"nan", "nat", "none", "null", "inf", "-inf", "+inf"}


def parse_optional_price(value: Any) -> Decimal | None:
    """Empty / NaN cell → None (TZ: взять среднюю реализацию 1С). Garbage → InvalidOperation."""
    if _is_blank(value) or _is_nan_like(value):
        return None
    text = str(value).replace(",", ".").replace(" ", "").replace("\xa0", "").strip()
    if not text or _is_nan_like(text):
        return None
    price = Decimal(text)
    if not price.is_finite() or price < 0:
        raise InvalidOperation
    return price


def _norm_header(value: Any) -> str:
    text = str(value or "").strip().lower().replace("ё", "е")
    text = text.replace("/", " ").replace("\\", " ")
    while "  " in text:
        text = text.replace("  ", " ")
    return text


def normalize_counterparty_name(value: Any) -> str:
    return " ".join(str(value or "").split())


def map_headers(headers: list[Any]) -> dict[str, int]:
    mapping: dict[str, int] = {}
    for idx, raw in enumerate(headers):
        h = _norm_header(raw)
        if "головн" in h and "контрагент" in h:
            mapping["head"] = idx
        elif "контрагент" in h:
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


def articles_from_records(records: list[dict[str, Any]]) -> list[str]:
    """Unique артикул/ШК from Excel rows — to load only matching 1C nomenclature."""
    if not records:
        return []
    colmap = map_headers(list(records[0].keys()))
    idx = colmap.get("article")
    if idx is None:
        return []
    seen: set[str] = set()
    articles: list[str] = []
    for rec in records:
        values = list(rec.values())
        if idx >= len(values):
            continue
        article = normalize_article(values[idx])
        if article and article not in seen:
            seen.add(article)
            articles.append(article)
    return articles


def validate_upload_dataframe(
    records: list[dict[str, Any]],
    *,
    known_counterparties: dict[str, Any],
    known_articles: set[str],
    counterparty_shops: dict[str, set[str]],
    require_price: bool = False,
    start_row: int = 2,
    empty_message: str = "Файл пуст",
) -> ValidationResult:
    """
    Batch validation: collect all errors.
    `known_counterparties` maps normalized name -> id
    `known_articles` articles and barcodes
    """
    result = ValidationResult()
    if not records:
        result.errors.append(RowError(0, "file", empty_message))
        return result

    headers = list(records[0].keys())
    colmap = map_headers(headers)
    if "head" not in colmap or "article" not in colmap or "qty" not in colmap:
        result.errors.append(
            RowError(0, "file", "Не найдены обязательные колонки: Головной контрагент, Артикул/ШК, Количество")
        )
        return result

    for i, rec in enumerate(records, start=start_row):
        values = list(rec.values())
        head = normalize_counterparty_name(values[colmap["head"]])
        article = normalize_article(values[colmap["article"]]) or ""
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
                    RowError(
                        i,
                        "head_counterparty",
                        f"Контрагент «{head}» не существует в 1С",
                        counterparty=head,
                    )
                )
                row_ok = False
            else:
                head = found
        else:
            head = next(k for k in known_counterparties if k.lower() == head.lower())

        if not article:
            result.errors.append(
                RowError(i, "article", "Не заполнен артикул/ШК", counterparty=head or None)
            )
            row_ok = False
        elif article not in known_articles:
            result.errors.append(
                RowError(i, "article", f"Артикул «{article}» не найден в 1С", counterparty=head or None)
            )
            row_ok = False

        if shop and head in counterparty_shops and counterparty_shops[head] and shop not in counterparty_shops[head]:
            result.errors.append(
                RowError(
                    i,
                    "shop",
                    f'Магазин "{shop}" не входит в список магазинов контрагента',
                    counterparty=head or None,
                )
            )
            row_ok = False

        try:
            qty = Decimal(str(qty_raw).replace(",", ".").replace(" ", ""))
            if qty <= 0 or qty != qty.to_integral_value():
                raise InvalidOperation
        except (InvalidOperation, ValueError, TypeError):
            result.errors.append(
                RowError(i, "quantity", "Количество должно быть целым числом > 0", counterparty=head or None)
            )
            row_ok = False
            qty = Decimal(0)

        price: Optional[Decimal] = None
        if "price" in colmap or require_price:
            try:
                price = parse_optional_price(price_raw)
            except InvalidOperation:
                result.errors.append(
                    RowError(i, "price", "Некорректная цена продажи", counterparty=head or None)
                )
                row_ok = False
            if require_price and price is None and row_ok:
                result.errors.append(
                    RowError(i, "price", "Не заполнена цена продажи", counterparty=head or None)
                )
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

    return result
