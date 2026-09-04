from app.api.documents import search_pattern


def test_search_pattern_strips_and_wraps():
    assert search_pattern("  Saona  ") == "%Saona%"
    assert search_pattern("") is None
    assert search_pattern("   ") is None
    assert search_pattern(None) is None
