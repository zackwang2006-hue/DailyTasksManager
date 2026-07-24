from app.database.db_manager import DBManager
from app.models.plan import PlanPeriod
from app.models.priority import normalize_priority
from app.models.task import Task


class ReportDataService:
    def __init__(self, db: DBManager | None = None):
        self.db = db or DBManager()

    def collect_period_data(self, period: PlanPeriod) -> dict:
        tasks = self.get_period_tasks(period)
        logs = self.get_period_logs(period)
        logs_by_task_id = self.group_logs_by_task_id(logs)

        task_items = []
        seen_task_ids = set()
        for task in tasks:
            if task.task_id is not None:
                seen_task_ids.add(task.task_id)
            task_logs = logs_by_task_id.get(task.task_id, [])
            task_items.append(self.task_to_dict(task, task_logs))

        for log in logs:
            task_id = log["task_id"]
            if task_id in seen_task_ids:
                continue
            task_items.append(self.log_to_task_dict(log))

        completed_count = sum(1 for item in task_items if item["is_completed"])
        total_count = len(task_items)
        return {
            "period": {
                "type": period.level.value,
                "title": period.title,
                "start": period.start.isoformat(),
                "end": period.end.isoformat(),
            },
            "statistics": {
                "total": total_count,
                "completed": completed_count,
                "uncompleted": total_count - completed_count,
                "completion_rate": round(completed_count / total_count, 4) if total_count else 0,
            },
            "tasks": task_items,
        }

    def has_meaningful_data(self, period_data: dict) -> bool:
        return bool(period_data.get("tasks"))

    def get_period_tasks(self, period: PlanPeriod) -> list[Task]:
        rows = self.db.fetch_all(
            """
            SELECT *
            FROM tasks
            WHERE plan_level = ?
              AND period_start = ?
              AND period_end = ?
            ORDER BY is_completed ASC, created_at ASC, id ASC
            """,
            (period.level.value, period.start.isoformat(), period.end.isoformat()),
        )
        return [Task.from_row(row) for row in rows]

    def get_period_logs(self, period: PlanPeriod):
        return self.db.fetch_all(
            """
            SELECT *
            FROM task_logs
            WHERE COALESCE(record_date, date(completed_at)) BETWEEN ? AND ?
            ORDER BY completed_at ASC, id ASC
            """,
            (period.start.isoformat(), period.end.isoformat()),
        )

    def group_logs_by_task_id(self, logs) -> dict[int, list]:
        grouped = {}
        for log in logs:
            task_id = log["task_id"]
            if task_id is None:
                continue
            grouped.setdefault(task_id, []).append(log)
        return grouped

    def task_to_dict(self, task: Task, logs: list) -> dict:
        latest_log = logs[-1] if logs else None
        completion_note = None
        if latest_log is not None and "completion_note" in latest_log.keys():
            completion_note = latest_log["completion_note"]
        return {
            "task_id": task.task_id,
            "title": task.title,
            "description": task.description,
            "minimal_action": getattr(task, "minimal_action", "") or "",
            "plan_level": task.plan_level,
            "period_key": task.period_key,
            "priority_level": normalize_priority(task.priority_level),
            "is_fixed_event": bool(task.is_fixed_event),
            "fixed_time": task.fixed_time,
            "scheduled_at": task.scheduled_at,
            "is_completed": bool(task.is_completed),
            "is_deleted": bool(task.is_deleted),
            "archived": bool(task.archived),
            "completed_at": task.completed_at or (latest_log["completed_at"] if latest_log else None),
            "completion_note": completion_note or "",
            "created_at": task.created_at,
            "source": "tasks",
        }

    def log_to_task_dict(self, log) -> dict:
        completion_note = log["completion_note"] if "completion_note" in log.keys() else ""
        return {
            "task_id": log["task_id"],
            "title": log["title"],
            "description": log["description"] or "",
            "minimal_action": "",
            "plan_level": None,
            "period_key": None,
            "priority_level": None,
            "is_fixed_event": log["task_type"] == "timed" or log["category"] == "timed",
            "fixed_time": None,
            "scheduled_at": log["scheduled_at"],
            "is_completed": True,
            "is_deleted": None,
            "archived": None,
            "completed_at": log["completed_at"],
            "completion_note": completion_note or "",
            "created_at": log["created_at"],
            "source": "task_logs",
        }
