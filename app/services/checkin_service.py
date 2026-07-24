from app.database.db_manager import DBManager


class CheckinService:
    def __init__(self):
        self.db = DBManager()

    def add_daily_checkin(self, task_id, checkin_date, completed_at, completion_note=None):
        sql = """
        INSERT OR REPLACE INTO daily_checkins (
            task_id, checkin_date, is_completed, completed_at, completion_note
        )
        VALUES (?, ?, 1, ?, ?)
        """

        return self.db.execute(sql, (task_id, checkin_date, completed_at, completion_note))

    def add_daily_missed(self, task_id, checkin_date, settled_at):
        sql = """
        INSERT OR IGNORE INTO daily_checkins (
            task_id, checkin_date, is_completed, completed_at
        )
        VALUES (?, ?, 0, ?)
        """

        return self.db.execute(sql, (task_id, checkin_date, settled_at))

    def get_checkins_by_task(self, task_id):
        sql = """
        SELECT *
        FROM daily_checkins
        WHERE task_id = ?
        ORDER BY checkin_date DESC
        """

        return self.db.fetch_all(sql, (task_id,))

    def get_checkin_dates_by_task(self, task_id):
        rows = self.get_checkins_by_task(task_id)
        return {row["checkin_date"] for row in rows if row["is_completed"]}

    def get_checkin_statuses_by_task(self, task_id):
        rows = self.get_checkins_by_task(task_id)
        return {row["checkin_date"]: bool(row["is_completed"]) for row in rows}
