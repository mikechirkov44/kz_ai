from datetime import date
from decimal import Decimal

from app.domain.motivation import calculate_line_bonus, motivation_grade, normalize_work_type
from app.domain.turnover import avg_quarter_turnover, next_quarter_plan, turnover_percent
from app.domain.fact_shipments import IlliquidCheckInput, include_in_fact
from app.domain.excel_validation import validate_upload_dataframe
from app.domain.ai_rules import (
    IlliquidCandidate,
    PatternHit,
    PriceArbitrageAlert,
    illiquid_recommendations,
    price_arbitrage_recommendations,
    successful_pattern_recommendations,
)
from app.odata.mapping import map_nomenclature, map_counterparty


def test_motivation_grades():
    assert motivation_grade(Decimal("95000"))[0] == Decimal("1500")
    assert motivation_grade(Decimal("150000"))[0] == Decimal("2500")
    assert motivation_grade(Decimal("420000"))[0] == Decimal("5000")
    assert motivation_grade(Decimal("600000"))[0] == Decimal("6000")


def test_motivation_no_merge_different_prices():
    b1, g1, t1 = calculate_line_bonus(price=Decimal("95000"), quantity=Decimal("2"))
    b2, g2, t2 = calculate_line_bonus(price=Decimal("180000"), quantity=Decimal("1"))
    assert g1 != g2
    assert t1 + t2 == Decimal("5500")


def test_motivation_client_totals_sorted():
    from uuid import uuid4

    from app.domain.motivation import add_client_sale, sorted_client_totals

    a, b = uuid4(), uuid4()
    acc = {}
    add_client_sale(acc, counterparty_id=a, counterparty="Бета", quantity=Decimal(1), total_bonus=Decimal(1000))
    add_client_sale(acc, counterparty_id=b, counterparty="Альфа", quantity=Decimal(2), total_bonus=Decimal(5000))
    add_client_sale(acc, counterparty_id=a, counterparty="Бета", quantity=Decimal(1), total_bonus=Decimal(500))
    rows = sorted_client_totals(acc)
    assert [r.counterparty for r in rows] == ["Альфа", "Бета"]
    assert rows[1].lines == 2
    assert rows[1].total_bonus == Decimal(1500)


def test_promo_motivation_fixed():
    bonus, grade, total = calculate_line_bonus(
        price=Decimal("1000"), quantity=Decimal("2"), is_promo_motivation=True
    )
    assert bonus == Decimal("6000")
    assert grade == "Доп. мотивация"
    assert total == Decimal("12000")


def test_work_type_alias():
    assert normalize_work_type("Прирост") == "growth"
    assert normalize_work_type("Удержание") == "hold"


def test_turnover_formula():
    # Example from TZ: sales 5m, begin 10m, end 8m => 55.56%
    value = turnover_percent(Decimal("5000000"), Decimal("10000000"), Decimal("8000000"))
    assert round(value, 2) == Decimal("55.56")


def test_next_quarter_plan():
    assert next_quarter_plan(Decimal("100"), "hold", Decimal("15")) == Decimal("100")
    assert next_quarter_plan(Decimal("100"), "growth", Decimal("15")) == Decimal("115")
    assert next_quarter_plan(Decimal("100"), "decline", Decimal("10")) == Decimal("90")
    assert avg_quarter_turnover(Decimal("30")) == Decimal("10")


def test_illiquid_fact_exclusion():
    # lts date after order => fact
    assert include_in_fact(
        IlliquidCheckInput(
            lts="Вывод",
            lts_date=date(2025, 12, 20),
            order_date=date(2025, 12, 10),
            order_target_warehouse=None,
            order_target_counterparty_ref="A",
            realization_counterparty_ref="A",
            amount=Decimal("100"),
        )
    )
    # lts date before order => NOT fact
    assert not include_in_fact(
        IlliquidCheckInput(
            lts="Вывод",
            lts_date=date(2026, 1, 5),
            order_date=date(2026, 1, 10),
            order_target_warehouse=None,
            order_target_counterparty_ref="A",
            realization_counterparty_ref="A",
            amount=Decimal("100"),
        )
    )


