import os

from PySide6.QtCore import QEvent, QObject, QSettings, QThread, QTimer, Signal, Slot
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFrame,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QGroupBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.config import APP_ICON_PATH, APP_NAME, WINDOW_HEIGHT, WINDOW_WIDTH
from app.services.date_refresh_coordinator import DateRefreshCoordinator
from app.services.global_hotkey import HOTKEY_DEFAULT, HOTKEY_OPTIONS, HOTKEY_SETTING_KEY, GlobalHotkeyManager
from app.services.integration_config_service import IntegrationConfigService
from app.services.period_service import period_service
from app.services.report_config import ReportConfigLoader
from app.services.report_email_service import ReportEmailError, ReportEmailService
from app.services.report_generation_service import ReportGenerationService
from app.services.report_job_service import ReportStartupRunner
from app.services.report_repository import ReportRepository
from app.services.task_service import TaskService
from app.ui.checkin_page import CheckinPage
from app.ui.dialog_style import apply_dialog_style, install_dialog_style
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

CLOSE_BEHAVIOR_ASK = "ask"
CLOSE_BEHAVIOR_TRAY = "tray"
CLOSE_BEHAVIOR_EXIT = "exit"

SETTINGS_COMBO_STYLE = """
QComboBox {
    min-height: 34px;
    padding: 4px 34px 4px 12px;
    border: 1px solid #cbd5e1;
    border-radius: 6px;
    background-color: #ffffff;
    color: #222222;
    font-size: 14px;
}

QComboBox:hover {
    border-color: #93c5fd;
}

QComboBox:focus {
    border-color: #60a5fa;
}

QComboBox:disabled {
    background-color: #f3f4f6;
    color: #9ca3af;
    border-color: #d1d5db;
}

QComboBox::drop-down {
    width: 28px;
    border: none;
    background-color: transparent;
}
"""

SETTINGS_COMBO_VIEW_STYLE = """
QAbstractItemView {
    background-color: #ffffff;
    color: #222222;
    border: 1px solid #cbd5e1;
    selection-background-color: #dbeafe;
    selection-color: #111827;
    outline: 0;
}

QAbstractItemView::item {
    min-height: 30px;
    padding: 6px 10px;
    background-color: #ffffff;
    color: #222222;
}

QAbstractItemView::item:hover,
QAbstractItemView::item:selected {
    background-color: #dbeafe;
    color: #111827;
}

QAbstractItemView::item:disabled {
    color: #9ca3af;
}
"""


