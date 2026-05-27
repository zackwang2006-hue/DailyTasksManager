from datetime import datetime, time


def get_short_task_ddl_status(task):
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

    if diff_seconds < 86400:
        return "urgent"
    if diff_seconds <= 3 * 86400:
        return "soon"
    return "safe"


def get_task_card_color(task):
    if task.task_type == "timed" or task.category == "timed":
        return "#9575cd", "#f3efff", "#5e35b1"

    if task.task_type == "daily" or task.category == "daily":
        return "#42a5f5", "#eaf4ff", "#1976d2"

    if task.category == "extra":
        return "#9e9e9e", "transparent", "#666666"

    if task.category == "long":
        return "#43a047", "#f0fff4", "#2e7d32"

    if task.category == "short":
        ddl_status = get_short_task_ddl_status(task)
        if ddl_status == "urgent":
            return "#e53935", "#fff0f0", "#e53935"
        if ddl_status == "soon":
            return "#fbc02d", "#fffbe6", "#f9a825"
        if ddl_status == "safe":
            return "#43a047", "#f0fff4", "#43a047"

    return "#cccccc", "#ffffff", "#666666"
