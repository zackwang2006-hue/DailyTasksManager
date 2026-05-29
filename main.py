import os
import sys
from datetime import datetime
from pathlib import Path

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from app.config import APP_ICON_PATH
from app.ui.main_window import MainWindow


def write_startup_log(message: str) -> None:
    try:
        if getattr(sys, "frozen", False):
            app_root = Path(sys.executable).resolve().parent
        else:
            app_root = Path(__file__).resolve().parent

        log_dir = app_root / "logs"
        log_dir.mkdir(exist_ok=True)
        log_file = log_dir / "startup.log"
        with log_file.open("a", encoding="utf-8") as f:
            f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message}\n")
    except Exception:
        pass


def main():
    if getattr(sys, "frozen", False):
        os.chdir(Path(sys.executable).resolve().parent)

    write_startup_log("main.py started")

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    if APP_ICON_PATH.exists():
        app.setWindowIcon(QIcon(str(APP_ICON_PATH)))

    window = MainWindow()
    # 默认只显示悬浮窗，主窗口可通过托盘菜单或悬浮窗入口打开。

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
