import pytest
from fastapi import HTTPException

from decimal import Decimal

from app.api.documents import _json_number, parse_production_doc_type, search_pattern
from app.odata.mapping import _optional_decimal


def test_search_pattern_strips_and_wraps():
    assert search_pattern("  Saona  ") == "%Saona%"
    assert search_pattern("") is None
    assert search_pattern("   ") is None
    assert search_pattern(None) is None


def test_parse_production_doc_type_accepts_1c_kinds():
    assert parse_production_doc_type(None) is None
    assert parse_production_doc_type("") is None
    assert parse_production_doc_type("production") == "production"
    assert parse_production_doc_type("goods") == "goods"
    with pytest.raises(HTTPException) as err:
        parse_production_doc_type("orders")
    assert err.value.status_code == 400


def test_client_order_sync_reads_price_and_amount_from_1c():
    import inspect as pyinspect

    from app.models import ClientOrder
    from app.services.sync import sync_client_orders

    assert {"doc_number", "price", "amount"} <= {c.name for c in ClientOrder.__table__.columns}
    src = pyinspect.getsource(sync_client_orders)
    assert '"Number"' in src
    assert '"Цена"' in src
    assert '"Сумма"' in src


def test_client_order_maps_line_price_and_amount():
    from app.odata.mapping import _get, _optional_decimal, as_decimal

    line = {"Количество": "3", "Цена": "1500,5", "Сумма": "4501,5"}
    assert as_decimal(_get(line, "Количество", default=0)) == Decimal("3")
    assert _optional_decimal(_get(line, "Цена")) == Decimal("1500.5")
    assert _optional_decimal(_get(line, "Сумма")) == Decimal("4501.5")
    assert _optional_decimal(_get({}, "Цена")) is None


def test_json_number_and_optional_decimal():
    assert _json_number(None) is None
    assert _json_number(2) == 2.0
    assert _optional_decimal(None) is None
    assert _optional_decimal("") is None
    assert _optional_decimal("1,5") == Decimal("1.5")
