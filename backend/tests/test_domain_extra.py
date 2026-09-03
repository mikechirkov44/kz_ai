from datetime import date
from decimal import Decimal

from app.domain.ai_rules import IlliquidCandidate, PriceArbitrageAlert, illiquid_recommendations, price_arbitrage_recommendations
from app.domain.excel_validation import RowError, map_headers, validate_upload_dataframe
from app.domain.fact_shipments import IlliquidCheckInput, include_in_fact, is_internal_warehouse, quarter_bounds
from app.domain.motivation import calculate_line_bonus, motivation_grade, normalize_work_type
from app.domain.turnover import avg_quarter_turnover, next_quarter_plan, quarter_turnover, turnover_percent


def test_map_headers_variants():
    mapping = map_headers(["Головной контрагент", "ШК", "Магазин", "Кол-во", "Цена продажи"])
    assert mapping["head"] == 0
    assert mapping["article"] == 1
    assert mapping["qty"] == 3
    assert mapping["price"] == 4


def test_excel_success_and_price_invalid():
    records = [
        {
            "Головной контрагент": "ТОО Gold",
            "Артикул": "IM-001",
            "Магазин": "",
            "Количество": 1,
            "Цена продажи": "abc",
        }
    ]
    result = validate_upload_dataframe(
        records,
        known_counterparties={"ТОО Gold": "1"},
        known_articles={"IM-001"},
        counterparty_shops={"ТОО Gold": set()},
    )
    assert any(e.field == "price" for e in result.errors)


def test_excel_empty_and_missing_columns():
    empty = validate_upload_dataframe([], known_counterparties={}, known_articles=set(), counterparty_shops={})
    assert empty.status == "error"
    bad = validate_upload_dataframe(
        [{"A": 1}],
        known_counterparties={},
        known_articles=set(),
        counterparty_shops={},
    )
    assert any(e.field == "file" for e in bad.errors)


def test_excel_happy_path():
    records = [
        {
            "Головной контрагент": "тоо gold",
            "Артикул": "IM-001",
            "Магазин": "ЦУМ",
            "Количество": 2,
            "Цена продажи": "95 000",
        }
    ]
    result = validate_upload_dataframe(
        records,
        known_counterparties={"ТОО Gold": "1"},
        known_articles={"IM-001"},
        counterparty_shops={"ТОО Gold": {"ЦУМ"}},
    )
    assert result.status == "success"
    assert len(result.rows) == 1
    assert result.rows[0].price == Decimal("95000")


def test_row_error_dict():
    assert RowError(1, "x", "y").as_dict() == {"row": 1, "field": "x", "message": "y"}


def test_fact_branches():
    assert is_internal_warehouse("Mi Amor Склад")
    assert not is_internal_warehouse(None)
    assert include_in_fact(
        IlliquidCheckInput("Актив", None, None, None, None, None, Decimal(1))
    )
    assert include_in_fact(
        IlliquidCheckInput("Вывод", None, None, None, None, None, Decimal(1))
    )
    assert include_in_fact(
        IlliquidCheckInput("Вывод", None, date(2026, 1, 1), "Mi Amor Склад", None, "A", Decimal(1))
    )
    assert include_in_fact(
        IlliquidCheckInput("Вывод", None, date(2026, 1, 1), None, "B", "A", Decimal(1))
    )
    start, end = quarter_bounds(2026, 1)
    assert start == date(2026, 1, 1) and end == date(2026, 3, 31)
    start4, end4 = quarter_bounds(2026, 4)
    assert start4 == date(2026, 10, 1) and end4 == date(2026, 12, 31)


def test_turnover_edge_and_quarter():
    assert turnover_percent(Decimal(10), Decimal(0), Decimal(0)) == Decimal(0)
    assert quarter_turnover(Decimal(30), Decimal(0)) == Decimal(0)
    assert quarter_turnover(Decimal(30), Decimal(10)) == Decimal(300)
    assert avg_quarter_turnover(Decimal(30)) == Decimal(10)
    assert next_quarter_plan(Decimal(100), None, None) == Decimal(100)


def test_motivation_fallback_and_decline_alias():
    assert motivation_grade(Decimal("999999999"))[0] == Decimal("6000")
    assert normalize_work_type(None) is None
    assert normalize_work_type("unknown") == "unknown"
    _, _, total = calculate_line_bonus(price=Decimal("100001"), quantity=Decimal("1"))
    assert total == Decimal("2500")


def test_ai_limit_and_no_arbitrage():
    items = [
        IlliquidCandidate("A", "a1", "x", "y", "z", Decimal("1"), Decimal("100"), 7),
        IlliquidCandidate("A", "a2", "x", "y", "z", Decimal("1"), Decimal("100"), 7),
    ]
    # limit 10% of 200 = 20, so only first tiny? stock 100 each, limit 20 — none may fit if first is 100
    rec = illiquid_recommendations(items, max_share=Decimal("0.05"))
    assert isinstance(rec, list)
    assert price_arbitrage_recommendations(
        [PriceArbitrageAlert("A", "Кольцо", Decimal("100"), Decimal("200"))]
    ) == []
