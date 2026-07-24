from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QTimeEdit,
    QVBoxLayout,
)
from PySide6.QtCore import QTime

from app.models.plan import PlanLevel
from app.ui.priority_controls import connect_priority_controls, sync_priority_controls
from app.ui.dialog_style import apply_dialog_style
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
        self.init_ui()
        apply_dialog_style(self)
        self.load_task_data()
        self.refresh_parent_tasks()
        self.sync_priority_state()
        self.setMinimumWidth(430)
        self.adjustSize()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        self.title_input = QLineEdit()
        self.title_input.setPlaceholderText("请输入每日任务名称")
        self.title_input.returnPressed.connect(self.accept_dialog)

        self.minimal_action_input = QLineEdit()
        self.minimal_action_input.setPlaceholderText("例如：打开文档开始写")
        self.minimal_action_input.setMaxLength(12)
        self.minimal_action_input.returnPressed.connect(self.accept_dialog)

        self.description_input = QTextEdit()
        self.description_input.setPlaceholderText("请输入描述，可不填")
        self.description_input.setFixedHeight(82)

        self.important_checkbox = QCheckBox("重要")
        self.urgent_checkbox = QCheckBox("紧急")
        priority_layout = QHBoxLayout()
        priority_layout.addWidget(self.important_checkbox)
        priority_layout.addWidget(self.urgent_checkbox)
        priority_layout.addStretch()

        self.fixed_event_checkbox = QCheckBox("固定事件")
        self.fixed_time_input = QTimeEdit()
        self.fixed_time_input.setDisplayFormat("HH:mm")
        self.fixed_time_input.setTime(QTime(9, 0))
        self._priority_sync_callback = connect_priority_controls(
            self.important_checkbox,
            self.urgent_checkbox,
            self.fixed_event_checkbox,
            (self.fixed_time_input,),
        )

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
        layout.addWidget(QLabel("最小动作"))
        layout.addWidget(self.minimal_action_input)
        layout.addWidget(QLabel("描述"))
        layout.addWidget(self.description_input)
        layout.addLayout(priority_layout)
        fixed_time_layout = QHBoxLayout()
        fixed_time_layout.addWidget(self.fixed_event_checkbox)
        fixed_time_layout.addWidget(QLabel("固定时间"))
        fixed_time_layout.addWidget(self.fixed_time_input)
        fixed_time_layout.addStretch()
        layout.addLayout(fixed_time_layout)
        layout.addWidget(QLabel("父计划层级"))
        layout.addWidget(self.parent_level_combo)
        layout.addWidget(QLabel("父计划任务"))
        layout.addWidget(self.parent_task_combo)
        layout.addWidget(self.empty_hint_label)
        layout.addLayout(button_layout)

    def load_task_data(self):
        if self.task is None:
            return
        self.title_input.setText(self.task.title)
        self.description_input.setPlainText(self.task.description)
        self.minimal_action_input.setText(getattr(self.task, "minimal_action", "") or "")
        self.important_checkbox.setChecked(self.task.is_important)
        self.urgent_checkbox.setChecked(self.task.is_urgent)
        self.fixed_event_checkbox.setChecked(bool(self.task.fixed_time or self.task.scheduled_at))
        if self.task.fixed_time or self.task.scheduled_at:
            value = self.task.fixed_time or self.task.scheduled_at
            text = str(value)[11:16] if len(str(value)) >= 16 and str(value)[10] in {" ", "T"} else str(value)[:5]
            fixed_time = QTime.fromString(text, "HH:mm")
            if fixed_time.isValid():
                self.fixed_time_input.setTime(fixed_time)
        self.sync_priority_state()
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
        minimal_action = self.minimal_action_input.text().strip()
        if not minimal_action:
            QMessageBox.warning(self, "提示", "请填写最小动作")
            return
        if len(minimal_action) > 12:
            QMessageBox.warning(self, "提示", "最小动作不能超过12个字符")
            return
        if self.parent_task_combo.currentData() is None:
            QMessageBox.warning(self, "提示", "请选择一张具体父计划任务")
            return
        if self.fixed_event_checkbox.isChecked() and (
            self.important_checkbox.isChecked() or self.urgent_checkbox.isChecked()
        ):
            QMessageBox.warning(self, "提示", "固定事件不能同时紧急或重要")
            return
        self.accept()

    def get_task_data(self):
        fixed_time = None
        if self.fixed_event_checkbox.isChecked():
            fixed_time = self.fixed_time_input.time().toString("HH:mm:ss")
        return {
            "title": self.title_input.text().strip(),
            "description": self.description_input.toPlainText().strip(),
            "minimal_action": self.minimal_action_input.text().strip(),
            "parent_plan_task_id": self.parent_task_combo.currentData(),
            "scheduled_at": None,
            "fixed_time": fixed_time,
            "is_important": self.important_checkbox.isChecked(),
            "is_urgent": self.urgent_checkbox.isChecked(),
            "is_fixed_event": self.fixed_event_checkbox.isChecked(),
        }

    def sync_priority_state(self):
        sync_priority_controls(
            self.important_checkbox,
            self.urgent_checkbox,
            self.fixed_event_checkbox,
            (self.fixed_time_input,),
        )
