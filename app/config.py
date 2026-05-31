import os
import sys
from pathlib import Path

# 应用基础配置
APP_NAME = "计划炼金台"
APP_INTERNAL_NAME = "ScheduleApp"

# 项目根目录：ScheduleApp/
BASE_DIR = Path(__file__).resolve().parent.parent

# 数据库目录
# - 打包后的 exe：使用用户正式数据目录，避免升级丢数据
# - 开发环境 python main.py：使用项目内 data 目录，避免误操作正式数据库
if getattr(sys, "frozen", False):
    DATA_DIR = Path(os.getenv("LOCALAPPDATA")) / APP_NAME
    RESOURCE_BASE_DIR = Path(sys._MEIPASS)
else:
    DATA_DIR = BASE_DIR / "data"
    RESOURCE_BASE_DIR = BASE_DIR

DB_PATH = DATA_DIR / "schedule.db"

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
    "timed": "定时任务",
}
