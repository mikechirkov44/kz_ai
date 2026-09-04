from datetime import date
from decimal import Decimal

from app.constants import SOURCE_ASIL, SOURCE_MIAMOR, allowed_directions_for_source
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


def test_direction_filter_per_source():
    assert allowed_directions_for_source(SOURCE_ASIL) == frozenset({"ИМПЕРИАЛ", "ИМПЕРИАЛ KZ"})
    assert allowed_directions_for_source(SOURCE_MIAMOR) == frozenset({"БЕЛЛА", "МиАмор"})
    assert "ИМПЕРИАЛ" not in allowed_directions_for_source(SOURCE_MIAMOR)
    assert "БЕЛЛА" not in allowed_directions_for_source(SOURCE_ASIL)
    # empty / unknown direction must not pass
    assert "" not in allowed_directions_for_source(SOURCE_ASIL)
    # unknown source → union
    unknown = allowed_directions_for_source("custom")
    assert "ИМПЕРИАЛ" in unknown and "БЕЛЛА" in unknown


def test_nomenclature_maps_weight_and_barcode():
    nom = map_nomenclature(
        {
            "Ref_Key": "guid-w",
            "Артикул": "W-1",
            "Description": "Кольцо",
            "Штрихкод": "460123",
            "СреднийВес": "2,45",
            "КС_Направление": {"Description": "ИМПЕРИАЛ"},
        },
        "asil",
    )
    assert nom["barcode"] == "460123"
    assert nom["weight"] == Decimal("2.45")


def test_nomenclature_maps_characteristics():
    nom = map_nomenclature(
        {
            "Ref_Key": "guid-c",
            "Артикул": "C-1",
            "Description": "Серьги",
            "Модель": "S2899",
            "Вставка": "фианит",
            "Комментарий": "проба",
            "ЮС_ВнешнийВид_Key": "look-1",
            "КС_КатегорияВставок_Key": "ins-1",
            "КС_Направление": {"Description": "ИМПЕРИАЛ"},
        },
        "asil",
        lookups={
            "appearance": {"look-1": "Классика"},
            "insert_category": {"ins-1": "Безкамни"},
        },
    )
    assert "Модель: S2899" in (nom["characteristics"] or "")
    assert "Внешний вид: Классика" in (nom["characteristics"] or "")
    assert "Категория вставок: Безкамни" in (nom["characteristics"] or "")


def test_buyers_folder_filter():
    from app.services.sync import _refs_under_buyers_folder

    rows = [
        {"onec_ref": "root", "name": "Покупатели", "is_folder": True, "parent_onec_ref": None},
        {"onec_ref": "shop", "name": "ТОО Shop", "is_folder": False, "parent_onec_ref": "root"},
        {"onec_ref": "other", "name": "Поставщики", "is_folder": True, "parent_onec_ref": None},
        {"onec_ref": "vendor", "name": "ТОО Vendor", "is_folder": False, "parent_onec_ref": "other"},
    ]
    allowed = _refs_under_buyers_folder(rows)
    assert allowed == {"root", "shop"}
    assert _refs_under_buyers_folder([{"onec_ref": "a", "name": "X", "is_folder": False, "parent_onec_ref": None}]) is None


def test_upsert_line_reuses_cache_on_duplicate_key():
    from app.models import ClientOrder
    from app.services.sync import _upsert_line

    class FakeDb:
        def __init__(self) -> None:
            self.scalar_calls = 0
            self.added = 0

        def scalar(self, _stmt):
            self.scalar_calls += 1
            return None

        def add(self, _obj):
            self.added += 1

    db = FakeDb()
    cache: dict = {}
    payload = {"source_id": "asil", "onec_ref": "doc-1", "line_number": 1, "quantity": 1}
    first = _upsert_line(db, ClientOrder, payload, cache)
    second = _upsert_line(db, ClientOrder, {**payload, "quantity": 2}, cache)
    assert first is second
    assert second.quantity == 2
    assert db.scalar_calls == 1
    assert db.added == 1


def test_motivation_grades():
    assert motivation_grade(Decimal("95000"))[0] == Decimal("1500")
    assert motivation_grade(Decimal("95000"))[1] == "1 — 100 000"
    assert motivation_grade(Decimal("150000"))[0] == Decimal("2500")
    assert motivation_grade(Decimal("420000"))[0] == Decimal("5000")
    assert motivation_grade(Decimal("600000"))[0] == Decimal("6000")
    assert motivation_grade(Decimal("600000"))[1] == "500 001 — 999 999 999"


def test_line_cost_metrics_difference():
    from app.domain.motivation import line_cost_metrics

    cost, unit, amount, diff = line_cost_metrics(
        price=Decimal("170000"),
        quantity=Decimal("2"),
        avg_realization=Decimal("100000"),
    )
    assert cost == Decimal("340000.00")
    assert unit == Decimal("170000.00")  # 100000 * 1.7
    assert amount == Decimal("340000.00")
    assert diff == Decimal("0.00")

    cost2, _, amount2, diff2 = line_cost_metrics(
        price=Decimal("200000"),
        quantity=Decimal("1"),
        avg_realization=Decimal("100000"),
    )
    assert cost2 == Decimal("200000.00")
    assert amount2 == Decimal("170000.00")
    assert diff2 == Decimal("17.65")


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


