from datetime import datetime

from app.database.db_manager import DBManager
from app.models.report_record import ReportRecord


AUTO_SEND_ENABLED_KEY = "auto_send_enabled"


class ReportRepository:
    def __init__(self, db: DBManager | None = None):
        self.db = db or DBManager()

    def now_text(self) -> str:
        return datetime.now().isoformat(timespec="seconds")

    def get_setting(self, key: str) -> str | None:
        row = self.db.fetch_one("SELECT value FROM report_settings WHERE key = ?", (key,))
        return row["value"] if row is not None else None

    def set_setting(self, key: str, value: str) -> None:
        now = self.now_text()
        self.db.execute(
            """
            INSERT INTO report_settings (key, value, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET
                value = excluded.value,
                updated_at = excluded.updated_at
            """,
            (key, value, now),
        )

    def has_setting(self, key: str) -> bool:
        return self.get_setting(key) is not None

    def get_bool_setting(self, key: str, default: bool = False) -> bool:
        value = self.get_setting(key)
        if value is None:
            return default
        return str(value).strip().lower() in {"1", "true", "yes", "on"}

    def set_bool_setting(self, key: str, enabled: bool) -> None:
        self.set_setting(key, "1" if enabled else "0")

    def get_auto_send_enabled(self, config_loader=None) -> bool:
        if self.has_setting(AUTO_SEND_ENABLED_KEY):
            return self.get_bool_setting(AUTO_SEND_ENABLED_KEY)

        enabled = False
        if config_loader is not None:
            try:
                enabled = bool(config_loader.load().enabled)
            except Exception:
                enabled = False
        self.set_bool_setting(AUTO_SEND_ENABLED_KEY, enabled)
        return enabled

    def set_auto_send_enabled(self, enabled: bool) -> None:
        self.set_bool_setting(AUTO_SEND_ENABLED_KEY, enabled)

    def get_or_create_period_report(self, period_type: str, period_start: str, period_end: str) -> ReportRecord:
        now = self.now_text()
        self.db.execute(
            """
            INSERT OR IGNORE INTO period_reports (
                period_type, period_start, period_end, status, created_at, updated_at
            )
            VALUES (?, ?, ?, 'pending', ?, ?)
            """,
            (period_type, period_start, period_end, now, now),
        )
        return self.get_report_by_period(period_type, period_start, period_end)

    def get_report_by_period(self, period_type: str, period_start: str, period_end: str) -> ReportRecord | None:
        row = self.db.fetch_one(
            """
            SELECT *
            FROM period_reports
            WHERE period_type = ?
              AND period_start = ?
              AND period_end = ?
            """,
            (period_type, period_start, period_end),
        )
        return ReportRecord.from_row(row) if row is not None else None

    def get_report_by_id(self, report_id: int) -> ReportRecord | None:
        row = self.db.fetch_one("SELECT * FROM period_reports WHERE id = ?", (report_id,))
        return ReportRecord.from_row(row) if row is not None else None

    def get_retryable_reports(self) -> list[ReportRecord]:
        rows = self.db.fetch_all(
            """
            SELECT *
            FROM period_reports
            WHERE status IN ('pending', 'generated', 'failed', 'generating', 'sending')
            ORDER BY period_end ASC, id ASC
            """
        )
        return [ReportRecord.from_row(row) for row in rows]

    def update_status(self, report_id: int, status: str, last_error: str | None = None) -> None:
        self.db.execute(
            """
            UPDATE period_reports
            SET status = ?,
                last_error = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (status, self.sanitize_error(last_error), self.now_text(), report_id),
        )

    def mark_generated(self, report_id: int, title: str, file_path: str, markdown: str) -> None:
        self.db.execute(
            """
            UPDATE period_reports
            SET status = 'generated',
                report_title = ?,
                file_path = ?,
                markdown = ?,
                last_error = NULL,
                updated_at = ?
            WHERE id = ?
            """,
            (title, file_path, markdown, self.now_text(), report_id),
        )

    def mark_sent(self, report_id: int) -> None:
        now = self.now_text()
        self.db.execute(
            """
            UPDATE period_reports
            SET status = 'sent',
                sent_at = ?,
                last_error = NULL,
                updated_at = ?
            WHERE id = ?
            """,
            (now, now, report_id),
        )

    def increment_api_attempts(self, report_id: int) -> None:
        self.db.execute(
            """
            UPDATE period_reports
            SET api_attempts = api_attempts + 1,
                updated_at = ?
            WHERE id = ?
            """,
            (self.now_text(), report_id),
        )

    def increment_email_attempts(self, report_id: int) -> None:
        self.db.execute(
            """
            UPDATE period_reports
            SET email_attempts = email_attempts + 1,
                updated_at = ?
            WHERE id = ?
            """,
            (self.now_text(), report_id),
        )

    def sanitize_error(self, error: str | None) -> str | None:
        if not error:
            return None
        return str(error)[:500]
