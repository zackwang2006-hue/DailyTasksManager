from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)

from app.services.task_service import MIN_COMPLETION_NOTE_CHARS
from app.ui.dialog_style import apply_dialog_style


def effective_completion_note_length(text):
    return len("".join((text or "").split()))


class CompletionDialog(QDialog):
    def __init__(self, task_title, parent=None):
        super().__init__(parent)
        self.setWindowTitle("填写完成情况")
        self.setMinimumWidth(420)
        self.init_ui(task_title)
        apply_dialog_style(self)
        self.update_state()
        self.adjustSize()

    def init_ui(self, task_title):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        title_label = QLabel(f"任务：{task_title}")
        title_label.setObjectName("TaskTitle")
        title_label.setWordWrap(True)

        self.note_input = QTextEdit()
        self.note_input.setPlaceholderText("请简要记录本次完成情况，至少填写5个字")
        self.note_input.setFixedHeight(120)
        self.note_input.textChanged.connect(self.update_state)

        self.hint_label = QLabel()
        self.hint_label.setObjectName("HintLabel")

        button_layout = QHBoxLayout()
        self.cancel_button = QPushButton("取消")
        self.confirm_button = QPushButton("确认完成")
        self.confirm_button.setDefault(True)
        self.confirm_button.setAutoDefault(True)
        self.cancel_button.clicked.connect(self.reject)
        self.confirm_button.clicked.connect(self.accept_dialog)
        button_layout.addStretch()
        button_layout.addWidget(self.cancel_button)
        button_layout.addWidget(self.confirm_button)

        layout.addWidget(title_label)
        layout.addWidget(self.note_input)
        layout.addWidget(self.hint_label)
        layout.addLayout(button_layout)

    def completion_note(self):
        return self.note_input.toPlainText().strip()

    def update_state(self):
        length = effective_completion_note_length(self.note_input.toPlainText())
        missing = max(0, MIN_COMPLETION_NOTE_CHARS - length)
        self.confirm_button.setEnabled(missing == 0)
        if missing:
            self.hint_label.setText(f"还需输入 {missing} 个字")
        else:
            self.hint_label.setText("已满足最低字数要求")

    def accept_dialog(self):
        length = effective_completion_note_length(self.note_input.toPlainText())
        if length < MIN_COMPLETION_NOTE_CHARS:
            QMessageBox.warning(self, "提示", "完成情况至少填写5个有效字符")
            return
        self.accept()
