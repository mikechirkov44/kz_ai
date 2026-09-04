from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from app.constants import (
    DEFAULT_PRICE_MARKUP,
    MOTIVATION_GRADES,
    PROMO_MOTIVATION_BONUS,
    PROMO_MOTIVATION_GRADE,
)


@dataclass
class ClientMotivationTotal:
    counterparty_id: UUID
    counterparty: str
    quantity: Decimal = Decimal(0)
    total_bonus: Decimal = Decimal(0)
    total_cost: Decimal = Decimal(0)
    total_calculated_cost: Decimal = Decimal(0)
    lines: int = 0


def add_client_sale(
    acc: dict[UUID, ClientMotivationTotal],
    *,
    counterparty_id: UUID,
    counterparty: str,
    quantity: Decimal,
    total_bonus: Decimal,
    cost_amount: Decimal = Decimal(0),
    calculated_amount: Decimal = Decimal(0),
) -> None:
    row = acc.get(counterparty_id)
    if row is None:
        row = ClientMotivationTotal(counterparty_id=counterparty_id, counterparty=counterparty)
        acc[counterparty_id] = row
    row.quantity += Decimal(quantity)
    row.total_bonus += Decimal(total_bonus)
    row.total_cost += Decimal(cost_amount)
    row.total_calculated_cost += Decimal(calculated_amount)
    row.lines += 1


def sorted_client_totals(acc: dict[UUID, ClientMotivationTotal]) -> list[ClientMotivationTotal]:
    return sorted(acc.values(), key=lambda r: (-r.total_bonus, r.counterparty.lower()))


def motivation_grade(price: Decimal) -> tuple[Decimal, str]:
    """Return (bonus_per_unit, grade_label) for a sale price."""
    value = Decimal(price)
    for max_price, bonus, label in MOTIVATION_GRADES:
        if max_price is None or value <= Decimal(max_price):
            return Decimal(bonus), label
    return Decimal(MOTIVATION_GRADES[-1][1]), MOTIVATION_GRADES[-1][2]


def calculate_line_bonus(
    *,
    price: Decimal,
    quantity: Decimal,
    is_promo_motivation: bool = False,
) -> tuple[Decimal, str, Decimal]:
    """Return (bonus_per_unit, grade, total_bonus). Do not merge different prices."""
    if is_promo_motivation:
        bonus = Decimal(PROMO_MOTIVATION_BONUS)
        return bonus, PROMO_MOTIVATION_GRADE, bonus * Decimal(quantity)
    bonus, grade = motivation_grade(price)
    return bonus, grade, bonus * Decimal(quantity)


def calculated_unit_price(avg_realization: Decimal | None, markup: Decimal | None = None) -> Decimal | None:
    """Стоимость расчётная (за ед.) = средняя цена реализации × наценка."""
    if avg_realization is None:
        return None
    factor = Decimal(str(markup if markup is not None else DEFAULT_PRICE_MARKUP))
    return (Decimal(avg_realization) * factor).quantize(Decimal("0.01"))


def line_cost_metrics(
    *,
    price: Decimal,
    quantity: Decimal,
    avg_realization: Decimal | None,
) -> tuple[Decimal, Decimal | None, Decimal | None, Decimal | None]:
    """Return (cost_amount, calculated_unit, calculated_amount, difference_percent).

    Разница % = (стоимость − расчётная) / расчётная × 100.
    """
    qty = Decimal(quantity)
    cost_amount = (Decimal(price) * qty).quantize(Decimal("0.01"))
    calc_unit = calculated_unit_price(avg_realization)
    if calc_unit is None:
        return cost_amount, None, None, None
    calc_amount = (calc_unit * qty).quantize(Decimal("0.01"))
    if calc_amount == 0:
        return cost_amount, calc_unit, calc_amount, None
    diff = ((cost_amount - calc_amount) / calc_amount * Decimal(100)).quantize(Decimal("0.01"))
    return cost_amount, calc_unit, calc_amount, diff


def grade_sort_key(grade: str) -> tuple[int, str]:
    """Доп. мотивация first, then bands low→high as in 1C."""
    if grade == PROMO_MOTIVATION_GRADE or grade.startswith("Доп"):
        return (0, grade)
    for idx, (_, _, label) in enumerate(MOTIVATION_GRADES, start=1):
        if grade == label:
            return (idx, grade)
    return (100, grade)


def normalize_work_type(raw: str | None) -> str | None:
    if raw is None:
        return None
    value = raw.strip().lower()
    mapping = {
        "удержание": "hold",
        "hold": "hold",
        "рост": "growth",
        "прирост": "growth",
        "growth": "growth",
        "падение": "decline",
        "decline": "decline",
    }
    return mapping.get(value, value)


WORK_TYPE_LABEL_RU = {
    "hold": "Удержание",
    "growth": "Рост",
    "decline": "Падение",
}


def work_type_label(raw: str | None) -> str:
    normalized = normalize_work_type(raw)
    if normalized in WORK_TYPE_LABEL_RU:
        return WORK_TYPE_LABEL_RU[normalized]
    return (raw or "").strip() or "—"
