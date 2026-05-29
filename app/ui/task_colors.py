from datetime import datetime, time

from app.utils.time_utils import is_task_overdue


def get_short_task_ddl_status(task):
    if getattr(task, "is_completed", False):
        return "none"

    if not task.ddl:
        return "none"

    try:
        ddl_datetime = datetime.fromisoformat(task.ddl)
    except ValueError:
        try:
            ddl_datetime = datetime.combine(
                datetime.fromisoformat(task.ddl[:10]).date(),
                time.max,
            )
        except ValueError:
            return "none"

    diff_seconds = (ddl_datetime - datetime.now()).total_seconds()

    if diff_seconds < 0:
        return "expired"
    if diff_seconds < 86400:
        return "urgent"
    if diff_seconds <= 3 * 86400:
        return "soon"
    return "safe"


def get_task_card_color(task):
    if is_task_overdue(task):
        return "#6F1616", "#8B1E1E", "#ffffff"

    if task.task_type == "timed" or task.category == "timed":
        return "#7e57c2", "#d8c7ff", "#111111"

    if task.task_type == "daily" or task.category == "daily":
        return "#1e88e5", "#cfe8ff", "#111111"

    if task.category == "extra":
        return "#757575", "#e0e0e0", "#111111"

    if task.category == "long":
        return "#2E8B57", "#B8E6D1", "#111111"

    if task.category == "short":
        ddl_status = get_short_task_ddl_status(task)
        if ddl_status == "expired":
            return "#6F1616", "#8B1E1E", "#ffffff"
        if ddl_status == "urgent":
            return "#c62828", "#ffb3b3", "#111111"
        if ddl_status == "soon":
            return "#f9a825", "#ffe680", "#111111"
        if ddl_status == "safe":
            return "#2e7d32", "#bfecc5", "#111111"

    return "#cccccc", "#ffffff", "#111111"
