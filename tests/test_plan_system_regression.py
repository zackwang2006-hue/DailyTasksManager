import sqlite3
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication

from app.database import db_manager
from app.database.db_manager import DBManager, PLAN_SCHEMA_MIGRATION
from app.models.plan import PLAN_LEVEL_ORDER, PlanLevel
from app.services.checkin_service import CheckinService
from app.services.date_refresh_coordinator import DateRefreshCoordinator
from app.services.period_service import period_service
from app.services.task_service import TaskService
from app.ui.checkin_page import CheckinPage
from app.ui.daily_task_dialog import DailyTaskDialog
from app.ui.floating_task_window import FloatingTaskItem, FloatingTaskWindow, PAGE_QUICK_NOTE, PAGE_TASKS
from app.ui.history_page import HistoryPage
from app.ui.main_window import MainWindow
from app.ui.task_dialog import TaskDialog
from app.ui.task_page import TaskPage


class PlanSystemRegressionTests(unittest.TestCase):
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

    def generated_dates(self, service, daily_task_id):
        rows = service.db.fetch_all(
            """
            SELECT generated_date
            FROM tasks
            WHERE source_daily_task_id = ?
            ORDER BY generated_date
            """,
            (daily_task_id,),
        )
        return [row["generated_date"] for row in rows]

    def visible_floating_titles(self, window):
        titles = []
        for index in range(window.task_layout.count()):
            widget = window.task_layout.itemAt(index).widget()
            if isinstance(widget, FloatingTaskItem):
                titles.append(widget.task.title)
        return titles

    def test_plan_periods_cover_boundaries_and_previous_periods(self):
        expected = {
            PlanLevel.DAY: (date(2026, 7, 23), date(2026, 7, 23)),
            PlanLevel.WEEK: (date(2026, 7, 20), date(2026, 7, 26)),
            PlanLevel.MONTH: (date(2026, 7, 1), date(2026, 7, 31)),
            PlanLevel.QUARTER: (date(2026, 7, 1), date(2026, 9, 30)),
            PlanLevel.YEAR: (date(2026, 1, 1), date(2026, 12, 31)),
            PlanLevel.FIVE_YEAR: (date(2026, 1, 1), date(2030, 12, 31)),
        }
        for level, (start, end) in expected.items():
            period = period_service.current_period(level, date(2026, 7, 23))
            self.assertEqual((period.start, period.end), (start, end))
            previous = period_service.previous_period(level, date(2026, 7, 23))
            self.assertLess(previous.end, period.start)

        self.assertEqual(period_service.current_period(PlanLevel.WEEK, date(2026, 7, 27)).start, date(2026, 7, 27))
        self.assertEqual(period_service.current_period(PlanLevel.MONTH, date(2026, 8, 1)).start, date(2026, 8, 1))
        self.assertEqual(period_service.current_period(PlanLevel.QUARTER, date(2026, 10, 1)).start, date(2026, 10, 1))
        self.assertEqual(period_service.current_period(PlanLevel.YEAR, date(2027, 1, 1)).start, date(2027, 1, 1))
        self.assertEqual(period_service.current_period(PlanLevel.FIVE_YEAR, date(2031, 1, 1)).start, date(2031, 1, 1))
        self.assertEqual(period_service.current_period(PlanLevel.MONTH, date(2028, 2, 10)).end, date(2028, 2, 29))

    def test_six_plan_levels_add_and_query_by_period(self):
        service = TaskService()
        ids = {}
        for level in PLAN_LEVEL_ORDER:
            ids[level] = service.add_plan_task(f"{level.value} task", plan_level=level, now=date(2026, 7, 23))

        for level in PLAN_LEVEL_ORDER:
            tasks = service.get_current_plan_tasks(level, date(2026, 7, 23), include_completed=True)
            self.assertEqual([task.task_id for task in tasks], [ids[level]])
            self.assertEqual(tasks[0].period_key, period_service.current_period(level, date(2026, 7, 23)).key)

        old_week_id = service.add_plan_task("old week", plan_level=PlanLevel.WEEK, now=date(2026, 7, 20))
        current_week_tasks = service.get_current_plan_tasks(PlanLevel.WEEK, date(2026, 7, 27), include_completed=True)
        previous_week_tasks = service.get_previous_plan_tasks(PlanLevel.WEEK, date(2026, 7, 27), include_completed=True)
        self.assertNotIn(old_week_id, [task.task_id for task in current_week_tasks])
        self.assertIn(old_week_id, [task.task_id for task in previous_week_tasks])

    def test_task_page_sections_and_previous_state_are_independent(self):
        page = TaskPage()
        self.assertEqual(list(page.sections.keys()), list(PLAN_LEVEL_ORDER))
        self.assertEqual(len(set(page.sections.keys())), 6)

        page.toggle_previous_period(PlanLevel.WEEK)
        self.assertTrue(page.sections[PlanLevel.WEEK].show_previous)
        self.assertFalse(page.sections[PlanLevel.DAY].show_previous)
        self.assertFalse(page.sections[PlanLevel.MONTH].show_previous)
        self.assertFalse(page.sections[PlanLevel.WEEK].add_button.isVisible())

        page.refresh_tasks()
        self.assertTrue(page.sections[PlanLevel.WEEK].show_previous)

    def test_dialogs_hide_legacy_controls_in_plan_mode_and_reject_day_daily_parent(self):
        plan_dialog = TaskDialog(mode="plan", plan_level=PlanLevel.MONTH)
        self.assertFalse(plan_dialog.category_combo.isVisible())
        self.assertFalse(plan_dialog.ddl_datetime_input.isVisible())
        self.assertFalse(plan_dialog.scheduled_date_input.isVisible())

        service = TaskService()
        day_parent = service.add_plan_task("day parent", plan_level=PlanLevel.DAY, now=date(2026, 7, 23))
        week_parent = service.add_plan_task("week parent", plan_level=PlanLevel.WEEK, now=date(2026, 7, 23))
        dialog = DailyTaskDialog(task_service=service)
        parent_levels = [dialog.parent_level_combo.itemData(i) for i in range(dialog.parent_level_combo.count())]
        self.assertNotIn(PlanLevel.DAY.value, parent_levels)
        self.assertIn(PlanLevel.WEEK.value, parent_levels)
        self.assertEqual([task.task_id for task in service.get_available_parent_plan_tasks(PlanLevel.WEEK)], [week_parent])
        with self.assertRaises(ValueError):
            service.add_daily_task_rule("bad", "", day_parent, today=date(2026, 7, 23))

    def test_daily_generation_lifecycle_and_legacy_preservation(self):
        service = TaskService()
        parent_id = service.add_plan_task("week parent", plan_level=PlanLevel.WEEK, now=date(2026, 7, 23))
        daily_id = service.add_daily_task_rule("daily", "", parent_id, today=date(2026, 7, 23))

        service.ensure_daily_plan_tasks_for_date(date(2026, 7, 22))
        service.ensure_daily_plan_tasks_for_date(date(2026, 7, 23))
        service.ensure_daily_plan_tasks_for_date(date(2026, 7, 23))
        service.ensure_daily_plan_tasks_for_date(date(2026, 7, 26))
        service.ensure_daily_plan_tasks_for_date(date(2026, 7, 27))
        self.assertEqual(self.generated_dates(service, daily_id), ["2026-07-23", "2026-07-26"])
        self.assertTrue(service.get_task_by_id(daily_id).archived)

        legacy_id = service.add_task("legacy daily", category="daily", task_type="daily", now=date(2026, 7, 20))
        CheckinService().add_daily_checkin(legacy_id, "2026-07-21", "2026-07-21T08:00:00")
        service.ensure_daily_plan_tasks_for_date(date(2026, 7, 24))
        self.assertEqual(self.generated_dates(service, legacy_id), [])
        self.assertIsNotNone(service.db.fetch_one("SELECT 1 FROM daily_checkins WHERE task_id = ?", (legacy_id,)))

    def test_parent_delete_and_completion_rules(self):
        service = TaskService()
        parent_id = service.add_plan_task("parent", plan_level=PlanLevel.WEEK, now=date(2026, 7, 23))
        daily_id = service.add_daily_task_rule("daily", "", parent_id, today=date(2026, 7, 23))

        service.complete_task_with_daily_sync(parent_id, "完成情况记录")
        service.ensure_daily_plan_tasks_for_date(date(2026, 7, 24))
        self.assertIn("2026-07-24", self.generated_dates(service, daily_id))

        service.delete_task(parent_id)
        service.ensure_daily_plan_tasks_for_date(date(2026, 7, 25))
        self.assertTrue(service.get_task_by_id(daily_id).archived)
        self.assertNotIn("2026-07-25", self.generated_dates(service, daily_id))

    def test_completion_sync_is_bidirectional_and_manual_day_is_ignored(self):
        service = TaskService()
        parent_id = service.add_plan_task("parent", plan_level=PlanLevel.WEEK, now=date(2026, 7, 23))
        daily_id = service.add_daily_task_rule("daily", "", parent_id, today=date(2026, 7, 23))
        generated = service.get_generated_daily_plan_task(daily_id, date(2026, 7, 23))

        service.complete_task_with_daily_sync(generated.task_id, "完成情况记录")
        with self.assertRaises(ValueError):
            service.complete_task_with_daily_sync(generated.task_id, "完成情况记录")
        rows = service.db.fetch_all("SELECT * FROM daily_checkins WHERE task_id = ?", (daily_id,))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["is_completed"], 1)

        service.ensure_daily_plan_tasks_for_date(date(2026, 7, 24))
        generated_next = service.get_generated_daily_plan_task(daily_id, date(2026, 7, 24))
        service.set_daily_checkin_with_plan_sync(daily_id, date(2026, 7, 24), True, "完成情况记录")
        self.assertTrue(service.get_task_by_id(generated_next.task_id).is_completed)

        manual_id = service.add_plan_task("manual", plan_level=PlanLevel.DAY, now=date(2026, 7, 23))
        service.complete_task_with_daily_sync(manual_id, "完成情况记录")
        manual_rows = service.db.fetch_all("SELECT * FROM daily_checkins WHERE task_id = ?", (manual_id,))
        self.assertEqual(manual_rows, [])

    def test_floating_window_only_shows_current_day_plans(self):
        service = TaskService()
        service.add_plan_task("today", plan_level=PlanLevel.DAY, now=date(2026, 7, 23))
        service.add_plan_task("yesterday", plan_level=PlanLevel.DAY, now=date(2026, 7, 22))
        service.add_plan_task("week", plan_level=PlanLevel.WEEK, now=date(2026, 7, 23))
        archived_id = service.add_plan_task("archived", plan_level=PlanLevel.DAY, now=date(2026, 7, 23))
        deleted_id = service.add_plan_task("deleted", plan_level=PlanLevel.DAY, now=date(2026, 7, 23))
        service.db.execute("UPDATE tasks SET archived = 1 WHERE id = ?", (archived_id,))
        service.soft_delete_task(deleted_id)
        service.add_task("legacy daily", category="daily", task_type="daily", now=date(2026, 7, 23))

        window = FloatingTaskWindow()
        window.task_service = service
        window.refresh_tasks()

        self.assertEqual(self.visible_floating_titles(window), ["today"])
        self.assertFalse(hasattr(window, "filter_buttons"))
        self.assertFalse(hasattr(window, "current_filter"))
        window.set_page(PAGE_QUICK_NOTE)
        self.assertEqual(window.current_page, PAGE_QUICK_NOTE)
        window.set_page(PAGE_TASKS)
        self.assertEqual(window.current_page, PAGE_TASKS)

    def test_date_coordinator_idempotence_and_multiday_resume(self):
        current = {"today": date(2026, 7, 23)}
        period_service.set_date_provider(lambda: current["today"])
        coordinator = DateRefreshCoordinator(watchdog_interval_ms=600000)
        coordinator.midnight_timer.stop()
        coordinator.watchdog_timer.stop()
        emissions = []
        coordinator.date_changed.connect(lambda old, new: emissions.append((old, new)))
        coordinator.check_date_change()
        current["today"] = date(2026, 7, 26)
        coordinator.check_date_change()
        coordinator.check_date_change()
        self.assertEqual(emissions, [(date(2026, 7, 23), date(2026, 7, 26))])

        service = TaskService()
        parent_id = service.add_plan_task("parent", plan_level=PlanLevel.WEEK, now=date(2026, 7, 23))
        daily_id = service.add_daily_task_rule("daily", "", parent_id, today=date(2026, 7, 23))
        service.ensure_daily_plan_tasks_for_date(date(2026, 7, 26))
        self.assertEqual(self.generated_dates(service, daily_id), ["2026-07-23", "2026-07-26"])

    def test_database_migration_and_transaction_rollback(self):
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
                INSERT INTO tasks (
                    title, description, category, ddl, task_type, scheduled_at,
                    is_completed, is_deleted, created_at, completed_at
                )
                VALUES ('legacy', '', 'short', NULL, 'normal', NULL, 0, 0, '2026-07-23T08:00:00', NULL)
                """
            )

        manager = DBManager()
        self.assertIsNotNone(manager.fetch_one("SELECT name FROM schema_migrations WHERE name = ?", (PLAN_SCHEMA_MIGRATION,)))
        self.assertEqual(len(list((self.db_path.parent / "backups").glob("*.db"))), 1)
        DBManager()
        self.assertEqual(len(list((self.db_path.parent / "backups").glob("*.db"))), 1)

        try:
            with manager.transaction() as conn:
                conn.execute(
                    """
                    INSERT INTO tasks (title, description, category, task_type, is_completed, is_deleted, created_at)
                    VALUES ('rolled back', '', 'plan', 'normal', 0, 0, '2026-07-23T09:00:00')
                    """
                )
                raise RuntimeError("rollback")
        except RuntimeError:
            pass
        self.assertIsNone(manager.fetch_one("SELECT 1 FROM tasks WHERE title = 'rolled back'"))

    def test_ui_smoke_main_pages_and_refresh_guard(self):
        main = MainWindow()
        labels = [main.tab_widget.tabText(i) for i in range(main.tab_widget.count())]
        self.assertIn("计划详情", labels)
        self.assertIn("每日任务", labels)
        self.assertIn("历史完成", labels)
        main._refreshing = True
        main.refresh_all()
        main._refreshing = False

        self.assertEqual(len(main.task_page.sections), 6)
        checkin = CheckinPage()
        history = HistoryPage()
        floating = FloatingTaskWindow()
        daily_dialog = DailyTaskDialog(task_service=TaskService())
        plan_dialog = TaskDialog(mode="plan", plan_level=PlanLevel.WEEK)
        self.assertIsNotNone(checkin)
        self.assertIsNotNone(history)
        self.assertIsNotNone(floating)
        self.assertNotIn(PlanLevel.DAY.value, [daily_dialog.parent_level_combo.itemData(i) for i in range(daily_dialog.parent_level_combo.count())])
        self.assertFalse(plan_dialog.category_combo.isVisible())


if __name__ == "__main__":
    unittest.main()
