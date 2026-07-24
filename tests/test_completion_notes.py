import sqlite3
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QLabel

from app.database import db_manager
from app.database.db_manager import COMPLETION_NOTE_SCHEMA_MIGRATION, DBManager
from app.models.plan import PlanLevel
from app.services.period_service import period_service
from app.services.task_service import TaskService
from app.ui.completion_dialog import CompletionDialog
from app.ui.history_page import HistoryPage


class CompletionNoteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.data_dir = Path(self.temp_dir.name) / "data"
        self.db_path = self.data_dir / "schedule.db"
        self.data_dir_patch = patch.object(db_manager, "DATA_DIR", self.data_dir)
        self.db_path_patch = patch.object(db_manager, "DB_PATH", self.db_path)
        self.data_dir_patch.start()
        self.db_path_patch.start()
        period_service.set_date_provider(lambda: date(2026, 7, 23))

    def tearDown(self):
        period_service.set_date_provider(None)
        self.db_path_patch.stop()
        self.data_dir_patch.stop()
        self.temp_dir.cleanup()

    def test_completion_note_validation(self):
        service = TaskService()
        task_id = service.add_plan_task("task", plan_level=PlanLevel.DAY, now=date(2026, 7, 23))

        for invalid in ("abcd", "   abcd   ", "a\nb\tc d"):
            with self.assertRaisesRegex(ValueError, "完成情况至少填写5个有效字符"):
                service.complete_task(task_id, invalid)

        self.assertFalse(service.get_task_by_id(task_id).is_completed)
        self.assertTrue(service.complete_task(task_id, " abcde "))

        task = service.get_task_by_id(task_id)
        log = service.db.fetch_one("SELECT * FROM task_logs WHERE task_id = ?", (task_id,))
        self.assertTrue(task.is_completed)
        self.assertIsNotNone(task.completed_at)
        self.assertEqual(log["completion_note"], "abcde")

    def test_completion_rollback_when_history_write_fails(self):
        service = TaskService()
        task_id = service.add_plan_task("task", plan_level=PlanLevel.DAY, now=date(2026, 7, 23))

        with patch.object(service.history_service, "add_task_log", side_effect=RuntimeError("boom")):
            with self.assertRaises(RuntimeError):
                service.complete_task(task_id, "完成情况记录")

        self.assertFalse(service.get_task_by_id(task_id).is_completed)
        self.assertIsNone(service.db.fetch_one("SELECT 1 FROM task_logs WHERE task_id = ?", (task_id,)))

    def test_completion_note_migration_keeps_old_rows_readable(self):
        self.data_dir.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
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
                CREATE TABLE task_logs (
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
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE daily_checkins (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id INTEGER NOT NULL,
                    checkin_date TEXT NOT NULL,
                    is_completed INTEGER NOT NULL DEFAULT 1,
                    completed_at TEXT NOT NULL,
                    UNIQUE(task_id, checkin_date)
                )
                """
            )
            conn.execute(
                """
                INSERT INTO task_logs (task_id, title, description, category, task_type, completed_at, record_date, created_at)
                VALUES (1, 'old log', '', 'plan', 'normal', '2026-07-23T08:00:00', '2026-07-23', '2026-07-23T07:00:00')
                """
            )

        manager = DBManager()
        log = manager.fetch_one("SELECT * FROM task_logs WHERE title = 'old log'")
        self.assertIn("completion_note", log.keys())
        self.assertIsNone(log["completion_note"])
        self.assertIsNotNone(
            manager.fetch_one(
                "SELECT 1 FROM schema_migrations WHERE name = ?",
                (COMPLETION_NOTE_SCHEMA_MIGRATION,),
            )
        )

    def test_daily_checkins_store_notes_by_date_and_undo_one_day_only(self):
        service = TaskService()
        parent_id = service.add_plan_task("parent", plan_level=PlanLevel.WEEK, now=date(2026, 7, 23))
        daily_id = service.add_daily_task_rule(
            "daily",
            "",
            parent_id,
            minimal_action="开始行动",
            today=date(2026, 7, 23),
        )

        generated_23 = service.get_generated_daily_plan_task(daily_id, date(2026, 7, 23))
        service.complete_task(generated_23.task_id, "第一天完成")
        service.set_daily_checkin_with_plan_sync(daily_id, date(2026, 7, 24), True, "第二天完成")
        service.set_daily_checkin_with_plan_sync(daily_id, date(2026, 7, 23), False)

        rows = service.db.fetch_all(
            """
            SELECT checkin_date, is_completed, completion_note
            FROM daily_checkins
            WHERE task_id = ?
            ORDER BY checkin_date
            """,
            (daily_id,),
        )
        self.assertEqual(rows[0]["checkin_date"], "2026-07-23")
        self.assertEqual(rows[0]["is_completed"], 0)
        self.assertIsNone(rows[0]["completion_note"])
        self.assertEqual(rows[1]["checkin_date"], "2026-07-24")
        self.assertEqual(rows[1]["is_completed"], 1)
        self.assertEqual(rows[1]["completion_note"], "第二天完成")
        self.assertFalse(service.get_task_by_id(generated_23.task_id).is_completed)

    def test_completion_dialog_live_validation(self):
        dialog = CompletionDialog("task")
        self.assertFalse(dialog.confirm_button.isEnabled())
        self.assertIn("还需输入", dialog.hint_label.text())

        dialog.note_input.setPlainText("a b\nc\td")
        self.assertFalse(dialog.confirm_button.isEnabled())

        dialog.note_input.setPlainText("abcde")
        self.assertTrue(dialog.confirm_button.isEnabled())
        self.assertEqual(dialog.completion_note(), "abcde")

    def test_history_page_shows_completion_note_and_legacy_fallback(self):
        service = TaskService()
        task_id = service.add_plan_task("task", plan_level=PlanLevel.DAY, now=date(2026, 7, 23))
        service.complete_task(task_id, "完成情况记录")
        record_date = service.db.fetch_one(
            "SELECT record_date FROM task_logs WHERE task_id = ?",
            (task_id,),
        )["record_date"]
        service.db.execute(
            """
            INSERT INTO task_logs (task_id, title, description, category, task_type, completed_at, record_date, created_at)
            VALUES (?, 'legacy', '', 'plan', 'normal', '2026-07-23T09:00:00', ?, '2026-07-23T08:00:00')
            """,
            (task_id, record_date),
        )

        page = HistoryPage()
        page.history_service = service.history_service
        page.show_logs_for_date(record_date)
        texts = []
        for index in range(page.log_layout.count()):
            card = page.log_layout.itemAt(index).widget()
            if card is None:
                continue
            for child in card.findChildren(QLabel):
                texts.append(child.text())

        self.assertTrue(any("完成情况记录" in text for text in texts))
        self.assertTrue(any("未记录完成情况" in text for text in texts))


if __name__ == "__main__":
    unittest.main()
