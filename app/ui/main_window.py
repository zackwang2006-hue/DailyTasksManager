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
