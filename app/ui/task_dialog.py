from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QTextEdit,
    QComboBox,
    QDateEdit,
    QCheckBox,
    QPushButton,
    QMessageBox,
)
from PySide6.QtCore import QDate

from app.config import TASK_CATEGORIES


class TaskDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle("新增任务")
        self.resize(420, 360)

        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        self.title_input = QLineEdit()
        self.title_input.setPlaceholderText("请输入任务标题")

        self.description_input = QTextEdit()
        self.description_input.setPlaceholderText("请输入任务描述，可不填")

        self.category_combo = QComboBox()

        for key, name in TASK_CATEGORIES.items():
            self.category_combo.addItem(name, key)

        self.use_ddl_checkbox = QCheckBox("设置 DDL")
        self.use_ddl_checkbox.setChecked(True)

        self.ddl_input = QDateEdit()
        self.ddl_input.setCalendarPopup(True)
        self.ddl_input.setDate(QDate.currentDate().addDays(1))
        self.ddl_input.setDisplayFormat("yyyy-MM-dd")

        self.use_ddl_checkbox.stateChanged.connect(self.toggle_ddl_input)

        button_layout = QHBoxLayout()

        confirm_button = QPushButton("确定")
        cancel_button = QPushButton("取消")

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

        layout.addWidget(self.use_ddl_checkbox)
        layout.addWidget(self.ddl_input)

        layout.addLayout(button_layout)

        self.setStyleSheet("""
            QLineEdit, QTextEdit, QComboBox, QDateEdit {
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

    def toggle_ddl_input(self):
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

        if self.use_ddl_checkbox.isChecked():
            ddl = self.ddl_input.date().toString("yyyy-MM-dd")
        else:
            ddl = None

        return {
            "title": title,
            "description": description,
            "category": category,
            "ddl": ddl,
        }