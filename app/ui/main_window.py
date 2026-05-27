from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QMainWindow, QTabWidget

from app.config import APP_ICON_PATH, APP_NAME, WINDOW_HEIGHT, WINDOW_WIDTH
from app.ui.checkin_page import CheckinPage
from app.ui.history_page import HistoryPage
from app.ui.task_page import TaskPage


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle(APP_NAME)
        self.resize(WINDOW_WIDTH, WINDOW_HEIGHT)

        if APP_ICON_PATH.exists():
            self.setWindowIcon(QIcon(str(APP_ICON_PATH)))

        self.init_ui()
        self.apply_global_style()

    def init_ui(self):
        tab_widget = QTabWidget()

        self.task_page = TaskPage(self)
        self.history_page = HistoryPage(self)
        self.checkin_page = CheckinPage(self)

        self.task_page.data_changed.connect(self.refresh_pages)
        self.checkin_page.data_changed.connect(self.refresh_pages)

        tab_widget.addTab(self.task_page, "任务清单")
        tab_widget.addTab(self.history_page, "历史完成")
        tab_widget.addTab(self.checkin_page, "打卡记录")

        self.setCentralWidget(tab_widget)

    def refresh_pages(self):
        self.task_page.refresh_tasks()
        self.history_page.refresh_page()
        self.checkin_page.refresh_page()

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
