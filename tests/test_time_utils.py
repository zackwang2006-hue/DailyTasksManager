from datetime import datetime, date

from app.utils.time_utils import get_business_date, get_daily_default_deadline


def test_business_date_at_2359_belongs_to_same_day():
    assert get_business_date(datetime(2026, 6, 1, 23, 59, 59)) == date(2026, 6, 1)


def test_business_date_at_midnight_belongs_to_new_day():
    assert get_business_date(datetime(2026, 6, 2, 0, 0, 0)) == date(2026, 6, 2)


def test_daily_default_deadline_is_today_235959():
    result = get_daily_default_deadline(datetime(2026, 6, 1, 12, 0))
    assert result == datetime(2026, 6, 1, 23, 59, 59)
