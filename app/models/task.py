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

    @classmethod
    def from_row(cls, row):
        keys = row.keys()

        return cls(
            task_id=row["id"],
            title=row["title"],
            description=row["description"] or "",
            category=row["category"],
            ddl=row["ddl"],
            task_type=row["task_type"] if "task_type" in keys else "normal",
            scheduled_at=row["scheduled_at"] if "scheduled_at" in keys else None,
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
        )