def test_excel_validation_batch_errors():
    records = [
        {
            "Головной контрагент": "ТОО Gold",
            "Артикул": "IM-001",
            "Магазин": "ЦУМ",
            "Количество": 2,
            "Цена продажи": 95000,
        },
        {
            "Головной контрагент": "ТОО Other",
            "Артикул": "BAD",
            "Магазин": "X",
            "Количество": "",
            "Цена продажи": 1,
        },
    ]
    result = validate_upload_dataframe(
        records,
        known_counterparties={"ТОО Gold": "1"},
        known_articles={"IM-001"},
        counterparty_shops={"ТОО Gold": {"ЦУМ"}},
    )
    assert result.status == "error"
    assert any(e.field == "head_counterparty" for e in result.errors)
    assert any(e.field == "article" for e in result.errors)
    assert any(e.field == "quantity" for e in result.errors)


def test_ai_rules():
    illiquid = illiquid_recommendations(
        [
            IlliquidCandidate("A", "X1", "Кольцо", "Вывод", "Красное", Decimal("5"), Decimal("10"), 7),
            IlliquidCandidate("A", "X2", "Серьги", "Актив", "Белое", Decimal("50"), Decimal("100"), 0),
        ]
    )
    assert any(i["article"] == "X1" for i in illiquid)

    patterns = successful_pattern_recommendations(
        [PatternHit("A", "Кольцо", "Актив Ядро", "Красное золото", Decimal("100"))]
    )
    assert "подсортировку" in patterns[0]["message"]

    arb = price_arbitrage_recommendations(
        [PriceArbitrageAlert("A", "Кольцо", Decimal("180000"), Decimal("130000"))]
    )
    assert arb and "ниже нашей отгрузочной" in arb[0]["message"]


def test_odata_mapping_expected_fields():
    nom = map_nomenclature(
        {
            "Ref_Key": "guid-1",
            "Артикул": "IM-001",
            "Description": "Кольцо",
            "ЮС_ЖЦТ": {"Description": "Вывод"},
            "Акция": True,
            "КС_Направление": {"Description": "МиАмор"},
            "ТипИзделия": {"Description": "Кольцо"},
            "ЮС_ЦветМеталла": {"Description": "Красное 585"},
            "Проба": {"Description": "585"},
        },
        "asil",
    )
    assert nom["article"] == "IM-001"
    assert nom["is_promo"] is True
    assert nom["lts"] == "Вывод"
    assert nom["direction"] == "МиАмор"

    nom_by_key = map_nomenclature(
        {
            "Ref_Key": "guid-1b",
            "Артикул": "IM-002",
            "Description": "Серьги",
            "КС_Направление_Key": "dir-1",
            "ТипИзделия_Key": "wear-1",
            "ЮС_ЦветМеталла_Key": "color-1",
            "Проба_Key": "assay-1",
            "ЮС_ЖЦТ_Key": "lts-1",
        },
        "asil",
        lookups={
            "direction": {"dir-1": "ИМПЕРИАЛ"},
            "wear_type": {"wear-1": "Серьги"},
            "metal_color": {"color-1": "Белое 585"},
            "assay": {"assay-1": "Au 585"},
            "lts": {"lts-1": "Актив"},
        },
    )
    assert nom_by_key["direction"] == "ИМПЕРИАЛ"
    assert nom_by_key["wear_type"] == "Серьги"
    assert nom_by_key["metal_color"] == "Белое 585"
    assert nom_by_key["assay"] == "Au 585"
    assert nom_by_key["lts"] == "Актив"

    cp = map_counterparty(
        {
            "Ref_Key": "guid-2",
            "Description": "ИП Test",
            "ТипРаботыКонтрагента": "Прирост",
            "ПроцентТипаРаботы": 15,
            "ГоловнойКонтрагент_Key": "00000000-0000-0000-0000-000000000000",
        },
        "asil",
    )
    assert cp["work_type"] == "Прирост"
    assert cp["head_counterparty_onec_ref"] is None
