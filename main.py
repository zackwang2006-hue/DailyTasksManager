import sys
from datetime import datetime

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from app.config import APP_ICON_PATH, APP_NAME, LOGS_DIR
from app.ui.dialog_style import install_dialog_style
from app.ui.main_window import MainWindow


STARTUP_HELPER_FLAG = "--startup-elevated-helper"


def write_startup_log(message: str) -> None:
    try:
        LOGS_DIR.mkdir(parents=True, exist_ok=True)
        log_file = LOGS_DIR / "startup.log"
        with log_file.open("a", encoding="utf-8") as f:
            f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message}\n")
    except Exception:
        pass


def main():
    if len(sys.argv) == 3 and sys.argv[1] == STARTUP_HELPER_FLAG:
        from startup_elevated_helper import run_startup_helper_action

        sys.exit(run_startup_helper_action(sys.argv[2]))

    write_startup_log("main.py started")

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationDisplayName(APP_NAME)
    app.setQuitOnLastWindowClosed(False)
    install_dialog_style(app)

    if APP_ICON_PATH.exists():
        app.setWindowIcon(QIcon(str(APP_ICON_PATH)))

    window = MainWindow()
    # 默认只显示悬浮窗，主窗口可通过托盘菜单或悬浮窗入口打开。

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
