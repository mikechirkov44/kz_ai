from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from app.constants import INTERNAL_WAREHOUSES


@dataclass(frozen=True)
class IlliquidCheckInput:
    lts: str | None
    lts_date: date | None
    order_date: date | None
    order_target_warehouse: str | None
    order_target_counterparty_ref: str | None
    realization_counterparty_ref: str | None
    amount: Decimal
    order_counterparty_name: str | None = None
    same_client_group: bool | None = None
    has_client_order: bool | None = None


def is_internal_warehouse(name: str | None) -> bool:
    if not name:
        return False
    normalized = " ".join(name.strip().lower().split())
    return any(" ".join(w.lower().split()) == normalized for w in INTERNAL_WAREHOUSES)


def _is_exit_lts(lts: str | None) -> bool:
    return "вывод" in (lts or "").strip().lower()


def _has_client_order(item: IlliquidCheckInput) -> bool:
    if item.has_client_order is not None:
        return item.has_client_order
    return bool(item.order_date or item.order_target_warehouse or item.order_target_counterparty_ref)


def _same_client_group(item: IlliquidCheckInput) -> bool | None:
    if item.same_client_group is not None:
        return item.same_client_group
    if item.order_target_counterparty_ref and item.realization_counterparty_ref:
        return item.order_target_counterparty_ref == item.realization_counterparty_ref
    return None


def include_in_fact(item: IlliquidCheckInput) -> bool:
    """
    Факт = реализации за квартал (Excel «Как считать ФАКТ»). Возвраты не вычитаем.

    ЖЦТ «Вывод» не входит, если клиент сам заказал изделие в производство
    (заказ на этого клиента или его магазин, и «Вывод» уже стоял на дату заказа).
    """
    if not _is_exit_lts(item.lts):
        return True

    if not _has_client_order(item):
        return True

    if is_internal_warehouse(item.order_target_warehouse) or is_internal_warehouse(
        item.order_counterparty_name
    ):
        return True

    same_group = _same_client_group(item)
    if same_group is False:
        return True
    if same_group is True and item.lts_date and item.order_date:
        # «Вывод» строго после заказа — факт; в день заказа и раньше — неликвид, не факт.
        return item.lts_date > item.order_date
    return True


def quarter_bounds(year: int, quarter: int) -> tuple[date, date]:
    start_month = (quarter - 1) * 3 + 1
    start = date(year, start_month, 1)
    if quarter == 4:
        end = date(year, 12, 31)
    else:
        end_month = start_month + 3
        end = date(year, end_month, 1) - timedelta(days=1)
    return start, end
