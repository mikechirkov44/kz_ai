from app.services.odata_settings import is_valid_source_id, next_source_id, source_public_view


def test_next_source_id_skips_taken():
    assert next_source_id([]) == "base_1"
    assert next_source_id({"asil", "miamor"}) == "base_1"
    assert next_source_id({"base_1", "asil"}) == "base_2"
    assert next_source_id(["base_1", "base_2", "base_4"]) == "base_3"


def test_valid_source_id():
    assert is_valid_source_id("asil")
    assert is_valid_source_id("miamor")
    assert is_valid_source_id("base_1")
    assert not is_valid_source_id("")
    assert not is_valid_source_id("Base_1")
    assert not is_valid_source_id("1base")
    assert not is_valid_source_id("has-dash")
    assert not is_valid_source_id("a" * 33)


def test_source_public_view_falls_back_to_id():
    class Row:
        source_id = "base_1"
        label = ""
        enabled = True

    assert source_public_view(Row()) == {"source_id": "base_1", "label": "base_1", "enabled": True}
