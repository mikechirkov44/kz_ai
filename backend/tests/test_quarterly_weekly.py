from datetime import date
from decimal import Decimal

from app.domain.quarterly import (
    allocate_weekly_plan,
    build_weekly_plan_fact,
    fact_amounts_by_week,
    quarter_weeks,
    week_index_for_date,
)


def test_quarter_weeks_q1_2026_clips_partial_ends():
    weeks = quarter_weeks(2026, 1)
    assert weeks[0].start == date(2026, 1, 1)
    assert weeks[0].end == date(2026, 1, 4)
    assert weeks[0].days == 4
    assert weeks[-1].start == date(2026, 3, 30)
    assert weeks[-1].end == date(2026, 3, 31)
    assert weeks[-1].days == 2
    assert sum(week.days for week in weeks) == 90
    assert week_index_for_date(date(2026, 1, 3), weeks) == 1
    assert week_index_for_date(date(2026, 1, 5), weeks) == 2
    assert week_index_for_date(date(2025, 12, 31), weeks) is None
    assert week_index_for_date(date(2026, 4, 1), weeks) is None


def test_quarter_weeks_q3_2026():
    weeks = quarter_weeks(2026, 3)
    assert weeks[0].start == date(2026, 7, 1)
    assert weeks[0].end == date(2026, 7, 5)
    assert weeks[0].days == 5
    assert weeks[-1].start == date(2026, 9, 28)
    assert weeks[-1].end == date(2026, 9, 30)
    assert weeks[-1].days == 3
    assert sum(week.days for week in weeks) == 92


def test_allocate_weekly_plan_sums_to_total():
    parts = allocate_weekly_plan(Decimal("1000"), [4, 7, 7, 2])
    assert sum(parts, Decimal(0)) == Decimal("1000.00")
    assert parts[0] == Decimal("200.00")
    assert parts[-1] == Decimal("100.00")
    assert allocate_weekly_plan(Decimal(0), [7, 7]) == [Decimal("0.00"), Decimal("0.00")]
    assert allocate_weekly_plan(Decimal(1), []) == []
    thirds = allocate_weekly_plan(Decimal("1.00"), [1, 1, 1])
    assert sum(thirds, Decimal(0)) == Decimal("1.00")
    assert thirds[:2] == [Decimal("0.33"), Decimal("0.33")]
    assert thirds[2] == Decimal("0.34")


def test_build_weekly_plan_fact_marks_current_and_buckets_fact():
    weeks = quarter_weeks(2026, 3)
    facts = fact_amounts_by_week(
        weeks,
        [
            (date(2026, 7, 3), Decimal("100")),
            (date(2026, 7, 5), Decimal("50")),
            (date(2026, 7, 6), Decimal("20")),
            (date(2026, 6, 30), Decimal("999")),
        ],
    )
    rows = build_weekly_plan_fact(weeks, Decimal("920"), facts, date(2026, 7, 3))
    assert rows[0].is_current is True
    assert rows[1].is_current is False
    assert rows[0].fact == Decimal("150.00")
    assert rows[1].fact == Decimal("20.00")
    assert sum((row.plan for row in rows), Decimal(0)) == Decimal("920.00")
    assert rows[0].percent == Decimal("300.00")
    assert not any(row.is_current for row in build_weekly_plan_fact(weeks, Decimal(1), {}, date(2025, 1, 1)))
