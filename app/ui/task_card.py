from datetime import date, datetime, time

from PySide6.QtWidgets import (
    QFrame,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
)
from PySide6.QtCore import Qt, Signal
from app.models.task import Task
from app.ui.task_colors import get_short_task_ddl_status, get_task_card_color
from app.utils.time_utils import format_task_time


class TaskCard(QFrame):
    complete_requested = Signal(int)
    delete_requested = Signal(int)
    edit_requested = Signal(int)
    clicked = Signal(object)

    def __init__(self, task: Task, parent=None):
        super().__init__(parent)

        self.task = task
        self.is_expanded = False

        self.setFixedWidth(280)
        self.setObjectName("TaskCard")
        self.init_ui()
        self.apply_style()

    def init_ui(self):
        main_layout = QVBoxLayout(self)

        title_layout = QHBoxLayout()

        self.title_label = QLabel(self.task.title)
        self.title_label.setObjectName("TaskTitle")


        title_layout.addWidget(self.title_label)

        if self.is_timed_task():
            self.timed_label = QLabel("定时任务")
            self.timed_label.setObjectName("TimedLabel")
            title_layout.addWidget(self.timed_label)

        title_layout.addStretch()

        self.description_label = QLabel(self.task.description if self.task.description else "无描述")
        self.description_label.setObjectName("TaskDescription")
        self.description_label.setWordWrap(True)

        ddl_text = self.get_scheduled_text() if self.is_timed_task() else self.get_ddl_text()
        self.ddl_label = QLabel(ddl_text)
        self.ddl_label.setObjectName("DDLLabel")

        self.button_widget = QFrame()
        button_layout = QHBoxLayout(self.button_widget)
        button_layout.setContentsMargins(0, 0, 0, 0)

        self.edit_button = QPushButton("编辑")
        self.complete_button = QPushButton("完成")
        self.delete_button = QPushButton("删除")

        self.edit_button.clicked.connect(self.on_edit_clicked)
        self.complete_button.clicked.connect(self.on_complete_clicked)
        self.delete_button.clicked.connect(self.on_delete_clicked)

        for button in (self.edit_button, self.complete_button, self.delete_button):
            button.setMinimumWidth(80)
            button.setMinimumHeight(50)

        button_layout.addStretch()
        button_layout.addWidget(self.edit_button)
        button_layout.addWidget(self.complete_button)
        button_layout.addWidget(self.delete_button)

        main_layout.addLayout(title_layout)
        main_layout.addStretch()
        main_layout.addWidget(self.description_label)
        main_layout.addStretch()
        main_layout.addWidget(self.ddl_label)
        main_layout.addStretch()
        main_layout.addWidget(self.button_widget)

        self.set_expanded(False)

    def get_ddl_text(self):
        if self.task.task_type == "daily" or self.task.category == "daily":
            daily_due = datetime.combine(date.today(), time(23, 59))
            return f"截止时间：{format_task_time(daily_due)}"

        if not self.task.ddl:
            return "截止时间：未设置"

        status = self.get_ddl_status()

        if status == "expired":
            return f"截止时间：{format_task_time(self.task.ddl)}（已过期）"
        elif status == "urgent":
            return f"截止时间：{format_task_time(self.task.ddl)}（紧急）"
        elif status == "soon":
            return f"截止时间：{format_task_time(self.task.ddl)}（较近）"
        else:
            return f"截止时间：{format_task_time(self.task.ddl)}（充足）"

    def is_timed_task(self):
        return self.task.task_type == "timed" or self.task.category == "timed"

    def get_scheduled_text(self):
        if not self.task.scheduled_at:
            return "时间：未设置"

        return f"时间：{format_task_time(self.task.scheduled_at)}"

    def get_ddl_status(self):
        if self.task.category == "short":
            return get_short_task_ddl_status(self.task)

        return "safe" if self.task.ddl else "none"

    def apply_style(self):
        border_color, background_color, text_color = get_task_card_color(self.task)

        self.setStyleSheet(f"""
            QFrame#TaskCard {{
                background-color: {background_color};
                border: 2px solid {border_color};
                border-radius: 10px;
                padding: 8px;
                margin: 4px;
            }}

            QLabel#TaskTitle {{
                font-size: 16px;
                font-weight: bold;
                color: {text_color};
                background-color: transparent;
            }}

            QLabel#TaskDescription {{
                color: {text_color};
                background-color: transparent;
            }}

            QLabel#DDLLabel {{
                color: {text_color};
                font-weight: bold;
                background-color: transparent;
            }}

            QLabel#TimedLabel {{
                color: {text_color};
                font-weight: bold;
                background-color: transparent;
            }}

            QPushButton {{
                padding: 5px 10px;
                border-radius: 6px;
                background-color: #eeeeee;
                color: #222222;
            }}

            QPushButton:hover {{
                background-color: #dddddd;
            }}
        """)

    def set_expanded(self, expanded):
        self.is_expanded = expanded
        self.description_label.setVisible(expanded)
        self.button_widget.setVisible(expanded)

        self.setMaximumHeight(16777215)
        self.layout().invalidate()
        self.updateGeometry()
        self.adjustSize()

        parent = self.parent()
        if parent is not None:
            if parent.layout() is not None:
                parent.layout().invalidate()
            parent.updateGeometry()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self)
        super().mousePressEvent(event)

    def on_complete_clicked(self):
        self.complete_requested.emit(self.task.task_id)

    def on_delete_clicked(self):
        self.delete_requested.emit(self.task.task_id)

    def on_edit_clicked(self):
        self.edit_requested.emit(self.task.task_id)
