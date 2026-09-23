"""Loaded sales, stocks and extra motivation: list, edit, delete, export."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.config import settings
from app.domain.articles import find_nomenclature_by_article
from app.domain.excel_validation import blank_shop
from app.models import ClientSale, ClientStock, Counterparty, PromoMotivation, User
from app.services.export_xlsx import rows_to_workbook, workbook_bytes
from app.services.scope import assert_counterparty_access, constrain_counterparty_column

KIND_MODELS = {
    "sales": ClientSale,
    "stocks": ClientStock,
    "promo": PromoMotivation,
}

KIND_TITLES = {
    "sales": "Продажи",
    "stocks": "Остатки",
    "promo": "Доп. мотивация",
}


def register_model(kind: str):
    model = KIND_MODELS.get(kind)
    if model is None:
        raise ValueError("Неизвестный регистр")
    return model


def _counterparty_column(model):
    if model is PromoMotivation:
        return model.counterparty_id
    return model.head_counterparty_id


def _row_dict(kind: str, row, counterparty_name: str) -> dict[str, Any]:
    cp_id = row.counterparty_id if kind == "promo" else row.head_counterparty_id
    payload: dict[str, Any] = {
        "id": str(row.id),
        "counterparty_id": str(cp_id),
        "counterparty_name": counterparty_name,
        "article": row.article,
        "shop": blank_shop(row.shop),
        "quantity": float(row.quantity),
        "upload_id": str(row.upload_id),
    }
    if kind == "sales":
        payload["price"] = float(row.price)
        payload["period_year"] = row.period_year
        payload["period_month"] = row.period_month
    else:
        payload["stock_date"] = row.stock_date.isoformat() if row.stock_date else None
    return payload


def _filtered_stmt(db: Session, kind: str, user: User, q: Optional[str]):
    model = register_model(kind)
    cp_col = _counterparty_column(model)
    stmt = select(model, Counterparty.name).join(Counterparty, Counterparty.id == cp_col)
    stmt = constrain_counterparty_column(stmt, cp_col, db, user)
    if q and q.strip():
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(model.article.ilike(like), Counterparty.name.ilike(like)))
    return stmt, model


def list_register(
    db: Session,
    kind: str,
    user: User,
    *,
    q: Optional[str] = None,
    page: int = 1,
    page_size: int = 50,
) -> dict:
    stmt, model = _filtered_stmt(db, kind, user, q)
    total = db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0
    rows = db.execute(
        stmt.order_by(Counterparty.name, model.article).offset((page - 1) * page_size).limit(page_size)
    ).all()
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [_row_dict(kind, row, name) for row, name in rows],
    }


def get_register_row(db: Session, kind: str, row_id: UUID, user: User):
    model = register_model(kind)
    row = db.get(model, row_id)
    if not row:
        return None
    cp_id = row.counterparty_id if kind == "promo" else row.head_counterparty_id
    assert_counterparty_access(db, user, cp_id)
    return row


def apply_register_edit(
    db: Session,
    row,
    *,
    article: Optional[str] = None,
    quantity: Optional[Decimal] = None,
    shop: Optional[str] = None,
    shop_set: bool = False,
) -> None:
    if article is not None:
        text = article.strip()
        if not text:
            raise ValueError("Укажите артикул")
        nom = find_nomenclature_by_article(db, text)
        if not nom or not (nom.article or nom.barcode):
            raise ValueError("Артикул не найден в 1С")
        row.article = nom.article or nom.barcode
    if quantity is not None:
        try:
            qty = Decimal(str(quantity))
        except (InvalidOperation, ValueError) as exc:
            raise ValueError("Некорректное количество") from exc
        if qty <= 0:
            raise ValueError("Количество должно быть больше 0")
        row.quantity = qty
    if shop_set:
        row.shop = (shop or "").strip() or None


def export_register(db: Session, kind: str, user: User, *, q: Optional[str] = None) -> tuple[bytes, str]:
    stmt, model = _filtered_stmt(db, kind, user, q)
    rows = db.execute(stmt.order_by(Counterparty.name, model.article).limit(settings.export_max_rows)).all()
    if kind == "sales":
        columns = ["Контрагент", "Артикул", "Магазин", "Количество", "Цена", "Год", "Месяц"]
        data = [
            [name, row.article, blank_shop(row.shop) or "", float(row.quantity), float(row.price), row.period_year, row.period_month]
            for row, name in rows
        ]
    else:
        columns = ["Контрагент", "Артикул", "Магазин", "Количество", "Дата"]
        data = [
            [name, row.article, blank_shop(row.shop) or "", float(row.quantity), row.stock_date.isoformat() if row.stock_date else ""]
            for row, name in rows
        ]
    content = workbook_bytes(rows_to_workbook(columns, data, KIND_TITLES[kind]))
    return content, f"register_{kind}.xlsx"
