from dataclasses import dataclass


@dataclass
class Task:
    task_id: int | None = None
    title: str = ""
    description: str = ""
    category: str = "short"
    ddl: str | None = None
    task_type: str = "normal"
    scheduled_at: str | None = None
    is_completed: bool = False
    is_deleted: bool = False
    created_at: str | None = None
    completed_at: str | None = None
    plan_level: str | None = None
    period_key: str | None = None
    period_start: str | None = None
    period_end: str | None = None
    archived: bool = False
    parent_plan_task_id: int | None = None
    source_daily_task_id: int | None = None
    generated_date: str | None = None
    is_important: bool = False
    is_urgent: bool = False
    is_fixed_event: bool = False
    priority_level: int = 4
    fixed_time: str | None = None
    minimal_action: str = ""

    @classmethod
    def from_row(cls, row):
        keys = row.keys()

        scheduled_at = row["scheduled_at"] if "scheduled_at" in keys else None
        fixed_time = row["fixed_time"] if "fixed_time" in keys else None
        minimal_action = row["minimal_action"] if "minimal_action" in keys else None
        minimal_action = (minimal_action or "").strip() or ((row["title"] or "").strip()[:12] or "开始行动")
        return cls(
            task_id=row["id"],
            title=row["title"],
            description=row["description"] or "",
            category=row["category"],
            ddl=row["ddl"],
            task_type=row["task_type"] if "task_type" in keys else "normal",
            scheduled_at=scheduled_at,
            is_completed=bool(row["is_completed"]),
            is_deleted=bool(row["is_deleted"]) if "is_deleted" in keys else False,
            created_at=row["created_at"],
            completed_at=row["completed_at"],
            plan_level=row["plan_level"] if "plan_level" in keys else None,
            period_key=row["period_key"] if "period_key" in keys else None,
            period_start=row["period_start"] if "period_start" in keys else None,
            period_end=row["period_end"] if "period_end" in keys else None,
            archived=bool(row["archived"]) if "archived" in keys else False,
            parent_plan_task_id=row["parent_plan_task_id"] if "parent_plan_task_id" in keys else None,
            source_daily_task_id=row["source_daily_task_id"] if "source_daily_task_id" in keys else None,
            generated_date=row["generated_date"] if "generated_date" in keys else None,
            is_important=bool(row["is_important"]) if "is_important" in keys else False,
            is_urgent=bool(row["is_urgent"]) if "is_urgent" in keys else False,
            is_fixed_event=bool(row["is_fixed_event"]) if "is_fixed_event" in keys else False,
            priority_level=row["priority_level"] if "priority_level" in keys else 4,
            fixed_time=fixed_time,
            minimal_action=minimal_action,
        )
