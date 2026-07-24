import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication

from app.database import db_manager
from app.models.plan import PlanLevel
from app.services.period_service import period_service
from app.services.task_service import TaskService
from app.ui.floating_task_window import FloatingTaskItem
from app.ui.task_card import TaskCard
from app.ui.task_dialog import TaskDialog
from app.ui.task_page import TaskPage


class UiDetailRegressionTests(unittest.TestCase):
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

    def test_floating_card_collapsed_and_expanded_text(self):
        service = TaskService()
        normal_id = service.add_plan_task("normal", plan_level=PlanLevel.DAY, now=date(2026, 7, 23))
        fixed_id = service.add_plan_task(
            "fixed",
            plan_level=PlanLevel.DAY,
            scheduled_at="2026-07-23 08:30:00",
            is_fixed_event=True,
            now=date(2026, 7, 23),
        )

        normal_item = FloatingTaskItem(service.get_task_by_id(normal_id), "", "日计划")
        fixed_item = FloatingTaskItem(service.get_task_by_id(fixed_id), "时间：2026-07-23 08:30", "日计划")

        self.assertEqual(normal_item.summary_label.text(), "normal")
        self.assertIn("08:30", fixed_item.summary_label.text())

        normal_item.set_expanded(True)
        detail_texts = [
            normal_item.detail_frame.layout().itemAt(index).widget().text()
            for index in range(normal_item.detail_frame.layout().count())
            if hasattr(normal_item.detail_frame.layout().itemAt(index).widget(), "text")
        ]
        self.assertIn("normal", detail_texts)
        self.assertIn("描述：我懒得描述", detail_texts)
        self.assertFalse(any("分类：" in text for text in detail_texts))
        self.assertFalse(any("时间：" in text or "日期：" in text for text in detail_texts))

    def test_plan_card_hides_deadline_and_previous_readonly_state(self):
        service = TaskService()
        task_id = service.add_plan_task("current", plan_level=PlanLevel.DAY, now=date(2026, 7, 23))
        task = service.get_task_by_id(task_id)

        card = TaskCard(task)
        card.set_expanded(True)
        self.assertFalse(card.ddl_label.isVisible())
        self.assertFalse(card.button_widget.isHidden())

        previous_card = TaskCard(task, read_only=True, show_previous_status=True)
        previous_card.set_expanded(True)
        self.assertEqual(previous_card.title_label.text(), "current (未完成)")
        self.assertIn("#e53935", previous_card.styleSheet())
        self.assertTrue(previous_card.button_widget.isHidden())
        previous_card.set_expanded(False)
        previous_card.set_expanded(True)
        self.assertEqual(previous_card.title_label.text(), "current (未完成)")

        service.complete_task(task_id, "完成情况记录")
        completed_card = TaskCard(service.get_task_by_id(task_id), read_only=True, show_previous_status=True)
        self.assertEqual(completed_card.title_label.text(), "current")

    def test_previous_mode_readonly_and_current_mode_restores_actions(self):
        service = TaskService()
        service.add_plan_task("previous", plan_level=PlanLevel.DAY, now=date(2026, 7, 22))
        service.add_plan_task("current", plan_level=PlanLevel.DAY, now=date(2026, 7, 23))

        page = TaskPage()
        page.task_service = service
        page.toggle_previous_period(PlanLevel.DAY)
        previous_cards = page.sections[PlanLevel.DAY].grid.cards
        self.assertEqual(previous_cards[0].title_label.text(), "previous (未完成)")
        previous_cards[0].set_expanded(True)
        self.assertTrue(previous_cards[0].button_widget.isHidden())

        page.toggle_previous_period(PlanLevel.DAY)
        current_cards = page.sections[PlanLevel.DAY].grid.cards
        self.assertEqual(current_cards[0].title_label.text(), "current")
        current_cards[0].set_expanded(True)
        self.assertFalse(current_cards[0].button_widget.isHidden())

    def test_previous_mode_report_button_visibility_for_all_plan_sections(self):
        page = TaskPage()
        for plan_level, section in page.sections.items():
            self.assertFalse(section.send_report_button.isVisible())

            page.toggle_previous_period(plan_level)
            self.assertTrue(section.send_report_button.isVisible())
            self.assertFalse(section.add_button.isVisible())
            self.assertEqual(section.send_report_button.text(), "发送报告")

            page.toggle_previous_period(plan_level)
            self.assertFalse(section.send_report_button.isVisible())
            self.assertTrue(section.add_button.isVisible())

    def test_sent_previous_period_uses_resend_report_text(self):
        page = TaskPage()
        section = page.sections[PlanLevel.DAY]
        period = period_service.previous_period(PlanLevel.DAY)
        record = page.report_repository.get_or_create_period_report(
            period.level.value,
            period.start.isoformat(),
            period.end.isoformat(),
        )
        page.report_repository.mark_generated(record.report_id, "title", "report.md", "# report")
        page.report_repository.mark_sent(record.report_id)

        page.toggle_previous_period(PlanLevel.DAY)

        self.assertTrue(section.send_report_button.isVisible())
        self.assertEqual(section.send_report_button.text(), "重新发送报告")

    def test_task_dialog_priority_controls_are_mutually_exclusive(self):
        dialog = TaskDialog(mode="plan", plan_level=PlanLevel.DAY)

        dialog.important_checkbox.setChecked(True)
        self.assertFalse(dialog.fixed_event_checkbox.isEnabled())

        dialog.important_checkbox.setChecked(False)
        dialog.fixed_event_checkbox.setChecked(True)
        self.assertFalse(dialog.important_checkbox.isChecked())
        self.assertFalse(dialog.urgent_checkbox.isChecked())
        self.assertFalse(dialog.important_checkbox.isEnabled())
        self.assertFalse(dialog.urgent_checkbox.isEnabled())
        self.assertTrue(dialog.scheduled_time_input.isEnabled())
        self.assertFalse(dialog.scheduled_date_input.isVisible())

        data = dialog.get_task_data()
        self.assertIsNone(data["scheduled_at"])
        self.assertIsNotNone(data["fixed_time"])
        self.assertTrue(data["is_fixed_event"])


if __name__ == "__main__":
    unittest.main()
