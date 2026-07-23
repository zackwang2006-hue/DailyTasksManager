from dataclasses import dataclass
from datetime import datetime

from app.services.checkin_status import get_checkin_cell_status


@dataclass
class DailyTask:
    created_at: str = "2026-06-01T09:00:00"
    scheduled_at: str | None = None


def test_today_uncompleted_is_pending_until_end_of_natural_day():
    status = get_checkin_cell_status(
        DailyTask(),
        datetime(2026, 6, 1).date(),
        datetime(2026, 6, 1, 23, 59, 59),
        completed_dates=set(),
    )

    assert status == "today_pending"


def test_previous_uncompleted_day_is_missed_after_midnight():
    status = get_checkin_cell_status(
        DailyTask(),
        datetime(2026, 6, 1).date(),
        datetime(2026, 6, 2, 0, 0, 0),
        completed_dates=set(),
        missed_dates={"2026-06-01"},
    )

    assert status == "missed"


def test_dates_before_task_creation_are_disabled():
    status = get_checkin_cell_status(
        DailyTask(created_at="2026-06-02T09:00:00"),
        datetime(2026, 6, 1).date(),
        datetime(2026, 6, 3, 12, 0, 0),
        completed_dates=set(),
    )

    assert status == "disabled"


def test_future_dates_are_disabled():
    status = get_checkin_cell_status(
        DailyTask(),
        datetime(2026, 6, 2).date(),
        datetime(2026, 6, 1, 12, 0, 0),
        completed_dates=set(),
    )

    assert status == "disabled"
