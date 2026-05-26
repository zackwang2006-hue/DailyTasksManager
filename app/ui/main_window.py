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
        tab_widget.addTab(TaskPage(self), "任务")
        tab_widget.addTab(HistoryPage(self), "历史")
        tab_widget.addTab(CheckinPage(self), "打卡")

        self.setCentralWidget(tab_widget)
