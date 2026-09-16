from decimal import Decimal

from app.middleware_rate_limit import SlidingWindowLimiter
from app.schemas import MotivationClientRow, MotivationItem, MotivationReport
from app.services.export_xlsx import motivation_workbook, nomenclature_workbook, workbook_bytes
from fastapi import HTTPException
import pytest


def test_motivation_workbook_bytes():
    report = MotivationReport(
        counterparty="Тест",
        period="2023-01",
        total_bonus=Decimal("6000"),
        items=[
            MotivationItem(
                article="A1",
                name="Кольцо",
                price=Decimal("100"),
                quantity=Decimal("2"),
                grade="1 — 100 000",
                bonus_per_unit=Decimal("50"),
                total_bonus=Decimal("100"),
                lts="Хит",
                lts_date="2022-01-01",
                cost_amount=Decimal("200"),
            )
        ],
        groups=[],
    )
    data = workbook_bytes(motivation_workbook(report))
    assert data[:2] == b"PK"
    assert len(data) > 100


def test_motivation_workbook_all_clients():
    from uuid import uuid4
    from io import BytesIO
    from openpyxl import load_workbook

    cid = uuid4()
    report = MotivationReport(
        counterparty="Все",
        period="2023-01",
        total_bonus=Decimal("1500"),
        clients=[
            MotivationClientRow(
                counterparty_id=cid,
                counterparty="ИП Saona",
                quantity=Decimal("2"),
                lines=1,
                total_bonus=Decimal("1500"),
            )
        ],
        items=[
            MotivationItem(
                article="A1",
                name="Кольцо",
                price=Decimal("95000"),
                quantity=Decimal("2"),
                grade="1 — 100 000",
                bonus_per_unit=Decimal("1500"),
                total_bonus=Decimal("3000"),
                counterparty="ИП Saona",
                counterparty_id=cid,
                cost_amount=Decimal("190000"),
            )
        ],
    )
    wb = load_workbook(BytesIO(workbook_bytes(motivation_workbook(report))))
    assert "По клиентам" in wb.sheetnames
    assert wb["По клиентам"]["A2"].value == "ИП Saona"
    assert wb["Мотивация"]["A1"].value == "Ценовые диапазоны / Номенклатура"


def test_nomenclature_workbook_includes_promo():
    from io import BytesIO
    from openpyxl import load_workbook

    wb = load_workbook(
        BytesIO(
            workbook_bytes(
                nomenclature_workbook(
                    [
                        {
                            "article": "IM-001",
                            "name": "Кольцо",
                            "lts": "Хит",
                            "lts_date": "2026-01-01",
                            "wear_type": "Кольцо",
                            "metal_color": "Красное",
                            "direction": "ИМПЕРИАЛ",
                            "is_promo": True,
                            "source_id": "asil",
                            "barcode": "123",
                        }
                    ]
                )
            )
        )
    )
    sheet = wb["Номенклатура"]
    headers = [cell.value for cell in sheet[1]]
    assert "Акция" in headers
    assert "Комплект" in headers
    assert "Дата карточки" in headers
    assert "Направление" in headers
    promo_col = headers.index("Акция") + 1
    assert sheet.cell(2, promo_col).value == "да"


def test_counterparties_workbook_includes_card_fields():
    from io import BytesIO
    from openpyxl import load_workbook

    from app.services.export_xlsx import counterparties_workbook, extra_properties_cell

    assert extra_properties_cell({"ID_Битрикс24": "3381", "Бренд": "X"}) == "ID_Битрикс24: 3381; Бренд: X"
    assert extra_properties_cell({}) == ""
    wb = load_workbook(
        BytesIO(
            workbook_bytes(
                counterparties_workbook(
                    [
                        {
                            "name": 'ИП "АСЕЛЬ"',
                            "code": "БП595",
                            "full_name": 'ИП "АСЕЛЬ"',
                            "legal_status": "Физ. лицо",
                            "iin": "640729300422",
                            "identity_document": "Уд. Личн.",
                            "director_name": "Турсунбаев",
                            "extra_properties": {"ID_Битрикс24": "3381"},
                            "work_type_label": "Рост",
                            "is_promo": True,
                            "source_id": "asil",
                            "shops": ["Магазин 1"],
                        }
                    ]
                )
            )
        )
    )
    sheet = wb["Контрагенты"]
    headers = [cell.value for cell in sheet[1]]
    assert "БИН/ИИН" in headers
    assert "Доп. сведения" in headers
    iin_col = headers.index("БИН/ИИН") + 1
    extra_col = headers.index("Доп. сведения") + 1
    assert sheet.cell(2, iin_col).value == "640729300422"
    assert sheet.cell(2, extra_col).value == "ID_Битрикс24: 3381"


def test_rate_limiter_blocks():
    lim = SlidingWindowLimiter()
    for _ in range(3):
        lim.check("t1", limit=3, window_sec=60)
    with pytest.raises(HTTPException) as exc:
        lim.check("t1", limit=3, window_sec=60)
    assert exc.value.status_code == 429