class IntegrationTestWorker(QObject):
    succeeded = Signal(str)
    failed = Signal(str, str)

    def __init__(self, test_type, ai_config=None, email_config=None):
        super().__init__(None)
        self.test_type = test_type
        self.ai_config = ai_config
        self.email_config = email_config

    @Slot()
    def run(self):
        try:
            if self.test_type == "api":
                ReportGenerationService().test_connection(self.ai_config)
            else:
                ReportEmailService().send_test_email(self.email_config)
        except ReportEmailError as error:
            self.failed.emit(self.test_type, error.user_message)
        except Exception as error:
            message = "API 请求失败" if self.test_type == "api" else str(error)
            if self.test_type == "email":
                message = ReportEmailService().sanitize_server_response(
                    message,
                    secrets=(getattr(self.email_config, "auth_code", ""),),
                )
            self.failed.emit(self.test_type, message or "测试失败")
        else:
            self.succeeded.emit(self.test_type)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        install_dialog_style()

        self.setWindowTitle(APP_NAME)
        self.resize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.settings = QSettings(APP_NAME, "MainWindow")
        self.report_repository = ReportRepository()
        self.report_config_loader = ReportConfigLoader()
        self.integration_config_service = IntegrationConfigService()
        self.integration_test_thread = None
        self.hotkey_manager = GlobalHotkeyManager(self)
        self.active_hotkey_id = None
        self.force_exit = False
        self.task_service = TaskService()
        self._refreshing = False

        if APP_ICON_PATH.exists():
            self.setWindowIcon(QIcon(str(APP_ICON_PATH)))

        self.init_ui()
        self.apply_global_style()
        self.init_floating_window()
        self.init_tray()
        self.init_global_hotkey()
        self.init_date_refresh_coordinator()
        self.run_daily_refresh_for_date(period_service.get_local_today())
        self.refresh_all(run_daily_refresh=False)
        self.init_report_startup_runner()

    def init_ui(self):
        self.tab_widget = QTabWidget()

        self.task_page = TaskPage(self)
        self.history_page = HistoryPage(self)
        self.checkin_page = CheckinPage(self)
        self.settings_page = self.create_settings_page()

        self.task_page.data_changed.connect(self.refresh_all)
        self.checkin_page.data_changed.connect(self.refresh_all)

        self.tab_widget.addTab(self.task_page, "计划详情")
        self.tab_widget.addTab(self.history_page, "历史完成")
        self.tab_widget.addTab(self.checkin_page, "每日任务")
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

        report_row = QFrame(page)
        report_row.setObjectName("SettingsRow")
        report_layout = QHBoxLayout(report_row)
        report_layout.setContentsMargins(16, 14, 16, 14)
        report_layout.setSpacing(12)

        report_text_layout = QVBoxLayout()
        report_text_layout.setContentsMargins(0, 0, 0, 0)
        report_text_layout.setSpacing(4)

        report_title_label = QLabel("自动发送周期报告")
        report_title_label.setObjectName("SettingsTitle")
        report_description_label = QLabel("周期结束后，将在下次启动程序时自动生成报告并发送到配置邮箱。")
        report_description_label.setObjectName("SettingsDescription")
        report_description_label.setWordWrap(True)

        report_text_layout.addWidget(report_title_label)
        report_text_layout.addWidget(report_description_label)

        self.auto_report_checkbox = QCheckBox()
        self.auto_report_checkbox.setObjectName("AutoReportCheckBox")
        self.auto_report_checkbox.setChecked(
            self.report_repository.get_auto_send_enabled(self.report_config_loader)
        )
        self.auto_report_checkbox.stateChanged.connect(self.on_auto_report_checkbox_changed)

        self.test_email_button = QPushButton("测试邮件配置")
        self.test_email_button.setObjectName("SecondaryButton")
        self.test_email_button.setMinimumWidth(132)
        self.test_email_button.clicked.connect(self.start_test_email)

        report_layout.addLayout(report_text_layout, 1)
        report_layout.addWidget(self.test_email_button)
        report_layout.addWidget(self.auto_report_checkbox)

        layout.addWidget(report_row)

        layout.addWidget(self.create_integration_settings_group(page))

        hotkey_row = QFrame(page)
        hotkey_row.setObjectName("SettingsRow")
        hotkey_layout = QHBoxLayout(hotkey_row)
        hotkey_layout.setContentsMargins(16, 14, 16, 14)
        hotkey_layout.setSpacing(12)

        hotkey_text_layout = QVBoxLayout()
        hotkey_text_layout.setContentsMargins(0, 0, 0, 0)
        hotkey_text_layout.setSpacing(4)
        hotkey_title_label = QLabel("悬浮窗显示/隐藏快捷键")
        hotkey_title_label.setObjectName("SettingsTitle")
        hotkey_description_label = QLabel("在其他程序中也可以使用此快捷键显示或隐藏悬浮窗。")
        hotkey_description_label.setObjectName("SettingsDescription")
        hotkey_description_label.setWordWrap(True)
        hotkey_text_layout.addWidget(hotkey_title_label)
        hotkey_text_layout.addWidget(hotkey_description_label)

        self.hotkey_combo = QComboBox()
        self.hotkey_combo.setObjectName("FloatingHotkeyComboBox")
        self.hotkey_combo.setMinimumHeight(34)
        self.hotkey_combo.setMinimumWidth(190)
        self.apply_settings_combo_style(self.hotkey_combo)
        for option_id, (label, _modifiers, _virtual_key) in HOTKEY_OPTIONS.items():
            self.hotkey_combo.addItem(label, option_id)
        saved_hotkey = self.settings.value(HOTKEY_SETTING_KEY, HOTKEY_DEFAULT)
        saved_index = self.hotkey_combo.findData(saved_hotkey)
        self.hotkey_combo.setCurrentIndex(saved_index if saved_index >= 0 else 0)
        self.hotkey_combo.currentIndexChanged.connect(self.on_hotkey_changed)

        hotkey_layout.addLayout(hotkey_text_layout, 1)
        hotkey_layout.addWidget(self.hotkey_combo)
        layout.addWidget(hotkey_row)

        close_row = QFrame(page)
        close_row.setObjectName("SettingsRow")
        close_layout = QHBoxLayout(close_row)
        close_layout.setContentsMargins(16, 14, 16, 14)
        close_layout.setSpacing(12)

        close_text_layout = QVBoxLayout()
        close_text_layout.setContentsMargins(0, 0, 0, 0)
        close_text_layout.setSpacing(4)

        close_title_label = QLabel("关闭主界面时")
        close_title_label.setObjectName("SettingsTitle")
        close_description_label = QLabel("控制点击主窗口关闭按钮后的程序行为")
        close_description_label.setObjectName("SettingsDescription")
        close_description_label.setWordWrap(True)

        close_text_layout.addWidget(close_title_label)
        close_text_layout.addWidget(close_description_label)

        self.close_behavior_combo = QComboBox()
        self.close_behavior_combo.setObjectName("CloseBehaviorComboBox")
        self.close_behavior_combo.setMinimumHeight(34)
        self.close_behavior_combo.setMinimumWidth(230)
        self.apply_settings_combo_style(self.close_behavior_combo)
        self.close_behavior_combo.addItem("每次询问 / 遗忘之前的选择", CLOSE_BEHAVIOR_ASK)
        self.close_behavior_combo.addItem("最小化到系统托盘", CLOSE_BEHAVIOR_TRAY)
        self.close_behavior_combo.addItem("彻底退出程序", CLOSE_BEHAVIOR_EXIT)
        saved_behavior = self.get_close_behavior()
        saved_index = self.close_behavior_combo.findData(saved_behavior)
        self.close_behavior_combo.setCurrentIndex(max(0, saved_index))
        self.close_behavior_combo.currentIndexChanged.connect(self.on_close_behavior_changed)
        close_layout.addLayout(close_text_layout, 1)
        close_layout.addWidget(self.close_behavior_combo)

        layout.addWidget(close_row)
        layout.addStretch()
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(page)
        return scroll

    def create_integration_settings_group(self, parent):
        group = QGroupBox("API 与邮件配置", parent)
        group_layout = QVBoxLayout(group)
        group_layout.setContentsMargins(14, 16, 14, 14)
        group_layout.setSpacing(12)

        ai_group = QGroupBox("AI 报告配置", group)
        ai_form = QFormLayout(ai_group)
        ai_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        ai_form.setHorizontalSpacing(12)
        ai_form.setVerticalSpacing(8)

        self.api_key_edit = QLineEdit()
        self.api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key_edit.setPlaceholderText("请输入 API Key")
        self.api_key_edit.setClearButtonEnabled(False)
        self.api_key_show = QCheckBox("显示密钥")
        self.api_key_show.toggled.connect(
            lambda checked: self.api_key_edit.setEchoMode(
                QLineEdit.EchoMode.Normal if checked else QLineEdit.EchoMode.Password
            )
        )
        api_key_row = QWidget()
        api_key_layout = QHBoxLayout(api_key_row)
        api_key_layout.setContentsMargins(0, 0, 0, 0)
        api_key_layout.addWidget(self.api_key_edit, 1)
        api_key_layout.addWidget(self.api_key_show)
        api_key_clear = QPushButton("清除")
        api_key_clear.clicked.connect(self.clear_api_key)
        api_key_layout.addWidget(api_key_clear)
        ai_form.addRow("API Key", api_key_row)

        self.api_base_url_edit = QLineEdit()
        self.api_base_url_edit.setPlaceholderText("请输入 API Base URL")
        ai_form.addRow("API Base URL", self.api_base_url_edit)

        self.api_model_combo = QComboBox()
        self.api_model_combo.setEditable(True)
        self.api_model_combo.lineEdit().setPlaceholderText("请输入模型名称")
        ai_form.addRow("模型名称", self.api_model_combo)

        self.test_api_button = QPushButton("测试 API")
        self.test_api_button.clicked.connect(self.start_test_api)
        ai_form.addRow("", self.test_api_button)
        group_layout.addWidget(ai_group)

        email_group = QGroupBox("邮件发送配置", group)
        email_form = QFormLayout(email_group)
        email_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        email_form.setHorizontalSpacing(12)
        email_form.setVerticalSpacing(8)

        self.sender_email_edit = QLineEdit()
        self.sender_email_edit.setPlaceholderText("请输入发件人邮箱")
        self.sender_email_edit.editingFinished.connect(self.suggest_smtp_host)
        email_form.addRow("发件人邮箱", self.sender_email_edit)

        self.smtp_host_edit = QLineEdit()
        self.smtp_host_edit.setPlaceholderText("请输入 SMTP 服务器")
        email_form.addRow("SMTP 服务器", self.smtp_host_edit)

        self.smtp_port_spin = QSpinBox()
        self.smtp_port_spin.setRange(1, 65535)
        self.smtp_port_spin.setValue(465)
        email_form.addRow("SMTP 端口", self.smtp_port_spin)

        self.smtp_encryption_combo = QComboBox()
        self.smtp_encryption_combo.addItem("SSL", "ssl")
        self.smtp_encryption_combo.addItem("STARTTLS", "starttls")
        self.smtp_encryption_combo.addItem("无加密", "none")
        self.smtp_encryption_combo.currentIndexChanged.connect(self.on_encryption_changed)
        email_form.addRow("加密方式", self.smtp_encryption_combo)

        self.smtp_password_edit = QLineEdit()
        self.smtp_password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.smtp_password_edit.setPlaceholderText("请输入 SMTP 授权码或应用专用密码")
        self.smtp_password_show = QCheckBox("显示授权码")
        self.smtp_password_show.toggled.connect(
            lambda checked: self.smtp_password_edit.setEchoMode(
                QLineEdit.EchoMode.Normal if checked else QLineEdit.EchoMode.Password
            )
        )
        smtp_password_row = QWidget()
        smtp_password_layout = QHBoxLayout(smtp_password_row)
        smtp_password_layout.setContentsMargins(0, 0, 0, 0)
        smtp_password_layout.addWidget(self.smtp_password_edit, 1)
        smtp_password_layout.addWidget(self.smtp_password_show)
        smtp_password_clear = QPushButton("清除")
        smtp_password_clear.clicked.connect(self.clear_smtp_password)
        smtp_password_layout.addWidget(smtp_password_clear)
        email_form.addRow("邮箱授权码", smtp_password_row)

        self.recipient_email_edit = QLineEdit()
        self.recipient_email_edit.setPlaceholderText("请输入收件人邮箱")
        email_form.addRow("收件人邮箱", self.recipient_email_edit)

        self.test_email_button = QPushButton("发送测试邮件")
        self.test_email_button.clicked.connect(self.start_test_email)
        email_form.addRow("", self.test_email_button)
        group_layout.addWidget(email_group)

        button_row = QHBoxLayout()
        button_row.addStretch()
        reset_button = QPushButton("恢复默认值")
        reset_button.clicked.connect(self.reset_integration_defaults)
        self.save_integration_button = QPushButton("保存配置")
        self.save_integration_button.setDefault(True)
        self.save_integration_button.clicked.connect(self.save_integration_config)
        button_row.addWidget(reset_button)
        button_row.addWidget(self.save_integration_button)
        group_layout.addLayout(button_row)

        self.api_key_clear_requested = False
        self.smtp_password_clear_requested = False
        self.load_integration_settings()
        return group

    def load_integration_settings(self):
        settings = self.integration_config_service.load_settings()
        self.api_base_url_edit.setText(settings.ai.base_url)
        self.api_model_combo.setEditText(settings.ai.model)
        self.api_key_edit.clear()
        self.api_key_edit.setPlaceholderText(
            "已保存 API Key" if settings.ai.api_key else "请输入 API Key"
        )
        self.sender_email_edit.setText(settings.email.sender_email)
        self.smtp_host_edit.setText(settings.email.smtp_host)
        self.smtp_port_spin.setValue(settings.email.smtp_port)
        self.smtp_encryption_combo.setCurrentIndex(
            max(0, self.smtp_encryption_combo.findData(settings.email.encryption))
        )
        self.smtp_password_edit.clear()
        self.smtp_password_edit.setPlaceholderText(
            "已保存邮箱授权码" if settings.email.auth_code else "请输入 SMTP 授权码或应用专用密码"
        )
        self.recipient_email_edit.setText(settings.email.recipient_email or settings.email.sender_email)
        self.api_key_clear_requested = False
        self.smtp_password_clear_requested = False

    def suggest_smtp_host(self):
        if self.smtp_host_edit.text().strip():
            return
        domain = self.sender_email_edit.text().rsplit("@", 1)[-1].lower()
        suggestions = {
            "qq.com": "smtp.qq.com",
            "163.com": "smtp.163.com",
            "gmail.com": "smtp.gmail.com",
            "googlemail.com": "smtp.gmail.com",
            "outlook.com": "smtp.office365.com",
            "hotmail.com": "smtp.office365.com",
        }
        if domain in suggestions:
            self.smtp_host_edit.setText(suggestions[domain])

    def on_encryption_changed(self, index):
        defaults = {"ssl": 465, "starttls": 587, "none": 25}
        encryption = self.smtp_encryption_combo.itemData(index)
        if self.smtp_port_spin.value() in {25, 465, 587}:
            self.smtp_port_spin.setValue(defaults.get(encryption, 465))

    def clear_api_key(self):
        self.api_key_edit.clear()
        self.api_key_edit.setPlaceholderText("保存时删除 API Key")
        self.api_key_clear_requested = True

    def clear_smtp_password(self):
        self.smtp_password_edit.clear()
        self.smtp_password_edit.setPlaceholderText("保存时删除邮箱授权码")
        self.smtp_password_clear_requested = True

    def reset_integration_defaults(self):
        defaults = self.integration_config_service.default_settings()
        self.api_base_url_edit.setText(defaults.ai.base_url)
        self.api_model_combo.setEditText(defaults.ai.model)
        self.smtp_host_edit.clear()
        self.smtp_port_spin.setValue(defaults.email.smtp_port)
        self.smtp_encryption_combo.setCurrentIndex(
            self.smtp_encryption_combo.findData(defaults.email.encryption)
        )

    def _current_integration_configs(self):
        saved = self.integration_config_service.load_settings()
        api_key = self.api_key_edit.text().strip() or saved.ai.api_key
        smtp_password = self.smtp_password_edit.text().strip() or saved.email.auth_code
        encryption = self.smtp_encryption_combo.currentData()
        ai = saved.ai.__class__(
            self.api_base_url_edit.text().strip(), api_key,
            self.api_model_combo.currentText().strip(), saved.ai.timeout_seconds, saved.ai.temperature,
        )
        email = saved.email.__class__(
            self.smtp_host_edit.text().strip(), self.smtp_port_spin.value(), encryption == "ssl",
            self.sender_email_edit.text().strip(), smtp_password, self.recipient_email_edit.text().strip(), encryption,
        )
        return ai, email, saved

    def save_integration_config(self):
        ai, email, saved = self._current_integration_configs()
        errors = self.integration_config_service.validate(ai, email)
        if errors:
            QMessageBox.warning(self, "配置不完整", "请填写：" + "、".join(errors))
            return
        if self.api_key_clear_requested and saved.ai.api_key:
            result = QMessageBox.question(self, "删除 API Key", "确认删除已保存的 API Key 吗？")
            if result != QMessageBox.StandardButton.Yes:
                return
        if self.smtp_password_clear_requested and saved.email.auth_code:
            result = QMessageBox.question(self, "删除邮箱授权码", "确认删除已保存的邮箱授权码吗？")
            if result != QMessageBox.StandardButton.Yes:
                return
        api_secret = "" if self.api_key_clear_requested else (self.api_key_edit.text().strip() or None)
        smtp_secret = "" if self.smtp_password_clear_requested else (self.smtp_password_edit.text().strip() or None)
        try:
            self.integration_config_service.save_settings(
                base_url=ai.base_url,
                model=ai.model,
                sender=email.sender_email,
                smtp_host=self.smtp_host_edit.text().strip(),
                smtp_port=email.smtp_port,
                encryption=email.encryption,
                recipient=email.recipient_email,
                api_key=api_secret,
                smtp_password=smtp_secret,
            )
        except Exception:
            QMessageBox.critical(self, "保存失败", "配置保存失败，请检查文件权限后重试。")
            return
        self.load_integration_settings()
        QMessageBox.information(self, "配置已保存", "配置已保存")

    @staticmethod
    def apply_settings_combo_style(combo):
        combo.setStyleSheet(SETTINGS_COMBO_STYLE)
        combo.view().setStyleSheet(SETTINGS_COMBO_VIEW_STYLE)

    def get_close_behavior(self):
        behavior = self.settings.value("close_behavior", CLOSE_BEHAVIOR_ASK)
        if behavior in {CLOSE_BEHAVIOR_TRAY, CLOSE_BEHAVIOR_EXIT}:
            return behavior
        return CLOSE_BEHAVIOR_ASK

    def on_close_behavior_changed(self):
        behavior = self.close_behavior_combo.currentData()
        self.settings.setValue("close_behavior", behavior or CLOSE_BEHAVIOR_ASK)

    def on_tab_changed(self, index):
        if hasattr(self, "date_refresh_coordinator"):
            self.date_refresh_coordinator.check_date_change()
        if self.tab_widget.widget(index) == self.settings_page:
            self.refresh_startup_checkbox()
            self.refresh_auto_report_checkbox()

    def refresh_startup_checkbox(self):
        self.startup_checkbox.blockSignals(True)
        self.startup_checkbox.setChecked(is_startup_enabled())
        self.startup_checkbox.blockSignals(False)

    def refresh_auto_report_checkbox(self):
        self.auto_report_checkbox.blockSignals(True)
        self.auto_report_checkbox.setChecked(
            self.report_repository.get_auto_send_enabled(self.report_config_loader)
        )
        self.auto_report_checkbox.blockSignals(False)

    def on_auto_report_checkbox_changed(self, state):
        self.report_repository.set_auto_send_enabled(self.auto_report_checkbox.isChecked())

    def _start_integration_test(self, test_type):
        ai, email, _saved = self._current_integration_configs()
        if test_type == "api":
            missing = []
            if not ai.api_key:
                missing.append("API Key")
            if not ai.base_url:
                missing.append("API Base URL")
            if not ai.model:
                missing.append("模型名称")
            button = self.test_api_button
        else:
            missing = ReportEmailService().validate_email_config(email)
            button = self.test_email_button
        if missing:
            QMessageBox.warning(self, "配置不完整", "请先填写：" + "、".join(missing))
            return

        button.setEnabled(False)
        button.setText("测试中…")
        thread = QThread(self)
        worker = IntegrationTestWorker(test_type, ai, email)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.succeeded.connect(self.on_integration_test_succeeded)
        worker.failed.connect(self.on_integration_test_failed)
        worker.succeeded.connect(thread.quit)
        worker.failed.connect(thread.quit)
        worker.succeeded.connect(worker.deleteLater)
        worker.failed.connect(worker.deleteLater)
        thread.finished.connect(self.on_integration_test_finished)
        thread.finished.connect(thread.deleteLater)
        self.integration_test_thread = (thread, worker)
        thread.start()

    def start_test_api(self):
        self._start_integration_test("api")

    def start_test_email(self):
        self._start_integration_test("email")

    @Slot(str)
    def on_integration_test_succeeded(self, test_type):
        button = self.test_api_button if test_type == "api" else self.test_email_button
        button.setEnabled(True)
        button.setText("测试 API" if test_type == "api" else "发送测试邮件")
        QMessageBox.information(
            self,
            "测试成功",
            "API 连接成功" if test_type == "api" else "测试邮件发送成功",
        )

    @Slot(str, str)
    def on_integration_test_failed(self, test_type, message):
        button = self.test_api_button if test_type == "api" else self.test_email_button
        button.setEnabled(True)
        button.setText("测试 API" if test_type == "api" else "发送测试邮件")
        QMessageBox.warning(self, "测试失败", message)

    @Slot()
    def on_integration_test_finished(self):
        self.integration_test_thread = None

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
        self.floating_window.date_check_requested.connect(self.check_date_change)
        self.floating_window.show_main_requested.connect(self.show_main_window)
        self.floating_window.new_task_requested.connect(
            lambda: self.open_add_task_dialog(parent=self.floating_window, show_main_window=False)
        )
        self.floating_window.show_window()

    def init_tray(self):
        self.tray_manager = SystemTrayManager(self)

    def init_global_hotkey(self):
        self.hotkey_manager.activated.connect(self.on_global_hotkey_activated)
        app = QApplication.instance()
        if app is not None:
            app.aboutToQuit.connect(self.hotkey_manager.stop)
        requested = self.hotkey_combo.currentData()
        active = self.hotkey_manager.start(requested or HOTKEY_DEFAULT)
        if active is not None:
            self.active_hotkey_id = active
            self.set_hotkey_combo(active)
            self.settings.setValue(HOTKEY_SETTING_KEY, active)

    @Slot(str)
    def on_global_hotkey_activated(self, option_id):
        self.toggle_floating_window(activate=False)

    def set_hotkey_combo(self, option_id):
        index = self.hotkey_combo.findData(option_id)
        if index < 0:
            return
        self.hotkey_combo.blockSignals(True)
        self.hotkey_combo.setCurrentIndex(index)
        self.hotkey_combo.blockSignals(False)

    def on_hotkey_changed(self, index):
        option_id = self.hotkey_combo.itemData(index)
        if option_id == self.active_hotkey_id:
            return
        previous = self.active_hotkey_id
        if self.hotkey_manager.replace(option_id):
            self.active_hotkey_id = option_id
            self.settings.setValue(HOTKEY_SETTING_KEY, option_id)
            return

        if previous is not None:
            self.set_hotkey_combo(previous)
        QMessageBox.warning(
            self,
            "快捷键设置",
            "该快捷键已被其他程序占用，请选择其他快捷键。",
        )

    def init_date_refresh_coordinator(self):
        self.date_refresh_coordinator = DateRefreshCoordinator(self)
        self.date_refresh_coordinator.date_changed.connect(self.on_date_changed)
        self.date_refresh_coordinator.start()

    def init_report_startup_runner(self):
        if os.environ.get("SCHEDULEAPP_DISABLE_REPORT_STARTUP") == "1":
            return
        self.report_startup_runner = ReportStartupRunner()
        QTimer.singleShot(0, self.report_startup_runner.start_once)

    def check_date_change(self):
        if hasattr(self, "date_refresh_coordinator"):
            self.date_refresh_coordinator.check_date_change()

    def run_daily_refresh_for_date(self, target_date):
        self.task_service.expire_daily_tasks(target_date)
        self.task_service.ensure_daily_plan_tasks_for_date(target_date)

    def on_date_changed(self, old_date, new_date):
        self.run_daily_refresh_for_date(new_date)
        self.refresh_all(run_daily_refresh=False)

    def refresh_all(self, run_daily_refresh=True):
        if self._refreshing:
            return
        self._refreshing = True
        try:
            if run_daily_refresh:
                self.run_daily_refresh_for_date(period_service.get_local_today())
            self.refresh_pages()
            self.floating_window.refresh_tasks()
        finally:
            self._refreshing = False

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == QEvent.ActivationChange and self.isActiveWindow():
            self.check_date_change()

    def showEvent(self, event):
        super().showEvent(event)
        self.check_date_change()

    def show_main_window(self):
        self.show()
        self.raise_()
        self.activateWindow()

    def toggle_floating_window(self, activate=True):
        if self.floating_window.isVisible():
            self.floating_window.hide_window()
        else:
            self.floating_window.show_window(activate=activate)

    def open_add_task_dialog(self, parent=None, show_main_window=True):
        if show_main_window:
            self.show_main_window()
        self.task_page.open_add_task_dialog(parent=parent)

    def open_new_task(self):
        self.open_add_task_dialog(show_main_window=True)

    def exit_application(self):
        self.force_exit = True
        self.hotkey_manager.stop()
        if hasattr(self, "floating_window"):
            if hasattr(self.floating_window, "quick_note_view"):
                self.floating_window.quick_note_view.final_save()
            self.floating_window.save_settings()
            self.floating_window.hide()
        if hasattr(self, "tray_manager"):
            self.tray_manager.hide()
        QApplication.instance().quit()

    def closeEvent(self, event):
        if self.force_exit:
            event.accept()
            return

        behavior = self.get_close_behavior()
        if behavior == CLOSE_BEHAVIOR_TRAY:
            self.hide()
            event.ignore()
            return
        if behavior == CLOSE_BEHAVIOR_EXIT:
            self.exit_application()
            event.accept()
            return

        message_box = QMessageBox(self)
        message_box.setWindowTitle("关闭主窗口")
        message_box.setText("关闭主窗口时，你希望执行什么操作？")
        tray_button = message_box.addButton("最小化到托盘", QMessageBox.AcceptRole)
        exit_button = message_box.addButton("完全退出", QMessageBox.DestructiveRole)
        cancel_button = message_box.addButton("取消", QMessageBox.RejectRole)
        tray_button.setObjectName("TrayCloseButton")
        exit_button.setObjectName("ExitCloseButton")
        cancel_button.setObjectName("CancelCloseButton")
        remember_checkbox = QCheckBox("记住我的选择")
        message_box.setCheckBox(remember_checkbox)
        apply_dialog_style(message_box)
        message_box.exec()

        clicked_button = message_box.clickedButton()
        if clicked_button == tray_button:
            if remember_checkbox.isChecked():
                self.settings.setValue("close_behavior", CLOSE_BEHAVIOR_TRAY)
                self.close_behavior_combo.setCurrentIndex(
                    self.close_behavior_combo.findData(CLOSE_BEHAVIOR_TRAY)
                )
            self.hide()
            event.ignore()
            return

        if clicked_button == exit_button:
            if remember_checkbox.isChecked():
                self.settings.setValue("close_behavior", CLOSE_BEHAVIOR_EXIT)
                self.close_behavior_combo.setCurrentIndex(
                    self.close_behavior_combo.findData(CLOSE_BEHAVIOR_EXIT)
                )
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
