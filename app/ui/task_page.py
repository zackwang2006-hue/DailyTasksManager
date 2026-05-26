from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
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


class TaskGridSection(QFrame):
    card_width = 280
    card_spacing = 12

    def __init__(self, parent=None):
        super().__init__(parent)

        self.cards = []
        self.available_width = 0
        self.column_count = 0
        self.setObjectName("CategoryFrame")

        self.grid_layout = QGridLayout(self)
        self.grid_layout.setContentsMargins(8, 8, 8, 8)
        self.grid_layout.setHorizontalSpacing(self.card_spacing)
        self.grid_layout.setVerticalSpacing(self.card_spacing)
        self.grid_layout.setAlignment(Qt.AlignLeft | Qt.AlignTop)

    def add_task_card(self, task_card):
        self.cards.append(task_card)
        self.reflow_cards()

    def set_available_width(self, width):
        if width <= 0:
            return

        self.available_width = width
        self.setFixedWidth(width)
        self.reflow_cards()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.reflow_cards()

    def reflow_cards(self):
        available_width = max(1, self.available_width or self.width())
        margins = self.grid_layout.contentsMargins()
        usable_width = max(1, available_width - margins.left() - margins.right())
        column_width = self.card_width + self.card_spacing
        columns = max(1, (usable_width + self.card_spacing) // column_width)

        if columns == self.column_count and self.grid_layout.count() == len(self.cards):
            return

        self.column_count = columns
        while self.grid_layout.count():
            self.grid_layout.takeAt(0)

        for index, card in enumerate(self.cards):
            row = index // columns
            column = index % columns
            self.grid_layout.addWidget(card, row, column, Qt.AlignTop)


class TaskPage(QWidget):
    data_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)

        self.task_service = TaskService()
        self.expanded_task_card = None
        self.grid_sections = []

        self.init_ui()
        self.refresh_tasks()
        self.init_refresh_timer()

    def init_ui(self):
        main_layout = QVBoxLayout(self)

        title_label = QLabel("任务清单")
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
        dialog = TaskDialog(parent=self)

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

            self.data_changed.emit()

    def init_refresh_timer(self):
        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self.refresh_tasks)
        self.refresh_timer.start(60000)

    def refresh_tasks(self):
        self.clear_task_layout()
        self.expanded_task_card = None
        self.grid_sections = []

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
        QTimer.singleShot(0, self.update_grid_widths)

    def add_task_section(self, section_name, tasks):
        category_title = QLabel(section_name)
        category_title.setObjectName("CategoryTitle")
        self.task_layout.addWidget(category_title)

        category_frame = TaskGridSection()
        self.grid_sections.append(category_frame)
        category_frame.set_available_width(self.get_grid_width())

        for task in tasks:
            task_card = TaskCard(task)
            task_card.complete_requested.connect(self.complete_task)
            task_card.delete_requested.connect(self.delete_task)
            task_card.edit_requested.connect(self.open_edit_task_dialog)
            task_card.clicked.connect(self.toggle_task_card)
            category_frame.add_task_card(task_card)

        self.task_layout.addWidget(category_frame)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_grid_widths()

    def showEvent(self, event):
        super().showEvent(event)
        self.update_grid_widths()

    def get_grid_width(self):
        if not hasattr(self, "scroll_area"):
            return 0

        return max(1, self.scroll_area.viewport().width() - 8)

    def update_grid_widths(self):
        width = self.get_grid_width()
        for section in self.grid_sections:
            section.set_available_width(width)

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
        self.data_changed.emit()

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
            self.data_changed.emit()

    def delete_task(self, task_id):
        result = QMessageBox.question(
            self,
            "确认删除",
            "确定要删除这个任务吗？",
            QMessageBox.Yes | QMessageBox.No,
        )

        if result == QMessageBox.Yes:
            self.task_service.delete_task(task_id)
            self.data_changed.emit()
