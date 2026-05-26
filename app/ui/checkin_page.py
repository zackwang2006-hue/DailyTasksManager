from datetime import date, datetime, timedelta

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.services.checkin_service import CheckinService
from app.services.task_service import TaskService


class CheckinPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.task_service = TaskService()
        self.checkin_service = CheckinService()
        self.daily_tasks = []
        self.selected_task = None
        self.task_buttons = {}

        self.init_ui()
        self.refresh_tasks()

    def init_ui(self):
        main_layout = QVBoxLayout(self)

        title_label = QLabel("打卡")
        title_label.setObjectName("TitleLabel")

        content_layout = QHBoxLayout()

        self.task_list_frame = QFrame()
        self.task_list_frame.setObjectName("PanelFrame")
        task_list_layout = QVBoxLayout(self.task_list_frame)

        task_list_title = QLabel("每日任务")
        task_list_title.setObjectName("PanelTitle")

        self.task_scroll_area = QScrollArea()
        self.task_scroll_area.setWidgetResizable(True)
        self.task_scroll_area.setFixedWidth(240)

        self.task_container = QWidget()
        self.task_layout = QVBoxLayout(self.task_container)
        self.task_layout.setAlignment(Qt.AlignTop)
        self.task_scroll_area.setWidget(self.task_container)

        task_list_layout.addWidget(task_list_title)
        task_list_layout.addWidget(self.task_scroll_area)

        self.calendar_frame = QFrame()
        self.calendar_frame.setObjectName("PanelFrame")
        calendar_outer_layout = QVBoxLayout(self.calendar_frame)

        self.calendar_title = QLabel("请选择一个每日任务")
        self.calendar_title.setObjectName("PanelTitle")

        self.calendar_grid = QGridLayout()
        self.calendar_grid.setSpacing(8)

        calendar_outer_layout.addWidget(self.calendar_title)
        calendar_outer_layout.addLayout(self.calendar_grid)
        calendar_outer_layout.addStretch()

        content_layout.addWidget(self.task_list_frame)
        content_layout.addWidget(self.calendar_frame, 1)

        main_layout.addWidget(title_label)
        main_layout.addLayout(content_layout)

        self.setStyleSheet("""
            QWidget {
                background-color: #f5f5f5;
            }

            QLabel#TitleLabel {
                font-size: 26px;
                font-weight: bold;
            }

            QFrame#PanelFrame {
                background-color: white;
                border-radius: 10px;
                padding: 8px;
            }

            QLabel#PanelTitle {
                font-size: 18px;
                font-weight: bold;
            }

            QPushButton#TaskButton {
                padding: 10px;
                border: 1px solid #dddddd;
                border-radius: 8px;
                background-color: #ffffff;
                color: #222222;
                text-align: left;
            }

            QPushButton#TaskButton:hover {
                background-color: #eef5ff;
            }

            QPushButton#TaskButton[selected="true"] {
                border: 2px solid #2d8cff;
                background-color: #eaf4ff;
            }

            QLabel#DayCell {
                min-height: 52px;
                border-radius: 8px;
                padding: 6px;
                font-weight: bold;
            }

            QLabel#DayCell[status="done"] {
                background-color: #e8f5e9;
                border: 1px solid #43a047;
                color: #2e7d32;
            }

            QLabel#DayCell[status="missed"] {
                background-color: #ffebee;
                border: 1px solid #e53935;
                color: #c62828;
            }

            QLabel#DayCell[status="disabled"] {
                background-color: #eeeeee;
                border: 1px solid #dddddd;
                color: #888888;
            }

            QLabel#EmptyLabel {
                color: #777777;
                padding: 24px;
            }

            QScrollArea {
                border: none;
            }
        """)

    def refresh_tasks(self):
        self.clear_layout(self.task_layout)
        self.daily_tasks = self.task_service.get_daily_tasks()
        self.task_buttons = {}

        if not self.daily_tasks:
            empty_label = QLabel("还没有每日任务")
            empty_label.setObjectName("EmptyLabel")
            empty_label.setAlignment(Qt.AlignCenter)
            self.task_layout.addWidget(empty_label)
            self.refresh_calendar(None)
            return

        if self.selected_task is None:
            self.selected_task = self.daily_tasks[0]

        task_ids = {task.task_id for task in self.daily_tasks}
        if self.selected_task.task_id not in task_ids:
            self.selected_task = self.daily_tasks[0]

        for task in self.daily_tasks:
            button = QPushButton(task.title)
            button.setObjectName("TaskButton")
            button.setProperty("selected", task.task_id == self.selected_task.task_id)
            button.clicked.connect(
                lambda checked=False, selected=task: self.select_task(selected)
            )

            self.task_buttons[task.task_id] = button
            self.task_layout.addWidget(button)

        self.task_layout.addStretch()
        self.refresh_calendar(self.selected_task)

    def select_task(self, task):
        self.selected_task = task

        for task_id, button in self.task_buttons.items():
            button.setProperty("selected", task_id == task.task_id)
            button.style().unpolish(button)
            button.style().polish(button)

        self.refresh_calendar(task)

    def refresh_calendar(self, task):
        self.clear_layout(self.calendar_grid)

        weekdays = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
        for col, weekday in enumerate(weekdays):
            label = QLabel(weekday)
            label.setAlignment(Qt.AlignCenter)
            self.calendar_grid.addWidget(label, 0, col)

        if task is None:
            self.calendar_title.setText("请选择一个每日任务")
            return

        self.calendar_title.setText(f"{task.title} · 最近 28 天")

        today = date.today()
        current_monday = today - timedelta(days=today.weekday())
        start_date = current_monday - timedelta(days=21)
        checkin_dates = self.checkin_service.get_checkin_dates_by_task(task.task_id)
        created_date = self.get_date_part(task.created_at)

        for week_offset in range(4):
            week_start = current_monday - timedelta(days=week_offset * 7)
            for day_offset in range(7):
                day = week_start + timedelta(days=day_offset)
                date_str = day.isoformat()
                status = self.get_day_status(day, date_str, created_date, checkin_dates, today)

                cell = QLabel(day.strftime("%m-%d"))
                cell.setObjectName("DayCell")
                cell.setProperty("status", status)
                cell.setAlignment(Qt.AlignCenter)
                self.calendar_grid.addWidget(cell, week_offset + 1, day_offset)

    def get_day_status(self, day, date_str, created_date, checkin_dates, today):
        if date_str in checkin_dates:
            return "done"

        if day < created_date or day > today:
            return "disabled"

        return "missed"

    def get_date_part(self, value):
        try:
            return datetime.fromisoformat(value).date()
        except (TypeError, ValueError):
            return date.today()

    def clear_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
