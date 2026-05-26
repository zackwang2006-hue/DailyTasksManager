from datetime import date, datetime, timedelta

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.services.history_service import HistoryService


TASK_TYPE_LABELS = {
    "normal": "普通任务",
    "timed": "定时任务",
    "daily": "每日任务",
}

CATEGORY_LABELS = {
    "short": "短期任务",
    "long": "长期任务",
    "daily": "每日任务",
    "extra": "附加任务",
    "timed": "定时任务",
}


class HistoryPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.history_service = HistoryService()
        self.selected_date = date.today().isoformat()
        self.day_buttons = {}

        self.init_ui()
        self.refresh_calendar()
        self.show_logs_for_date(self.selected_date)

    def refresh_page(self):
        self.refresh_calendar()
        self.show_logs_for_date(self.selected_date)

    def init_ui(self):
        main_layout = QVBoxLayout(self)

        title_label = QLabel("历史完成")
        title_label.setObjectName("TitleLabel")

        self.calendar_frame = QFrame()
        self.calendar_frame.setObjectName("CalendarFrame")
        self.calendar_layout = QGridLayout(self.calendar_frame)
        self.calendar_layout.setSpacing(8)

        self.detail_title = QLabel()
        self.detail_title.setObjectName("DetailTitle")

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)

        self.log_container = QWidget()
        self.log_layout = QVBoxLayout(self.log_container)
        self.log_layout.setAlignment(Qt.AlignTop)
        self.scroll_area.setWidget(self.log_container)

        main_layout.addWidget(title_label)
        main_layout.addWidget(self.calendar_frame)
        main_layout.addWidget(self.detail_title)
        main_layout.addWidget(self.scroll_area)

        self.setStyleSheet("""
            QWidget {
                background-color: #f5f5f5;
            }

            QLabel#TitleLabel {
                font-size: 26px;
                font-weight: bold;
            }

            QFrame#CalendarFrame {
                background-color: white;
                border-radius: 10px;
                padding: 8px;
            }

            QLabel#WeekdayLabel {
                font-weight: bold;
                color: #444444;
            }

            QPushButton#DayButton {
                min-height: 56px;
                border: 1px solid #dddddd;
                border-radius: 8px;
                background-color: #ffffff;
                color: #222222;
                text-align: center;
            }

            QPushButton#DayButton:hover {
                background-color: #eef5ff;
            }

            QPushButton#DayButton[selected="true"] {
                border: 2px solid #2d8cff;
                background-color: #eaf4ff;
            }

            QPushButton#DayButton[status="light"] {
                background-color: #e8f5e9;
                border: 1px solid #a5d6a7;
                color: #2e7d32;
            }

            QPushButton#DayButton[status="medium"] {
                background-color: #66bb6a;
                border: 1px solid #43a047;
                color: #ffffff;
            }

            QPushButton#DayButton[status="dark"] {
                background-color: #1b5e20;
                border: 1px solid #0f3d14;
                color: #ffffff;
            }

            QPushButton#DayButton[status="future"] {
                background-color: #eeeeee;
                border: 1px solid #dddddd;
                color: #999999;
            }

            QPushButton#DayButton:disabled {
                background-color: #eeeeee;
                border: 1px solid #dddddd;
                color: #999999;
            }

            QLabel#DetailTitle {
                font-size: 18px;
                font-weight: bold;
                margin-top: 10px;
            }

            QFrame#LogCard {
                background-color: white;
                border: 1px solid #dddddd;
                border-radius: 8px;
                padding: 8px;
            }

            QFrame#LogCard QLabel {
                background-color: transparent;
            }

            QLabel#LogTitle {
                font-size: 15px;
                font-weight: bold;
                background-color: transparent;
            }

            QLabel#LogMeta {
                color: #666666;
                background-color: transparent;
            }

            QLabel#EmptyLabel {
                color: #777777;
                padding: 24px;
            }

            QScrollArea {
                border: none;
            }
        """)

    def refresh_calendar(self):
        self.clear_layout(self.calendar_layout)
        self.day_buttons = {}

        weekdays = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
        for col, weekday in enumerate(weekdays):
            label = QLabel(weekday)
            label.setObjectName("WeekdayLabel")
            label.setAlignment(Qt.AlignCenter)
            self.calendar_layout.addWidget(label, 0, col)

        today = date.today()
        if self.selected_date > today.isoformat():
            self.selected_date = today.isoformat()

        current_monday = today - timedelta(days=today.weekday())
        start_date = current_monday - timedelta(days=21)
        end_date = current_monday + timedelta(days=6)
        logs = self.history_service.get_logs_between(
            start_date.isoformat(),
            end_date.isoformat(),
        )

        counts_by_date = {}
        for log in logs:
            log_date = self.get_date_part(log["completed_at"])
            counts_by_date[log_date] = counts_by_date.get(log_date, 0) + 1

        for week_offset in range(4):
            week_start = current_monday - timedelta(days=week_offset * 7)
            for day_offset in range(7):
                day = week_start + timedelta(days=day_offset)
                date_str = day.isoformat()
                count = counts_by_date.get(date_str, 0)
                text = day.strftime("%m-%d")
                if count:
                    text = f"{text}\n{count} 项"

                button = QPushButton(text)
                button.setObjectName("DayButton")
                button.setProperty("status", self.get_day_status(day, count, today))
                button.setProperty("selected", date_str == self.selected_date)
                button.setContextMenuPolicy(Qt.NoContextMenu)
                if day > today:
                    button.setEnabled(False)
                else:
                    button.clicked.connect(
                        lambda checked=False, selected=date_str: self.select_date(selected)
                    )

                self.day_buttons[date_str] = button
                self.calendar_layout.addWidget(button, week_offset + 1, day_offset)

    def get_day_status(self, day, count, today):
        if day > today:
            return "future"
        if count >= 5:
            return "dark"
        if count >= 3:
            return "medium"
        if count >= 1:
            return "light"
        return "normal"

    def select_date(self, date_str):
        self.selected_date = date_str

        for button_date, button in self.day_buttons.items():
            button.setProperty("selected", button_date == date_str)
            button.style().unpolish(button)
            button.style().polish(button)

        self.show_logs_for_date(date_str)

    def show_logs_for_date(self, date_str):
        self.clear_layout(self.log_layout)
        self.detail_title.setText(f"{date_str} 完成记录")

        logs = self.history_service.get_logs_by_date(date_str)
        if not logs:
            empty_label = QLabel("这一天还没有完成任务")
            empty_label.setObjectName("EmptyLabel")
            empty_label.setAlignment(Qt.AlignCenter)
            self.log_layout.addWidget(empty_label)
            self.log_layout.addStretch()
            return

        for log in logs:
            self.log_layout.addWidget(self.create_log_card(log))

        self.log_layout.addStretch()

    def create_log_card(self, log):
        card = QFrame()
        card.setObjectName("LogCard")

        layout = QVBoxLayout(card)

        title_label = QLabel(log["title"])
        title_label.setObjectName("LogTitle")

        task_type = self.get_task_type_text(log)
        completed_at = self.format_datetime(log["completed_at"])
        meta_text = f"{task_type} · 完成：{completed_at}"

        if log["scheduled_at"]:
            meta_text += f" · 定时：{self.format_datetime(log['scheduled_at'])}"

        meta_label = QLabel(meta_text)
        meta_label.setObjectName("LogMeta")
        meta_label.setWordWrap(True)

        layout.addWidget(title_label)
        layout.addWidget(meta_label)

        if log["description"]:
            description_label = QLabel(log["description"])
            description_label.setWordWrap(True)
            layout.addWidget(description_label)

        return card

    def get_task_type_text(self, log):
        if log["task_type"] == "timed" or log["category"] == "timed":
            return "定时任务"

        if log["task_type"] == "daily" or log["category"] == "daily":
            return "每日任务"

        return CATEGORY_LABELS.get(
            log["category"] or "",
            TASK_TYPE_LABELS.get(log["task_type"] or "normal", "普通任务"),
        )

    def clear_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def get_date_part(self, value):
        try:
            return datetime.fromisoformat(value).date().isoformat()
        except (TypeError, ValueError):
            return value[:10]

    def format_datetime(self, value):
        if not value:
            return ""

        try:
            return datetime.fromisoformat(value).strftime("%Y-%m-%d %H:%M")
        except ValueError:
            return value
