from decimal import Decimal

from app.domain.articles import index_nomenclature, lookup_nomenclature
from app.domain.motivation import work_type_label
from app.domain.quarterly import (
    assign_matrix_recommendations,
    dim_metrics,
    recommendations_digest,
    should_include_summary_client,
    summary_counterparty_ids,
    zip_block_rows,
)
from app.domain.turnover import (
    dynamics_trend,
    month_avg_stock,
    quarter_avg_stock,
    sales_dynamics_percent,
    sales_dynamics_qty,
    shift_quarter,
)
from app.services.export_xlsx import quarterly_summary_workbook, workbook_bytes
from app.services.quarterly_summary import filter_summary_clients


def test_month_and_quarter_avg_stock():
    assert month_avg_stock(Decimal(10), Decimal(20)) == Decimal(15)
    assert quarter_avg_stock([Decimal(15), Decimal(20), Decimal(15)]) == Decimal("50") / Decimal(3)


def test_summary_clients_follow_sales_not_promo_or_stock_only():
    assert should_include_summary_client(has_quarter_sales=True, include_empty=False) is True
    assert should_include_summary_client(has_quarter_sales=False, include_empty=False) is False
    assert should_include_summary_client(
        has_quarter_sales=False, include_empty=False, has_empty_anchor=True
    ) is False
    assert should_include_summary_client(
        has_quarter_sales=False, include_empty=True, has_empty_anchor=True
    ) is True
    assert summary_counterparty_ids({"sale"}, {"extra"}, include_empty=False) == {"sale"}
    assert summary_counterparty_ids({"sale"}, {"extra"}, include_empty=True) == {"sale", "extra"}


def test_shift_quarter_wraps_year():
    assert shift_quarter(2026, 1, -1) == (2025, 4)
    assert shift_quarter(2026, 1, -2) == (2025, 3)
    assert shift_quarter(2026, 3, 1) == (2026, 4)
    assert shift_quarter(2026, 4, 1) == (2027, 1)


def test_sales_dynamics_percent():
    assert sales_dynamics_percent(Decimal(43), Decimal(100)) == Decimal(43)
    assert sales_dynamics_percent(Decimal(10), Decimal(0)) is None


def test_sales_dynamics_qty():
    assert sales_dynamics_qty(Decimal(43), Decimal(100)) == Decimal(-57)
    assert sales_dynamics_qty(Decimal(10), Decimal(0)) == Decimal(10)


def test_dynamics_trend_two_and_three_quarters():
    assert dynamics_trend(Decimal(120), Decimal(100)) == "Рост"
    assert dynamics_trend(Decimal(90), Decimal(100), Decimal(80)) == "Нестабильный"


def test_dim_metrics_pads_short_month_lists():
    m = dim_metrics(Decimal(10), [Decimal(4)], [Decimal(6)])
    # one month avg 5, two months padded 0 → quarter avg 5/3
    assert m["avg_stock"] == Decimal(5) / Decimal(3)
    # begin/end 10/10 three months, sales 30 → avg stock 10, об-ть 300%, ср.об-ть 100%
    m = dim_metrics(Decimal(30), [Decimal(10)] * 3, [Decimal(10)] * 3)
    assert m["avg_stock"] == Decimal(10)
    assert m["sales_total"] == Decimal(30)
    assert m["quarter_turnover_percent"] == Decimal(300)
    assert m["avg_month_turnover_percent"] == Decimal(100)


def test_zip_block_rows_pads_short_block():
    a = [{"dimension": "Белое 585"}]
    b = [{"dimension": "Актив"}, {"dimension": "Новинка"}]
    c = []
    rows = zip_block_rows(a, b, c)
    assert len(rows) == 2
    assert rows[0][0]["dimension"] == "Белое 585"
    assert rows[1][0] is None
    assert rows[1][1]["dimension"] == "Новинка"
    assert rows[0][2] is None


def test_recommendations_digest_limit():
    items = [{"message": "A"}, {"message": "B"}, {"message": " "}, {"message": "C"}]
    assert recommendations_digest(items, limit=2) == "A · B"
    assert recommendations_digest(items) == "A · B · C"
    assert recommendations_digest([{"title": "Коротко", "message": "длинный текст"}], limit=1) == "Коротко"


