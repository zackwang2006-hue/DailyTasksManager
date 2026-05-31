from datetime import datetime

from app.database.db_manager import DBManager
from app.models.task import Task
from app.services.checkin_service import CheckinService
from app.services.history_service import HistoryService
from app.utils.time_utils import get_business_date, get_daily_default_deadline


class TaskService:
    def __init__(self):
        self.db = DBManager()
        self.history_service = HistoryService()
        self.checkin_service = CheckinService()

    def add_task(
        self,
        title,
        description="",
        category="short",
        ddl=None,
        task_type="normal",
        scheduled_at=None,
    ):
        now = datetime.now().isoformat(timespec="seconds")

        if category == "timed" or task_type == "timed":
            category = "timed"
            task_type = "timed"
            ddl = None
        else:
            task_type = "daily" if category == "daily" else "normal"
            scheduled_at = None
            if task_type == "daily" and not ddl:
                ddl = get_daily_default_deadline().strftime("%Y-%m-%d %H:%M:%S")

        sql = """
        INSERT INTO tasks (
            title, description, category, ddl, task_type, scheduled_at,
            is_completed, is_deleted,
            created_at, completed_at
        )
        VALUES (?, ?, ?, ?, ?, ?, 0, 0, ?, NULL)
        """

        return self.db.execute(
            sql,
            (title, description, category, ddl, task_type, scheduled_at, now)
        )

    def get_uncompleted_tasks(self):
        self.refresh_daily_tasks()

        sql = """
        SELECT *
        FROM tasks
        WHERE is_completed = 0
          AND COALESCE(is_deleted, 0) = 0
        ORDER BY 
            CASE WHEN task_type = 'timed' THEN 0 ELSE 1 END,
            CASE WHEN task_type = 'timed' THEN scheduled_at END ASC,
            ddl IS NULL,
            ddl ASC,
            created_at DESC
        """

        rows = self.db.fetch_all(sql)
        return [Task.from_row(row) for row in rows]

    def get_completed_tasks(self):
        sql = """
        SELECT *
        FROM tasks
        WHERE is_completed = 1
          AND COALESCE(is_deleted, 0) = 0
        ORDER BY completed_at DESC
        """

        rows = self.db.fetch_all(sql)
        return [Task.from_row(row) for row in rows]

    def get_timed_tasks(self):
        sql = """
        SELECT *
        FROM tasks
        WHERE is_completed = 0
          AND task_type = 'timed'
          AND COALESCE(is_deleted, 0) = 0
        ORDER BY
            scheduled_at IS NULL,
            scheduled_at ASC,
            created_at DESC
        """

        rows = self.db.fetch_all(sql)
        return [Task.from_row(row) for row in rows]

    def get_tasks_by_category(self, category):
        self.refresh_daily_tasks()

        sql = """
        SELECT *
        FROM tasks
        WHERE is_completed = 0
          AND category = ?
          AND COALESCE(is_deleted, 0) = 0
        ORDER BY
            CASE WHEN task_type = 'timed' THEN 0 ELSE 1 END,
            CASE WHEN task_type = 'timed' THEN scheduled_at END ASC,
            ddl IS NULL,
            ddl ASC,
            created_at DESC
        """

        rows = self.db.fetch_all(sql, (category,))
        return [Task.from_row(row) for row in rows]

    def complete_task(self, task_id):
        task = self.get_task_by_id(task_id)

        if task is None or task.is_completed:
            return

        completed_time = datetime.now()
        completed_at = completed_time.isoformat(timespec="seconds")

        sql = """
        UPDATE tasks
        SET is_completed = 1,
            completed_at = ?
        WHERE id = ?
        """

        self.db.execute(sql, (completed_at, task_id))

        task.completed_at = completed_at
        self.history_service.add_task_log(task)

        if task.task_type == "daily" or task.category == "daily":
            checkin_date = get_business_date(completed_time).isoformat()
            self.checkin_service.add_daily_checkin(
                task.task_id,
                checkin_date,
                completed_at,
            )

    def get_daily_tasks(self):
        self.refresh_daily_tasks()

        sql = """
        SELECT *
        FROM tasks
        WHERE (task_type = 'daily' OR category = 'daily')
          AND COALESCE(is_deleted, 0) = 0
        ORDER BY created_at DESC
        """

        rows = self.db.fetch_all(sql)
        return [Task.from_row(row) for row in rows]

    def refresh_daily_tasks(self, now=None):
        now = now or datetime.now()
        cycle_date = get_business_date(now).isoformat()

        sql = """
        UPDATE tasks
        SET is_completed = 0,
            completed_at = NULL
        WHERE (task_type = 'daily' OR category = 'daily')
          AND is_completed = 1
          AND COALESCE(is_deleted, 0) = 0
          AND NOT EXISTS (
              SELECT 1
              FROM daily_checkins
              WHERE daily_checkins.task_id = tasks.id
                AND daily_checkins.checkin_date = ?
                AND daily_checkins.is_completed = 1
          )
        """

        self.db.execute(sql, (cycle_date,))

    def get_daily_cycle_date(self, value):
        return get_business_date(value)

    def delete_task(self, task_id):
        task = self.get_task_by_id(task_id)

        if task is not None and (task.task_type == "daily" or task.category == "daily"):
            self.soft_delete_task(task_id)
            return

        sql = """
        DELETE FROM tasks
        WHERE id = ?
        """

        self.db.execute(sql, (task_id,))

    def soft_delete_task(self, task_id):
        sql = """
        UPDATE tasks
        SET is_deleted = 1
        WHERE id = ?
        """

        self.db.execute(sql, (task_id,))

    def get_task_by_id(self, task_id):
        sql = """
        SELECT *
        FROM tasks
        WHERE id = ?
          AND COALESCE(is_deleted, 0) = 0
        """

        row = self.db.fetch_one(sql, (task_id,))

        if row is None:
            return None

        return Task.from_row(row)

    def update_task(
        self,
        task_id,
        title,
        description,
        category,
        ddl,
        task_type="normal",
        scheduled_at=None,
    ):
        if category == "timed" or task_type == "timed":
            category = "timed"
            task_type = "timed"
            ddl = None
        else:
            task_type = "daily" if category == "daily" else "normal"
            scheduled_at = None
            if task_type == "daily" and not ddl:
                ddl = get_daily_default_deadline().strftime("%Y-%m-%d %H:%M:%S")

        sql = """
        UPDATE tasks
        SET title = ?,
            description = ?,
            category = ?,
            ddl = ?,
            task_type = ?,
            scheduled_at = ?
        WHERE id = ?
        """

        self.db.execute(
            sql,
            (title, description, category, ddl, task_type, scheduled_at, task_id)
        )
