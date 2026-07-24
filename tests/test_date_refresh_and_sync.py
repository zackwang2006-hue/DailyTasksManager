import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication

from app.database import db_manager
from app.models.plan import PlanLevel
from app.services.checkin_service import CheckinService
from app.services.date_refresh_coordinator import DateRefreshCoordinator
from app.services.period_service import period_service
from app.services.task_service import TaskService


class DateRefreshAndSyncTests(unittest.TestCase):
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

    def create_week_daily_rule(self, service, today=date(2026, 7, 23)):
        parent_id = service.add_plan_task(
            "week parent",
            plan_level=PlanLevel.WEEK,
            now=today,
        )
        daily_id = service.add_daily_task_rule(
            "daily generated",
            "",
            parent_id,
            today=today,
        )
        return parent_id, daily_id

    def test_same_day_refresh_is_idempotent(self):
        service = TaskService()
        _, daily_id = self.create_week_daily_rule(service)

        service.ensure_daily_plan_tasks_for_date(date(2026, 7, 23))
        service.ensure_daily_plan_tasks_for_date(date(2026, 7, 23))

        self.assertEqual(self.generated_dates(service, daily_id), ["2026-07-23"])

    def test_date_refresh_coordinator_emits_only_on_date_change(self):
        current = {"today": date(2026, 7, 23)}
        period_service.set_date_provider(lambda: current["today"])
        coordinator = DateRefreshCoordinator(watchdog_interval_ms=600000)
        coordinator.midnight_timer.stop()
        coordinator.watchdog_timer.stop()
        emissions = []
        coordinator.date_changed.connect(lambda old, new: emissions.append((old, new)))

        coordinator.check_date_change()
        current["today"] = date(2026, 7, 24)
        coordinator.check_date_change()
        coordinator.check_date_change()

        self.assertEqual(emissions, [(date(2026, 7, 23), date(2026, 7, 24))])

    def test_cross_midnight_generates_new_day_and_hides_yesterday(self):
        service = TaskService()
        _, daily_id = self.create_week_daily_rule(service)

        service.ensure_daily_plan_tasks_for_date(date(2026, 7, 24))

        self.assertEqual(
            self.generated_dates(service, daily_id),
            ["2026-07-23", "2026-07-24"],
        )
        current_tasks = service.get_current_plan_tasks(PlanLevel.DAY, date(2026, 7, 24))
        self.assertEqual([task.generated_date for task in current_tasks], ["2026-07-24"])

    def test_sleep_across_multiple_days_generates_only_resume_day(self):
        service = TaskService()
        _, daily_id = self.create_week_daily_rule(service)

        service.ensure_daily_plan_tasks_for_date(date(2026, 7, 26))

        self.assertEqual(self.generated_dates(service, daily_id), ["2026-07-23", "2026-07-26"])

    def test_period_end_generates_and_next_day_archives(self):
        service = TaskService()
        _, daily_id = self.create_week_daily_rule(service)

        service.ensure_daily_plan_tasks_for_date(date(2026, 7, 26))
        self.assertIn("2026-07-26", self.generated_dates(service, daily_id))

        service.ensure_daily_plan_tasks_for_date(date(2026, 7, 27))
        self.assertTrue(service.get_task_by_id(daily_id).archived)
        self.assertNotIn("2026-07-27", self.generated_dates(service, daily_id))

    def test_generated_plan_completion_syncs_daily_checkin_once(self):
        service = TaskService()
        _, daily_id = self.create_week_daily_rule(service)
        generated = service.get_generated_daily_plan_task(daily_id, date(2026, 7, 23))

        service.complete_task_with_daily_sync(generated.task_id, "完成情况记录")
        with self.assertRaises(ValueError):
            service.complete_task_with_daily_sync(generated.task_id, "完成情况记录")

        rows = service.db.fetch_all(
            """
            SELECT *
            FROM daily_checkins
            WHERE task_id = ? AND checkin_date = ?
            """,
            (daily_id, "2026-07-23"),
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["is_completed"], 1)

    def test_daily_checkin_completion_syncs_generated_plan_card(self):
        service = TaskService()
        _, daily_id = self.create_week_daily_rule(service)
        generated = service.get_generated_daily_plan_task(daily_id, date(2026, 7, 23))
        self.assertFalse(generated.is_completed)

        service.set_daily_checkin_with_plan_sync(daily_id, date(2026, 7, 23), True, "完成情况记录")

        self.assertTrue(service.get_task_by_id(generated.task_id).is_completed)
        status = CheckinService().get_checkin_statuses_by_task(daily_id)
        self.assertTrue(status["2026-07-23"])

    def test_manual_day_plan_completion_does_not_create_daily_checkin(self):
        service = TaskService()
        task_id = service.add_plan_task("manual", plan_level=PlanLevel.DAY, now=date(2026, 7, 23))

        service.complete_task_with_daily_sync(task_id, "完成情况记录")

        rows = service.db.fetch_all("SELECT * FROM daily_checkins")
        self.assertEqual(rows, [])

    def test_parent_completed_still_generates_but_parent_delete_archives(self):
        service = TaskService()
        parent_id, daily_id = self.create_week_daily_rule(service)

        service.complete_task_with_daily_sync(parent_id, "完成情况记录")
        service.ensure_daily_plan_tasks_for_date(date(2026, 7, 24))
        self.assertIn("2026-07-24", self.generated_dates(service, daily_id))

        service.delete_task(parent_id)
        service.ensure_daily_plan_tasks_for_date(date(2026, 7, 25))
        self.assertTrue(service.get_task_by_id(daily_id).archived)
        self.assertNotIn("2026-07-25", self.generated_dates(service, daily_id))

    def test_legacy_unbound_daily_history_is_preserved(self):
        service = TaskService()
        legacy_id = service.add_task(
            "legacy daily",
            category="daily",
            task_type="daily",
            now=date(2026, 7, 20),
        )
        CheckinService().add_daily_checkin(legacy_id, "2026-07-21", "2026-07-21T09:00:00")

        service.expire_daily_tasks(date(2026, 7, 24))
        service.ensure_daily_plan_tasks_for_date(date(2026, 7, 24))

        self.assertIsNotNone(service.get_task_by_id(legacy_id))
        self.assertIsNotNone(
            service.db.fetch_one(
                "SELECT 1 FROM daily_checkins WHERE task_id = ? AND checkin_date = ?",
                (legacy_id, "2026-07-21"),
            )
        )
        self.assertEqual(self.generated_dates(service, legacy_id), [])


if __name__ == "__main__":
    unittest.main()
