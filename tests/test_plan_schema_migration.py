import sqlite3

from app.database import db_manager
from app.database.db_manager import DBManager, PLAN_SCHEMA_MIGRATION
from app.models.plan import PlanLevel
from app.services.task_service import TaskService


PLAN_COLUMNS = {
    "plan_level",
    "period_key",
    "period_start",
    "period_end",
    "archived",
    "parent_plan_task_id",
    "source_daily_task_id",
    "generated_date",
}


def create_old_database(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as conn:
        conn.execute(
            """
            CREATE TABLE tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT,
                category TEXT NOT NULL,
                ddl TEXT,
                task_type TEXT NOT NULL DEFAULT 'normal',
                scheduled_at TEXT,
                is_completed INTEGER NOT NULL DEFAULT 0,
                is_highlighted INTEGER NOT NULL DEFAULT 0,
                is_deleted INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                completed_at TEXT
            )
            """
        )
        conn.execute(
            """
            INSERT INTO tasks (
                title, description, category, ddl, task_type, scheduled_at,
                is_completed, is_deleted, created_at, completed_at
            )
            VALUES ('legacy task', '', 'short', NULL, 'normal', NULL, 0, 0, '2026-07-23T09:00:00', NULL)
            """
        )
        conn.commit()


def configure_database(monkeypatch, tmp_path):
    data_dir = tmp_path / "data"
    db_path = data_dir / "schedule.db"
    monkeypatch.setattr(db_manager, "DATA_DIR", data_dir)
    monkeypatch.setattr(db_manager, "DB_PATH", db_path)
    return db_path


def test_plan_schema_migration_adds_columns_and_backup_once(monkeypatch, tmp_path):
    db_path = configure_database(monkeypatch, tmp_path)
    create_old_database(db_path)

    manager = DBManager()
    columns = {
        row["name"]
        for row in manager.fetch_all("PRAGMA table_info(tasks)")
    }
    assert PLAN_COLUMNS.issubset(columns)
    assert manager.fetch_one("SELECT title FROM tasks WHERE title = 'legacy task'") is not None
    assert manager.fetch_one("SELECT name FROM schema_migrations WHERE name = ?", (PLAN_SCHEMA_MIGRATION,)) is not None
    backups = list((db_path.parent / "backups").glob("*.db"))
    assert len(backups) == 1

    DBManager()
    backups_after_second_start = list((db_path.parent / "backups").glob("*.db"))
    assert len(backups_after_second_start) == 1


def test_task_service_queries_plan_tasks_by_level_and_period(monkeypatch, tmp_path):
    configure_database(monkeypatch, tmp_path)
    service = TaskService()
    day_id = service.add_plan_task(
        "day plan",
        plan_level=PlanLevel.DAY,
        now="2026-07-23",
    )
    service.add_plan_task(
        "week plan",
        plan_level=PlanLevel.WEEK,
        now="2026-07-23",
    )

    tasks = service.get_current_plan_tasks(PlanLevel.DAY, "2026-07-23")

    assert [task.task_id for task in tasks] == [day_id]
    assert tasks[0].plan_level == PlanLevel.DAY.value
    assert tasks[0].period_key == "day:2026-07-23"


def test_generated_daily_plan_task_is_not_duplicated(monkeypatch, tmp_path):
    configure_database(monkeypatch, tmp_path)
    service = TaskService()

    first_id = service.get_or_create_generated_daily_plan_task(
        source_daily_task_id=10,
        parent_plan_task_id=20,
        generated_date="2026-07-23",
        title="generated task",
    )
    second_id = service.get_or_create_generated_daily_plan_task(
        source_daily_task_id=10,
        parent_plan_task_id=20,
        generated_date="2026-07-23",
        title="generated task",
    )

    assert second_id == first_id
    rows = service.db.fetch_all(
        """
        SELECT *
        FROM tasks
        WHERE source_daily_task_id = ?
          AND generated_date = ?
        """,
        (10, "2026-07-23"),
    )
    assert len(rows) == 1

