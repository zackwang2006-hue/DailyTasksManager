import tempfile
import unittest
import sqlite3
from datetime import date
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication

from app.database import db_manager
from app.database.db_manager import DBManager
from app.models.plan import PlanLevel
from app.models.priority import (
    PRIORITY_CARD_COLORS,
    PRIORITY_SCHEMA_MIGRATION,
    calculate_priority,
)
from app.services.period_service import period_service
from app.services.task_service import TaskService
from app.ui.daily_task_dialog import DailyTaskDialog
from app.ui.floating_task_window import FloatingTaskItem, FloatingTaskWindow


class PrioritySystemTests(unittest.TestCase):
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

    def floating_titles(self, window):
        titles = []
        for index in range(window.task_layout.count()):
            widget = window.task_layout.itemAt(index).widget()
            if isinstance(widget, FloatingTaskItem):
                titles.append(widget.task.title)
        return titles

    def test_priority_calculation_rules(self):
        self.assertEqual(calculate_priority(True, False, False), 0)
        self.assertEqual(calculate_priority(True, True, True), 0)
        self.assertEqual(calculate_priority(False, True, True), 1)
        self.assertEqual(calculate_priority(False, True, False), 2)
        self.assertEqual(calculate_priority(False, False, True), 3)
        self.assertEqual(calculate_priority(False, False, False), 4)

    def test_priority_migration_defaults_legacy_tasks_to_p4(self):
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
                INSERT INTO tasks (title, description, category, task_type, created_at)
                VALUES ('legacy', '', 'short', 'normal', '2026-07-23T09:00:00')
                """
            )

        manager = DBManager()
        row = manager.fetch_one("SELECT * FROM tasks WHERE title = 'legacy'")

        self.assertFalse(bool(row["is_important"]))
        self.assertFalse(bool(row["is_urgent"]))
        self.assertFalse(bool(row["is_fixed_event"]))
        self.assertEqual(row["priority_level"], 4)
        self.assertIsNotNone(
            manager.fetch_one(
                "SELECT name FROM schema_migrations WHERE name = ?",
                (PRIORITY_SCHEMA_MIGRATION,),
            )
        )

    def test_day_plan_priority_and_fixed_event_validation(self):
        service = TaskService()
        with self.assertRaisesRegex(ValueError, "固定事件必须设置固定时间"):
            service.add_plan_task(
                "invalid fixed",
                plan_level=PlanLevel.DAY,
                is_fixed_event=True,
                now=date(2026, 7, 23),
            )

        task_id = service.add_plan_task(
            "fixed",
            plan_level=PlanLevel.DAY,
            scheduled_at="2026-07-23 08:30:00",
            is_important=True,
            is_urgent=True,
            is_fixed_event=True,
            now=date(2026, 7, 23),
        )
        task = service.get_task_by_id(task_id)

        self.assertTrue(task.is_fixed_event)
        self.assertEqual(task.priority_level, 0)
        self.assertEqual(task.scheduled_at, "2026-07-23T08:30:00")
        self.assertEqual(task.fixed_time, "08:30:00")

        service.update_task(
            task_id,
            "urgent only",
            "",
            "plan",
            None,
            "normal",
            None,
            is_important=False,
            is_urgent=True,
            is_fixed_event=False,
        )
        updated = service.get_task_by_id(task_id)
        self.assertFalse(updated.is_fixed_event)
        self.assertEqual(updated.priority_level, 2)

    def test_daily_template_priority_and_fixed_time_are_inherited(self):
        service = TaskService()
        parent_id = service.add_plan_task("week parent", plan_level=PlanLevel.WEEK, now=date(2026, 7, 23))
        daily_id = service.add_daily_task_rule(
            "daily fixed",
            "",
            parent_id,
            scheduled_at="2026-07-23 09:15:00",
            is_important=True,
            is_urgent=True,
            is_fixed_event=True,
            today=date(2026, 7, 23),
        )

        template = service.get_task_by_id(daily_id)
        generated = service.get_generated_daily_plan_task(daily_id, date(2026, 7, 23))

        self.assertEqual(template.priority_level, 0)
        self.assertIsNone(template.scheduled_at)
        self.assertEqual(template.fixed_time, "09:15:00")
        self.assertEqual(generated.priority_level, 0)
        self.assertTrue(generated.is_fixed_event)
        self.assertEqual(generated.scheduled_at, "2026-07-23T09:15:00")
        self.assertEqual(generated.fixed_time, "09:15:00")

        service.archive_daily_task(daily_id)
        new_daily_id = service.add_daily_task_rule(
            "daily later",
            "",
            parent_id,
            is_important=True,
            is_urgent=False,
            is_fixed_event=False,
            today=date(2026, 7, 24),
        )
        service.ensure_daily_plan_tasks_for_date(date(2026, 7, 24))
        new_generated = service.get_generated_daily_plan_task(new_daily_id, date(2026, 7, 24))
        self.assertEqual(new_generated.priority_level, 3)

    def test_floating_window_sorts_and_colors_by_priority(self):
        service = TaskService()
        service.add_plan_task("p4", plan_level=PlanLevel.DAY, now=date(2026, 7, 23))
        service.add_plan_task("p3", plan_level=PlanLevel.DAY, is_important=True, now=date(2026, 7, 23))
        service.add_plan_task("p2", plan_level=PlanLevel.DAY, is_urgent=True, now=date(2026, 7, 23))
        service.add_plan_task("p1", plan_level=PlanLevel.DAY, is_urgent=True, is_important=True, now=date(2026, 7, 23))
        service.add_plan_task(
            "p0 late",
            plan_level=PlanLevel.DAY,
            scheduled_at="2026-07-23 10:00:00",
            is_fixed_event=True,
            now=date(2026, 7, 23),
        )
        service.add_plan_task(
            "p0 early",
            plan_level=PlanLevel.DAY,
            scheduled_at="2026-07-23 08:00:00",
            is_fixed_event=True,
            now=date(2026, 7, 23),
        )

        window = FloatingTaskWindow()
        window.task_service = service
        window.refresh_tasks()

        self.assertEqual(
            self.floating_titles(window),
            ["p0 early", "p0 late", "p1", "p2", "p3", "p4"],
        )

        first_item = next(
            window.task_layout.itemAt(index).widget()
            for index in range(window.task_layout.count())
            if isinstance(window.task_layout.itemAt(index).widget(), FloatingTaskItem)
        )
        self.assertIn("224, 90, 169", first_item.styleSheet())
        self.assertEqual(PRIORITY_CARD_COLORS[0], "#E05AA9")
        self.assertEqual(PRIORITY_CARD_COLORS[4], "#72B8E8")

    def test_priority_controls_are_mutually_exclusive(self):
        dialog = DailyTaskDialog(task_service=TaskService())

        dialog.urgent_checkbox.setChecked(True)
        self.assertFalse(dialog.fixed_event_checkbox.isEnabled())
        self.assertFalse(dialog.fixed_event_checkbox.isChecked())

        dialog.urgent_checkbox.setChecked(False)
        self.assertTrue(dialog.fixed_event_checkbox.isEnabled())
        dialog.fixed_event_checkbox.setChecked(True)

        self.assertFalse(dialog.urgent_checkbox.isChecked())
        self.assertFalse(dialog.important_checkbox.isChecked())
        self.assertFalse(dialog.urgent_checkbox.isEnabled())
        self.assertFalse(dialog.important_checkbox.isEnabled())
        self.assertTrue(dialog.fixed_time_input.isEnabled())

        dialog.fixed_event_checkbox.setChecked(False)
        self.assertTrue(dialog.urgent_checkbox.isEnabled())
        self.assertTrue(dialog.important_checkbox.isEnabled())
        self.assertFalse(dialog.fixed_time_input.isEnabled())


if __name__ == "__main__":
    unittest.main()
