from datetime import datetime

from app.database.db_manager import DBManager
from app.utils.time_utils import get_business_date


class HistoryService:
    def __init__(self):
        self.db = DBManager()

    def add_task_log(self, task):
        sql = """
        INSERT INTO task_logs (
            task_id, title, description, category, task_type,
            ddl, scheduled_at, completed_at, record_date, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        completed_at = datetime.fromisoformat(task.completed_at)
        record_date = get_business_date(completed_at).isoformat()

        return self.db.execute(
            sql,
            (
                task.task_id,
                task.title,
                task.description,
                task.category,
                task.task_type,
                task.ddl,
                task.scheduled_at,
                task.completed_at,
                record_date,
                task.created_at,
            ),
        )

    def get_logs_by_date(self, date_str):
        sql = """
        SELECT *
        FROM task_logs
        WHERE COALESCE(record_date, date(completed_at)) = ?
        ORDER BY completed_at DESC
        """

        return self.db.fetch_all(sql, (date_str,))

    def get_logs_between(self, start_date, end_date):
        sql = """
        SELECT *
        FROM task_logs
        WHERE COALESCE(record_date, date(completed_at)) BETWEEN ? AND ?
        ORDER BY completed_at DESC
        """

        return self.db.fetch_all(sql, (start_date, end_date))
