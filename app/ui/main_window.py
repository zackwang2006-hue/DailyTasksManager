from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QScrollArea,
    QMessageBox,
    QFrame,
)
from PySide6.QtCore import Qt

from app.config import APP_NAME, WINDOW_WIDTH, WINDOW_HEIGHT, TASK_CATEGORIES
from app.services.task_service import TaskService
from app.ui.task_dialog import TaskDialog
from app.ui.task_card import TaskCard


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.task_service = TaskService()

        self.setWindowTitle(APP_NAME)
        self.resize(WINDOW_WIDTH, WINDOW_HEIGHT)

        self.init_ui()
        self.refresh_tasks()

    def init_ui(self):
        central_widget = QWidget()
        main_layout = QVBoxLayout(central_widget)

        title_label = QLabel("日程表 1.0")
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

        self.setCentralWidget(central_widget)

        self.setStyleSheet("""
            QMainWindow {
                background-color: #f5f5f5;
            }

            QLabel#TitleLabel {
                font-size: 26px;
                font-weight: bold;
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
                ddl=data["ddl"]
            )

            self.refresh_tasks()

    def refresh_tasks(self):
        self.clear_task_layout()

        for category_key, category_name in TASK_CATEGORIES.items():
            tasks = self.task_service.get_tasks_by_category(category_key)

            category_title = QLabel(category_name)
            category_title.setObjectName("CategoryTitle")
            self.task_layout.addWidget(category_title)

            category_frame = QFrame()
            category_frame.setObjectName("CategoryFrame")

            category_layout = QVBoxLayout(category_frame)
            category_layout.setAlignment(Qt.AlignTop)

            if not tasks:
                empty_label = QLabel("暂无任务")
                empty_label.setStyleSheet("color: gray;")
                category_layout.addWidget(empty_label)
            else:
                for task in tasks:
                    task_card = TaskCard(task)
                    task_card.complete_requested.connect(self.complete_task)
                    task_card.delete_requested.connect(self.delete_task)
                    task_card.highlight_requested.connect(self.toggle_highlight)
                    category_layout.addWidget(task_card)

            self.task_layout.addWidget(category_frame)

        self.task_layout.addStretch()

    def clear_task_layout(self):
        while self.task_layout.count():
            item = self.task_layout.takeAt(0)

            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def complete_task(self, task_id):
        self.task_service.complete_task(task_id)
        self.refresh_tasks()

    def delete_task(self, task_id):
        result = QMessageBox.question(
            self,
            "确认删除",
            "确定要删除这个任务吗？",
            QMessageBox.Yes | QMessageBox.No
        )

        if result == QMessageBox.Yes:
            self.task_service.delete_task(task_id)
            self.refresh_tasks()

    def toggle_highlight(self, task_id):
        self.task_service.toggle_highlight(task_id)
        self.refresh_tasks()