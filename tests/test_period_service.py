from datetime import date

from app.models.plan import PlanLevel
from app.services.period_service import FIVE_YEAR_BASE_YEAR, period_service


def assert_period(level, target, expected_start, expected_end):
    period = period_service.current_period(level, target)
    assert period.start == expected_start
    assert period.end == expected_end
    assert period.key == f"{PlanLevel(level).value}:{expected_start.isoformat()}"
    return period


def test_periods_for_2026_07_23():
    assert FIVE_YEAR_BASE_YEAR == 2026
    assert_period(PlanLevel.DAY, date(2026, 7, 23), date(2026, 7, 23), date(2026, 7, 23))
    assert_period(PlanLevel.WEEK, date(2026, 7, 23), date(2026, 7, 20), date(2026, 7, 26))
    assert_period(PlanLevel.MONTH, date(2026, 7, 23), date(2026, 7, 1), date(2026, 7, 31))
    assert_period(PlanLevel.QUARTER, date(2026, 7, 23), date(2026, 7, 1), date(2026, 9, 30))
    assert_period(PlanLevel.YEAR, date(2026, 7, 23), date(2026, 1, 1), date(2026, 12, 31))
    assert_period(PlanLevel.FIVE_YEAR, date(2026, 7, 23), date(2026, 1, 1), date(2030, 12, 31))


def test_week_switch_from_2026_07_26_to_2026_07_27():
    assert_period(PlanLevel.WEEK, date(2026, 7, 26), date(2026, 7, 20), date(2026, 7, 26))
    assert_period(PlanLevel.WEEK, date(2026, 7, 27), date(2026, 7, 27), date(2026, 8, 2))


def test_month_switch_from_2026_07_31_to_2026_08_01():
    assert_period(PlanLevel.MONTH, date(2026, 7, 31), date(2026, 7, 1), date(2026, 7, 31))
    assert_period(PlanLevel.MONTH, date(2026, 8, 1), date(2026, 8, 1), date(2026, 8, 31))


def test_quarter_switch_from_2026_09_30_to_2026_10_01():
    assert_period(PlanLevel.QUARTER, date(2026, 9, 30), date(2026, 7, 1), date(2026, 9, 30))
    assert_period(PlanLevel.QUARTER, date(2026, 10, 1), date(2026, 10, 1), date(2026, 12, 31))


def test_year_switch_from_2026_12_31_to_2027_01_01():
    assert_period(PlanLevel.YEAR, date(2026, 12, 31), date(2026, 1, 1), date(2026, 12, 31))
    assert_period(PlanLevel.YEAR, date(2027, 1, 1), date(2027, 1, 1), date(2027, 12, 31))


def test_five_year_switch_from_2030_12_31_to_2031_01_01():
    assert_period(PlanLevel.FIVE_YEAR, date(2030, 12, 31), date(2026, 1, 1), date(2030, 12, 31))
    assert_period(PlanLevel.FIVE_YEAR, date(2031, 1, 1), date(2031, 1, 1), date(2035, 12, 31))


def test_leap_year_february():
    assert_period(PlanLevel.MONTH, date(2028, 2, 10), date(2028, 2, 1), date(2028, 2, 29))


def test_cross_year_week():
    assert_period(PlanLevel.WEEK, date(2027, 1, 1), date(2026, 12, 28), date(2027, 1, 3))


def test_previous_periods():
    assert period_service.previous_period(PlanLevel.DAY, date(2026, 7, 23)).start == date(2026, 7, 22)
    assert period_service.previous_period(PlanLevel.WEEK, date(2026, 7, 27)).start == date(2026, 7, 20)
    assert period_service.previous_period(PlanLevel.MONTH, date(2026, 8, 1)).start == date(2026, 7, 1)
    assert period_service.previous_period(PlanLevel.QUARTER, date(2026, 10, 1)).start == date(2026, 7, 1)
    assert period_service.previous_period(PlanLevel.YEAR, date(2027, 1, 1)).start == date(2026, 1, 1)
    assert period_service.previous_period(PlanLevel.FIVE_YEAR, date(2031, 1, 1)).start == date(2026, 1, 1)