def test_ignore_turnover_property_mapping():
    from app.odata.mapping import (
        classify_property_object,
        collect_ignore_turnover_refs,
        collect_true_object_refs,
        find_ignore_turnover_property_key,
        find_property_key_by_name,
        is_ignore_turnover_property,
        is_promo_participation_property,
    )

    assert is_ignore_turnover_property("Не учитывать при оборачиваемости")
    assert is_ignore_turnover_property("другое", "00125")
    assert not is_ignore_turnover_property("Комментарий")
    assert classify_property_object("StandardODATA.Document_РеализацияТоваровУслуг") == "realization"
    assert classify_property_object("StandardODATA.Document_ВозвратТоваровОтПокупателя") == "return"
    assert classify_property_object("Catalog_Номенклатура") is None
    assert classify_property_object("StandardODATA.Catalog_Контрагенты") == "counterparty"

    assert is_promo_participation_property("Участвует в акции")
    assert not is_promo_participation_property("ID_Битрикс24")
    promo_prop = "aaaa1111-c477-11f0-be76-d843ae2600bf"
    assert find_property_key_by_name(
        [
            {"Ref_Key": "x", "Description": "ID_Битрикс24"},
            {"Ref_Key": promo_prop, "Description": "Участвует в акции"},
        ],
        "Участвует в акции",
    ) == promo_prop
    promo_refs = collect_true_object_refs(
        [
            {
                "Свойство_Key": promo_prop,
                "Объект": "cp-1",
                "Объект_Type": "StandardODATA.Catalog_Контрагенты",
                "Значение": True,
            },
            {
                "Свойство_Key": promo_prop,
                "Объект": "cp-off",
                "Объект_Type": "StandardODATA.Catalog_Контрагенты",
                "Значение": False,
            },
            {
                "Свойство_Key": promo_prop,
                "Объект": "doc-r",
                "Объект_Type": "StandardODATA.Document_РеализацияТоваровУслуг",
                "Значение": True,
            },
        ],
        promo_prop,
    )
    assert promo_refs["counterparty"] == {"cp-1"}
    assert promo_refs["realization"] == {"doc-r"}

    prop = "422243c2-c477-11f0-be76-d843ae2600bf"
    key = find_ignore_turnover_property_key(
        [
            {"Ref_Key": "other", "Description": "Комментарий", "Code": "00001"},
            {"Ref_Key": prop, "Description": "Не учитывать при оборачиваемости", "Code": "00125"},
        ]
    )
    assert key == prop
    reals, rets = collect_ignore_turnover_refs(
        [
            {
                "Свойство_Key": prop,
                "Объект": "doc-r",
                "Объект_Type": "StandardODATA.Document_РеализацияТоваровУслуг",
                "Значение": True,
            },
            {
                "Свойство_Key": prop,
                "Объект": "doc-t",
                "Объект_Type": "StandardODATA.Document_ВозвратТоваровОтПокупателя",
                "Значение": True,
            },
            {
                "Свойство_Key": prop,
                "Объект": "doc-skip",
                "Объект_Type": "StandardODATA.Document_РеализацияТоваровУслуг",
                "Значение": False,
            },
            {
                "Свойство_Key": "other",
                "Объект": "doc-other",
                "Объект_Type": "StandardODATA.Document_РеализацияТоваровУслуг",
                "Значение": True,
            },
        ],
        prop,
    )
    assert reals == {"doc-r"}
    assert rets == {"doc-t"}


def test_same_quarter_return_cancels_realization():
    from types import SimpleNamespace
    from uuid import uuid4

    from app.domain.fact_shipments import cancelled_realization_ids, return_matches_realization

    nom = uuid4()
    other = uuid4()
    assert return_matches_realization(
        real_series="ser-1", real_nom_id=nom, ret_series="ser-1", ret_nom_id=other
    )
    assert return_matches_realization(
        real_series=None, real_nom_id=nom, ret_series=None, ret_nom_id=nom
    )
    assert not return_matches_realization(
        real_series="ser-1", real_nom_id=nom, ret_series="ser-2", ret_nom_id=nom
    )

    r1 = SimpleNamespace(id="r1", series="ser-1", nomenclature_id=nom)
    r2 = SimpleNamespace(id="r2", series=None, nomenclature_id=other)
    ret = SimpleNamespace(id="t1", series="ser-1", nomenclature_id=nom)
    cancelled = cancelled_realization_ids([r1, r2], [ret])
    assert cancelled == {"r1"}


def test_plan_fulfillment_slice():
    from uuid import uuid4

    from app.schemas import QuarterlyClientRow
    from app.services.reports import _fulfillment_slice

    rows = [
        QuarterlyClientRow(
            counterparty="A",
            counterparty_id=uuid4(),
            plan=Decimal("100"),
            fact=Decimal("120"),
            percent=Decimal("120"),
        ),
        QuarterlyClientRow(
            counterparty="B",
            counterparty_id=uuid4(),
            plan=Decimal("50"),
            fact=Decimal("10"),
            percent=Decimal("20"),
        ),
    ]
    slice_row = _fulfillment_slice("Всего", rows)
    assert slice_row.clients == 2
    assert slice_row.fulfilled == 1
    assert slice_row.percent == Decimal("86.67")
