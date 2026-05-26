from datetime import datetime, date

from PySide6.QtWidgets import (
    QFrame,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
)
from PySide6.QtCore import Signal

from app.models.task import Task


class TaskCard(QFrame):
    complete_requested = Signal(int)
    delete_requested = Signal(int)
    highlight_requested = Signal(int)

    def __init__(self, task: Task, parent=None):
        super().__init__(parent)

        self.task = task

        self.setObjectName("TaskCard")
        self.init_ui()
        self.apply_style()

    def init_ui(self):
        main_layout = QVBoxLayout(self)

        title_layout = QHBoxLayout()

        title_label = QLabel(self.task.title)
        title_label.setObjectName("TaskTitle")

        if self.task.is_highlighted:
            highlight_label = QLabel("★ 高亮")
            highlight_label.setObjectName("HighlightLabel")
            title_layout.addWidget(highlight_label)

        title_layout.addWidget(title_label)
        title_layout.addStretch()

        description_label = QLabel(self.task.description if self.task.description else "无描述")
        description_label.setObjectName("TaskDescription")
        description_label.setWordWrap(True)

        ddl_text = self.get_ddl_text()
        ddl_label = QLabel(ddl_text)
        ddl_label.setObjectName("DDLLabel")

        button_layout = QHBoxLayout()

        highlight_button = QPushButton("高亮/取消")
        complete_button = QPushButton("完成")
        delete_button = QPushButton("删除")

        highlight_button.clicked.connect(self.on_highlight_clicked)
        complete_button.clicked.connect(self.on_complete_clicked)
        delete_button.clicked.connect(self.on_delete_clicked)

        button_layout.addStretch()
        button_layout.addWidget(highlight_button)
        button_layout.addWidget(complete_button)
        button_layout.addWidget(delete_button)

        main_layout.addLayout(title_layout)
        main_layout.addWidget(description_label)
        main_layout.addWidget(ddl_label)
        main_layout.addLayout(button_layout)

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

        if self.task.is_highlighted:
            border_color = "#ff9800"
            background_color = "#fff7e6"
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
                color: #666666;
                font-weight: bold;
            }}

            QLabel#HighlightLabel {{
                color: #ff9800;
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

    def on_complete_clicked(self):
        self.complete_requested.emit(self.task.task_id)

    def on_delete_clicked(self):
        self.delete_requested.emit(self.task.task_id)

    def on_highlight_clicked(self):
        self.highlight_requested.emit(self.task.task_id)