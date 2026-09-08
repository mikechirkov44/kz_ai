from datetime import date
from decimal import Decimal

from app.domain.ai_rules import (
    IlliquidCandidate,
    PatternHit,
    PriceArbitrageAlert,
    apply_plan_boost,
    bundle_label,
    build_recommendations_summary,
    dedupe_recommendations,
    has_bundle_attrs,
    illiquid_recommendations,
    is_recent_month,
    mix_imbalance_recommendations,
    money_label,
    needs_restock,
    price_arbitrage_recommendations,
    qty_label,
    rank_recommendations,
    ru_count,
    score_illiquid,
    successful_pattern_recommendations,
    suggested_restock_qty,
    transfer_recommendations,
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
    assert "Довезите 45 шт." in rows[0]["message"]
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
    assert price_arbitrage_recommendations(
        [
            PriceArbitrageAlert("A", "Кольцо", Decimal("NaN"), Decimal("130000"), 5),
            PriceArbitrageAlert("A", "Кольцо", Decimal("180000"), Decimal("NaN"), 5),
        ]
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
        SimpleNamespace(article="X1", quantity=Decimal("1"), price=Decimal("100"), period_year=2026, period_month=7),
        SimpleNamespace(article="X1", quantity=Decimal("1"), price=Decimal("110"), period_year=2026, period_month=8),
        SimpleNamespace(article="X1", quantity=Decimal("1"), price=Decimal("120"), period_year=2026, period_month=9),
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
    assert illiquid[0].months_without_sales == 0
    assert patterns and patterns[0].recent_sales == Decimal("3")
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


def test_recent_month_window():
    as_of = date(2026, 9, 7)
    assert is_recent_month(2026, 9, as_of) is True
    assert is_recent_month(2026, 7, as_of) is True
    assert is_recent_month(2026, 6, as_of) is False
    assert is_recent_month(None, 9, as_of) is False


def test_restock_qty_scales_with_recent_sales():
    hit = PatternHit("A", "Кольцо", "Актив", "Красное", Decimal("100"), Decimal("5"), recent_sales=Decimal("100"))
    assert suggested_restock_qty(hit) == Decimal("45")
    modest = PatternHit("A", "Кольцо", "Актив", "Красное", Decimal("10"), Decimal("1"), recent_sales=Decimal("10"))
    assert suggested_restock_qty(modest) == Decimal("4")
    tiny_gap = PatternHit("A", "Кольцо", "Актив", "Красное", Decimal("6"), Decimal("2.8"), recent_sales=Decimal("6"))
    assert suggested_restock_qty(tiny_gap) == Decimal(1)


def test_stale_sales_do_not_restock():
    stale = PatternHit("A", "Кольцо", "Актив", "Красное", Decimal("80"), Decimal("1"), recent_sales=Decimal("0"))
    assert needs_restock(stale) is False
    assert successful_pattern_recommendations([stale]) == []


def test_restock_caps_per_client():
    hits = [
        PatternHit("A", "Кольцо", "Актив", "Красное", Decimal("40"), Decimal("1")),
        PatternHit("A", "Серьги", "Актив", "Белое", Decimal("30"), Decimal("1")),
        PatternHit("A", "Цепь", "Актив", "Красное", Decimal("20"), Decimal("1")),
        PatternHit("A", "Браслет", "Актив", "Белое", Decimal("15"), Decimal("1")),
        PatternHit("B", "Кольцо", "Актив", "Красное", Decimal("40"), Decimal("1")),
    ]
    rows = successful_pattern_recommendations(hits)
    assert sum(1 for row in rows if row["counterparty"] == "A") == 3
    assert sum(1 for row in rows if row["counterparty"] == "B") == 1


def test_exit_lts_scores_higher_than_active():
    exit_item = IlliquidCandidate("A", "X1", "Кольцо", "Вывод", "Красное", Decimal("5"), Decimal("10"), 7)
    live = IlliquidCandidate("A", "X2", "Кольцо", "Актив", "Красное", Decimal("5"), Decimal("10"), 7)
    assert score_illiquid(exit_item) > score_illiquid(live)


def test_plan_boost_raises_score_when_behind():
    items = [{"type": "illiquid", "score": 40, "counterparty": "A", "details": {}}]
    apply_plan_boost(items, {"A": Decimal("20")})
    assert items[0]["score"] == 52
    apply_plan_boost(items, {"A": Decimal("80")})
    assert items[0]["score"] == 52


def test_transfer_pairs_dead_stock_with_need():
    patterns = [PatternHit("B", "Кольцо", "Актив", "Красное", Decimal("40"), Decimal("2"))]
    stocks = [IlliquidCandidate("A", "OLD", "Кольцо", "Актив", "Красное", Decimal("1"), Decimal("8"), 9)]
    rows = transfer_recommendations(patterns, stocks)
    assert len(rows) == 1
    assert rows[0]["action"] == "transfer"
    assert rows[0]["article"] == "OLD"
    assert rows[0]["details"]["to_counterparty"] == "B"
    assert "Переложите" in rows[0]["title"]


def test_transfer_skips_exit_lts_and_same_client():
    patterns = [PatternHit("A", "Кольцо", "Актив", "Красное", Decimal("40"), Decimal("2"))]
    stocks = [IlliquidCandidate("A", "OLD", "Кольцо", "Вывод", "Красное", Decimal("1"), Decimal("8"), 9)]
    assert transfer_recommendations(patterns, stocks) == []


def test_dedupe_transfer_drops_illiquid_and_restock():
    items = [
        {"type": "transfer", "counterparty": "A", "article": "OLD", "details": {"to_counterparty": "B", "bundle": "Кольцо / Актив / Красное"}},
        {"type": "illiquid", "counterparty": "A", "article": "OLD"},
        {"type": "pattern", "counterparty": "B", "details": {"bundle": "Кольцо / Актив / Красное"}},
        {"type": "illiquid", "counterparty": "A", "article": "KEEP"},
    ]
    out = dedupe_recommendations(items)
    assert [row["type"] for row in out] == ["transfer", "illiquid"]
    assert out[1]["article"] == "KEEP"


def test_compose_recommendation_items_includes_transfer():
    from app.domain.ai_rules import compose_recommendation_items

    patterns = [PatternHit("B", "Кольцо", "Актив", "Красное", Decimal("40"), Decimal("2"))]
    stocks = [IlliquidCandidate("A", "OLD", "Кольцо", "Актив", "Красное", Decimal("1"), Decimal("8"), 9)]
    rows = compose_recommendation_items(illiquid_items=stocks, patterns=patterns, alerts=[])
    transfers = [row for row in rows if row["type"] == "transfer"]
    assert transfers
    assert any((row.get("details") or {}).get("to_counterparty") == "B" for row in transfers)
