from sqlalchemy import create_engine, inspect, text

from app.bootstrap import ensure_production_doc_number_column, ensure_sync_schedule_time_columns


def test_ensure_production_doc_number_adds_column_once():
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE production_receipt (id INTEGER PRIMARY KEY)"))
    ensure_production_doc_number_column(engine)
    cols = {c["name"] for c in inspect(engine).get_columns("production_receipt")}
    assert "doc_number" in cols
    ensure_production_doc_number_column(engine)
    cols_again = {c["name"] for c in inspect(engine).get_columns("production_receipt")}
    assert cols_again == cols


def test_ensure_production_doc_number_skips_missing_table():
    engine = create_engine("sqlite:///:memory:")
    ensure_production_doc_number_column(engine)
    assert "production_receipt" not in inspect(engine).get_table_names()


def test_ensure_sync_schedule_time_columns_adds_once():
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE sync_schedule (id INTEGER PRIMARY KEY)"))
    ensure_sync_schedule_time_columns(engine)
    cols = {c["name"] for c in inspect(engine).get_columns("sync_schedule")}
    assert "mode" in cols
    assert "run_at" in cols
    ensure_sync_schedule_time_columns(engine)
    assert {c["name"] for c in inspect(engine).get_columns("sync_schedule")} == cols
