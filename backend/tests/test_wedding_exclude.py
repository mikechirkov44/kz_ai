from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

from app.domain.turnover_matrix import assemble_turnover_rows


def test_assemble_skips_wedding_ring_sales_and_stocks():
    cp_id = uuid4()
    cp = SimpleNamespace(
        id=cp_id,
        name="ИП Test",
        work_type="hold",
        work_type_percent=Decimal("10"),
        source_id="asil",
    )
    ring = SimpleNamespace(
        id=uuid4(),
        article="К-ОБР-1",
        barcode=None,
        name="Кольцо обручальное",
        wear_type="Обручальное кольцо",
        metal_color="Красное 585",
        lts="Актив",
        lts_date=None,
    )
    other = SimpleNamespace(
        id=uuid4(),
        article="К-ОБЫЧ-1",
        barcode=None,
        name="Кольцо",
        wear_type="Кольцо",
        metal_color="Красное 585",
        lts="Актив",
        lts_date=None,
    )
    noms = {"К-ОБР-1": ring, "К-ОБЫЧ-1": other}
    sales = [
        SimpleNamespace(
            head_counterparty_id=cp_id,
            article="К-ОБР-1",
            quantity=Decimal("5"),
            period_year=2026,
            period_month=5,
        ),
        SimpleNamespace(
            head_counterparty_id=cp_id,
            article="К-ОБЫЧ-1",
            quantity=Decimal("2"),
            period_year=2026,
            period_month=5,
        ),
    ]
    stocks = [
        SimpleNamespace(
            head_counterparty_id=cp_id,
            article="К-ОБР-1",
            quantity=Decimal("10"),
            stock_date=date(2026, 4, 30),
        ),
        SimpleNamespace(
            head_counterparty_id=cp_id,
            article="К-ОБЫЧ-1",
            quantity=Decimal("3"),
            stock_date=date(2026, 4, 30),
        ),
    ]
    rows = assemble_turnover_rows(
        view="main",
        month_bounds=[("2026-05", date(2026, 5, 1), date(2026, 5, 31))],
        counterparties=[cp],
        sales=sales,
        stocks=stocks,
        noms=noms,
        movements={},
    )
    sku_articles = [r["article"] for r in rows if r.get("row_type") == "sku"]
    assert sku_articles == ["К-ОБЫЧ-1"]
    head = next(r for r in rows if r.get("row_type") == "counterparty")
    assert head["months"]["2026-05"]["sales"] == 2.0
