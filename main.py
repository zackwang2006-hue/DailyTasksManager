import sys

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from app.config import APP_ICON_PATH
from app.ui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)

    if APP_ICON_PATH.exists():
        app.setWindowIcon(QIcon(str(APP_ICON_PATH)))

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()