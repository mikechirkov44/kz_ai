from decimal import Decimal

from app.domain.ai_rules import (
    IlliquidCandidate,
    PatternHit,
    PriceArbitrageAlert,
    bundle_label,
    build_recommendations_summary,
    dedupe_recommendations,
    has_bundle_attrs,
    illiquid_recommendations,
    mix_imbalance_recommendations,
    money_label,
    needs_restock,
    price_arbitrage_recommendations,
    qty_label,
    rank_recommendations,
    ru_count,
    score_illiquid,
    successful_pattern_recommendations,
)


def test_illiquid_has_score_and_action():
    rows = illiquid_recommendations(
        [
            IlliquidCandidate("A", "X1", "Кольцо", "Вывод", "Красное", Decimal("5"), Decimal("10"), 7),
            IlliquidCandidate("A", "X2", "Серьги", "Актив", "Белое", Decimal("50"), Decimal("100"), 0),
        ]
    )
    assert rows
    assert rows[0]["article"] == "X1"
    assert rows[0]["action"] == "return"
    assert rows[0]["title"].startswith("Верните")
    assert "Не больше" not in rows[0]["message"]
    assert "0.00" not in rows[0]["message"]
    assert "об-ть 5%" in rows[0]["message"]
    assert rows[0]["score"] == score_illiquid(
        IlliquidCandidate("A", "X1", "Кольцо", "Вывод", "Красное", Decimal("5"), Decimal("10"), 7)
    )
    assert 0 < rows[0]["score"] <= 100


def test_qty_and_money_labels():
    assert qty_label(Decimal("4")) == "4"
    assert qty_label(Decimal("10.0")) == "10"
    assert qty_label(Decimal("10.25")) == "10.3"
    assert money_label(Decimal("43098.281333333333333333333333")) == "43 098"
    assert money_label(Decimal("156285.6590909090909090909091")) == "156 286"


def test_pattern_only_when_stock_is_low():
    strong = PatternHit("A", "Кольцо", "Актив Ядро", "Красное золото", Decimal("100"), Decimal("5"))
    covered = PatternHit("A", "Серьги", "Актив", "Белое", Decimal("100"), Decimal("80"))
    assert needs_restock(strong) is True
    assert needs_restock(covered) is False
    rows = successful_pattern_recommendations([strong, covered])
    assert len(rows) == 1
    assert rows[0]["action"] == "restock"
    assert "Довезите 95 шт." in rows[0]["message"]
    assert successful_pattern_recommendations([covered]) == []
    exit_lts = PatternHit("A", "Кольцо", "Вывод", "Красное", Decimal("40"), Decimal("1"))
    assert needs_restock(exit_lts) is False
    empty = PatternHit("Demo", "—", "—", "—", Decimal("1"), Decimal("0"))
    tiny = PatternHit("A", "Кольцо", "Актив", "Красное", Decimal("1"), Decimal("0"))
    assert has_bundle_attrs("—", "—", None) is False
    assert needs_restock(empty) is False
    assert needs_restock(tiny) is False
    assert successful_pattern_recommendations([empty, tiny]) == []


def test_mix_imbalance_one_per_client():
    patterns = [PatternHit("A", "Кольцо", "Актив", "Красное", Decimal("40"), Decimal("2"))]
    stocks = [
        IlliquidCandidate("A", "OLD", "Серьги", "Вывод", "Белое", Decimal("1"), Decimal("8"), 9),
        IlliquidCandidate("A", "NEW", "Кольцо", "Актив", "Красное", Decimal("20"), Decimal("2"), 1),
    ]
    rows = mix_imbalance_recommendations(patterns, stocks)
    assert len(rows) == 1
    assert rows[0]["type"] == "mix"
    assert rows[0]["article"] == "OLD"
    assert rows[0]["action"] == "return"
    assert "Верните" in rows[0]["title"]


def test_mix_skips_same_bundle():
    patterns = [PatternHit("A", "Кольцо", "Актив", "Красное", Decimal("40"), Decimal("2"))]
    stocks = [IlliquidCandidate("A", "X", "Кольцо", "Актив", "Красное", Decimal("1"), Decimal("8"), 9)]
    assert mix_imbalance_recommendations(patterns, stocks) == []


def test_mix_skips_empty_bundle():
    patterns = [PatternHit("Demo", "—", "—", "—", Decimal("10"), Decimal("0"))]
    stocks = [IlliquidCandidate("Demo", "OLD", "Серьги", "Вывод", "Белое", Decimal("1"), Decimal("8"), 9)]
    assert mix_imbalance_recommendations(patterns, stocks) == []


