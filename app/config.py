from pathlib import Path

# 项目根目录：ScheduleApp/
BASE_DIR = Path(__file__).resolve().parent.parent

# 数据库目录和数据库文件
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "schedule.db"

# 资源目录
ASSETS_DIR = BASE_DIR / "assets"
ICON_DIR = ASSETS_DIR / "icons"
IMAGE_DIR = ASSETS_DIR / "images"

# 程序图标
APP_ICON_PATH = ICON_DIR / "app_icon.ico"

# 应用基础配置
APP_NAME = "ScheduleApp"
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
