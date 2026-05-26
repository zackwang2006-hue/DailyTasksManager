from datetime import datetime

from app.database.db_manager import DBManager
from app.models.task import Task


class TaskService:
    def __init__(self):
        self.db = DBManager()

    def add_task(self, title, description="", category="short", ddl=None):
        now = datetime.now().isoformat(timespec="seconds")

        sql = """
        INSERT INTO tasks (
            title, description, category, ddl,
            is_completed, is_highlighted,
            created_at, completed_at
        )
        VALUES (?, ?, ?, ?, 0, 0, ?, NULL)
        """

        return self.db.execute(
            sql,
            (title, description, category, ddl, now)
        )

    def get_uncompleted_tasks(self):
        sql = """
        SELECT *
        FROM tasks
        WHERE is_completed = 0
        ORDER BY 
            CASE category
                WHEN 'short' THEN 1
                WHEN 'long' THEN 2
                WHEN 'daily' THEN 3
                WHEN 'extra' THEN 4
                ELSE 5
            END,
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

    def get_tasks_by_category(self, category):
        sql = """
        SELECT *
        FROM tasks
        WHERE is_completed = 0 AND category = ?
        ORDER BY ddl IS NULL, ddl ASC, created_at DESC
        """

        rows = self.db.fetch_all(sql, (category,))
        return [Task.from_row(row) for row in rows]

    def complete_task(self, task_id):
        now = datetime.now().isoformat(timespec="seconds")

        sql = """
        UPDATE tasks
        SET is_completed = 1,
            completed_at = ?
        WHERE id = ?
        """

        self.db.execute(sql, (now, task_id))

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