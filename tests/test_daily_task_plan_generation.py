import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from app.database import db_manager
from app.models.plan import PlanLevel
from app.services.checkin_service import CheckinService
from app.services.period_service import period_service
from app.services.task_service import TaskService


class DailyTaskPlanGenerationTests(unittest.TestCase):
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

    def generated_rows(self, service, daily_task_id):
        return service.db.fetch_all(
            """
            SELECT *
            FROM tasks
            WHERE source_daily_task_id = ?
            ORDER BY generated_date
            """,
            (daily_task_id,),
        )

    def create_parent(self, service, level=PlanLevel.WEEK, today=date(2026, 7, 23), title="parent"):
        return service.add_plan_task(title, plan_level=level, now=today)

    def test_daily_task_generates_from_creation_date_and_is_idempotent(self):
        service = TaskService()
        parent_id = self.create_parent(service)

        daily_id = service.add_daily_task_rule(
            "daily module",
            "one module",
            parent_id,
            today=date(2026, 7, 23),
        )

        rows = self.generated_rows(service, daily_id)
        self.assertEqual([row["generated_date"] for row in rows], ["2026-07-23"])
        self.assertEqual(rows[0]["plan_level"], PlanLevel.DAY.value)
        self.assertEqual(rows[0]["period_key"], "day:2026-07-23")
        self.assertEqual(rows[0]["category"], "plan")
        self.assertEqual(rows[0]["task_type"], "normal")
        self.assertEqual(rows[0]["parent_plan_task_id"], parent_id)

        service.ensure_daily_plan_tasks_for_date(date(2026, 7, 22))
        self.assertEqual([row["generated_date"] for row in self.generated_rows(service, daily_id)], ["2026-07-23"])

        service.ensure_daily_plan_tasks_for_date(date(2026, 7, 24))
        service.ensure_daily_plan_tasks_for_date(date(2026, 7, 24))
        self.assertEqual(
            [row["generated_date"] for row in self.generated_rows(service, daily_id)],
            ["2026-07-23", "2026-07-24"],
        )

    def test_daily_task_generates_on_parent_end_date_but_not_after(self):
        service = TaskService()
        parent_id = self.create_parent(service)
        daily_id = service.add_daily_task_rule("daily", "", parent_id, today=date(2026, 7, 23))

        service.ensure_daily_plan_tasks_for_date(date(2026, 7, 26))
        service.ensure_daily_plan_tasks_for_date(date(2026, 7, 27))

        generated_dates = [row["generated_date"] for row in self.generated_rows(service, daily_id)]
        self.assertIn("2026-07-26", generated_dates)
        self.assertNotIn("2026-07-27", generated_dates)
        self.assertTrue(service.get_task_by_id(daily_id).archived)

    def test_parent_delete_archives_related_daily_tasks(self):
        service = TaskService()
        parent_id = self.create_parent(service)
        daily_id = service.add_daily_task_rule("daily", "", parent_id, today=date(2026, 7, 23))

        service.delete_task(parent_id)

        row = service.db.fetch_one("SELECT archived FROM tasks WHERE id = ?", (daily_id,))
        self.assertEqual(row["archived"], 1)

    def test_completed_parent_does_not_expire_daily_task_before_period_end(self):
        service = TaskService()
        parent_id = self.create_parent(service)
        daily_id = service.add_daily_task_rule("daily", "", parent_id, today=date(2026, 7, 23))

        service.complete_task(parent_id)
        service.ensure_daily_plan_tasks_for_date(date(2026, 7, 24))

        self.assertIn("2026-07-24", [row["generated_date"] for row in self.generated_rows(service, daily_id)])
        self.assertFalse(service.get_task_by_id(daily_id).archived)

    def test_legacy_daily_task_without_parent_is_preserved_but_not_generated(self):
        service = TaskService()
        legacy_id = service.add_task(
            "legacy daily",
            category="daily",
            task_type="daily",
            now=date(2026, 7, 20),
        )

        CheckinService().add_daily_checkin(legacy_id, "2026-07-21", "2026-07-21T10:00:00")
        service.ensure_daily_plan_tasks_for_date(date(2026, 7, 23))

        self.assertIsNotNone(service.get_task_by_id(legacy_id))
        self.assertIsNotNone(
            service.db.fetch_one(
                "SELECT 1 FROM daily_checkins WHERE task_id = ? AND checkin_date = ?",
                (legacy_id, "2026-07-21"),
            )
        )
        self.assertIsNone(
            service.db.fetch_one(
                "SELECT 1 FROM tasks WHERE source_daily_task_id = ?",
                (legacy_id,),
            )
        )

    def test_daily_generated_completion_writes_checkin_history(self):
        service = TaskService()
        parent_id = self.create_parent(service)
        daily_id = service.add_daily_task_rule("daily", "", parent_id, today=date(2026, 7, 23))
        generated = service.get_generated_daily_plan_task(daily_id, date(2026, 7, 23))

        service.complete_task(generated.task_id)

        row = service.db.fetch_one(
            "SELECT is_completed FROM daily_checkins WHERE task_id = ? AND checkin_date = ?",
            (daily_id, "2026-07-23"),
        )
        self.assertEqual(row["is_completed"], 1)

    def test_available_parent_tasks_only_current_active_period(self):
        service = TaskService()
        current_parent = self.create_parent(service, PlanLevel.MONTH, date(2026, 7, 23), "current")
        service.add_plan_task("previous", plan_level=PlanLevel.MONTH, now=date(2026, 6, 20))

        tasks = service.get_available_parent_plan_tasks(PlanLevel.MONTH, date(2026, 7, 23))

        self.assertEqual([task.task_id for task in tasks], [current_parent])
        self.assertEqual(
            period_service.current_period(PlanLevel.MONTH, date(2026, 7, 23)).key,
            tasks[0].period_key,
        )


if __name__ == "__main__":
    unittest.main()
