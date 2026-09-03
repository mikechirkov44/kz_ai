from app.domain.motivation import calculate_line_bonus
from decimal import Decimal


def test_tz_motivation_example_total():
    lines = [
        calculate_line_bonus(price=Decimal("95000"), quantity=Decimal("2")),
        calculate_line_bonus(price=Decimal("150000"), quantity=Decimal("1")),
        calculate_line_bonus(price=Decimal("420000"), quantity=Decimal("1")),
        calculate_line_bonus(price=Decimal("180000"), quantity=Decimal("1")),
    ]
    total = sum(t for _, _, t in lines)
    assert total == Decimal("13000")
