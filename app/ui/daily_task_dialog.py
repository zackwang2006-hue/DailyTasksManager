from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)

from app.models.plan import PlanLevel
from app.services.task_service import DAILY_TASK_PARENT_LEVELS, TaskService


DAILY_PARENT_LABELS = {
    PlanLevel.WEEK: "周计划",
    PlanLevel.MONTH: "月计划",
    PlanLevel.QUARTER: "季计划",
    PlanLevel.YEAR: "年计划",
    PlanLevel.FIVE_YEAR: "五年计划",
}


class DailyTaskDialog(QDialog):
    def __init__(self, task=None, parent=None, task_service=None):
        super().__init__(parent)
        self.task = task
        self.task_service = task_service or TaskService()
        self.parent_tasks = []

        self.setWindowTitle("编辑每日任务" if task else "新增每日任务")
        self.resize(430, 330)
        self.init_ui()
        self.load_task_data()
        self.refresh_parent_tasks()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        self.title_input = QLineEdit()
        self.title_input.setPlaceholderText("请输入每日任务名称")
        self.title_input.returnPressed.connect(self.accept_dialog)

        self.description_input = QTextEdit()
        self.description_input.setPlaceholderText("请输入描述，可不填")
        self.description_input.setFixedHeight(90)

        self.parent_level_combo = QComboBox()
        for level in DAILY_TASK_PARENT_LEVELS:
            self.parent_level_combo.addItem(DAILY_PARENT_LABELS[level], level.value)
        self.parent_level_combo.currentIndexChanged.connect(self.refresh_parent_tasks)

        self.parent_task_combo = QComboBox()
        self.empty_hint_label = QLabel("")
        self.empty_hint_label.setObjectName("HintLabel")
        self.empty_hint_label.setWordWrap(True)

        button_layout = QHBoxLayout()
        self.cancel_button = QPushButton("取消")
        self.save_button = QPushButton("保存")
        self.save_button.setDefault(True)
        self.save_button.setAutoDefault(True)
        self.cancel_button.clicked.connect(self.reject)
        self.save_button.clicked.connect(self.accept_dialog)
        button_layout.addStretch()
        button_layout.addWidget(self.cancel_button)
        button_layout.addWidget(self.save_button)

        layout.addWidget(QLabel("每日任务名称"))
        layout.addWidget(self.title_input)
        layout.addWidget(QLabel("描述"))
        layout.addWidget(self.description_input)
        layout.addWidget(QLabel("父计划层级"))
        layout.addWidget(self.parent_level_combo)
        layout.addWidget(QLabel("父计划任务"))
        layout.addWidget(self.parent_task_combo)
        layout.addWidget(self.empty_hint_label)
        layout.addLayout(button_layout)

        self.setStyleSheet("""
            QDialog {
                background-color: #ffffff;
                color: #222222;
            }

            QLabel {
                background-color: transparent;
                color: #222222;
            }

            QLabel#HintLabel {
                color: #777777;
            }

            QLineEdit, QTextEdit, QComboBox {
                padding: 6px;
                border: 1px solid #cccccc;
                border-radius: 6px;
                background-color: #ffffff;
                color: #222222;
                selection-background-color: #dbeafe;
                selection-color: #111111;
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
        """)

    def load_task_data(self):
        if self.task is None:
            return
        self.title_input.setText(self.task.title)
        self.description_input.setPlainText(self.task.description)
        if self.task.parent_plan_task_id:
            parent = self.task_service.get_task_by_id(self.task.parent_plan_task_id)
            if parent and parent.plan_level:
                index = self.parent_level_combo.findData(parent.plan_level)
                if index >= 0:
                    self.parent_level_combo.setCurrentIndex(index)

    def refresh_parent_tasks(self):
        level_value = self.parent_level_combo.currentData()
        self.parent_task_combo.clear()
        self.parent_tasks = []

        if not level_value:
            self.save_button.setEnabled(False)
            return

        self.parent_tasks = self.task_service.get_available_parent_plan_tasks(level_value)
        for task in self.parent_tasks:
            self.parent_task_combo.addItem(task.title, task.task_id)

        has_parent_tasks = bool(self.parent_tasks)
        self.parent_task_combo.setEnabled(has_parent_tasks)
        self.save_button.setEnabled(has_parent_tasks)
        if has_parent_tasks:
            self.empty_hint_label.setText("")
            if self.task is not None and self.task.parent_plan_task_id:
                index = self.parent_task_combo.findData(self.task.parent_plan_task_id)
                if index >= 0:
                    self.parent_task_combo.setCurrentIndex(index)
        else:
            self.parent_task_combo.addItem("暂无可用父计划任务", None)
            self.empty_hint_label.setText("请先在当前周期创建对应计划，再新增每日任务。")

    def accept_dialog(self):
        if not self.title_input.text().strip():
            QMessageBox.warning(self, "提示", "每日任务名称不能为空")
            return
        if self.parent_task_combo.currentData() is None:
            QMessageBox.warning(self, "提示", "请选择一张具体父计划任务")
            return
        self.accept()

    def get_task_data(self):
        return {
            "title": self.title_input.text().strip(),
            "description": self.description_input.toPlainText().strip(),
            "parent_plan_task_id": self.parent_task_combo.currentData(),
        }
