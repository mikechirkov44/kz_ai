from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from app.constants import MOTIVATION_GRADES, PROMO_MOTIVATION_BONUS


@dataclass
class ClientMotivationTotal:
    counterparty_id: UUID
    counterparty: str
    quantity: Decimal = Decimal(0)
    total_bonus: Decimal = Decimal(0)
    lines: int = 0


def add_client_sale(
    acc: dict[UUID, ClientMotivationTotal],
    *,
    counterparty_id: UUID,
    counterparty: str,
    quantity: Decimal,
    total_bonus: Decimal,
) -> None:
    row = acc.get(counterparty_id)
    if row is None:
        row = ClientMotivationTotal(counterparty_id=counterparty_id, counterparty=counterparty)
        acc[counterparty_id] = row
    row.quantity += Decimal(quantity)
    row.total_bonus += Decimal(total_bonus)
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
        return bonus, "Доп. мотивация", bonus * Decimal(quantity)
    bonus, grade = motivation_grade(price)
    return bonus, grade, bonus * Decimal(quantity)


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
