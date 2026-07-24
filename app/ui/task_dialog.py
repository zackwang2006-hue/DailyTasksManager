from PySide6.QtWidgets import (
    QCalendarWidget,
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QTextEdit,
    QComboBox,
    QDateEdit,
    QDateTimeEdit,
    QTimeEdit,
    QCheckBox,
    QPushButton,
    QMessageBox,
)
from PySide6.QtCore import QDate, QDateTime, QTime, Qt
from PySide6.QtGui import QColor, QPen

from app.config import TASK_CATEGORIES
from app.models.plan import PlanLevel
from app.ui.priority_controls import connect_priority_controls, sync_priority_controls
from app.ui.dialog_style import apply_dialog_style
from app.utils.time_utils import get_daily_default_deadline


class CurrentMonthCalendar(QCalendarWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._shown_year = self.yearShown()
        self._shown_month = self.monthShown()
        self._last_valid_date = self.selectedDate()
        self._restoring_selection = False
        self.currentPageChanged.connect(self.on_current_page_changed)
        self.selectionChanged.connect(self.keep_selection_in_current_month)

    def on_current_page_changed(self, year, month):
        self._shown_year = year
        self._shown_month = month
        self.updateCells()

    def is_in_current_page(self, date):
        return date.year() == self._shown_year and date.month() == self._shown_month

    def keep_selection_in_current_month(self):
        if self._restoring_selection:
            return

        selected_date = self.selectedDate()
        if self.is_in_current_page(selected_date):
            self._last_valid_date = selected_date
            return

        self._restoring_selection = True
        self.setSelectedDate(self._last_valid_date)
        self._restoring_selection = False

    def paintCell(self, painter, rect, date):
        if self.is_in_current_page(date):
            super().paintCell(painter, rect, date)
            return

        painter.save()
        painter.fillRect(rect, QColor("#f3f4f6"))
        painter.setPen(QPen(QColor("#b6bcc6")))
        painter.drawText(rect, Qt.AlignCenter, str(date.day()))
        painter.restore()


class TaskDialog(QDialog):
    def __init__(self, task=None, parent=None, mode="legacy", plan_level=None):
        super().__init__(parent)

        self.task = task
        self.mode = mode
        self.plan_level = self.normalize_plan_level(plan_level or getattr(task, "plan_level", None))
        self._applying_deadline_default = False
        self._deadline_manually_changed = False
        self.setWindowTitle("编辑任务" if task else "新增任务")

        self.init_ui()
        apply_dialog_style(self)
        self.load_task_data()
        self.update_ddl_rule()
        self.setMinimumWidth(420)
        self.adjustSize()

    def init_ui(self):
        layout = QVBoxLayout(self)

        self.title_input = QLineEdit()
        self.title_input.setPlaceholderText("请输入任务标题")

        # 在标题输入框里按回车，直接确认新增任务
        self.title_input.returnPressed.connect(self.accept_dialog)

        self.minimal_action_label = QLabel("最小动作")
        self.minimal_action_input = QLineEdit()
        self.minimal_action_input.setPlaceholderText("例如：打开文档开始写")
        self.minimal_action_input.setMaxLength(12)
        self.minimal_action_input.returnPressed.connect(self.accept_dialog)

        self.description_input = QTextEdit()
        self.description_input.setPlaceholderText("请输入任务描述，可不填")
        self.description_input.setFixedHeight(105)

        self.category_combo = QComboBox()
        self.category_combo.addItem("请选择任务类型", None)

        for key, name in TASK_CATEGORIES.items():
            self.category_combo.addItem(name, key)

        self.category_combo.currentIndexChanged.connect(self.on_category_changed)

        self.is_timed_checkbox = QCheckBox("这是固定事件")
        self.is_timed_checkbox.hide()
        self.is_timed_checkbox.stateChanged.connect(self.update_ddl_rule)

        self.important_checkbox = QCheckBox("重要")
        self.urgent_checkbox = QCheckBox("紧急")
        self.fixed_event_checkbox = QCheckBox("固定事件")

        self.scheduled_date_label = QLabel("固定日期")
        self.scheduled_date_input = QDateEdit()
        self.scheduled_date_input.setCalendarPopup(True)
        self.scheduled_date_input.setCalendarWidget(CurrentMonthCalendar(self.scheduled_date_input))
        self.scheduled_date_input.setDate(QDate.currentDate().addDays(1))
        self.scheduled_date_input.setDisplayFormat("yyyy-MM-dd")

        self.scheduled_time_label = QLabel("固定时间")
        self.scheduled_time_input = QTimeEdit()
        self.scheduled_time_input.setTime(QTime(23, 59))
        self.scheduled_time_input.setDisplayFormat("HH:mm")

        self.use_ddl_checkbox = QCheckBox("设置 DDL")
        self.use_ddl_checkbox.setChecked(False)

        self.ddl_input = QDateEdit()
        self.ddl_input.setCalendarPopup(True)
        self.ddl_input.setCalendarWidget(CurrentMonthCalendar(self.ddl_input))
        self.ddl_input.setDate(QDate.currentDate().addDays(1))
        self.ddl_input.setDisplayFormat("yyyy-MM-dd")

        self.ddl_datetime_input = QDateTimeEdit()
        self.ddl_datetime_input.setCalendarPopup(True)
        self.ddl_datetime_input.setCalendarWidget(CurrentMonthCalendar(self.ddl_datetime_input))
        self.ddl_datetime_input.setDate(QDate.currentDate().addDays(1))
        self.ddl_datetime_input.setTime(QTime(23, 59))
        self.ddl_datetime_input.setDisplayFormat("yyyy-MM-dd HH:mm")
        self.ddl_datetime_input.dateTimeChanged.connect(self.on_deadline_changed)
        self.apply_calendar_style()

        self.use_ddl_checkbox.stateChanged.connect(self.toggle_ddl_input)
        self._priority_sync_callback = connect_priority_controls(
            self.important_checkbox,
            self.urgent_checkbox,
            self.fixed_event_checkbox,
            (self.scheduled_time_input,),
        )

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

        self.title_label = QLabel("任务标题")
        self.description_label = QLabel("任务描述")
        self.category_label = QLabel("任务分类")

        layout.addWidget(self.title_label)
        layout.addWidget(self.title_input)
        layout.addWidget(self.minimal_action_label)
        layout.addWidget(self.minimal_action_input)

        layout.addWidget(self.description_label)
        layout.addWidget(self.description_input)

        layout.addWidget(self.category_label)
        layout.addWidget(self.category_combo)

        priority_layout = QHBoxLayout()
        priority_layout.addWidget(self.important_checkbox)
        priority_layout.addWidget(self.urgent_checkbox)
        priority_layout.addStretch()
        layout.addLayout(priority_layout)
        layout.addWidget(self.fixed_event_checkbox)

        layout.addWidget(self.is_timed_checkbox)
        layout.addWidget(self.scheduled_date_label)
        layout.addWidget(self.scheduled_date_input)
        layout.addWidget(self.scheduled_time_label)
        layout.addWidget(self.scheduled_time_input)

        layout.addWidget(self.use_ddl_checkbox)
        layout.addWidget(self.ddl_datetime_input)
        layout.addWidget(self.ddl_input)
        layout.addWidget(self.ddl_rule_label)

        layout.addLayout(button_layout)

    def apply_calendar_style(self):
        calendar_style = """
            QCalendarWidget {
                background-color: #ffffff;
                color: #222222;
            }

            QCalendarWidget QWidget#qt_calendar_navigationbar {
                background-color: #f0f4f8;
                color: #222222;
            }

            QCalendarWidget QToolButton {
                background-color: transparent;
                color: #222222;
                border: none;
                padding: 4px 8px;
                font-weight: bold;
            }

            QCalendarWidget QToolButton:hover {
                background-color: #dbeafe;
                border-radius: 4px;
            }

            QCalendarWidget QMenu {
                background-color: #ffffff;
                color: #222222;
                border: 1px solid #cccccc;
            }

            QCalendarWidget QSpinBox {
                background-color: #ffffff;
                color: #222222;
                border: 1px solid #cccccc;
                selection-background-color: #dbeafe;
                selection-color: #111111;
            }

            QCalendarWidget QAbstractItemView {
                background-color: #ffffff;
                color: #222222;
                selection-background-color: #2d8cff;
                selection-color: #ffffff;
                alternate-background-color: #ffffff;
            }

            QCalendarWidget QHeaderView::section {
                background-color: #f8fafc;
                color: #222222;
                border: none;
                padding: 4px;
            }
        """

        for date_input in (
            self.scheduled_date_input,
            self.ddl_input,
            self.ddl_datetime_input,
        ):
            date_input.calendarWidget().setStyleSheet("")

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

    def on_deadline_changed(self):
        if not self._applying_deadline_default:
            self._deadline_manually_changed = True

    def set_deadline_datetime(self, q_datetime):
        self._applying_deadline_default = True
        self.ddl_datetime_input.setDateTime(q_datetime)
        self._applying_deadline_default = False

    def set_daily_default_deadline(self):
        default_deadline = get_daily_default_deadline()
        self.set_deadline_datetime(
            QDateTime(
                QDate(default_deadline.year, default_deadline.month, default_deadline.day),
                QTime(default_deadline.hour, default_deadline.minute, default_deadline.second),
            )
        )

    def set_short_default_deadline(self):
        self.set_deadline_datetime(
            QDateTime(QDate.currentDate().addDays(1), QTime(23, 59))
        )

    def on_category_changed(self):
        category = self.category_combo.currentData()
        if self.task is None:
            if category == "daily" and not self._deadline_manually_changed:
                self.set_daily_default_deadline()
            elif category == "short":
                self.set_short_default_deadline()
        self.update_ddl_rule()

    def update_ddl_rule(self):
        priority_enabled = self.priority_controls_enabled()
        minimal_action_enabled = self.minimal_action_enabled()
        self.minimal_action_label.setVisible(minimal_action_enabled)
        self.minimal_action_input.setVisible(minimal_action_enabled)
        for widget in (
            self.important_checkbox,
            self.urgent_checkbox,
            self.fixed_event_checkbox,
        ):
            widget.setVisible(priority_enabled)
        if not priority_enabled:
            self.important_checkbox.setChecked(False)
            self.urgent_checkbox.setChecked(False)
            self.fixed_event_checkbox.setChecked(False)
        sync_priority_controls(
            self.important_checkbox,
            self.urgent_checkbox,
            self.fixed_event_checkbox,
            (self.scheduled_time_input,),
        )

        if self.is_plan_mode():
            self.category_label.setVisible(False)
            self.category_combo.setVisible(False)
            self.is_timed_checkbox.setVisible(False)
            self.scheduled_date_label.setText("固定日期")
            self.scheduled_time_label.setText("固定时间")
            self.scheduled_date_label.setVisible(False)
            self.scheduled_date_input.setVisible(False)
            self.scheduled_time_label.setVisible(priority_enabled)
            self.scheduled_time_input.setVisible(priority_enabled)
            self.use_ddl_checkbox.setVisible(False)
            self.ddl_input.setVisible(False)
            self.ddl_datetime_input.setVisible(False)
            self.ddl_rule_label.setVisible(False)
            return

        category = self.category_combo.currentData()
        is_timed = category == "timed"

        self.scheduled_date_label.setText("固定日期")
        self.scheduled_time_label.setText("固定时间")
        self.scheduled_date_label.setVisible(is_timed)
        self.scheduled_date_input.setVisible(is_timed)
        self.scheduled_time_label.setVisible(is_timed or priority_enabled)
        self.scheduled_time_input.setVisible(is_timed or priority_enabled)
        self.use_ddl_checkbox.setVisible(False)
        self.ddl_input.setVisible(False)
        self.ddl_datetime_input.setVisible(False)
        self.ddl_rule_label.setText("")

        if is_timed:
            self.scheduled_date_input.setEnabled(True)
            self.scheduled_time_input.setEnabled(True)
            self.use_ddl_checkbox.setChecked(False)
            self.use_ddl_checkbox.setEnabled(False)
            self.ddl_input.setEnabled(False)
            self.ddl_datetime_input.setEnabled(False)
            self.ddl_rule_label.setText("固定事件使用具体日期和时间")
            return

        if category is None:
            self.use_ddl_checkbox.setEnabled(False)
            self.ddl_input.setEnabled(False)
            self.ddl_datetime_input.setEnabled(False)
            return

        if category == "short":
            # 短期任务：强制有分钟级 DDL
            self.use_ddl_checkbox.setChecked(True)
            self.use_ddl_checkbox.setEnabled(False)
            self.ddl_datetime_input.setVisible(True)
            self.ddl_datetime_input.setEnabled(True)
            self.ddl_rule_label.setText("短期任务必须设置精确到分钟的 DDL")

        elif category == "long":
            # 长期任务：强制有日期级 DDL
            self.use_ddl_checkbox.setChecked(True)
            self.use_ddl_checkbox.setEnabled(False)
            self.ddl_input.setVisible(True)
            self.ddl_input.setEnabled(True)
            self.ddl_rule_label.setText("长期任务必须设置日期级 DDL")

        elif category == "daily":
            # 每日任务：默认截止到当天 23:59:59，按本地自然日结算。
            self.use_ddl_checkbox.setChecked(False)
            self.use_ddl_checkbox.setEnabled(False)
            self.ddl_datetime_input.setVisible(True)
            self.ddl_datetime_input.setEnabled(True)
            if self.task is None and not self._deadline_manually_changed:
                self.set_daily_default_deadline()
            self.ddl_rule_label.setText("每日任务默认截止到当天 23:59:59")

        elif category == "extra":
            # 附加任务：可选 DDL
            self.use_ddl_checkbox.setVisible(True)
            self.use_ddl_checkbox.setEnabled(True)
            self.ddl_input.setVisible(self.use_ddl_checkbox.isChecked())
            self.ddl_input.setEnabled(self.use_ddl_checkbox.isChecked())
            self.ddl_rule_label.setText("附加任务可选择是否设置 DDL")

        else:
            self.use_ddl_checkbox.setEnabled(True)
            self.ddl_input.setEnabled(self.use_ddl_checkbox.isChecked())
            self.ddl_rule_label.setText("")

    def toggle_ddl_input(self):
        category = self.category_combo.currentData()

        if category == "timed":
            self.use_ddl_checkbox.setChecked(False)
            self.ddl_input.setEnabled(False)
            return

        # 短期、长期强制开启
        if category in ("short", "long"):
            self.use_ddl_checkbox.setChecked(True)
            self.ddl_input.setEnabled(True)
            return

        # 每日任务强制关闭
        if category == "daily":
            self.use_ddl_checkbox.setChecked(False)
            self.ddl_datetime_input.setEnabled(True)
            return

        # 附加任务自由开关
        self.ddl_input.setVisible(self.use_ddl_checkbox.isChecked())
        self.ddl_input.setEnabled(self.use_ddl_checkbox.isChecked())

    def priority_controls_enabled(self):
        if self.is_plan_mode():
            return self.plan_level == PlanLevel.DAY
        return self.category_combo.currentData() == "daily"

    def minimal_action_enabled(self):
        return self.is_plan_mode() and self.plan_level == PlanLevel.DAY

    def accept_dialog(self):
        title = self.title_input.text().strip()

        if not title:
            QMessageBox.warning(self, "提示", "任务标题不能为空")
            return

        if not self.is_plan_mode() and self.category_combo.currentData() is None:
            QMessageBox.warning(self, "提示", "请选择任务类型")
            return
        if self.minimal_action_input.isVisible():
            minimal_action = self.minimal_action_input.text().strip()
            if not minimal_action:
                QMessageBox.warning(self, "提示", "请填写最小动作")
                return
            if len(minimal_action) > 12:
                QMessageBox.warning(self, "提示", "最小动作不能超过12个字符")
                return
        if self.fixed_event_checkbox.isVisible() and self.fixed_event_checkbox.isChecked():
            if self.important_checkbox.isChecked() or self.urgent_checkbox.isChecked():
                QMessageBox.warning(self, "提示", "固定事件不能同时紧急或重要")
                return

        self.accept()

    def get_task_data(self):
        title = self.title_input.text().strip()
        description = self.description_input.toPlainText().strip()
        if self.is_plan_mode():
            scheduled_at = None
            fixed_time = None
            if self.priority_controls_enabled() and self.fixed_event_checkbox.isChecked():
                fixed_time = self.scheduled_time_input.time().toString("HH:mm:ss")
            return {
                "title": title,
                "description": description,
                "minimal_action": self.minimal_action_input.text().strip(),
                "category": "plan",
                "ddl": None,
                "task_type": "normal",
                "scheduled_at": scheduled_at,
                "fixed_time": fixed_time,
                "plan_level": self.plan_level.value if self.plan_level else None,
                "is_important": self.important_checkbox.isChecked(),
                "is_urgent": self.urgent_checkbox.isChecked(),
                "is_fixed_event": self.fixed_event_checkbox.isChecked(),
            }

        category = self.category_combo.currentData()
        is_timed = category == "timed"

        if is_timed:
            scheduled_date = self.scheduled_date_input.date().toString("yyyy-MM-dd")
            scheduled_time = self.scheduled_time_input.time().toString("HH:mm:ss")

            return {
                "title": title,
                "description": description,
                "category": "timed",
                "ddl": None,
                "task_type": "timed",
                "scheduled_at": f"{scheduled_date} {scheduled_time}",
                "is_important": False,
                "is_urgent": False,
                "is_fixed_event": True,
            }

        if category == "short":
            ddl = self.ddl_datetime_input.dateTime().toString("yyyy-MM-dd HH:mm:ss")
        elif category == "long":
            ddl = self.ddl_input.date().toString("yyyy-MM-dd")
        elif category == "daily":
            ddl = self.ddl_datetime_input.dateTime().toString("yyyy-MM-dd HH:mm:ss")
            if not ddl:
                ddl = get_daily_default_deadline().strftime("%Y-%m-%d %H:%M:%S")
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
            "fixed_time": (
                self.scheduled_time_input.time().toString("HH:mm:ss")
                if category == "daily" and self.fixed_event_checkbox.isChecked()
                else None
            ),
            "is_important": self.important_checkbox.isChecked() if category == "daily" else False,
            "is_urgent": self.urgent_checkbox.isChecked() if category == "daily" else False,
            "is_fixed_event": self.fixed_event_checkbox.isChecked() if category == "daily" else False,
        }

    def load_task_data(self):
        if self.task is None:
            return

        self.title_input.setText(self.task.title)
        self.description_input.setPlainText(self.task.description)
        self.minimal_action_input.setText(getattr(self.task, "minimal_action", "") or "")

        if self.is_plan_mode():
            self.important_checkbox.setChecked(self.task.is_important)
            self.urgent_checkbox.setChecked(self.task.is_urgent)
            self.fixed_event_checkbox.setChecked(bool(self.task.fixed_time or self.task.scheduled_at))
            self.load_fixed_time(self.task.fixed_time or self.task.scheduled_at)
            self.update_ddl_rule()
            return

        category = "timed" if self.task.task_type == "timed" else self.task.category
        index = self.category_combo.findData(category)
        if index >= 0:
            self.category_combo.setCurrentIndex(index)
        if category == "daily":
            self.important_checkbox.setChecked(self.task.is_important)
            self.urgent_checkbox.setChecked(self.task.is_urgent)
            self.fixed_event_checkbox.setChecked(bool(self.task.fixed_time or self.task.scheduled_at))

        if self.task.ddl:
            ddl_datetime = QDateTime.fromString(self.task.ddl, "yyyy-MM-dd HH:mm:ss")
            if ddl_datetime.isValid():
                self.set_deadline_datetime(ddl_datetime)

            try:
                ddl_date = QDate.fromString(self.task.ddl[:10], "yyyy-MM-dd")
                if ddl_date.isValid():
                    self.ddl_input.setDate(ddl_date)
            except TypeError:
                pass

            if category == "extra":
                self.use_ddl_checkbox.setChecked(True)
        elif category == "daily":
            self.set_daily_default_deadline()

        if self.task.fixed_time or self.task.scheduled_at:
            self.load_scheduled_datetime(self.task.scheduled_at)
            self.load_fixed_time(self.task.fixed_time or self.task.scheduled_at)
            if category == "daily":
                self.fixed_event_checkbox.setChecked(True)
                self.update_ddl_rule()

    def load_scheduled_datetime(self, value):
        try:
            scheduled_date = QDate.fromString(value[:10], "yyyy-MM-dd")
            scheduled_time = QTime.fromString(value[11:16], "HH:mm")
            if scheduled_date.isValid():
                self.scheduled_date_input.setDate(scheduled_date)
            if scheduled_time.isValid():
                self.scheduled_time_input.setTime(scheduled_time)
        except TypeError:
            pass

    def load_fixed_time(self, value):
        if not value:
            return
        text = str(value)
        if len(text) >= 19 and text[10] in {" ", "T"}:
            text = text[11:16]
        else:
            text = text[:5]
        fixed_time = QTime.fromString(text, "HH:mm")
        if fixed_time.isValid():
            self.scheduled_time_input.setTime(fixed_time)
    def is_plan_mode(self):
        return self.mode == "plan"

    def normalize_plan_level(self, plan_level):
        if plan_level is None:
            return None
        if isinstance(plan_level, PlanLevel):
            return plan_level
        return PlanLevel(str(plan_level))