def test_price_and_rank_and_summary():
    arb = price_arbitrage_recommendations(
        [PriceArbitrageAlert("A", "Кольцо", Decimal("180000"), Decimal("130000"))]
    )
    assert arb[0]["action"] == "reprice"
    assert arb[0]["score"] > 0
    assert "130 000 тенге" in arb[0]["message"]
    ranked = rank_recommendations(
        [
            {"type": "pattern", "score": 20, "action": "restock", "title": "Подсортировать", "counterparty": "B"},
            {"type": "illiquid", "score": 90, "action": "return", "title": "Вернуть X", "counterparty": "A"},
        ]
    )
    assert ranked[0]["type"] == "illiquid"
    summary = build_recommendations_summary(ranked)
    assert "2 сигнала" in summary
    assert "Первым делом: A — Вернуть X." in summary
    assert build_recommendations_summary([]) == "Сигналов нет. Нужны продажи, остатки и участники акции ★."
    assert ru_count(1, "сигнал", "сигнала", "сигналов") == "1 сигнал"
    assert ru_count(3, "сигнал", "сигнала", "сигналов") == "3 сигнала"
    assert ru_count(11, "сигнал", "сигнала", "сигналов") == "11 сигналов"
    assert bundle_label(None, None, None) == "без характеристик 1С"
    assert bundle_label("Кольцо", "Актив", "Красное") == "Кольцо / Актив / Красное"


def test_illiquid_skips_tiny_stock_and_caps_per_client():
    tiny = IlliquidCandidate("A", "X", "Кольцо", "Вывод", "Красное", Decimal("1"), Decimal("1"), 9)
    assert illiquid_recommendations([tiny]) == []
    a_item = IlliquidCandidate("A", "A1", "Кольцо", "Вывод", "Красное", Decimal("1"), Decimal("8"), 9)
    a_ok = IlliquidCandidate("A", "A2", "Серьги", "Актив", "Белое", Decimal("40"), Decimal("80"), 0)
    b_item = IlliquidCandidate("B", "B1", "Кольцо", "Вывод", "Белое", Decimal("1"), Decimal("8"), 9)
    b_ok = IlliquidCandidate("B", "B2", "Серьги", "Актив", "Красное", Decimal("40"), Decimal("80"), 0)
    rows = illiquid_recommendations([a_item, a_ok, b_item, b_ok])
    articles = {row["article"] for row in rows}
    assert articles == {"A1", "B1"}


def test_price_needs_gap_and_samples():
    assert price_arbitrage_recommendations(
        [PriceArbitrageAlert("A", "—", Decimal("180000"), Decimal("130000"), 5)]
    ) == []
    assert price_arbitrage_recommendations(
        [PriceArbitrageAlert("A", "Кольцо", Decimal("180000"), Decimal("179000"), 5)]
    ) == []
    assert price_arbitrage_recommendations(
        [PriceArbitrageAlert("A", "Кольцо", Decimal("180000"), Decimal("130000"), 2)]
    ) == []


def test_dedupe_mix_drops_same_illiquid():
    items = [
        {"type": "illiquid", "counterparty": "A", "article": "OLD", "score": 80},
        {"type": "mix", "counterparty": "A", "article": "OLD", "score": 70},
        {"type": "illiquid", "counterparty": "A", "article": "OTHER", "score": 60},
    ]
    out = dedupe_recommendations(items)
    assert [row["article"] for row in out] == ["OLD", "OTHER"]
    assert [row["type"] for row in out] == ["mix", "illiquid"]


def test_collect_client_signals_from_sales_and_stocks():
    from datetime import date
    from types import SimpleNamespace

    from app.domain.articles import index_nomenclature
    from app.services.ai import collect_client_signals

    nom = SimpleNamespace(article="X1", barcode=None, wear_type="Кольцо", lts="Вывод", metal_color="Красное")
    index = index_nomenclature([nom])  # type: ignore[arg-type]
    sales = [
        SimpleNamespace(article="X1", quantity=Decimal("1"), price=Decimal("100"), period_year=2026, period_month=1),
        SimpleNamespace(article="X1", quantity=Decimal("1"), price=Decimal("110"), period_year=2026, period_month=2),
        SimpleNamespace(article="X1", quantity=Decimal("1"), price=Decimal("120"), period_year=2026, period_month=3),
    ]
    stocks = [SimpleNamespace(article="X1", quantity=Decimal("10"), stock_date=date(2026, 1, 1))]
    illiquid, patterns, arb = collect_client_signals(
        counterparty="A",
        sales=sales,
        stocks=stocks,
        nom_index=index,
        as_of=date(2026, 9, 7),
        ship_avg_by_wear={"Кольцо": Decimal("180")},
    )
    assert len(illiquid) == 1
    assert illiquid[0].article == "X1"
    assert illiquid[0].months_without_sales >= 5
    assert patterns
    assert arb and arb[0].wear_type == "Кольцо"
    _, _, no_arb = collect_client_signals(
        counterparty="A",
        sales=sales[:2],
        stocks=stocks,
        nom_index=index,
        as_of=date(2026, 9, 7),
        ship_avg_by_wear={"Кольцо": Decimal("180")},
    )
    assert no_arb == []
