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


def test_json_number_and_optional_decimal():
    assert _json_number(None) is None
    assert _json_number(2) == 2.0
    assert _optional_decimal(None) is None
    assert _optional_decimal("") is None
    assert _optional_decimal("1,5") == Decimal("1.5")
