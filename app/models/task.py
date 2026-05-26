from dataclasses import dataclass


@dataclass
class Task:
    task_id: int | None = None
    title: str = ""
    description: str = ""
    category: str = "short"
    ddl: str | None = None
    is_completed: bool = False
    is_highlighted: bool = False
    created_at: str | None = None
    completed_at: str | None = None

    @classmethod
    def from_row(cls, row):
        return cls(
            task_id=row["id"],
            title=row["title"],
            description=row["description"] or "",
            category=row["category"],
            ddl=row["ddl"],
            is_completed=bool(row["is_completed"]),
            is_highlighted=bool(row["is_highlighted"]),
            created_at=row["created_at"],
            completed_at=row["completed_at"],
        )