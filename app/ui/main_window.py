from PySide6.QtCore import QSettings
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.config import APP_ICON_PATH, APP_NAME, WINDOW_HEIGHT, WINDOW_WIDTH
from app.ui.checkin_page import CheckinPage
from app.ui.floating_task_window import FloatingTaskWindow
from app.ui.history_page import HistoryPage
from app.ui.system_tray import SystemTrayManager
from app.ui.task_page import TaskPage
from app.utils.startup_manager import (
    disable_startup,
    enable_startup,
    get_last_error_message,
    get_last_error_type,
    is_startup_enabled,
    request_elevated_startup_change,
    wait_for_startup_state,
)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle(APP_NAME)
        self.resize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.settings = QSettings(APP_NAME, "MainWindow")
        self.force_exit = False

        if APP_ICON_PATH.exists():
            self.setWindowIcon(QIcon(str(APP_ICON_PATH)))

        self.init_ui()
        self.apply_global_style()
        self.init_floating_window()
        self.init_tray()

    def init_ui(self):
        self.tab_widget = QTabWidget()

        self.task_page = TaskPage(self)
        self.history_page = HistoryPage(self)
        self.checkin_page = CheckinPage(self)
        self.settings_page = self.create_settings_page()

        self.task_page.data_changed.connect(self.refresh_all)
        self.checkin_page.data_changed.connect(self.refresh_all)

        self.tab_widget.addTab(self.task_page, "任务清单")
        self.tab_widget.addTab(self.history_page, "历史完成")
        self.tab_widget.addTab(self.checkin_page, "打卡记录")
        self.tab_widget.addTab(self.settings_page, "设置")
        self.tab_widget.currentChanged.connect(self.on_tab_changed)

        self.setCentralWidget(self.tab_widget)

    def create_settings_page(self):
        page = QWidget(self)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        startup_row = QFrame(page)
        startup_row.setObjectName("SettingsRow")
        row_layout = QHBoxLayout(startup_row)
        row_layout.setContentsMargins(16, 14, 16, 14)
        row_layout.setSpacing(12)

        text_layout = QVBoxLayout()
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(4)

        title_label = QLabel("开机自启动")
        title_label.setObjectName("SettingsTitle")
        description_label = QLabel("登录 Windows 当前用户账户时自动启动 ScheduleApp")
        description_label.setObjectName("SettingsDescription")
        description_label.setWordWrap(True)

        text_layout.addWidget(title_label)
        text_layout.addWidget(description_label)

        self.startup_checkbox = QCheckBox()
        self.startup_checkbox.setObjectName("StartupCheckBox")
        self.startup_checkbox.setChecked(is_startup_enabled())
        self.startup_checkbox.stateChanged.connect(self.on_startup_checkbox_changed)

        row_layout.addLayout(text_layout, 1)
        row_layout.addWidget(self.startup_checkbox)

        layout.addWidget(startup_row)
        layout.addStretch()
        return page

    def on_tab_changed(self, index):
        if self.tab_widget.widget(index) == self.settings_page:
            self.refresh_startup_checkbox()

    def refresh_startup_checkbox(self):
        self.startup_checkbox.blockSignals(True)
        self.startup_checkbox.setChecked(is_startup_enabled())
        self.startup_checkbox.blockSignals(False)

    def on_startup_checkbox_changed(self, state):
        enabled = self.startup_checkbox.isChecked()
        success = enable_startup() if enabled else disable_startup()
        if success:
            self.settings.setValue("startup_enabled", enabled)
            return

        if get_last_error_type() == "access_denied":
            if self.confirm_elevated_startup_change(enabled):
                action = "enable" if enabled else "disable"
                if (
                    request_elevated_startup_change(action)
                    and wait_for_startup_state(enabled)
                ):
                    self.startup_checkbox.blockSignals(True)
                    self.startup_checkbox.setChecked(enabled)
                    self.startup_checkbox.blockSignals(False)
                    self.settings.setValue("startup_enabled", enabled)
                    return

                self.restore_startup_checkbox(enabled)
                self.show_startup_error(get_last_error_message())
                return

            self.restore_startup_checkbox(enabled)
            return

        self.restore_startup_checkbox(enabled)
        self.show_startup_error(get_last_error_message())

    def restore_startup_checkbox(self, attempted_enabled):
        self.startup_checkbox.blockSignals(True)
        self.startup_checkbox.setChecked(not attempted_enabled)
        self.startup_checkbox.blockSignals(False)

    def confirm_elevated_startup_change(self, enabled):
        if enabled:
            title = "开机自启动需要管理员权限"
            message = (
                "当前系统拒绝了普通权限创建任务计划程序。\n"
                "是否现在请求管理员权限来开启开机自启动？"
            )
        else:
            title = "关闭开机自启动需要管理员权限"
            message = (
                "当前系统拒绝了普通权限删除任务计划程序。\n"
                "是否现在请求管理员权限来关闭开机自启动？"
            )

        return (
            QMessageBox.question(
                self,
                title,
                message,
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes,
            )
            == QMessageBox.Yes
        )

    def show_startup_error(self, message):
        if not message:
            message = "开机自启动设置失败，请检查系统权限或任务计划程序是否可用。"
        QMessageBox.warning(
            self,
            "开机自启动",
            message,
        )

    def refresh_pages(self):
        self.task_page.refresh_tasks()
        self.history_page.refresh_page()
        self.checkin_page.refresh_page()

    def init_floating_window(self):
        self.floating_window = FloatingTaskWindow()
        self.floating_window.data_changed.connect(self.refresh_all)
        self.floating_window.show_main_requested.connect(self.show_main_window)
        self.floating_window.new_task_requested.connect(self.open_new_task)
        self.floating_window.show_window()

    def init_tray(self):
        self.tray_manager = SystemTrayManager(self)

    def refresh_all(self):
        self.refresh_pages()
        self.floating_window.refresh_tasks()

    def show_main_window(self):
        self.show()
        self.raise_()
        self.activateWindow()

    def toggle_floating_window(self):
        if self.floating_window.isVisible():
            self.floating_window.hide_window()
        else:
            self.floating_window.show_window()

    def open_new_task(self):
        self.show_main_window()
        self.task_page.open_add_task_dialog()

    def exit_application(self):
        self.force_exit = True
        if hasattr(self, "floating_window"):
            self.floating_window.save_settings()
            self.floating_window.hide()
        if hasattr(self, "tray_manager"):
            self.tray_manager.hide()
        QApplication.instance().quit()

    def closeEvent(self, event):
        if self.force_exit:
            event.accept()
            return

        behavior = self.settings.value("close_behavior", "")
        if behavior == "tray":
            self.hide()
            event.ignore()
            return
        if behavior == "exit":
            self.exit_application()
            event.accept()
            return

        message_box = QMessageBox(self)
        message_box.setWindowTitle("关闭主窗口")
        message_box.setText("关闭主窗口时，你希望执行什么操作？")
        tray_button = message_box.addButton("最小化到系统托盘", QMessageBox.AcceptRole)
        exit_button = message_box.addButton("完全退出程序", QMessageBox.DestructiveRole)
        message_box.addButton(QMessageBox.Cancel)
        remember_checkbox = QCheckBox("记住我的选择")
        message_box.setCheckBox(remember_checkbox)
        message_box.exec()

        clicked_button = message_box.clickedButton()
        if clicked_button == tray_button:
            if remember_checkbox.isChecked():
                self.settings.setValue("close_behavior", "tray")
            self.hide()
            event.ignore()
            return

        if clicked_button == exit_button:
            if remember_checkbox.isChecked():
                self.settings.setValue("close_behavior", "exit")
            self.exit_application()
            event.accept()
            return

        event.ignore()

    def apply_global_style(self):
        self.setStyleSheet("""
            QLabel, QCheckBox {
                background-color: transparent;
                color: #222222;
            }

            QLineEdit, QTextEdit, QPlainTextEdit, QComboBox,
            QDateEdit, QDateTimeEdit, QTimeEdit, QSpinBox {
                background-color: transparent;
                color: #222222;
                border: 1px solid #cccccc;
                border-radius: 6px;
                selection-background-color: transparent;
                selection-color: #111111;
            }

            QPushButton {
                color: #222222;
                border: 1px solid #cccccc;
            }

            QFrame#SettingsRow {
                background-color: #ffffff;
                border: 1px solid #d0d7de;
                border-radius: 8px;
            }

            QLabel#SettingsTitle {
                font-size: 15px;
                font-weight: bold;
                color: #222222;
            }

            QLabel#SettingsDescription {
                color: #666666;
            }

            QCalendarWidget {
                background-color: transparent;
                color: #222222;
            }

            QCalendarWidget QWidget#qt_calendar_navigationbar {
                background-color: transparent;
                color: #222222;
            }

            QCalendarWidget QToolButton {
                background-color: transparent;
                color: #222222;
            }

            QCalendarWidget QAbstractItemView {
                background-color: transparent;
                color: #222222;
                selection-background-color: transparent;
                selection-color: #ffffff;
            }

            QCalendarWidget QHeaderView::section {
                background-color: transparent;
                color: #222222;
                border: none;
            }
        """)
