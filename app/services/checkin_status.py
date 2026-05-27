from datetime import date as date_cls, datetime, time


CHECKIN_DEADLINE = time(3, 59)


def get_task_effective_date(task, fallback=None):
    for attr in ("start_date", "effective_date", "created_at"):
        value = getattr(task, attr, None)
        parsed = parse_date(value)
        if parsed is not None:
            return parsed

    return fallback


def get_task_end_date(task):
    for attr in ("end_date", "archived_at", "stopped_at", "deleted_at"):
        parsed = parse_date(getattr(task, attr, None))
        if parsed is not None:
            return parsed

    return None


def get_checkin_cell_status(task, day, now, completed_dates):
    today = now.date()
    start_date = get_task_effective_date(task)
    end_date = get_task_end_date(task)
    date_str = day.isoformat()

    if start_date is not None and day < start_date:
        return "disabled"

    if end_date is not None and day > end_date:
        return "disabled"

    if day > today:
        return "disabled"

    if date_str in completed_dates:
        return "completed"

    if day == today:
        if now.time() > CHECKIN_DEADLINE:
            return "missed"
        return "today_pending"

    return "missed"


def parse_date(value):
    if not value:
        return None

    if isinstance(value, datetime):
        return value.date()

    if isinstance(value, date_cls):
        return value

    try:
        return datetime.fromisoformat(str(value)).date()
    except ValueError:
        try:
            return datetime.fromisoformat(str(value)[:10]).date()
        except ValueError:
            return None
