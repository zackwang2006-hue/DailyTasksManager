import os
import sys
from pathlib import Path

# 应用基础配置
APP_NAME = "计划炼金台"
APP_INTERNAL_NAME = "ScheduleApp"

# 项目根目录：ScheduleApp/
BASE_DIR = Path(__file__).resolve().parent.parent


def _packaged_user_data_dir() -> Path:
    local_app_data = os.getenv("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data) / APP_NAME
    return Path.home() / ".scheduleapp"

# 数据库目录
# - 打包后的 exe：使用用户正式数据目录，避免升级丢数据
# - 开发环境 python main.py：使用项目内 data 目录，避免误操作正式数据库
if getattr(sys, "frozen", False):
    DATA_DIR = _packaged_user_data_dir()
    RESOURCE_BASE_DIR = Path(sys._MEIPASS)
else:
    DATA_DIR = BASE_DIR / "data"
    RESOURCE_BASE_DIR = BASE_DIR


def resource_path(relative_path: str) -> Path:
    return RESOURCE_BASE_DIR / relative_path


def user_data_path(relative_path: str) -> Path:
    return DATA_DIR / relative_path


DB_PATH = DATA_DIR / "schedule.db"
CONFIG_DIR = DATA_DIR / "config"
REPORT_DELIVERY_CONFIG_PATH = CONFIG_DIR / "report_delivery.json"
REPORTS_DIR = DATA_DIR / "reports"
LOGS_DIR = DATA_DIR / "logs"

# 资源目录
ASSETS_DIR = RESOURCE_BASE_DIR / "assets"
ICON_DIR = ASSETS_DIR / "icons"
IMAGE_DIR = ASSETS_DIR / "images"

# 程序图标
APP_ICON_PATH = ICON_DIR / "app_icon.ico"

WINDOW_WIDTH = 900
WINDOW_HEIGHT = 650

# 任务分类
TASK_CATEGORIES = {
    "short": "短期任务",
    "long": "长期任务",
    "daily": "每日任务",
    "extra": "附加任务",
    "timed": "固定事件",
}
