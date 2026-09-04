from decimal import Decimal

from app.domain.articles import build_known_articles, normalize_article
from app.domain.turnover import avg_quarter_turnover, next_quarter_plan, quarter_turnover, turnover_percent
from app.services.turnover_matrix import _month_iter


def test_month_iter_span():
    months = _month_iter(2023, 11, 2024, 2)
    assert months == [(2023, 11), (2023, 12), (2024, 1), (2024, 2)]


def test_normalize_and_known_articles():
    class Nom:
        article = "  A1  "
        barcode = "B1"

    known = build_known_articles([Nom()])  # type: ignore[arg-type]
    assert "A1" in known and "B1" in known
    assert normalize_article("  x  ") == "x"


def test_next_plan_aliases():
    assert next_quarter_plan(Decimal(100), "рост", Decimal(10)) == Decimal(110)
    assert next_quarter_plan(Decimal(100), "падение", Decimal(10)) == Decimal(90)
    assert next_quarter_plan(Decimal(100), "hold", Decimal(10)) == Decimal(100)


def test_quarter_metrics_chain():
    q = quarter_turnover(Decimal(90), Decimal(30))
    assert q == Decimal(300)
    assert avg_quarter_turnover(q) == Decimal(100)
    assert turnover_percent(Decimal(10), Decimal(10), Decimal(10)) == Decimal(100)
