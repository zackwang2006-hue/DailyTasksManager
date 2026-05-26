from app.database.db_manager import DBManager


class HistoryService:
    def __init__(self):
        self.db = DBManager()

    def add_task_log(self, task):
        sql = """
        INSERT INTO task_logs (
            task_id, title, description, category, task_type,
            ddl, scheduled_at, completed_at, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """

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
                task.created_at,
            ),
        )

    def get_logs_by_date(self, date_str):
        sql = """
        SELECT *
        FROM task_logs
        WHERE date(completed_at) = ?
        ORDER BY completed_at DESC
        """

        return self.db.fetch_all(sql, (date_str,))

    def get_logs_between(self, start_date, end_date):
        sql = """
        SELECT *
        FROM task_logs
        WHERE date(completed_at) BETWEEN ? AND ?
        ORDER BY completed_at DESC
        """

        return self.db.fetch_all(sql, (start_date, end_date))
