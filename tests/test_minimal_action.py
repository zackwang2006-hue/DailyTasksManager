import sqlite3
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication

from app.database import db_manager
from app.database.db_manager import DBManager, MINIMAL_ACTION_SCHEMA_MIGRATION
from app.models.plan import PlanLevel
from app.services.period_service import period_service
from app.services.task_service import TaskService
from app.ui.daily_task_dialog import DailyTaskDialog
from app.ui.floating_task_window import FloatingTaskItem, FloatingTaskWindow
from app.ui.task_card import TaskCard
from app.ui.task_dialog import TaskDialog


class MinimalActionTests(unittest.TestCase):
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

    def test_day_plan_minimal_action_validation_and_persistence(self):
        service = TaskService()

        with self.assertRaisesRegex(ValueError, "请填写最小动作"):
            service.add_plan_task(
                "title",
                plan_level=PlanLevel.DAY,
                minimal_action="",
                now=date(2026, 7, 23),
            )
        with self.assertRaisesRegex(ValueError, "请填写最小动作"):
            service.add_plan_task(
                "title",
                plan_level=PlanLevel.DAY,
                minimal_action="   ",
                now=date(2026, 7, 23),
            )
        with self.assertRaisesRegex(ValueError, "最小动作不能超过12个字符"):
            service.add_plan_task(
                "title",
                plan_level=PlanLevel.DAY,
                minimal_action="1234567890123",
                now=date(2026, 7, 23),
            )

        task_id = service.add_plan_task(
            "long title",
            plan_level=PlanLevel.DAY,
            minimal_action="  123456789012  ",
            now=date(2026, 7, 23),
        )
        self.assertEqual(service.get_task_by_id(task_id).minimal_action, "123456789012")

        service.update_task(
            task_id,
            "long title",
            "desc",
            "plan",
            None,
            "normal",
            minimal_action=" 新动作 ",
        )
        self.assertEqual(service.get_task_by_id(task_id).minimal_action, "新动作")

    def test_daily_template_minimal_action_is_inherited_by_generated_task(self):
        service = TaskService()
        parent_id = service.add_plan_task(
            "week parent",
            plan_level=PlanLevel.WEEK,
            now=date(2026, 7, 23),
        )
        daily_id = service.add_daily_task_rule(
            "daily title",
            "",
            parent_id,
            minimal_action="打开文档",
            today=date(2026, 7, 23),
        )
        generated = service.get_generated_daily_plan_task(daily_id, date(2026, 7, 23))

        self.assertEqual(service.get_task_by_id(daily_id).minimal_action, "打开文档")
        self.assertEqual(generated.minimal_action, "打开文档")

    def test_floating_card_uses_minimal_action_only_when_collapsed(self):
        service = TaskService()
        task_id = service.add_plan_task(
            "完成机器学习课程论文的实验部分",
            "实验描述",
            plan_level=PlanLevel.DAY,
            minimal_action="打开实验代码",
            now=date(2026, 7, 23),
        )
        task = service.get_task_by_id(task_id)
        item = FloatingTaskItem(task, "", "日计划")

        self.assertEqual(item.summary_label.text(), "打开实验代码")
        self.assertNotIn(task.title, item.summary_label.text())

        item.set_expanded(True)
        detail_texts = [
            item.detail_frame.layout().itemAt(index).widget().text()
            for index in range(item.detail_frame.layout().count())
            if hasattr(item.detail_frame.layout().itemAt(index).widget(), "text")
        ]
        self.assertIn(task.title, detail_texts)
        self.assertTrue(any("实验描述" in text for text in detail_texts))
        self.assertFalse(any("打开实验代码" in text for text in detail_texts))

    def test_floating_fixed_event_keeps_time_and_priority_style(self):
        service = TaskService()
        task_id = service.add_plan_task(
            "fixed title",
            plan_level=PlanLevel.DAY,
            fixed_time="08:30:00",
            is_fixed_event=True,
            minimal_action="穿上跑鞋",
            now=date(2026, 7, 23),
        )
        task = service.get_task_by_id(task_id)
        item = FloatingTaskItem(task, "时间：2026-07-23 08:30", "日计划")

        self.assertIn("穿上跑鞋", item.summary_label.text())
        self.assertIn("08:30", item.summary_label.text())
        self.assertEqual(task.priority_level, 0)
        self.assertIn("224, 90, 169", item.styleSheet())

    def test_main_task_card_still_uses_title(self):
        service = TaskService()
        task_id = service.add_plan_task(
            "主程序标题",
            plan_level=PlanLevel.DAY,
            minimal_action="最小动作",
            now=date(2026, 7, 23),
        )
        card = TaskCard(service.get_task_by_id(task_id))
        self.assertEqual(card.title_label.text(), "主程序标题")

    def test_minimal_action_migration_backfills_legacy_tasks(self):
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
                VALUES ('  abcdefghijklmnop  ', '', 'plan', 'normal', '2026-07-23T08:00:00')
                """
            )
            conn.execute(
                """
                INSERT INTO tasks (title, description, category, task_type, created_at)
                VALUES ('', '', 'plan', 'normal', '2026-07-23T09:00:00')
                """
            )

        manager = DBManager()
        rows = manager.fetch_all("SELECT title, minimal_action FROM tasks ORDER BY id")

        self.assertEqual(rows[0]["minimal_action"], "abcdefghijkl")
        self.assertEqual(rows[1]["minimal_action"], "开始行动")
        self.assertIsNotNone(
            manager.fetch_one(
                "SELECT 1 FROM schema_migrations WHERE name = ?",
                (MINIMAL_ACTION_SCHEMA_MIGRATION,),
            )
        )

    def test_dialog_visibility_and_input_limits(self):
        day_dialog = TaskDialog(mode="plan", plan_level=PlanLevel.DAY)
        month_dialog = TaskDialog(mode="plan", plan_level=PlanLevel.MONTH)
        daily_dialog = DailyTaskDialog(task_service=TaskService())

        self.assertFalse(day_dialog.minimal_action_input.isHidden())
        self.assertTrue(month_dialog.minimal_action_input.isHidden())
        self.assertEqual(day_dialog.minimal_action_input.maxLength(), 12)
        self.assertEqual(daily_dialog.minimal_action_input.maxLength(), 12)

    def test_floating_refresh_shows_edited_minimal_action(self):
        service = TaskService()
        task_id = service.add_plan_task(
            "title",
            plan_level=PlanLevel.DAY,
            minimal_action="旧动作",
            now=date(2026, 7, 23),
        )
        service.update_task(
            task_id,
            "title",
            "",
            "plan",
            None,
            "normal",
            minimal_action="新动作",
        )

        window = FloatingTaskWindow()
        window.task_service = service
        window.refresh_tasks()
        item = next(
            window.task_layout.itemAt(index).widget()
            for index in range(window.task_layout.count())
            if isinstance(window.task_layout.itemAt(index).widget(), FloatingTaskItem)
        )
        self.assertEqual(item.summary_label.text(), "新动作")


if __name__ == "__main__":
    unittest.main()
