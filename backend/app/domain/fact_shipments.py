from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Any, Iterable
from uuid import UUID

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


def is_internal_warehouse(name: str | None) -> bool:
    if not name:
        return False
    normalized = name.strip().lower()
    return any(w.lower() == normalized for w in INTERNAL_WAREHOUSES)


def include_in_fact(item: IlliquidCheckInput) -> bool:
    """
    База: реализации − возвраты.
    Для ЖЦТ «Вывод» — исключить навязанный неликвид (дата ЖЦТ раньше даты заказа
    тому же клиенту).
    """
    if not item.lts or item.lts.strip().lower() != "вывод":
        return True

    # Нет заказа → Факт
    if item.order_date is None and not item.order_target_warehouse and not item.order_target_counterparty_ref:
        return True

    if is_internal_warehouse(item.order_target_warehouse):
        return True

    if (
        item.order_target_counterparty_ref
        and item.realization_counterparty_ref
        and item.order_target_counterparty_ref != item.realization_counterparty_ref
    ):
        return True

    same_client = (
        item.order_target_counterparty_ref
        and item.realization_counterparty_ref
        and item.order_target_counterparty_ref == item.realization_counterparty_ref
    )
    if same_client and item.lts_date and item.order_date:
        # Дата ЖЦТ Вывод ПОЗЖЕ заказа → Факт; РАНЬШЕ → не учитывать
        return item.lts_date >= item.order_date

    # Пустой заказ / неизвестная связь → Факт
    return True


def return_matches_realization(
    *,
    real_series: str | None,
    real_nom_id: UUID | None,
    ret_series: str | None,
    ret_nom_id: UUID | None,
) -> bool:
    """Same-quarter return of the same series (or SKU) cancels that shipment."""
    if real_series and ret_series:
        return real_series == ret_series
    return bool(real_nom_id and ret_nom_id and real_nom_id == ret_nom_id)


def cancelled_realization_ids(realizations: Iterable[Any], returns: Iterable[Any]) -> set[Any]:
    """Pair each return to at most one realization (series, else nomenclature)."""
    unused = list(returns)
    cancelled: set[Any] = set()
    for real in realizations:
        real_id = getattr(real, "id", None)
        for idx, ret in enumerate(unused):
            if return_matches_realization(
                real_series=getattr(real, "series", None),
                real_nom_id=getattr(real, "nomenclature_id", None),
                ret_series=getattr(ret, "series", None),
                ret_nom_id=getattr(ret, "nomenclature_id", None),
            ):
                if real_id is not None:
                    cancelled.add(real_id)
                unused.pop(idx)
                break
    return cancelled


def quarter_bounds(year: int, quarter: int) -> tuple[date, date]:
    start_month = (quarter - 1) * 3 + 1
    start = date(year, start_month, 1)
    if quarter == 4:
        end = date(year, 12, 31)
    else:
        end_month = start_month + 3
        end = date(year, end_month, 1) - timedelta(days=1)
    return start, end
