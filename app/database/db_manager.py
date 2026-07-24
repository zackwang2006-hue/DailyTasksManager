import shutil
import sqlite3
from contextlib import contextmanager
from datetime import datetime

from app.config import DB_PATH, DATA_DIR
from app.models.priority import PRIORITY_SCHEMA_MIGRATION


PLAN_SCHEMA_MIGRATION = "20260723_plan_schema"
MINIMAL_ACTION_SCHEMA_MIGRATION = "20260724_minimal_action_schema"
COMPLETION_NOTE_SCHEMA_MIGRATION = "20260724_completion_note_schema"
REPORT_SCHEMA_MIGRATION = "20260724_period_report_schema"


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
    completed_at TEXT,
    is_important INTEGER NOT NULL DEFAULT 0,
    is_urgent INTEGER NOT NULL DEFAULT 0,
    is_fixed_event INTEGER NOT NULL DEFAULT 0,
    priority_level INTEGER NOT NULL DEFAULT 4,
    fixed_time TEXT,
    minimal_action TEXT
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
    created_at TEXT,
    completion_note TEXT
);
"""

CREATE_DAILY_CHECKINS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS daily_checkins (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id INTEGER NOT NULL,
    checkin_date TEXT NOT NULL,
    is_completed INTEGER NOT NULL DEFAULT 1,
    completed_at TEXT NOT NULL,
    completion_note TEXT,
    UNIQUE(task_id, checkin_date)
);
"""

CREATE_SCHEMA_MIGRATIONS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    name TEXT PRIMARY KEY,
    applied_at TEXT NOT NULL
);
"""

CREATE_REPORT_SETTINGS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS report_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""

CREATE_PERIOD_REPORTS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS period_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    period_type TEXT NOT NULL,
    period_start TEXT NOT NULL,
    period_end TEXT NOT NULL,
    report_title TEXT,
    file_path TEXT,
    markdown TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    api_attempts INTEGER NOT NULL DEFAULT 0,
    email_attempts INTEGER NOT NULL DEFAULT 0,
    last_error TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    sent_at TEXT,
    UNIQUE(period_type, period_start, period_end)
);
"""


