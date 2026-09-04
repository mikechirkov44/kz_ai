from datetime import date

from app.domain.dwell import dwell_bucket, months_without_sales
from app.services.heatmap import heatmap_article_label


def test_months_since_last_sale():
    as_of = date(2026, 9, 4)
    assert months_without_sales(last_sale_year=2026, last_sale_month=9, as_of=as_of) == 0
    assert months_without_sales(last_sale_year=2026, last_sale_month=3, as_of=as_of) == 6
    assert months_without_sales(last_sale_year=2025, last_sale_month=9, as_of=as_of) == 12


def test_never_sold_uses_first_stock():
    as_of = date(2026, 9, 4)
    assert months_without_sales(
        last_sale_year=None,
        last_sale_month=None,
        as_of=as_of,
        first_stock=date(2026, 6, 1),
    ) == 3
    assert months_without_sales(last_sale_year=None, last_sale_month=None, as_of=as_of) == 12


def test_dwell_bucket():
    assert dwell_bucket(0) == "fresh"
    assert dwell_bucket(3) == "warm"
    assert dwell_bucket(6) == "stale"
    assert dwell_bucket(9) == "dead"


def test_heatmap_article_label():
    assert heatmap_article_label("000001797", "Кольцо золото") == "Кольцо золото"
    assert heatmap_article_label("000001797") == "1797"
    assert heatmap_article_label("IM-001") == "IM-001"
    assert heatmap_article_label("  ") == ""
