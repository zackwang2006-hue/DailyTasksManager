from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QTextEdit,
    QComboBox,
    QDateEdit,
    QTimeEdit,
    QCheckBox,
    QPushButton,
    QMessageBox,
)
from PySide6.QtCore import QDate, QTime, Qt

from app.config import TASK_CATEGORIES


class TaskDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle("新增任务")
        self.resize(420, 460)

        self.init_ui()
        self.update_ddl_rule()

    def init_ui(self):
        layout = QVBoxLayout(self)

        self.title_input = QLineEdit()
        self.title_input.setPlaceholderText("请输入任务标题")

        # 在标题输入框里按回车，直接确认新增任务
        self.title_input.returnPressed.connect(self.accept_dialog)

        self.description_input = QTextEdit()
        self.description_input.setPlaceholderText("请输入任务描述，可不填")

        self.category_combo = QComboBox()

        for key, name in TASK_CATEGORIES.items():
            self.category_combo.addItem(name, key)

        self.category_combo.currentIndexChanged.connect(self.update_ddl_rule)

        self.is_timed_checkbox = QCheckBox("这是定时任务")
        self.is_timed_checkbox.stateChanged.connect(self.update_ddl_rule)

        self.scheduled_date_label = QLabel("定时日期")
        self.scheduled_date_input = QDateEdit()
        self.scheduled_date_input.setCalendarPopup(True)
        self.scheduled_date_input.setDate(QDate.currentDate().addDays(1))
        self.scheduled_date_input.setDisplayFormat("yyyy-MM-dd")

        self.scheduled_time_label = QLabel("定时时间")
        self.scheduled_time_input = QTimeEdit()
        current_time = QTime.currentTime()
        self.scheduled_time_input.setTime(QTime(current_time.hour(), current_time.minute()))
        self.scheduled_time_input.setDisplayFormat("HH:mm")

        self.use_ddl_checkbox = QCheckBox("设置 DDL")
        self.use_ddl_checkbox.setChecked(True)

        self.ddl_input = QDateEdit()
        self.ddl_input.setCalendarPopup(True)
        self.ddl_input.setDate(QDate.currentDate().addDays(1))
        self.ddl_input.setDisplayFormat("yyyy-MM-dd")

        self.use_ddl_checkbox.stateChanged.connect(self.toggle_ddl_input)

        self.ddl_rule_label = QLabel()
        self.ddl_rule_label.setStyleSheet("color: gray;")

        button_layout = QHBoxLayout()

        confirm_button = QPushButton("确定")
        cancel_button = QPushButton("取消")

        # 设置默认按钮：弹窗中按回车会触发确定
        confirm_button.setDefault(True)
        confirm_button.setAutoDefault(True)

        confirm_button.clicked.connect(self.accept_dialog)
        cancel_button.clicked.connect(self.reject)

        button_layout.addStretch()
        button_layout.addWidget(cancel_button)
        button_layout.addWidget(confirm_button)

        layout.addWidget(QLabel("任务标题"))
        layout.addWidget(self.title_input)

        layout.addWidget(QLabel("任务描述"))
        layout.addWidget(self.description_input)

        layout.addWidget(QLabel("任务分类"))
        layout.addWidget(self.category_combo)

        layout.addWidget(self.is_timed_checkbox)
        layout.addWidget(self.scheduled_date_label)
        layout.addWidget(self.scheduled_date_input)
        layout.addWidget(self.scheduled_time_label)
        layout.addWidget(self.scheduled_time_input)

        layout.addWidget(self.use_ddl_checkbox)
        layout.addWidget(self.ddl_input)
        layout.addWidget(self.ddl_rule_label)

        layout.addLayout(button_layout)

        self.setStyleSheet("""
            QLineEdit, QTextEdit, QComboBox, QDateEdit, QTimeEdit {
                padding: 6px;
                border: 1px solid #cccccc;
                border-radius: 6px;
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

    def keyPressEvent(self, event):
        """
        处理回车键确认。

        注意：
        QTextEdit 默认按回车是换行。
        所以当焦点在任务描述框里时，不拦截回车。
        """
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            if self.focusWidget() == self.description_input:
                super().keyPressEvent(event)
                return

            self.accept_dialog()
            return

        super().keyPressEvent(event)

    def update_ddl_rule(self):
        is_timed = self.is_timed_checkbox.isChecked()
        category = self.category_combo.currentData()

        self.scheduled_date_label.setVisible(is_timed)
        self.scheduled_date_input.setVisible(is_timed)
        self.scheduled_time_label.setVisible(is_timed)
        self.scheduled_time_input.setVisible(is_timed)

        if is_timed:
            self.use_ddl_checkbox.setChecked(False)
            self.use_ddl_checkbox.setEnabled(False)
            self.ddl_input.setEnabled(False)
            self.ddl_rule_label.setText("定时任务使用具体日期和时间，不使用普通 DDL")
            return

        if category in ("short", "long"):
            # 短期任务、长期任务：强制有 DDL
            self.use_ddl_checkbox.setChecked(True)
            self.use_ddl_checkbox.setEnabled(False)
            self.ddl_input.setEnabled(True)
            self.ddl_rule_label.setText("当前分类必须设置 DDL")

        elif category == "daily":
            # 每日任务：强制无 DDL
            self.use_ddl_checkbox.setChecked(False)
            self.use_ddl_checkbox.setEnabled(False)
            self.ddl_input.setEnabled(False)
            self.ddl_rule_label.setText("每日任务固定无 DDL")

        elif category == "extra":
            # 附加任务：可选 DDL
            self.use_ddl_checkbox.setEnabled(True)
            self.use_ddl_checkbox.setChecked(False)
            self.ddl_input.setEnabled(False)
            self.ddl_rule_label.setText("附加任务可选择是否设置 DDL")

        else:
            self.use_ddl_checkbox.setEnabled(True)
            self.ddl_input.setEnabled(self.use_ddl_checkbox.isChecked())
            self.ddl_rule_label.setText("")

    def toggle_ddl_input(self):
        if self.is_timed_checkbox.isChecked():
            self.use_ddl_checkbox.setChecked(False)
            self.ddl_input.setEnabled(False)
            return

        category = self.category_combo.currentData()

        # 短期、长期强制开启
        if category in ("short", "long"):
            self.use_ddl_checkbox.setChecked(True)
            self.ddl_input.setEnabled(True)
            return

        # 每日任务强制关闭
        if category == "daily":
            self.use_ddl_checkbox.setChecked(False)
            self.ddl_input.setEnabled(False)
            return

        # 附加任务自由开关
        self.ddl_input.setEnabled(self.use_ddl_checkbox.isChecked())

    def accept_dialog(self):
        title = self.title_input.text().strip()

        if not title:
            QMessageBox.warning(self, "提示", "任务标题不能为空")
            return

        self.accept()

    def get_task_data(self):
        title = self.title_input.text().strip()
        description = self.description_input.toPlainText().strip()
        category = self.category_combo.currentData()
        is_timed = self.is_timed_checkbox.isChecked()

        if is_timed:
            scheduled_date = self.scheduled_date_input.date().toString("yyyy-MM-dd")
            scheduled_time = self.scheduled_time_input.time().toString("HH:mm:ss")

            return {
                "title": title,
                "description": description,
                "category": category,
                "ddl": None,
                "task_type": "timed",
                "scheduled_at": f"{scheduled_date} {scheduled_time}",
            }

        if category in ("short", "long"):
            ddl = self.ddl_input.date().toString("yyyy-MM-dd")
        elif category == "daily":
            ddl = None
        elif category == "extra":
            if self.use_ddl_checkbox.isChecked():
                ddl = self.ddl_input.date().toString("yyyy-MM-dd")
            else:
                ddl = None
        else:
            ddl = None

        return {
            "title": title,
            "description": description,
            "category": category,
            "ddl": ddl,
            "task_type": "daily" if category == "daily" else "normal",
            "scheduled_at": None,
        }
