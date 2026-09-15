from datetime import datetime, timedelta, timezone

from app.constants import SYNC_DOCUMENT_ENTITIES, SYNC_ENTITIES, SyncStatus
from app.domain.sync_run import (
    is_stale_sync_status,
    normalize_sync_items,
    ordered_entities,
    queued_idle_status,
    should_report_sync_progress,
    sync_count_unit,
    sync_progress_percent,
)


def test_ordered_entities_keeps_catalog_first():
    assert ordered_entities(None) == list(SYNC_ENTITIES)
    assert ordered_entities([]) == list(SYNC_ENTITIES)
    assert ordered_entities(["realization", "nomenclature", "nope"]) == ["nomenclature", "realization"]


def test_normalize_sync_items_skips_bad_and_dupes():
    assert normalize_sync_items(None) == []
    assert normalize_sync_items(
        [
            {"source_id": "asil", "entity": "realization"},
            {"source_id": "asil", "entity": "realization"},
            {"source_id": "", "entity": "nomenclature"},
            {"source_id": "miamor", "entity": "unknown"},
            {"source_id": "miamor", "entity": "return_doc"},
        ]
    ) == [("asil", "realization"), ("miamor", "return_doc")]


def test_sync_progress_percent():
    assert sync_progress_percent(0, 0, "running") is None
    assert sync_progress_percent(50, 100, "running") == 50
    assert sync_progress_percent(120, 100, "running") == 99
    assert sync_progress_percent(120, 100, "queued") == 99
    assert sync_progress_percent(120, 100, "success") == 100
    assert sync_progress_percent(0, 10, "success") == 100
    assert sync_progress_percent(3, 10, "failed") == 30


def test_queued_idle_status():
    assert queued_idle_status(0) == SyncStatus.IDLE.value
    assert queued_idle_status(12) == SyncStatus.SUCCESS.value


def test_sync_count_unit():
    assert sync_count_unit("realization") == "документов"
    assert sync_count_unit("production_receipt") == "документов"
    assert sync_count_unit("nomenclature") == "записей"
    assert sync_count_unit("lts_history") == "записей"


def test_document_count_models_match_journals():
    from app.services.sync import DOCUMENT_COUNT_MODELS

    assert set(DOCUMENT_COUNT_MODELS) == set(SYNC_DOCUMENT_ENTITIES)


def test_is_stale_sync_status():
    now = datetime(2026, 9, 15, 8, 0, tzinfo=timezone.utc)
    old = now - timedelta(minutes=20)
    fresh = now - timedelta(minutes=2)
    assert is_stale_sync_status("running", old, now=now, stale_after_seconds=600) is True
    assert is_stale_sync_status("queued", old, now=now, stale_after_seconds=600) is False
    assert is_stale_sync_status("running", fresh, now=now, stale_after_seconds=600) is False
    assert is_stale_sync_status("success", old, now=now, stale_after_seconds=600) is False
    assert is_stale_sync_status("failed", old, now=now, stale_after_seconds=600) is False
    assert is_stale_sync_status("running", None, now=now, stale_after_seconds=600) is True
    naive_old = datetime(2026, 9, 15, 7, 0)
    assert is_stale_sync_status("running", naive_old, now=now, stale_after_seconds=600) is True


def test_should_report_sync_progress():
    assert should_report_sync_progress(done=0, seen=0, lines=0) is False
    assert should_report_sync_progress(done=20, seen=3, lines=0) is True
    assert should_report_sync_progress(done=1, seen=100, lines=0) is True
    assert should_report_sync_progress(done=1, seen=50, lines=200) is True
    assert should_report_sync_progress(done=19, seen=99, lines=199) is False


def test_recover_stale_sync_states_marks_old_running_failed():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app.constants import STALE_SYNC_ERROR
    from app.db import Base
    from app.models import SyncState
    from app.services.sync import recover_stale_sync_states

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    now = datetime.now(timezone.utc)
    stale = SyncState(
        source_id="asil",
        entity="nomenclature",
        status="running",
        rows_synced=10,
        rows_done=3,
        rows_expected=10,
    )
    fresh = SyncState(
        source_id="asil",
        entity="counterparty",
        status="running",
        rows_synced=4,
        rows_done=1,
        rows_expected=4,
    )
    done = SyncState(
        source_id="asil",
        entity="lts_history",
        status="success",
        rows_synced=8,
        rows_done=8,
        rows_expected=8,
    )
    db.add_all([stale, fresh, done])
    db.commit()
    stale.updated_at = now - timedelta(minutes=20)
    fresh.updated_at = now - timedelta(minutes=2)
    done.updated_at = now - timedelta(minutes=20)
    db.commit()
    recovered = recover_stale_sync_states(db, now=now, stale_after_seconds=600)
    db.refresh(stale)
    db.refresh(fresh)
    db.refresh(done)
    assert recovered == 1
    assert stale.status == SyncStatus.FAILED.value
    assert stale.last_error == STALE_SYNC_ERROR
    assert fresh.status == SyncStatus.RUNNING.value
    assert done.status == SyncStatus.SUCCESS.value
    db.close()
    engine.dispose()
