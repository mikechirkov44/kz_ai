from __future__ import annotations

from decimal import Decimal

from app.constants import MOTIVATION_GRADES, PROMO_MOTIVATION_BONUS


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