def test_compact_recommendation_lines_merge_same_action():
    from app.domain.quarterly import compact_recommendation_lines

    items = [
        {"action": "return", "title": "Верните 4 шт. A", "article": "A", "details": {"wear_type": "Кольцо"}},
        {"action": "return", "title": "Верните 2 шт. B", "article": "B", "details": {"wear_type": "Кольцо"}},
        {"action": "restock", "title": "Довезите кольца", "details": {"wear_type": "Кольцо"}},
        {"llm_comment": "Позвоните по плану", "title": "План ниже 50%"},
    ]
    assert compact_recommendation_lines(items) == [
        "Верните 2 SKU (Кольцо): A, B.",
        "Довезите кольца",
        "Позвоните по плану",
    ]
    assert compact_recommendation_lines(
        [{"title": "Довезите кольца", "message": "длинный текст про остаток"}]
    ) == ["Довезите кольца"]
    assert compact_recommendation_lines(
        [
            {
                "action": "reprice",
                "title": "Снизить цену отгрузки · Браслет",
                "message": "Клиент продаёт [Браслет] ниже отгрузки на 21%.",
                "details": {
                    "wear_type": "Браслет",
                    "gap_percent": "21.4",
                    "client_avg_price": "45000",
                    "articles": [
                        {"article": "BR-1", "gap_percent": "24"},
                        {"article": "BR-2", "gap_percent": "18"},
                    ],
                },
            }
        ]
    ) == [
        "Клиент продаёт «Браслет» на 21% дешевле отгрузки. Следующие отгрузки — не выше 45 000 ₸. "
        "Сильнее всего: BR-1 (−24%), BR-2 (−18%)."
    ]
    assert compact_recommendation_lines(
        [
            {
                "action": "return",
                "title": "Верните 2 шт. К0237-320",
                "details": {"avg_turnover": "0", "months_without_sales": 40},
            }
        ]
    ) == ["Верните 2 шт. К0237-320: оборачиваемость 0%, 40 мес. без продаж."]


def test_assign_matrix_recommendations_by_row_dims():
    ring = {"title": "Довезите кольца", "details": {"wear_type": "Кольцо", "metal_color": "Красное 585"}}
    mix = {
        "title": "Верните серьги и довезите кольца",
        "details": {
            "strong_bundle": "Кольцо / Актив / Красное 585",
            "weak_bundle": "Серьги / Вывод / Белое",
        },
    }
    plan = {"title": "План отгрузки ниже 50%", "details": {}}
    unmatched = {"title": "Без измерения", "details": {"wear_type": "—", "lts": "Итого"}}
    matrix = [
        {
            "metal_color": {"dimension": "Красное 585"},
            "lts": {"dimension": "Актив"},
            "wear_type": {"dimension": "Кольцо"},
        },
        {
            "metal_color": {"dimension": "Белое"},
            "lts": {"dimension": "Вывод"},
            "wear_type": {"dimension": "Серьги"},
        },
        {
            "is_total": True,
            "metal_color": {"dimension": "Итого"},
            "lts": {"dimension": "Итого"},
            "wear_type": {"dimension": "Итого"},
        },
    ]
    assign_matrix_recommendations(matrix, [ring, mix, plan, unmatched])
    assert [item["title"] for item in matrix[0]["recommendations"]] == [
        "Довезите кольца",
        "Верните серьги и довезите кольца",
    ]
    assert [item["title"] for item in matrix[1]["recommendations"]] == ["Верните серьги и довезите кольца"]
    assert [item["title"] for item in matrix[2]["recommendations"]] == [
        "План отгрузки ниже 50%",
        "Без измерения",
    ]
    assert ring not in matrix[2]["recommendations"]
    assert mix not in matrix[2]["recommendations"]
    assert matrix[0]["recommendations_text"].startswith("Довезите кольца")


def test_work_type_label_ru():
    assert work_type_label("hold") == "Удержание"
    assert work_type_label("Прирост") == "Рост"
    assert work_type_label("падение") == "Падение"
    assert work_type_label(None) == "—"


