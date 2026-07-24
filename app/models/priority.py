PRIORITY_SCHEMA_MIGRATION = "20260724_priority_schema"

PRIORITY_CARD_COLORS = {
    0: "#E05AA9",
    1: "#FF8A3D",
    2: "#F6D76B",
    3: "#48CFAE",
    4: "#72B8E8",
}

PRIORITY_TEXT_COLOR = "#181818"


def calculate_priority(is_fixed_event: bool, is_urgent: bool, is_important: bool) -> int:
    if is_fixed_event:
        return 0
    if is_urgent and is_important:
        return 1
    if is_urgent:
        return 2
    if is_important:
        return 3
    return 4


def normalize_priority_state(fixed_time=None, is_urgent=False, is_important=False, is_fixed_event=False):
    if is_fixed_event and fixed_time:
        return {
            "fixed_time": fixed_time,
            "is_fixed_event": True,
            "is_urgent": False,
            "is_important": False,
            "priority_level": calculate_priority(True, False, False),
        }
    if is_fixed_event:
        raise ValueError("固定事件必须设置固定时间")
    return {
        "fixed_time": None,
        "is_fixed_event": False,
        "is_urgent": bool(is_urgent),
        "is_important": bool(is_important),
        "priority_level": calculate_priority(False, bool(is_urgent), bool(is_important)),
    }


def normalize_priority(value) -> int:
    try:
        priority = int(value)
    except (TypeError, ValueError):
        return 4
    return max(0, min(4, priority))


def priority_card_color(priority_level) -> str:
    return PRIORITY_CARD_COLORS[normalize_priority(priority_level)]
