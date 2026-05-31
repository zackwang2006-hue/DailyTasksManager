from datetime import datetime, date

from app.utils.time_utils import get_business_date, get_daily_default_deadline


def test_business_date_before_4am_belongs_to_previous_day():
    assert get_business_date(datetime(2026, 6, 1, 3, 59)) == date(2026, 5, 31)


def test_business_date_at_4am_belongs_to_same_day():
    assert get_business_date(datetime(2026, 6, 1, 4, 0)) == date(2026, 6, 1)


def test_business_date_after_4am_belongs_to_same_day():
    assert get_business_date(datetime(2026, 6, 1, 4, 1)) == date(2026, 6, 1)


def test_daily_default_deadline_is_tomorrow_0359():
    result = get_daily_default_deadline(datetime(2026, 6, 1, 12, 0))
    assert result == datetime(2026, 6, 2, 3, 59)