def test_index_and_lookup_nomenclature():
    class Nom:
        def __init__(self, article, barcode):
            self.article = article
            self.barcode = barcode

    items = [Nom("  00012 ", "B-1")]
    index = index_nomenclature(items)  # type: ignore[arg-type]
    assert lookup_nomenclature(index, "12") is items[0]
    assert lookup_nomenclature(index, "B-1") is items[0]
    assert lookup_nomenclature(index, "missing") is None


def test_unique_nomenclatures_dedupes_index():
    from app.domain.articles import index_nomenclature, unique_nomenclatures

    class Nom:
        def __init__(self, nom_id, article, barcode):
            self.id = nom_id
            self.article = article
            self.barcode = barcode

    first = Nom("1", "A-1", "B-1")
    index = index_nomenclature([first])  # type: ignore[arg-type]
    assert unique_nomenclatures(index) == [first]


def test_index_nomenclature_for_articles_skips_empty():
    from app.domain.articles import index_nomenclature_for_articles

    class Boom:
        def scalars(self, *args, **kwargs):
            raise AssertionError("must not query empty keys")

    assert index_nomenclature_for_articles(Boom(), []) == {}
    assert index_nomenclature_for_articles(Boom(), ["", None, "  "]) == {}


def test_facts_for_periods_indexes_by_counterparty(monkeypatch):
    from types import SimpleNamespace
    from uuid import uuid4

    from app.services import quarterly_summary as qs

    cp_id = uuid4()
    item = SimpleNamespace(counterparty_id=cp_id)

    def fake(_db, *, periods, allowed_ids):
        assert periods == [(2025, 4)]
        assert allowed_ids == {cp_id}
        return {(2025, 4): [item]}

    monkeypatch.setattr(qs, "list_fact_shipments_by_periods", fake)
    out = qs._facts_for_periods(None, periods=[(2025, 4)], allowed_ids={cp_id})
    assert out[(2025, 4)][cp_id] is item


def test_zero_fact_placeholder():
    from types import SimpleNamespace
    from uuid import uuid4

    from app.services.quarterly_summary import _zero_fact

    cp_id = uuid4()
    result = _zero_fact(SimpleNamespace(id=cp_id, name="ИП Test"), 2026, 2)
    assert result.counterparty_id == cp_id
    assert result.fact_amount == Decimal(0)
    assert result.excluded_illiquid_amount == Decimal(0)


def test_decimal_price_skips_invalid():
    from types import SimpleNamespace

    from app.services.quarterly_summary import _decimal_price, _price_alerts

    assert _decimal_price(None) is None
    assert _decimal_price("abc") is None
    assert _decimal_price(Decimal("NaN")) is None
    assert _decimal_price(0) is None
    assert _decimal_price(Decimal("1500.50")) == Decimal("1500.50")
    assert _decimal_price("2500") == Decimal("2500")

    nom = SimpleNamespace(id="n1", article="R-1", wear_type="Кольцо")
    ship = SimpleNamespace(nomenclature_id="n1", price=Decimal("180000"))
    alerts = _price_alerts(
        counterparty="A",
        wear_client_prices={"Кольцо": [Decimal("100000")] * 3},
        article_client_prices={"R-1": [Decimal("100000"), Decimal("110000")]},
        wear_by_article={"R-1": "Кольцо"},
        realizations=[ship, ship, ship],
        noms={"R-1": nom},
    )
    assert alerts and alerts[0].articles and alerts[0].articles[0].article == "R-1"


