from decimal import Decimal

from app.domain.digest_html import (
    format_digest_number,
    format_digest_with_trend,
    html_table,
    render_behind_html,
    render_progress_html,
    render_recommendations_html,
    render_results_html,
    wrap_digest_html,
)
from app.domain.quarterly import fulfillment_percent, promo_scope_ids, quarterly_results_labels


def test_promo_scope_ids_intersects_access():
    promo = {"a", "b", "c"}
    assert promo_scope_ids(promo) == promo
    assert promo_scope_ids(promo, allowed_ids={"b", "z"}) == {"b"}
    assert promo_scope_ids(promo, allowed_ids=set()) == set()
    assert promo_scope_ids(promo, counterparty_id="a") == {"a"}
    assert promo_scope_ids(promo, allowed_ids={"a", "b"}, counterparty_id="b") == {"b"}
    assert promo_scope_ids(promo, allowed_ids={"c"}, counterparty_id="a") == set()


def test_fulfillment_percent():
    assert fulfillment_percent(Decimal(50), Decimal(100)) == Decimal("50.00")
    assert fulfillment_percent(Decimal(10), Decimal(0)) == Decimal(0)


def test_quarterly_results_labels_use_quarter_numbers():
    labels = quarterly_results_labels(3, 2, 1)
    assert labels["plan"] == "План отгрузок на 3 квартал"
    assert labels["shipment_prev"] == "Факт отгрузок 2 квартал"
    assert labels["sales_prev2"] == "Продажи 1 кв."


def test_format_digest_number():
    assert format_digest_number(None) == "—"
    assert format_digest_number("abc") == "—"
    assert format_digest_number(Decimal("10.50")) == "10,5"
    assert format_digest_number(1.25) == "1,25"
    assert format_digest_number(Decimal("NaN")) == "—"


def test_format_digest_with_trend():
    assert format_digest_with_trend(Decimal("80"), "Падение") == "80 Падение"
    assert format_digest_with_trend(None, "Рост") == "Рост"
    assert format_digest_with_trend(Decimal("100"), None) == "100"


def test_html_table_escapes_and_empty():
    html = html_table(["A"], [("<script>",)], caption="Заголовок")
    assert "&lt;script&gt;" in html
    assert "<script>" not in html
    empty = html_table(["A", "B"], [])
    assert "Нет данных." in empty
    assert 'colspan="2"' in empty


def test_render_progress_includes_dynamics():
    clients = [
        {
            "counterparty": "ИП A",
            "manager_name": "Иванов",
            "work_type_label": "Рост",
            "work_type_percent": 10,
            "plan": 100,
            "fact": 40,
            "percent": 40,
            "dynamics": 1.25,
        },
        {
            "counterparty": "ИП B",
            "manager_name": None,
            "work_type": "hold",
            "plan": 50,
            "fact": 60,
            "percent": 120,
        },
    ]
    slices = [{"name": "Всего", "clients": 2, "fulfilled": 1, "percent": 80}]
    progress = render_progress_html(2026, 3, clients, slices)
    assert "Промежуточные итоги 2026 Q3" in progress
    assert "Динамика" in progress
    assert "1,25" in progress
    assert "ИП A" in progress
    behind = render_behind_html(clients)
    assert "ИП A" in behind
    assert "ИП B" not in behind


def test_render_results_and_recommendations_and_wrap():
    html = render_results_html(
        2026,
        3,
        [
            {
                "counterparty": "Клиент <X>",
                "plan": 10,
                "shipment_fact": 5,
                "shipment_percent": 50,
                "comment": "ok",
            }
        ],
        {"plan": "План отгрузок на 3 квартал"},
    )
    assert "Клиент &lt;X&gt;" in html
    assert "План отгрузок на 3 квартал" in html
    recs = render_recommendations_html([{"counterparty": "A", "message": "Довезите"}, {"message": ""}])
    assert "A: Довезите" in recs
    wrapped = wrap_digest_html("Письмо <тест>", [html])
    assert "Письмо &lt;тест&gt;" in wrapped
    empty = wrap_digest_html("Пусто", [])
    assert "ничего не выбрано" in empty
