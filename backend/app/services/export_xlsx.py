"""Build Excel workbooks for report/catalog exports."""

from __future__ import annotations

from io import BytesIO
from typing import Any, Iterable, Sequence

from openpyxl import Workbook
from openpyxl.styles import Font
from openpyxl.utils import get_column_letter


def _style_header(ws, columns: Sequence[str]) -> None:
    bold = Font(bold=True)
    for idx, title in enumerate(columns, start=1):
        cell = ws.cell(row=1, column=idx, value=title)
        cell.font = bold
        ws.column_dimensions[get_column_letter(idx)].width = min(max(len(title) + 2, 12), 36)


def rows_to_workbook(columns: Sequence[str], rows: Iterable[Sequence[Any]], sheet_name: str = "Данные") -> Workbook:
    wb = Workbook()
    ws = wb.active
    ws.title = sheet_name[:31]
    _style_header(ws, columns)
    for r_idx, row in enumerate(rows, start=2):
        for c_idx, value in enumerate(row, start=1):
            ws.cell(row=r_idx, column=c_idx, value=value)
    return wb


def workbook_bytes(wb: Workbook) -> bytes:
    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()


def motivation_workbook(report: Any) -> Workbook:
    columns = [
        "Артикул",
        "Наименование",
        "ЖЦТ",
        "Дата ЖЦТ",
        "Цена",
        "Продано",
        "Грейд",
        "Вознаграждение",
        "Итого",
        "Доп.мотивация",
    ]
    rows = [
        (
            item.article,
            item.name,
            item.lts,
            item.lts_date,
            float(item.price),
            float(item.quantity),
            item.grade,
            float(item.bonus_per_unit),
            float(item.total_bonus),
            bool(getattr(item, "is_promo_motivation", False)),
        )
        for item in report.items
    ]
    wb = rows_to_workbook(columns, rows, "Мотивация")
    meta = wb.create_sheet("Итог", 0)
    meta["A1"] = "Контрагент"
    meta["B1"] = report.counterparty
    meta["A2"] = "Период"
    meta["B2"] = report.period
    meta["A3"] = "Итого бонус"
    meta["B3"] = float(report.total_bonus)
    return wb


def turnover_matrix_workbook(report: dict) -> Workbook:
    months: list[str] = list(report.get("months") or [])
    view = report.get("view") or "matrix"
    is_main = view == "main"
    base_cols = ["Измерение"]
    if is_main:
        base_cols += ["Артикул", "ЖЦТ", "Дней ЖЦТ"]
    if view == "counterparty":
        base_cols += ["Тип работы", "Предложение"]
    month_cols: list[str] = []
    for m in months:
        if is_main:
            month_cols += [f"{m} Реал.", f"{m} Возвр.", f"{m} Прод.", f"{m} Ост."]
        else:
            month_cols += [f"{m} Ост.нач", f"{m} Ост.кон", f"{m} Прод."]
    columns = base_cols + month_cols
    rows: list[list[Any]] = []
    for r in report.get("rows") or []:
        row: list[Any] = [r.get("dimension") or r.get("counterparty") or ""]
        if is_main:
            row += [r.get("article"), r.get("lts"), r.get("lts_days")]
        if view == "counterparty":
            row += [r.get("work_type"), r.get("proposal")]
        for m in months:
            cell = (r.get("months") or {}).get(m) or {}
            if is_main:
                row += [
                    cell.get("realization", 0),
                    cell.get("return_qty", 0),
                    cell.get("sales", 0),
                    cell.get("stock_end", 0),
                ]
            else:
                row += [cell.get("stock_begin", 0), cell.get("stock_end", 0), cell.get("sales", 0)]
        rows.append(row)
    return rows_to_workbook(columns, rows, "Оборачиваемость")


def quarterly_plans_workbook(report: Any) -> Workbook:
    columns = ["Контрагент", "План", "Факт", "% выполнения", "Динамика"]
    rows = [
        (
            c.counterparty,
            float(c.plan),
            float(c.fact),
            float(c.percent),
            c.dynamics,
        )
        for c in report.clients
    ]
    return rows_to_workbook(columns, rows, "ПланФакт")


def nomenclature_workbook(items: Iterable[dict]) -> Workbook:
    columns = ["Артикул", "Наименование", "ЖЦТ", "Дата ЖЦТ", "Тип", "Цвет", "База", "Штрихкод"]
    rows = [
        (
            n.get("article"),
            n.get("name"),
            n.get("lts"),
            n.get("lts_date"),
            n.get("wear_type"),
            n.get("metal_color"),
            n.get("source_id"),
            n.get("barcode"),
        )
        for n in items
    ]
    return rows_to_workbook(columns, rows, "Номенклатура")


def counterparties_workbook(items: Iterable[dict]) -> Workbook:
    columns = ["Наименование", "Тип работы", "%", "Акция", "Регион", "База", "Магазины"]
    rows = [
        (
            c.get("name"),
            c.get("work_type"),
            c.get("work_type_percent"),
            "да" if c.get("is_promo") else "нет",
            c.get("region"),
            c.get("source_id"),
            ", ".join(c.get("shops") or []),
        )
        for c in items
    ]
    return rows_to_workbook(columns, rows, "Контрагенты")


def documents_workbook(items: Iterable[dict]) -> Workbook:
    columns = ["Дата", "Номер", "Контрагент", "Строк", "Кол-во", "Сумма", "База"]
    rows = [
        (
            d.get("doc_date"),
            d.get("doc_number"),
            d.get("counterparty"),
            d.get("lines"),
            d.get("quantity"),
            d.get("amount"),
            d.get("source_id"),
        )
        for d in items
    ]
    return rows_to_workbook(columns, rows, "Документы")