def test_quarterly_summary_workbook_matrix():
    report = {
        "labels": {
            "plan": "План отгрузки на 3 квартал",
            "sales": "итого продажи 3 кв",
            "turnover": "Об-ть 3 кв",
            "avg_turnover": "Ср. об-ть за 3 кв",
            "sales_prev": "итого продажи 2 кв.",
            "sales_prev2": "итого продажи 1 кв.",
            "dynamics": "Динамика 3 кв. / 2 кв. (шт)",
            "next_plan": "План работы на 4 кв (шт)",
        },
        "clients": [
            {
                "counterparty": "ИП Garant.S",
                "work_type_label": "Удержание",
                "work_type_percent": 0,
                "plan": 50,
                "sales_prev_quarter": 80,
                "sales_prev2_quarter": 70,
                "dynamics_percent": 43,
                "dynamics_qty": -46,
                "comment": "Участвует в повышенной мотивации",
                "next_quarter_plan": 34,
                "recommendations_text": "Подсортировать кольца Актив Ядро.",
                "matrix": [
                    {
                        "metal_color": {
                            "dimension": "Красное 585",
                            "avg_stock": 10,
                            "sales_total": 8,
                            "quarter_turnover_percent": 80,
                            "avg_month_turnover_percent": 26.67,
                        },
                        "lts": {
                            "dimension": "Актив",
                            "avg_stock": 12,
                            "sales_total": 9,
                            "quarter_turnover_percent": 75,
                            "avg_month_turnover_percent": 25,
                        },
                        "wear_type": {
                            "dimension": "Кольцо",
                            "avg_stock": 5,
                            "sales_total": 4,
                            "quarter_turnover_percent": 80,
                            "avg_month_turnover_percent": 26.67,
                        },
                        "recommendations_text": "Довезите кольца",
                        "recommendations_llm": "Сначала заберите К0237, новые не везите.",
                    },
                    {
                        "is_total": True,
                        "metal_color": {
                            "dimension": "Итого",
                            "avg_stock": 10,
                            "sales_total": 34,
                            "quarter_turnover_percent": 340,
                            "avg_month_turnover_percent": 113.33,
                        },
                        "lts": {
                            "dimension": "Итого",
                            "avg_stock": 10,
                            "sales_total": 34,
                            "quarter_turnover_percent": 340,
                            "avg_month_turnover_percent": 113.33,
                        },
                        "wear_type": {
                            "dimension": "Итого",
                            "avg_stock": 10,
                            "sales_total": 34,
                            "quarter_turnover_percent": 340,
                            "avg_month_turnover_percent": 113.33,
                        },
                        "recommendations_text": "План отгрузки ниже 50%",
                    },
                ],
            }
        ],
    }
    data = workbook_bytes(quarterly_summary_workbook(report))
    assert data[:2] == b"PK"
    from openpyxl import load_workbook
    from io import BytesIO

    wb = load_workbook(BytesIO(data))
    ws = wb.active
    assert ws["A1"].value == "Контрагент"
    assert "Цвет металла" in str(ws["E1"].value)
    assert ws["A3"].value == "ИП Garant.S"
    assert ws["E3"].value == "Красное 585"
    assert "(шт)" in str(ws.cell(row=1, column=22).value)
    assert ws.cell(row=4, column=22).value == -46
    assert any(c.value == "Итого" for row in ws.iter_rows(min_row=3, max_row=6, min_col=5, max_col=5) for c in row)
    assert ws.cell(row=3, column=25).value == "Сначала заберите К0237, новые не везите."
    assert ws.cell(row=4, column=25).value == "План отгрузки ниже 50%"


def test_filter_summary_clients():
    rows = [
        {"counterparty": "ИП Almaz-A", "work_type_label": "Удержание", "manager_name": "Иванов"},
        {"counterparty": "Гранат", "work_type_label": "Рост", "manager_name": "Петров"},
    ]
    assert [c["counterparty"] for c in filter_summary_clients(rows, query="almaz")] == ["ИП Almaz-A"]
    assert [c["counterparty"] for c in filter_summary_clients(rows, work_type="рост")] == ["Гранат"]
    assert [c["counterparty"] for c in filter_summary_clients(rows, manager="петр")] == ["Гранат"]
    assert len(filter_summary_clients(rows)) == 2


def test_summary_from_post_uses_clients():
    from app.api.reports import _summary_from_post

    assert _summary_from_post(None) is None
    assert _summary_from_post({"clients": []}) is None
    posted = _summary_from_post({"year": 2026, "clients": [{"counterparty": "ИП A"}], "labels": {"plan": "План"}})
    assert posted is not None
    assert posted["year"] == 2026
    assert posted["clients"][0]["counterparty"] == "ИП A"
    assert posted["labels"]["plan"] == "План"
