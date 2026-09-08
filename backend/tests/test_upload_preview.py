from datetime import date, datetime
from decimal import Decimal

from app.domain.upload_preview import PREVIEW_ROW_LIMIT, preview_cell, spreadsheet_preview


def test_preview_cell_normalizes_values():
    assert preview_cell(None) is None
    assert preview_cell(float("nan")) is None
    assert preview_cell(12.0) == 12
    assert preview_cell(12.5) == 12.5
    assert preview_cell(Decimal("4.00")) == 4
    assert preview_cell(date(2026, 5, 1)) == "2026-05-01"
    assert preview_cell(datetime(2026, 9, 8, 10, 23, 14)) == "2026-09-08 10:23:14"
    assert preview_cell("  nan ") is None
    assert preview_cell("ИП Garant") == "ИП Garant"


def test_spreadsheet_preview_limits_rows_and_keeps_columns():
    columns = ["Головной контрагент", "Артикул", "Количество"]
    records = [
        {"Головной контрагент": "А", "Артикул": "IM-001", "Количество": 2},
        {"Головной контрагент": "Б", "Артикул": "IM-002", "Количество": 3},
        {"Головной контрагент": "В", "Артикул": None, "Количество": float("nan")},
    ]
    out = spreadsheet_preview(columns, records, limit=2)
    assert out["total_rows"] == 3
    assert out["shown_rows"] == 2
    assert out["columns"] == columns
    assert out["rows"][0]["Количество"] == 2
    assert out["rows"][1]["Артикул"] == "IM-002"


def test_spreadsheet_preview_empty_and_default_limit():
    assert spreadsheet_preview([], [], limit=0) == {
        "columns": [],
        "rows": [],
        "total_rows": 0,
        "shown_rows": 0,
    }
    rows = [{"A": i} for i in range(PREVIEW_ROW_LIMIT + 5)]
    out = spreadsheet_preview(["A"], rows)
    assert out["total_rows"] == PREVIEW_ROW_LIMIT + 5
    assert out["shown_rows"] == PREVIEW_ROW_LIMIT


def test_normalize_upload_errors():
    from app.domain.upload_preview import normalize_upload_errors

    assert normalize_upload_errors(None) == []
    assert normalize_upload_errors("x") == []
    assert normalize_upload_errors([{"row": "4", "field": "article", "message": "Нет"}]) == [
        {"row": 4, "field": "article", "message": "Нет"}
    ]
