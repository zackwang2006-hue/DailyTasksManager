from datetime import date, datetime, timedelta

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.services.checkin_service import CheckinService
from app.services.task_service import TaskService
from app.ui.task_dialog import TaskDialog


class CheckinPage(QWidget):
    data_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)

        self.task_service = TaskService()
        self.checkin_service = CheckinService()
        self.daily_tasks = []
        self.selected_task = None
        self.task_buttons = {}

        self.init_ui()
        self.refresh_tasks()

    def refresh_page(self):
        self.refresh_tasks()

    def init_ui(self):
        main_layout = QVBoxLayout(self)

        title_label = QLabel("打卡记录")
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

        self.start_date_label = QLabel("")
        self.start_date_label.setObjectName("StartDateLabel")

        self.range_hint_label = QLabel("只显示最近 28 天的完成情况")
        self.range_hint_label.setObjectName("RangeHintLabel")
        self.range_hint_label.setAlignment(Qt.AlignCenter)

        self.calendar_grid = QGridLayout()
        self.calendar_grid.setSpacing(8)

        calendar_outer_layout.addWidget(self.calendar_title)
        calendar_outer_layout.addWidget(self.start_date_label)
        calendar_outer_layout.addWidget(self.range_hint_label)
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

            QLabel#StartDateLabel {
                color: #555555;
            }

            QLabel#RangeHintLabel {
                color: #777777;
                padding: 4px;
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
        else:
            self.selected_task = next(
                task for task in self.daily_tasks
                if task.task_id == self.selected_task.task_id
            )

        for task in self.daily_tasks:
            button = QPushButton(task.title)
            button.setObjectName("TaskButton")
            button.setProperty("selected", task.task_id == self.selected_task.task_id)
            button.setContextMenuPolicy(Qt.CustomContextMenu)
            button.clicked.connect(
                lambda checked=False, selected=task: self.select_task(selected)
            )
            button.customContextMenuRequested.connect(
                lambda position, selected=task, source=button:
                    self.open_task_menu(selected, source, position)
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

    def open_task_menu(self, task, source, position):
        menu = QMenu(self)
        edit_action = menu.addAction("编辑每日任务")
        delete_action = menu.addAction("删除每日任务")

        selected_action = menu.exec(source.mapToGlobal(position))

        if selected_action == edit_action:
            self.open_edit_task_dialog(task.task_id)
        elif selected_action == delete_action:
            self.delete_daily_task(task.task_id)

    def open_edit_task_dialog(self, task_id):
        task = self.task_service.get_task_by_id(task_id)
        if task is None:
            return

        dialog = TaskDialog(task, self)

        if dialog.exec():
            data = dialog.get_task_data()
            self.task_service.update_task(
                task_id=task_id,
                title=data["title"],
                description=data["description"],
                category=data["category"],
                ddl=data["ddl"],
                task_type=data["task_type"],
                scheduled_at=data["scheduled_at"],
            )
            self.refresh_tasks()
            self.data_changed.emit()

    def delete_daily_task(self, task_id):
        result = QMessageBox.question(
            self,
            "确认删除",
            "确定要删除这个每日任务吗？历史打卡记录会保留。",
            QMessageBox.Yes | QMessageBox.No,
        )

        if result != QMessageBox.Yes:
            return

        if self.selected_task is not None and self.selected_task.task_id == task_id:
            self.selected_task = None

        self.task_service.soft_delete_task(task_id)
        self.refresh_tasks()
        self.data_changed.emit()

    def refresh_calendar(self, task):
        self.clear_layout(self.calendar_grid)

        weekdays = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
        for col, weekday in enumerate(weekdays):
            label = QLabel(weekday)
            label.setAlignment(Qt.AlignCenter)
            self.calendar_grid.addWidget(label, 0, col)

        if task is None:
            self.calendar_title.setText("请选择一个每日任务")
            self.start_date_label.setText("")
            return

        today = date.today()
        current_monday = today - timedelta(days=today.weekday())
        checkin_dates = self.checkin_service.get_checkin_dates_by_task(task.task_id)
        created_date = self.get_date_part(task.created_at)
        start_date = self.get_task_start_date(created_date, checkin_dates)
        streak_days = self.get_streak_days(checkin_dates, today)

        self.calendar_title.setText(f"{task.title} · 你已经坚持打卡 {streak_days} 天")
        self.start_date_label.setText(f"始于 {start_date.strftime('%Y 年 %m 月 %d 日')}")

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

    def get_task_start_date(self, created_date, checkin_dates):
        if created_date:
            return created_date

        if checkin_dates:
            return datetime.fromisoformat(min(checkin_dates)).date()

        return date.today()

    def get_streak_days(self, checkin_dates, today):
        if not checkin_dates:
            return 0

        current_day = today
        if current_day.isoformat() not in checkin_dates:
            current_day -= timedelta(days=1)

        streak_days = 0
        while current_day.isoformat() in checkin_dates:
            streak_days += 1
            current_day -= timedelta(days=1)

        return streak_days

    def get_day_status(self, day, date_str, created_date, checkin_dates, today):
        if date_str in checkin_dates:
            return "done"

        if (created_date and day < created_date) or day > today:
            return "disabled"

        return "missed"

    def get_date_part(self, value):
        try:
            return datetime.fromisoformat(value).date()
        except (TypeError, ValueError):
            return None

    def clear_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
