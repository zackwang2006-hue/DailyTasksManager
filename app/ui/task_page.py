from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.config import TASK_CATEGORIES
from app.services.task_service import TaskService
from app.ui.task_card import TaskCard
from app.ui.task_dialog import TaskDialog


class TaskPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.task_service = TaskService()
        self.expanded_task_card = None

        self.init_ui()
        self.refresh_tasks()

    def init_ui(self):
        main_layout = QVBoxLayout(self)

        title_label = QLabel("任务")
        title_label.setObjectName("TitleLabel")

        add_button = QPushButton("新增任务")
        add_button.clicked.connect(self.open_add_task_dialog)

        refresh_button = QPushButton("刷新")
        refresh_button.clicked.connect(self.refresh_tasks)

        top_layout = QHBoxLayout()
        top_layout.addWidget(title_label)
        top_layout.addStretch()
        top_layout.addWidget(refresh_button)
        top_layout.addWidget(add_button)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)

        self.task_container = QWidget()
        self.task_layout = QVBoxLayout(self.task_container)
        self.task_layout.setAlignment(Qt.AlignTop)

        self.scroll_area.setWidget(self.task_container)

        main_layout.addLayout(top_layout)
        main_layout.addWidget(self.scroll_area)

        self.setStyleSheet("""
            QWidget {
                background-color: #f5f5f5;
            }

            QLabel#TitleLabel {
                font-size: 26px;
                font-weight: bold;
            }

            QLabel#AllDoneLabel {
                font-size: 22px;
                font-weight: bold;
                color: #2e7d32;
                padding: 40px;
            }

            QPushButton {
                padding: 8px 14px;
                border-radius: 8px;
                background-color: #2d8cff;
                color: white;
                font-weight: bold;
            }

            QPushButton:hover {
                background-color: #1f6fd1;
            }

            QScrollArea {
                border: none;
            }

            QLabel#CategoryTitle {
                font-size: 18px;
                font-weight: bold;
                margin-top: 16px;
                margin-bottom: 6px;
            }

            QFrame#CategoryFrame {
                background-color: white;
                border-radius: 12px;
                padding: 8px;
            }
        """)

    def open_add_task_dialog(self):
        dialog = TaskDialog(self)

        if dialog.exec():
            data = dialog.get_task_data()

            self.task_service.add_task(
                title=data["title"],
                description=data["description"],
                category=data["category"],
                ddl=data["ddl"],
                task_type=data["task_type"],
                scheduled_at=data["scheduled_at"],
            )

            self.refresh_tasks()

    def refresh_tasks(self):
        self.clear_task_layout()
        self.expanded_task_card = None

        has_any_task = False

        timed_tasks = self.task_service.get_timed_tasks()
        if timed_tasks:
            has_any_task = True
            self.add_task_section("定时任务", timed_tasks)

        for category_key, category_name in TASK_CATEGORIES.items():
            tasks = self.task_service.get_tasks_by_category(category_key)
            tasks = [task for task in tasks if task.task_type != "timed"]

            if not tasks:
                continue

            has_any_task = True
            self.add_task_section(category_name, tasks)

        if not has_any_task:
            all_done_label = QLabel("太牛逼了，任务全给你做完了")
            all_done_label.setObjectName("AllDoneLabel")
            all_done_label.setAlignment(Qt.AlignCenter)
            self.task_layout.addWidget(all_done_label)

        self.task_layout.addStretch()

    def add_task_section(self, section_name, tasks):
        category_title = QLabel(section_name)
        category_title.setObjectName("CategoryTitle")
        self.task_layout.addWidget(category_title)

        category_frame = QFrame()
        category_frame.setObjectName("CategoryFrame")

        category_layout = QVBoxLayout(category_frame)
        category_layout.setAlignment(Qt.AlignTop)

        for task in tasks:
            task_card = TaskCard(task)
            task_card.complete_requested.connect(self.complete_task)
            task_card.delete_requested.connect(self.delete_task)
            task_card.highlight_requested.connect(self.toggle_highlight)
            task_card.clicked.connect(self.toggle_task_card)
            category_layout.addWidget(task_card)

        self.task_layout.addWidget(category_frame)

    def clear_task_layout(self):
        self.expanded_task_card = None

        while self.task_layout.count():
            item = self.task_layout.takeAt(0)

            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def toggle_task_card(self, task_card):
        if self.expanded_task_card is task_card:
            task_card.set_expanded(False)
            self.expanded_task_card = None
            return

        if self.expanded_task_card is not None:
            self.expanded_task_card.set_expanded(False)

        task_card.set_expanded(True)
        self.expanded_task_card = task_card

    def complete_task(self, task_id):
        self.task_service.complete_task(task_id)
        self.refresh_tasks()

    def delete_task(self, task_id):
        result = QMessageBox.question(
            self,
            "确认删除",
            "确定要删除这个任务吗？",
            QMessageBox.Yes | QMessageBox.No,
        )

        if result == QMessageBox.Yes:
            self.task_service.delete_task(task_id)
            self.refresh_tasks()

    def toggle_highlight(self, task_id):
        self.task_service.toggle_highlight(task_id)
        self.refresh_tasks()
