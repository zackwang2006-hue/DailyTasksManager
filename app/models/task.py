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
        )
