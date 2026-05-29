from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import QApplication, QMenu, QStyle, QSystemTrayIcon

from app.config import APP_ICON_PATH


class SystemTrayManager:
    def __init__(self, parent):
        self.parent = parent
        self.tray_icon = QSystemTrayIcon(self.get_icon(), parent)
        self.tray_icon.setToolTip("ScheduleApp")
        self.tray_icon.setContextMenu(self.create_menu())
        self.tray_icon.activated.connect(self.on_activated)
        self.tray_icon.show()

    def get_icon(self):
        if APP_ICON_PATH.exists():
            return QIcon(str(APP_ICON_PATH))

        app = QApplication.instance()
        if app is not None:
            return app.style().standardIcon(QStyle.SP_ComputerIcon)

        return QIcon()

    def create_menu(self):
        menu = QMenu(self.parent)

        show_main_action = QAction("显示主窗口", menu)
        show_main_action.triggered.connect(self.parent.show_main_window)

        toggle_floating_action = QAction("显示 / 隐藏悬浮窗", menu)
        toggle_floating_action.triggered.connect(self.parent.toggle_floating_window)

        new_task_action = QAction("新建任务", menu)
        new_task_action.triggered.connect(self.parent.open_new_task)

        refresh_action = QAction("刷新任务", menu)
        refresh_action.triggered.connect(self.parent.refresh_all)

        exit_action = QAction("退出程序", menu)
        exit_action.triggered.connect(self.parent.exit_application)

        menu.addAction(show_main_action)
        menu.addAction(toggle_floating_action)
        menu.addAction(new_task_action)
        menu.addAction(refresh_action)
        menu.addSeparator()
        menu.addAction(exit_action)
        return menu

    def on_activated(self, reason):
        if reason == QSystemTrayIcon.DoubleClick:
            self.parent.show_main_window()

    def hide(self):
        self.tray_icon.hide()
