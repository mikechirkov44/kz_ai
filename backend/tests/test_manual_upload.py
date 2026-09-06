from datetime import date
from decimal import Decimal

import pytest

from app.domain.excel_validation import validate_upload_dataframe
from app.domain.manual_upload import records_from_manual_rows, require_manual_period


def test_records_from_manual_rows_match_excel_columns():
    records = records_from_manual_rows(
        [
            {
                "counterparty": "ТОО Demo",
                "article": "IM-001",
                "shop": "ЦУМ",
                "quantity": 2,
                "price": "95000",
            }
        ]
    )
    assert records == [
        {
            "Головной контрагент": "ТОО Demo",
            "Артикул": "IM-001",
            "Магазин": "ЦУМ",
            "Количество": 2,
            "Цена продажи": "95000",
        }
    ]
    result = validate_upload_dataframe(
        records,
        known_counterparties={"ТОО Demo": "1"},
        known_articles={"IM-001"},
        counterparty_shops={"ТОО Demo": {"ЦУМ"}},
        start_row=1,
    )
    assert result.status == "success"
    assert result.rows[0].row_number == 1
    assert result.rows[0].quantity == Decimal("2")


def test_manual_empty_shop_and_price_optional():
    records = records_from_manual_rows(
        [{"counterparty": "ТОО Demo", "article": "IM-001", "shop": "", "quantity": 1, "price": None}]
    )
    assert records[0]["Магазин"] is None
    result = validate_upload_dataframe(
        records,
        known_counterparties={"ТОО Demo": "1"},
        known_articles={"IM-001"},
        counterparty_shops={"ТОО Demo": set()},
        start_row=1,
    )
    assert result.status == "success"
    assert result.rows[0].shop is None
    assert result.rows[0].price is None


def test_manual_empty_rows_message():
    result = validate_upload_dataframe(
        [],
        known_counterparties={"ТОО Demo": "1"},
        known_articles={"IM-001"},
        counterparty_shops={},
        start_row=1,
        empty_message="Нет строк для загрузки",
    )
    assert result.status == "error"
    assert result.errors[0].message == "Нет строк для загрузки"


def test_manual_invalid_quantity():
    records = records_from_manual_rows(
        [{"counterparty": "ТОО Demo", "article": "IM-001", "quantity": 0, "price": None}]
    )
    result = validate_upload_dataframe(
        records,
        known_counterparties={"ТОО Demo": "1"},
        known_articles={"IM-001"},
        counterparty_shops={"ТОО Demo": set()},
        start_row=1,
    )
    assert result.status == "error"
    assert any(e.field == "quantity" for e in result.errors)


def test_manual_unknown_article():
    records = records_from_manual_rows(
        [{"counterparty": "ТОО Demo", "article": "NOPE", "quantity": 1, "price": None}]
    )
    result = validate_upload_dataframe(
        records,
        known_counterparties={"ТОО Demo": "1"},
        known_articles={"IM-001"},
        counterparty_shops={"ТОО Demo": set()},
        start_row=1,
    )
    assert result.status == "error"
    assert any("не найден" in e.message for e in result.errors)


def test_manual_one_counterparty_rule():
    records = records_from_manual_rows(
        [
            {"counterparty": "ТОО Demo", "article": "IM-001", "quantity": 1, "price": None},
            {"counterparty": "Другой", "article": "IM-001", "quantity": 1, "price": None},
        ]
    )
    result = validate_upload_dataframe(
        records,
        known_counterparties={"ТОО Demo": "1", "Другой": "2"},
        known_articles={"IM-001"},
        counterparty_shops={"ТОО Demo": set(), "Другой": set()},
        start_row=1,
    )
    assert result.status == "error"
    assert result.rows == []
    assert any("одинаков" in e.message for e in result.errors)


def test_require_manual_period():
    require_manual_period("sales", period_year=2026, period_month=9, stock_date=None)
    require_manual_period("promo_motivation", period_year=None, period_month=None, stock_date=None)
    require_manual_period("stocks", period_year=None, period_month=None, stock_date=date(2026, 9, 1))

    with pytest.raises(ValueError, match="продаж"):
        require_manual_period("sales", period_year=None, period_month=9, stock_date=None)
    with pytest.raises(ValueError, match="остатков"):
        require_manual_period("both", period_year=2026, period_month=9, stock_date=None)
    with pytest.raises(ValueError, match="ручного ввода"):
        require_manual_period("quarterly_plans", period_year=2026, period_month=1, stock_date=None)
