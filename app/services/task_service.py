from datetime import datetime

from app.database.db_manager import DBManager
from app.models.task import Task
from app.services.checkin_service import CheckinService
from app.services.history_service import HistoryService


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

        if task_type != "timed":
            task_type = "daily" if category == "daily" else "normal"
            scheduled_at = None

        sql = """
        INSERT INTO tasks (
            title, description, category, ddl, task_type, scheduled_at,
            is_completed, is_highlighted,
            created_at, completed_at
        )
        VALUES (?, ?, ?, ?, ?, ?, 0, 0, ?, NULL)
        """

        return self.db.execute(
            sql,
            (title, description, category, ddl, task_type, scheduled_at, now)
        )

    def get_uncompleted_tasks(self):
        sql = """
        SELECT *
        FROM tasks
        WHERE is_completed = 0
        ORDER BY 
            CASE WHEN task_type = 'timed' THEN 0 ELSE 1 END,
            CASE WHEN task_type = 'timed' THEN scheduled_at END ASC,
            is_highlighted DESC,
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
        ORDER BY completed_at DESC
        """

        rows = self.db.fetch_all(sql)
        return [Task.from_row(row) for row in rows]

    def get_timed_tasks(self):
        sql = """
        SELECT *
        FROM tasks
        WHERE is_completed = 0 AND task_type = 'timed'
        ORDER BY
            scheduled_at IS NULL,
            scheduled_at ASC,
            created_at DESC
        """

        rows = self.db.fetch_all(sql)
        return [Task.from_row(row) for row in rows]

    def get_tasks_by_category(self, category):
        sql = """
        SELECT *
        FROM tasks
        WHERE is_completed = 0 AND category = ?
        ORDER BY
            CASE WHEN task_type = 'timed' THEN 0 ELSE 1 END,
            CASE WHEN task_type = 'timed' THEN scheduled_at END ASC,
            is_highlighted DESC,
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

        completed_at = datetime.now().isoformat(timespec="seconds")

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
            checkin_date = datetime.fromisoformat(completed_at).date().isoformat()
            self.checkin_service.add_daily_checkin(
                task.task_id,
                checkin_date,
                completed_at,
            )

    def get_daily_tasks(self):
        sql = """
        SELECT *
        FROM tasks
        WHERE task_type = 'daily' OR category = 'daily'
        ORDER BY created_at DESC
        """

        rows = self.db.fetch_all(sql)
        return [Task.from_row(row) for row in rows]

    def delete_task(self, task_id):
        sql = """
        DELETE FROM tasks
        WHERE id = ?
        """

        self.db.execute(sql, (task_id,))

    def toggle_highlight(self, task_id):
        task = self.get_task_by_id(task_id)

        if task is None:
            return

        new_value = 0 if task.is_highlighted else 1

        sql = """
        UPDATE tasks
        SET is_highlighted = ?
        WHERE id = ?
        """

        self.db.execute(sql, (new_value, task_id))

    def get_task_by_id(self, task_id):
        sql = """
        SELECT *
        FROM tasks
        WHERE id = ?
        """

        row = self.db.fetch_one(sql, (task_id,))

        if row is None:
            return None

        return Task.from_row(row)

    def update_task(self, task_id, title, description, category, ddl):
        sql = """
        UPDATE tasks
        SET title = ?,
            description = ?,
            category = ?,
            ddl = ?
        WHERE id = ?
        """

        self.db.execute(
            sql,
            (title, description, category, ddl, task_id)
        )
