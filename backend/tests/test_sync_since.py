from datetime import date

from app.constants import (
    SYNC_DATE_FILTER_ENTITIES,
    default_since_date,
    effective_since,
    is_before_since,
)
from app.schemas import SyncStateOut, SyncSinceUpdate


def test_since_defaults():
    assert default_since_date("realization") == date(2023, 1, 1)
    assert default_since_date("return_doc") == date(2023, 1, 1)
    assert default_since_date("client_order") == date(2023, 1, 1)
    assert default_since_date("lts_history") == date(2023, 1, 1)
    assert default_since_date("production_receipt") == date(2025, 1, 1)
    assert default_since_date("nomenclature") is None
    assert default_since_date("object_properties") is None


def test_date_filter_entities():
    assert "realization" in SYNC_DATE_FILTER_ENTITIES
    assert "production_receipt" in SYNC_DATE_FILTER_ENTITIES
    assert "nomenclature" not in SYNC_DATE_FILTER_ENTITIES
    assert "counterparty" not in SYNC_DATE_FILTER_ENTITIES
    assert "object_properties" not in SYNC_DATE_FILTER_ENTITIES


def test_is_before_since():
    cutoff = date(2025, 1, 1)
    assert is_before_since(date(2024, 12, 31), cutoff) is True
    assert is_before_since(date(2025, 1, 1), cutoff) is False
    assert is_before_since(None, cutoff) is True
    assert is_before_since(date(2020, 1, 1), None) is False
    assert is_before_since(None, None) is True


def test_effective_since_override():
    stored = date(2023, 1, 1)
    override = date(2024, 6, 1)
    assert effective_since(override, stored) == override
    assert effective_since(None, stored) == stored
    assert effective_since(None, None) is None


def test_sync_state_out_date_filter():
    docs = SyncStateOut(
        source_id="asil",
        entity="realization",
        status="idle",
        rows_synced=0,
        since_date=date(2023, 1, 1),
    )
    assert docs.date_filter is True
    assert docs.since_date == date(2023, 1, 1)
    catalog = SyncStateOut(source_id="asil", entity="nomenclature", status="idle", rows_synced=0)
    assert catalog.date_filter is False
    assert catalog.since_date is None


def test_sync_since_update_allows_null():
    payload = SyncSinceUpdate(source_id="asil", entity="production_receipt", since_date=None)
    assert payload.since_date is None
