from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.models.plan import PLAN_LEVEL_LABELS, PLAN_LEVEL_ORDER, PlanLevel
from app.services.period_service import period_service
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
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)

        self.grid_layout = QGridLayout(self)
        self.grid_layout.setContentsMargins(8, 8, 8, 8)
        self.grid_layout.setHorizontalSpacing(self.card_spacing)
        self.grid_layout.setVerticalSpacing(self.card_spacing)
        self.grid_layout.setAlignment(Qt.AlignLeft | Qt.AlignTop)

    def clear_cards(self):
        self.cards = []
        self.column_count = 0
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def add_task_card(self, task_card):
        self.cards.append(task_card)
        self.reflow_cards()

    def set_available_width(self, width):
        if width <= 0:
            return
        self.available_width = width
        self.setFixedWidth(width)
        self.reflow_cards()

    def reflow_cards(self, force=False):
        available_width = max(1, self.available_width or self.width())
        margins = self.grid_layout.contentsMargins()
        usable_width = max(1, available_width - margins.left() - margins.right())
        columns = max(1, (usable_width + self.card_spacing) // (self.card_width + self.card_spacing))
        total_spacing = self.card_spacing * (columns - 1)
        actual_card_width = max(self.card_width, (usable_width - total_spacing) // columns)

        if (
            not force
            and columns == self.column_count
            and self.grid_layout.count() == len(self.cards)
            and getattr(self, "actual_card_width", None) == actual_card_width
        ):
            return

        self.column_count = columns
        self.actual_card_width = actual_card_width
        while self.grid_layout.count():
            self.grid_layout.takeAt(0)

        for index, card in enumerate(self.cards):
            card.setFixedWidth(actual_card_width)
            row = index // columns
            column = index % columns
            self.grid_layout.addWidget(card, row, column, Qt.AlignTop)

        self.grid_layout.invalidate()
        self.updateGeometry()


class PlanSection(QFrame):
    toggle_previous_requested = Signal(PlanLevel)
    add_task_requested = Signal(PlanLevel)
    complete_requested = Signal(int)
    delete_requested = Signal(int)
    edit_requested = Signal(int)
    card_clicked = Signal(object)

    def __init__(self, plan_level, parent=None):
        super().__init__(parent)
        self.plan_level = plan_level
        self.show_previous = False
        self.period = None
        self.setObjectName("PlanSection")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(10)

        self.title_label = QLabel(PLAN_LEVEL_LABELS[plan_level])
        self.title_label.setObjectName("CategoryTitle")
        self.title_label.setMinimumWidth(70)

        self.period_label = QLabel("")
        self.period_label.setObjectName("PeriodLabel")
        self.period_label.setMinimumWidth(260)
        self.period_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.period_label.setWordWrap(False)

        self.toggle_button = QPushButton("查看上期")
        self.toggle_button.setObjectName("SecondaryButton")
        self.toggle_button.setMinimumWidth(86)
        self.toggle_button.clicked.connect(lambda: self.toggle_previous_requested.emit(self.plan_level))

        self.add_button = QPushButton("+ 新增任务")
        self.add_button.setObjectName("PrimaryButton")
        self.add_button.setMinimumWidth(98)
        self.add_button.clicked.connect(lambda: self.add_task_requested.emit(self.plan_level))

        header_layout.addWidget(self.title_label, 0)
        header_layout.addWidget(self.period_label, 1)
        header_layout.addStretch(1)
        header_layout.addWidget(self.toggle_button, 0)
        header_layout.addWidget(self.add_button, 0)

        self.empty_label = QLabel("")
        self.empty_label.setObjectName("EmptyPlanLabel")
        self.empty_label.setAlignment(Qt.AlignCenter)
        self.empty_label.setVisible(False)

        self.grid = TaskGridSection()

        layout.addLayout(header_layout)
        layout.addWidget(self.empty_label)
        layout.addWidget(self.grid)

    def set_available_width(self, width):
        self.grid.set_available_width(max(1, width - 24))

    def set_previous_mode(self, enabled):
        self.show_previous = bool(enabled)

    def render(self, period, tasks):
        self.period = period
        self.period_label.setText(period.display_text.replace("\n", "  "))
        self.toggle_button.setText("返回本期" if self.show_previous else "查看上期")
        self.add_button.setVisible(not self.show_previous)
        self.add_button.setEnabled(not self.show_previous)
        self.grid.clear_cards()

        if not tasks:
            self.empty_label.setText("上一周期没有计划" if self.show_previous else "本周期暂无计划")
            self.empty_label.setVisible(True)
            self.grid.setVisible(False)
            return

        self.empty_label.setVisible(False)
        self.grid.setVisible(True)
        for task in tasks:
            task_card = TaskCard(task)
            task_card.complete_requested.connect(self.complete_requested)
            task_card.delete_requested.connect(self.delete_requested)
            task_card.edit_requested.connect(self.edit_requested)
            task_card.clicked.connect(self.card_clicked)
            self.grid.add_task_card(task_card)


class TaskPage(QWidget):
    data_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.task_service = TaskService()
        self.expanded_task_card = None
        self.sections = {}
        self.init_ui()
        self.refresh_tasks()
        self.init_refresh_timer()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(12)

        title_label = QLabel("五年计划")
        title_label.setObjectName("TitleLabel")

        refresh_button = QPushButton("刷新")
        refresh_button.setObjectName("SecondaryButton")
        refresh_button.clicked.connect(self.refresh_tasks)

        top_layout = QHBoxLayout()
        top_layout.addWidget(title_label)
        top_layout.addStretch()
        top_layout.addWidget(refresh_button)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        self.task_container = QWidget()
        self.task_layout = QVBoxLayout(self.task_container)
        self.task_layout.setAlignment(Qt.AlignTop)
        self.task_layout.setContentsMargins(0, 0, 0, 0)
        self.task_layout.setSpacing(12)

        for plan_level in PLAN_LEVEL_ORDER:
            section = PlanSection(plan_level)
            section.toggle_previous_requested.connect(self.toggle_previous_period)
            section.add_task_requested.connect(self.open_add_task_dialog)
            section.complete_requested.connect(self.complete_task)
            section.delete_requested.connect(self.delete_task)
            section.edit_requested.connect(self.open_edit_task_dialog)
            section.card_clicked.connect(self.toggle_task_card)
            self.sections[plan_level] = section
            self.task_layout.addWidget(section)

        self.task_layout.addStretch()
        self.scroll_area.setWidget(self.task_container)

        main_layout.addLayout(top_layout)
        main_layout.addWidget(self.scroll_area, 1)

        self.setStyleSheet("""
            QWidget {
                background-color: transparent;
            }

            QLabel#TitleLabel {
                font-size: 26px;
                font-weight: bold;
            }

            QLabel#CategoryTitle {
                font-size: 18px;
                font-weight: bold;
                margin-top: 4px;
                margin-bottom: 4px;
            }

            QLabel#PeriodLabel {
                color: #555555;
                font-size: 13px;
            }

            QLabel#EmptyPlanLabel {
                color: #777777;
                padding: 16px;
                border: 1px dashed #dddddd;
                border-radius: 8px;
            }

            QFrame#PlanSection {
                background-color: transparent;
                border: 1px solid #e5e7eb;
                border-radius: 12px;
            }

            QFrame#CategoryFrame {
                background-color: white;
                border-radius: 12px;
                padding: 8px;
            }

            QPushButton {
                padding: 8px 14px;
                border-radius: 8px;
                font-weight: bold;
            }

            QPushButton#PrimaryButton {
                background-color: #2d8cff;
                color: white;
                border: 1px solid #2d8cff;
            }

            QPushButton#PrimaryButton:hover {
                background-color: #1f6fd1;
            }

            QPushButton#SecondaryButton {
                background-color: #ffffff;
                color: #222222;
                border: 1px solid #cccccc;
            }

            QPushButton#SecondaryButton:hover {
                background-color: #eef2f7;
            }

            QScrollArea {
                border: none;
            }

            QScrollBar:vertical {
                width: 10px;
                background: transparent;
                margin: 4px 2px 4px 2px;
            }

            QScrollBar::handle:vertical {
                background: #d1d5db;
                border-radius: 5px;
                min-height: 40px;
            }

            QScrollBar::handle:vertical:hover {
                background: #9ca3af;
            }

            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {
                height: 0px;
                background: transparent;
            }

            QScrollBar::add-page:vertical,
            QScrollBar::sub-page:vertical {
                background: transparent;
            }

            QScrollBar:horizontal {
                height: 0px;
                background: transparent;
            }

            QScrollBar::handle:horizontal {
                background: transparent;
            }
        """)

    def init_refresh_timer(self):
        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self.refresh_tasks)
        self.refresh_timer.start(60000)

    def refresh_tasks(self):
        self.expanded_task_card = None
        for plan_level, section in self.sections.items():
            self.refresh_section(plan_level)
        QTimer.singleShot(0, self.update_grid_widths)

    def refresh_section(self, plan_level):
        section = self.sections[plan_level]
        if section.show_previous:
            period = period_service.previous_period(plan_level)
            tasks = self.task_service.get_previous_plan_tasks(plan_level)
        else:
            period = period_service.current_period(plan_level)
            tasks = self.task_service.get_current_plan_tasks(plan_level)
        section.render(period, tasks)

    def toggle_previous_period(self, plan_level):
        section = self.sections[plan_level]
        section.set_previous_mode(not section.show_previous)
        self.refresh_section(plan_level)
        QTimer.singleShot(0, self.update_grid_widths)

    def open_add_task_dialog(self, plan_level=None, parent=None):
        if plan_level is None:
            plan_level = PlanLevel.DAY
        dialog = TaskDialog(parent=parent or self, mode="plan", plan_level=plan_level)
        if dialog.exec():
            data = dialog.get_task_data()
            self.task_service.add_plan_task(
                title=data["title"],
                description=data["description"],
                plan_level=plan_level,
            )
            self.refresh_section(plan_level)
            self.data_changed.emit()

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
        for section in self.sections.values():
            section.set_available_width(width)

    def relayout_task_cards(self):
        for section in self.sections.values():
            section.grid.reflow_cards(force=True)
            section.updateGeometry()
        self.task_container.layout().invalidate()
        self.task_container.updateGeometry()
        self.scroll_area.widget().adjustSize()

    def toggle_task_card(self, task_card):
        if self.expanded_task_card is task_card:
            task_card.set_expanded(False)
            self.expanded_task_card = None
            self.relayout_task_cards()
            return

        if self.expanded_task_card is not None:
            self.expanded_task_card.set_expanded(False)

        task_card.set_expanded(True)
        self.expanded_task_card = task_card
        self.relayout_task_cards()

    def complete_task(self, task_id):
        task = self.task_service.get_task_by_id(task_id)
        self.task_service.complete_task(task_id)
        self.refresh_task_section(task)
        self.data_changed.emit()

    def open_edit_task_dialog(self, task_id):
        task = self.task_service.get_task_by_id(task_id)
        if task is None:
            return

        if task.plan_level:
            dialog = TaskDialog(task, self, mode="plan", plan_level=task.plan_level)
        else:
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
            self.refresh_task_section(task)
            self.data_changed.emit()

    def delete_task(self, task_id):
        task = self.task_service.get_task_by_id(task_id)
        message_box = QMessageBox(self)
        message_box.setWindowTitle("确认删除")
        message_box.setText("确定要删除这个任务吗？")
        if task is not None and task.plan_level and self.task_service.has_active_daily_tasks_for_parent(task_id):
            message_box.setText("该计划下存在每日任务，删除计划后关联每日任务将停止并归档。")
        message_box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        message_box.button(QMessageBox.Yes).setText("确定")
        message_box.button(QMessageBox.No).setText("取消")
        message_box.setDefaultButton(QMessageBox.No)
        message_box.setStyleSheet("""
            QMessageBox {
                background-color: #ffffff;
                color: #222222;
            }

            QMessageBox QLabel {
                background-color: transparent;
                color: #222222;
            }
        """)
        result = message_box.exec()

        if result == QMessageBox.Yes:
            self.task_service.delete_task(task_id)
            self.refresh_task_section(task)
            self.data_changed.emit()

    def refresh_task_section(self, task):
        if task is not None and task.plan_level:
            try:
                self.refresh_section(PlanLevel(task.plan_level))
                QTimer.singleShot(0, self.update_grid_widths)
                return
            except ValueError:
                pass
        self.refresh_tasks()
