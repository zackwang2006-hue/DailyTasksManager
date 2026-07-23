from datetime import datetime

from app.database import db_manager
from app.services.task_service import TaskService


def make_service(monkeypatch, tmp_path):
    data_dir = tmp_path / "data"
    monkeypatch.setattr(db_manager, "DATA_DIR", data_dir)
    monkeypatch.setattr(db_manager, "DB_PATH", data_dir / "schedule.db")
    return TaskService()


def add_daily_task(service, created_at, is_completed=0, completed_at=None):
    return service.db.execute(
        """
        INSERT INTO tasks (
            title, description, category, ddl, task_type, scheduled_at,
            is_completed, is_deleted, created_at, completed_at
        )
        VALUES (?, '', 'daily', NULL, 'daily', NULL, ?, 0, ?, ?)
        """,
        ("daily task", is_completed, created_at, completed_at),
    )


def get_checkins(service, task_id):
    rows = service.db.fetch_all(
        """
        SELECT checkin_date, is_completed
        FROM daily_checkins
        WHERE task_id = ?
        ORDER BY checkin_date
        """,
        (task_id,),
    )
    return {row["checkin_date"]: bool(row["is_completed"]) for row in rows}


def get_task_row(service, task_id):
    return service.db.fetch_one("SELECT * FROM tasks WHERE id = ?", (task_id,))


def test_previous_uncompleted_daily_task_is_recorded_as_missed_after_midnight(monkeypatch, tmp_path):
    service = make_service(monkeypatch, tmp_path)
    task_id = add_daily_task(service, "2026-06-01T09:00:00")

    service.refresh_daily_tasks(datetime(2026, 6, 2, 0, 0, 0))

    assert get_checkins(service, task_id) == {"2026-06-01": False}
    row = get_task_row(service, task_id)
    assert row["is_completed"] == 0
    assert row["completed_at"] is None


def test_previous_completed_daily_task_keeps_completed_record_after_midnight(monkeypatch, tmp_path):
    service = make_service(monkeypatch, tmp_path)
    completed_at = "2026-06-01T23:59:00"
    task_id = add_daily_task(
        service,
        "2026-06-01T09:00:00",
        is_completed=1,
        completed_at=completed_at,
    )

    service.refresh_daily_tasks(datetime(2026, 6, 2, 0, 0, 0))

    assert get_checkins(service, task_id) == {"2026-06-01": True}
    row = get_task_row(service, task_id)
    assert row["is_completed"] == 0
    assert row["completed_at"] is None


def test_refresh_after_multiple_inactive_days_fills_each_missed_day(monkeypatch, tmp_path):
    service = make_service(monkeypatch, tmp_path)
    task_id = add_daily_task(service, "2026-06-01T09:00:00")

    service.refresh_daily_tasks(datetime(2026, 6, 5, 8, 0, 0))

    assert get_checkins(service, task_id) == {
        "2026-06-01": False,
        "2026-06-02": False,
        "2026-06-03": False,
        "2026-06-04": False,
    }
