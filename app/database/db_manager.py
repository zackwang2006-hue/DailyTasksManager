import sqlite3
from app.config import DB_PATH, DATA_DIR


CREATE_TASKS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS tasks (
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
);
"""

CREATE_TASK_LOGS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS task_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id INTEGER,
    title TEXT NOT NULL,
    description TEXT,
    category TEXT,
    task_type TEXT,
    ddl TEXT,
    scheduled_at TEXT,
    completed_at TEXT NOT NULL,
    record_date TEXT,
    created_at TEXT
);
"""

CREATE_DAILY_CHECKINS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS daily_checkins (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id INTEGER NOT NULL,
    checkin_date TEXT NOT NULL,
    is_completed INTEGER NOT NULL DEFAULT 1,
    completed_at TEXT NOT NULL,
    UNIQUE(task_id, checkin_date)
);
"""


class DBManager:
    def __init__(self):
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.db_path = DB_PATH
        self.init_db()

    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(CREATE_TASKS_TABLE_SQL)
            cursor.execute(CREATE_TASK_LOGS_TABLE_SQL)
            cursor.execute(CREATE_DAILY_CHECKINS_TABLE_SQL)
            self.migrate_tasks_table(cursor)
            self.migrate_task_logs_table(cursor)
            conn.commit()

    def migrate_tasks_table(self, cursor):
        cursor.execute("PRAGMA table_info(tasks)")
        columns = {row["name"] for row in cursor.fetchall()}

        if "task_type" not in columns:
            cursor.execute(
                "ALTER TABLE tasks "
                "ADD COLUMN task_type TEXT NOT NULL DEFAULT 'normal'"
            )

        if "scheduled_at" not in columns:
            cursor.execute("ALTER TABLE tasks ADD COLUMN scheduled_at TEXT")

        if "is_deleted" not in columns:
            cursor.execute(
                "ALTER TABLE tasks "
                "ADD COLUMN is_deleted INTEGER NOT NULL DEFAULT 0"
            )

        cursor.execute(
            """
            UPDATE tasks
            SET task_type = 'daily'
            WHERE category = 'daily'
              AND (task_type IS NULL OR task_type = 'normal')
            """
        )

    def migrate_task_logs_table(self, cursor):
        cursor.execute("PRAGMA table_info(task_logs)")
        columns = {row["name"] for row in cursor.fetchall()}

        if "record_date" not in columns:
            cursor.execute("ALTER TABLE task_logs ADD COLUMN record_date TEXT")

    def execute(self, sql, params=None):
        if params is None:
            params = ()

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, params)
            conn.commit()
            return cursor.lastrowid

    def fetch_all(self, sql, params=None):
        if params is None:
            params = ()

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, params)
            rows = cursor.fetchall()
            return rows

    def fetch_one(self, sql, params=None):
        if params is None:
            params = ()

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, params)
            row = cursor.fetchone()
            return row
