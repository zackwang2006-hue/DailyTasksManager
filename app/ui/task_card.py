from datetime import datetime, date

from PySide6.QtWidgets import (
    QFrame,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
)
from PySide6.QtCore import Qt, Signal

from app.models.task import Task


class TaskCard(QFrame):
    complete_requested = Signal(int)
    delete_requested = Signal(int)
    highlight_requested = Signal(int)
    clicked = Signal(object)

    def __init__(self, task: Task, parent=None):
        super().__init__(parent)

        self.task = task
        self.is_expanded = False

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
            self.timed_label = QLabel("⏰ 定时任务")
            self.timed_label.setObjectName("TimedLabel")
            title_layout.addWidget(self.timed_label)

        if self.task.is_highlighted:
            self.highlight_label = QLabel("★ 高亮")
            self.highlight_label.setObjectName("HighlightLabel")
            title_layout.addWidget(self.highlight_label)
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

        self.highlight_button = QPushButton("高亮/取消")
        self.complete_button = QPushButton("完成")
        self.delete_button = QPushButton("删除")

        self.highlight_button.clicked.connect(self.on_highlight_clicked)
        self.complete_button.clicked.connect(self.on_complete_clicked)
        self.delete_button.clicked.connect(self.on_delete_clicked)

        button_layout.addStretch()
        button_layout.addWidget(self.highlight_button)
        button_layout.addWidget(self.complete_button)
        button_layout.addWidget(self.delete_button)

        main_layout.addLayout(title_layout)
        main_layout.addWidget(self.description_label)
        main_layout.addWidget(self.ddl_label)
        main_layout.addWidget(self.button_widget)

        self.set_expanded(False)

    def get_ddl_text(self):
        if not self.task.ddl:
            return "DDL：未设置"

        status = self.get_ddl_status()

        if status == "expired":
            return f"DDL：{self.task.ddl}（已过期）"
        elif status == "urgent":
            return f"DDL：{self.task.ddl}（紧急）"
        elif status == "soon":
            return f"DDL：{self.task.ddl}（较近）"
        else:
            return f"DDL：{self.task.ddl}（充足）"

    def is_timed_task(self):
        return self.task.task_type == "timed"

    def get_scheduled_text(self):
        if not self.task.scheduled_at:
            return "定时：未设置"

        try:
            scheduled_at = datetime.fromisoformat(self.task.scheduled_at)
        except ValueError:
            return f"定时：{self.task.scheduled_at}"

        return f"定时：{scheduled_at.strftime('%Y-%m-%d %H:%M')}"

    def get_ddl_status(self):
        if not self.task.ddl:
            return "none"

        try:
            ddl_date = datetime.fromisoformat(self.task.ddl).date()
        except ValueError:
            return "none"

        today = date.today()
        diff_days = (ddl_date - today).days

        if diff_days < 0:
            return "expired"
        elif diff_days <= 1:
            return "urgent"
        elif diff_days <= 3:
            return "soon"
        else:
            return "safe"

    def apply_style(self):
        ddl_status = self.get_ddl_status()
        ddl_color = "#666666"

        if self.task.is_highlighted:
            border_color = "#64b5f6"
            background_color = "#eaf4ff"
        elif self.is_timed_task():
            border_color = "#9575cd"
            background_color = "#f3efff"
        elif ddl_status in ["expired", "urgent"]:
            border_color = "#e53935"
            background_color = "#fff0f0"
        elif ddl_status == "soon":
            border_color = "#fbc02d"
            background_color = "#fffbe6"
        elif ddl_status == "safe":
            border_color = "#43a047"
            background_color = "#f0fff4"
        else:
            border_color = "#cccccc"
            background_color = "#ffffff"

        if ddl_status in ["expired", "urgent"]:
            ddl_color = "#e53935"
        elif ddl_status == "soon":
            ddl_color = "#f9a825"
        elif ddl_status == "safe":
            ddl_color = "#43a047"

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
            }}

            QLabel#TaskDescription {{
                color: #444444;
            }}

            QLabel#DDLLabel {{
                color: {ddl_color};
                font-weight: bold;
            }}

            QLabel#HighlightLabel {{
                color: #1976d2;
                font-weight: bold;
            }}

            QLabel#TimedLabel {{
                color: #5e35b1;
                font-weight: bold;
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

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self)
        super().mousePressEvent(event)

    def on_complete_clicked(self):
        self.complete_requested.emit(self.task.task_id)

    def on_delete_clicked(self):
        self.delete_requested.emit(self.task.task_id)

    def on_highlight_clicked(self):
        self.highlight_requested.emit(self.task.task_id)
