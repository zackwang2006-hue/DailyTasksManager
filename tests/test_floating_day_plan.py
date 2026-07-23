import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QLabel

from app.database import db_manager
from app.models.plan import PlanLevel
from app.services.task_service import TaskService
from app.ui.floating_task_window import FloatingTaskItem, FloatingTaskWindow, PAGE_QUICK_NOTE, PAGE_TASKS


class FloatingDayPlanTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.temp_dir.name) / "data"
        self.db_path = self.data_dir / "schedule.db"
        self.data_dir_patch = patch.object(db_manager, "DATA_DIR", self.data_dir)
        self.db_path_patch = patch.object(db_manager, "DB_PATH", self.db_path)
        self.data_dir_patch.start()
        self.db_path_patch.start()

    def tearDown(self):
        self.db_path_patch.stop()
        self.data_dir_patch.stop()
        self.temp_dir.cleanup()

    def visible_task_titles(self, window):
        titles = []
        for index in range(window.task_layout.count()):
            widget = window.task_layout.itemAt(index).widget()
            if isinstance(widget, FloatingTaskItem):
                titles.append(widget.task.title)
        return titles

    def empty_label_texts(self, window):
        texts = []
        for index in range(window.task_layout.count()):
            widget = window.task_layout.itemAt(index).widget()
            if isinstance(widget, QLabel):
                texts.append(widget.text())
        return texts

    def test_only_current_day_plan_tasks_are_displayed(self):
        service = TaskService()
        today_id = service.add_plan_task("today manual", plan_level=PlanLevel.DAY, now=date.today())
        service.add_plan_task("week plan", plan_level=PlanLevel.WEEK, now=date.today())
        service.add_plan_task("old day", plan_level=PlanLevel.DAY, now=date.today() - timedelta(days=1))
        archived_id = service.add_plan_task("archived day", plan_level=PlanLevel.DAY, now=date.today())
        service.db.execute("UPDATE tasks SET archived = 1 WHERE id = ?", (archived_id,))
        deleted_id = service.add_plan_task("deleted day", plan_level=PlanLevel.DAY, now=date.today())
        service.soft_delete_task(deleted_id)
        service.add_task("legacy daily", category="daily", task_type="daily", now=date.today())

        window = FloatingTaskWindow()
        window.task_service = service
        window.refresh_tasks()

        self.assertEqual(self.visible_task_titles(window), ["today manual"])
        self.assertIsNotNone(service.get_task_by_id(today_id))

    def test_generated_daily_plan_task_is_displayed_without_duplicates(self):
        service = TaskService()
        parent_id = service.add_plan_task("week parent", plan_level=PlanLevel.WEEK, now=date.today())
        daily_id = service.add_daily_task_rule("generated daily", "", parent_id, today=date.today())

        window = FloatingTaskWindow()
        window.task_service = service
        window.refresh_tasks()
        window.refresh_tasks()

        self.assertEqual(self.visible_task_titles(window), ["generated daily"])
        rows = service.db.fetch_all(
            "SELECT * FROM tasks WHERE source_daily_task_id = ?",
            (daily_id,),
        )
        self.assertEqual(len(rows), 1)

    def test_empty_state_and_removed_filter_members(self):
        window = FloatingTaskWindow()
        window.refresh_tasks()

        self.assertIn("今日日计划为空", self.empty_label_texts(window))
        self.assertFalse(hasattr(window, "filter_buttons"))
        self.assertFalse(hasattr(window, "filter_group"))
        self.assertFalse(hasattr(window, "filter_frame"))

    def test_quick_note_switch_and_data_changed_signal(self):
        service = TaskService()
        task_id = service.add_plan_task("complete me", plan_level=PlanLevel.DAY, now=date.today())
        window = FloatingTaskWindow()
        window.task_service = service

        window.set_page(PAGE_QUICK_NOTE)
        self.assertEqual(window.current_page, PAGE_QUICK_NOTE)
        self.assertEqual(window.content_stack.currentWidget(), window.quick_note_page)
        window.set_page(PAGE_TASKS)
        self.assertEqual(window.content_stack.currentWidget(), window.task_page)

        emissions = []
        window.data_changed.connect(lambda: emissions.append(True))
        window.complete_task(task_id)

        self.assertEqual(len(emissions), 1)
        self.assertTrue(service.get_task_by_id(task_id).is_completed)


if __name__ == "__main__":
    unittest.main()
