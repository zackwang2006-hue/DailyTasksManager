from datetime import date, datetime, time, timedelta


def parse_task_datetime(value):
    if not value:
        return None

    text = str(value)
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        try:
            return datetime.combine(datetime.fromisoformat(text[:10]).date(), time(23, 59))
        except ValueError:
            return None

    if len(text) <= 10:
        return datetime.combine(parsed.date(), time(23, 59))
    return parsed


def format_task_time(value) -> str:
    dt = parse_task_datetime(value)
    if dt is None:
        return str(value) if value else "未设置"

    today = date.today()
    task_date = dt.date()
    if task_date == today:
        day_text = "今天"
    elif task_date == today + timedelta(days=1):
        day_text = "明天"
    elif task_date == today + timedelta(days=2):
        day_text = "后天"
    else:
        return dt.strftime("%Y-%m-%d %H:%M")

    return f"{day_text} {dt.strftime('%H:%M')}"


def is_task_overdue(task) -> bool:
    if getattr(task, "is_completed", False):
        return False

    if task.task_type == "daily" or task.category == "daily":
        return False

    value = task.scheduled_at if task.task_type == "timed" or task.category == "timed" else task.ddl
    dt = parse_task_datetime(value)
    if dt is None:
        return False
    return dt < datetime.now()
