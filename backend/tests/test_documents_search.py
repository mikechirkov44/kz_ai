import pytest
from fastapi import HTTPException

from app.api.documents import parse_production_doc_type, search_pattern


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