class DBManager:
    def __init__(self):
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.db_path = DB_PATH
        self.had_existing_db = self.db_path.exists() and self.db_path.stat().st_size > 0
        self.migration_backup_path = None
        if self.had_existing_db and not self.migration_exists_in_database(PLAN_SCHEMA_MIGRATION):
            self.backup_database_file(PLAN_SCHEMA_MIGRATION)
        self.init_db()

    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    @contextmanager
    def transaction(self):
        conn = self.get_connection()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def init_db(self):
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(CREATE_TASKS_TABLE_SQL)
            cursor.execute(CREATE_TASK_LOGS_TABLE_SQL)
            cursor.execute(CREATE_DAILY_CHECKINS_TABLE_SQL)
            cursor.execute(CREATE_SCHEMA_MIGRATIONS_TABLE_SQL)
            cursor.execute(CREATE_REPORT_SETTINGS_TABLE_SQL)
            cursor.execute(CREATE_PERIOD_REPORTS_TABLE_SQL)
            self.migrate_tasks_table(cursor)
            self.migrate_priority_columns(cursor)
            self.migrate_minimal_action_column(cursor)
            self.migrate_completion_note_columns(cursor)
            self.migrate_report_tables(cursor)
            self.migrate_task_logs_table(cursor)
            conn.commit()
        finally:
            conn.close()

    def migrate_tasks_table(self, cursor):
        cursor.execute("PRAGMA table_info(tasks)")
        columns = {row["name"] for row in cursor.fetchall()}
        plan_columns = {
            "plan_level": "TEXT",
            "period_key": "TEXT",
            "period_start": "TEXT",
            "period_end": "TEXT",
            "archived": "INTEGER NOT NULL DEFAULT 0",
            "parent_plan_task_id": "INTEGER",
            "source_daily_task_id": "INTEGER",
            "generated_date": "TEXT",
        }
        missing_plan_columns = set(plan_columns) - columns
        if missing_plan_columns:
            self.backup_before_migration(cursor, PLAN_SCHEMA_MIGRATION)

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

        for column, definition in plan_columns.items():
            if column not in columns:
                cursor.execute(f"ALTER TABLE tasks ADD COLUMN {column} {definition}")

        cursor.execute(
            """
            UPDATE tasks
            SET task_type = 'daily'
            WHERE category = 'daily'
              AND (task_type IS NULL OR task_type = 'normal')
            """
        )
        cursor.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS idx_tasks_daily_generated_unique
            ON tasks(source_daily_task_id, generated_date)
            WHERE source_daily_task_id IS NOT NULL
              AND generated_date IS NOT NULL
              AND COALESCE(is_deleted, 0) = 0
            """
        )
        if missing_plan_columns or not self.is_migration_applied(cursor, PLAN_SCHEMA_MIGRATION):
            self.mark_migration_applied(cursor, PLAN_SCHEMA_MIGRATION)

    def migrate_priority_columns(self, cursor):
        cursor.execute("PRAGMA table_info(tasks)")
        columns = {row["name"] for row in cursor.fetchall()}
        priority_columns = {
            "is_important": "INTEGER NOT NULL DEFAULT 0",
            "is_urgent": "INTEGER NOT NULL DEFAULT 0",
            "is_fixed_event": "INTEGER NOT NULL DEFAULT 0",
            "priority_level": "INTEGER NOT NULL DEFAULT 4",
            "fixed_time": "TEXT",
        }
        missing_priority_columns = set(priority_columns) - columns
        if missing_priority_columns:
            self.backup_before_migration(cursor, PRIORITY_SCHEMA_MIGRATION)

        for column, definition in priority_columns.items():
            if column not in columns:
                cursor.execute(f"ALTER TABLE tasks ADD COLUMN {column} {definition}")

        cursor.execute(
            """
            UPDATE tasks
            SET is_important = COALESCE(is_important, 0),
                is_urgent = COALESCE(is_urgent, 0),
                is_fixed_event = CASE
                    WHEN COALESCE(is_fixed_event, 0) = 1
                      OR (scheduled_at IS NOT NULL AND COALESCE(priority_level, 4) = 0)
                    THEN 1
                    ELSE 0
                END,
                priority_level = COALESCE(priority_level, 4),
                fixed_time = CASE
                    WHEN fixed_time IS NULL
                     AND scheduled_at IS NOT NULL
                     AND (COALESCE(is_fixed_event, 0) = 1 OR COALESCE(priority_level, 4) = 0)
                    THEN substr(scheduled_at, 12, 8)
                    ELSE fixed_time
                END
            """
        )
        if missing_priority_columns or not self.is_migration_applied(cursor, PRIORITY_SCHEMA_MIGRATION):
            self.mark_migration_applied(cursor, PRIORITY_SCHEMA_MIGRATION)

    def migrate_minimal_action_column(self, cursor):
        cursor.execute("PRAGMA table_info(tasks)")
        columns = {row["name"] for row in cursor.fetchall()}
        if "minimal_action" not in columns:
            self.backup_before_migration(cursor, MINIMAL_ACTION_SCHEMA_MIGRATION)
            cursor.execute("ALTER TABLE tasks ADD COLUMN minimal_action TEXT")

        cursor.execute(
            """
            UPDATE tasks
            SET minimal_action = CASE
                WHEN TRIM(COALESCE(title, '')) = '' THEN '开始行动'
                ELSE substr(TRIM(title), 1, 12)
            END
            WHERE minimal_action IS NULL
               OR TRIM(minimal_action) = ''
            """
        )
        if (
            "minimal_action" not in columns
            or not self.is_migration_applied(cursor, MINIMAL_ACTION_SCHEMA_MIGRATION)
        ):
            self.mark_migration_applied(cursor, MINIMAL_ACTION_SCHEMA_MIGRATION)

    def migrate_task_logs_table(self, cursor):
        cursor.execute("PRAGMA table_info(task_logs)")
        columns = {row["name"] for row in cursor.fetchall()}

        if "record_date" not in columns:
            cursor.execute("ALTER TABLE task_logs ADD COLUMN record_date TEXT")

    def migrate_completion_note_columns(self, cursor):
        changed = False
        cursor.execute("PRAGMA table_info(task_logs)")
        log_columns = {row["name"] for row in cursor.fetchall()}
        cursor.execute("PRAGMA table_info(daily_checkins)")
        checkin_columns = {row["name"] for row in cursor.fetchall()}

        if "completion_note" not in log_columns or "completion_note" not in checkin_columns:
            self.backup_before_migration(cursor, COMPLETION_NOTE_SCHEMA_MIGRATION)

        if "completion_note" not in log_columns:
            cursor.execute("ALTER TABLE task_logs ADD COLUMN completion_note TEXT")
            changed = True
        if "completion_note" not in checkin_columns:
            cursor.execute("ALTER TABLE daily_checkins ADD COLUMN completion_note TEXT")
            changed = True

        if changed or not self.is_migration_applied(cursor, COMPLETION_NOTE_SCHEMA_MIGRATION):
            self.mark_migration_applied(cursor, COMPLETION_NOTE_SCHEMA_MIGRATION)

    def migrate_report_tables(self, cursor):
        cursor.execute(CREATE_REPORT_SETTINGS_TABLE_SQL)
        cursor.execute(CREATE_PERIOD_REPORTS_TABLE_SQL)
        cursor.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS idx_period_reports_unique_period
            ON period_reports(period_type, period_start, period_end)
            """
        )
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_period_reports_status
            ON period_reports(status, period_end)
            """
        )
        if not self.is_migration_applied(cursor, REPORT_SCHEMA_MIGRATION):
            self.mark_migration_applied(cursor, REPORT_SCHEMA_MIGRATION)

    def backup_before_migration(self, cursor, migration_name):
        if (
            not self.had_existing_db
            or self.migration_backup_path is not None
            or self.is_migration_applied(cursor, migration_name)
        ):
            return
        self.backup_database_file(migration_name)

    def backup_database_file(self, migration_name):
        backup_dir = self.db_path.parent / "backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = backup_dir / f"{self.db_path.stem}_{migration_name}_{timestamp}{self.db_path.suffix}"
        shutil.copy2(self.db_path, backup_path)
        self.migration_backup_path = backup_path

    def migration_exists_in_database(self, migration_name):
        try:
            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT 1
                    FROM sqlite_master
                    WHERE type = 'table'
                      AND name = 'schema_migrations'
                    """
                )
                if cursor.fetchone() is None:
                    return False
                cursor.execute(
                    "SELECT 1 FROM schema_migrations WHERE name = ?",
                    (migration_name,),
                )
                return cursor.fetchone() is not None
            finally:
                conn.close()
        except sqlite3.DatabaseError:
            return False

    def is_migration_applied(self, cursor, migration_name):
        cursor.execute(
            "SELECT 1 FROM schema_migrations WHERE name = ?",
            (migration_name,),
        )
        return cursor.fetchone() is not None

    def mark_migration_applied(self, cursor, migration_name):
        cursor.execute(
            """
            INSERT OR IGNORE INTO schema_migrations (name, applied_at)
            VALUES (?, ?)
            """,
            (migration_name, datetime.now().isoformat(timespec="seconds")),
        )

    def execute(self, sql, params=None):
        if params is None:
            params = ()

        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(sql, params)
            conn.commit()
            return cursor.lastrowid
        finally:
            conn.close()

    def fetch_all(self, sql, params=None):
        if params is None:
            params = ()

        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(sql, params)
            rows = cursor.fetchall()
            return rows
        finally:
            conn.close()

    def fetch_one(self, sql, params=None):
        if params is None:
            params = ()

        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(sql, params)
            row = cursor.fetchone()
            return row
        finally:
            conn.close()
