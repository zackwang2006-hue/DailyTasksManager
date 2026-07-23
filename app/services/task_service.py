from datetime import date, datetime, time, timedelta

from app.database.db_manager import DBManager
from app.models.plan import PlanLevel
from app.models.task import Task
from app.services.checkin_service import CheckinService
from app.services.history_service import HistoryService
from app.services.period_service import period_service
from app.utils.time_utils import get_daily_default_deadline


DAILY_TASK_PARENT_LEVELS = (
    PlanLevel.WEEK,
    PlanLevel.MONTH,
    PlanLevel.QUARTER,
    PlanLevel.YEAR,
    PlanLevel.FIVE_YEAR,
)


class TaskService:
    def __init__(self):
        self.db = DBManager()
        self.history_service = HistoryService()
        self.checkin_service = CheckinService()

    def add_task(
        self,
        title,
        description="",
        category="short",
        ddl=None,
        task_type="normal",
        scheduled_at=None,
        plan_level=None,
        period_key=None,
        period_start=None,
        period_end=None,
        archived=False,
        parent_plan_task_id=None,
        source_daily_task_id=None,
        generated_date=None,
        now=None,
    ):
        now_value = now or datetime.now()
        if isinstance(now_value, date) and not isinstance(now_value, datetime):
            now_value = datetime.combine(now_value, time.min)
        elif not isinstance(now_value, datetime):
            now_value = datetime.fromisoformat(str(now_value))
        created_at = now_value.isoformat(timespec="seconds")

        if plan_level:
            category = "plan"
            task_type = "normal"
            scheduled_at = None
            ddl = None
        elif category == "timed" or task_type == "timed":
            category = "timed"
            task_type = "timed"
            ddl = None
        else:
            task_type = "daily" if category == "daily" else "normal"
            scheduled_at = None
            if task_type == "daily" and not ddl:
                ddl = get_daily_default_deadline(now_value).strftime("%Y-%m-%d %H:%M:%S")

        sql = """
        INSERT INTO tasks (
            title, description, category, ddl, task_type, scheduled_at,
            is_completed, is_deleted, created_at, completed_at,
            plan_level, period_key, period_start, period_end, archived,
            parent_plan_task_id, source_daily_task_id, generated_date
        )
        VALUES (?, ?, ?, ?, ?, ?, 0, 0, ?, NULL, ?, ?, ?, ?, ?, ?, ?, ?)
        """

        return self.db.execute(
            sql,
            (
                title,
                description,
                category,
                ddl,
                task_type,
                scheduled_at,
                created_at,
                self.normalize_plan_level(plan_level),
                period_key,
                period_start,
                period_end,
                1 if archived else 0,
                parent_plan_task_id,
                source_daily_task_id,
                generated_date,
            ),
        )

    def add_plan_task(self, title, description="", plan_level=PlanLevel.DAY, now=None):
        period = period_service.current_period(plan_level, now)
        return self.add_task(
            title=title,
            description=description,
            category="plan",
            ddl=None,
            task_type="normal",
            scheduled_at=None,
            plan_level=period.level,
            period_key=period.key,
            period_start=period.start.isoformat(),
            period_end=period.end.isoformat(),
            archived=False,
            now=now,
        )

    def get_tasks_by_plan_period(
        self,
        plan_level,
        period_key,
        include_completed=False,
        include_archived=False,
    ):
        sql = """
        SELECT *
        FROM tasks
        WHERE plan_level = ?
          AND period_key = ?
          AND COALESCE(is_deleted, 0) = 0
        """
        params = [self.normalize_plan_level(plan_level), period_key]
        if not include_completed:
            sql += " AND is_completed = 0"
        if not include_archived:
            sql += " AND COALESCE(archived, 0) = 0"
        sql += """
        ORDER BY
            is_completed ASC,
            created_at DESC,
            id DESC
        """
        rows = self.db.fetch_all(sql, params)
        return [Task.from_row(row) for row in rows]

    def get_current_plan_tasks(self, plan_level, today=None, **kwargs):
        if PlanLevel(plan_level) == PlanLevel.DAY:
            self.ensure_daily_plan_tasks_for_date(today)
        period = period_service.current_period(plan_level, today)
        return self.get_tasks_by_plan_period(plan_level, period.key, **kwargs)

    def get_previous_plan_tasks(self, plan_level, today=None, **kwargs):
        period = period_service.previous_period(plan_level, today)
        return self.get_tasks_by_plan_period(plan_level, period.key, **kwargs)

    def get_or_create_generated_daily_plan_task(
        self,
        source_daily_task_id,
        parent_plan_task_id,
        generated_date,
        title,
        description="",
    ):
        generated_date = period_service.normalize_date(generated_date)
        existing = self.get_generated_daily_plan_task(source_daily_task_id, generated_date)
        if existing is not None:
            return existing.task_id

        period = period_service.current_period(PlanLevel.DAY, generated_date)
        return self.add_task(
            title=title,
            description=description,
            category="plan",
            ddl=None,
            task_type="normal",
            scheduled_at=None,
            plan_level=PlanLevel.DAY,
            period_key=period.key,
            period_start=period.start.isoformat(),
            period_end=period.end.isoformat(),
            archived=False,
            parent_plan_task_id=parent_plan_task_id,
            source_daily_task_id=source_daily_task_id,
            generated_date=generated_date.isoformat(),
        )

    def get_generated_daily_plan_task(self, source_daily_task_id, generated_date):
        generated_date = period_service.normalize_date(generated_date).isoformat()
        sql = """
        SELECT *
        FROM tasks
        WHERE source_daily_task_id = ?
          AND generated_date = ?
          AND COALESCE(is_deleted, 0) = 0
        LIMIT 1
        """
        row = self.db.fetch_one(sql, (source_daily_task_id, generated_date))
        return Task.from_row(row) if row is not None else None

    def add_daily_task_rule(self, title, description, parent_plan_task_id, today=None):
        target_date = period_service.normalize_date(today)
        parent = self.get_task_by_id(parent_plan_task_id)
        self.validate_daily_task_parent(parent, target_date)

        parent_period_end = self.parse_date(parent.period_end)
        task_id = self.add_task(
            title=title,
            description=description,
            category="daily",
            ddl=None,
            task_type="daily",
            scheduled_at=None,
            plan_level=None,
            period_key=None,
            period_start=target_date.isoformat(),
            period_end=parent_period_end.isoformat(),
            archived=False,
            parent_plan_task_id=parent.task_id,
            source_daily_task_id=None,
            generated_date=None,
            now=datetime.combine(target_date, time.min),
        )
        self.ensure_daily_plan_tasks_for_date(target_date)
        return task_id

    def validate_daily_task_parent(self, parent, target_date):
        if parent is None:
            raise ValueError("Parent plan task does not exist.")

        try:
            parent_level = PlanLevel(parent.plan_level)
        except (TypeError, ValueError):
            raise ValueError("Daily tasks must be attached to a plan task.") from None

        if parent_level not in DAILY_TASK_PARENT_LEVELS:
            raise ValueError("Daily tasks can only attach to week or longer plans.")
        if parent.is_deleted or parent.archived:
            raise ValueError("Parent plan task is not active.")

        period_start = self.parse_date(parent.period_start)
        period_end = self.parse_date(parent.period_end)
        if period_start is None or period_end is None:
            raise ValueError("Parent plan task has no valid period.")
        if not period_start <= target_date <= period_end:
            raise ValueError("Parent plan task is not in the current valid period.")

    def get_available_parent_plan_tasks(self, plan_level, today=None):
        plan_level = PlanLevel(plan_level)
        if plan_level not in DAILY_TASK_PARENT_LEVELS:
            return []
        period = period_service.current_period(plan_level, today)
        return self.get_tasks_by_plan_period(
            plan_level,
            period.key,
            include_completed=True,
            include_archived=False,
        )

    def ensure_daily_plan_tasks_for_date(self, target_date=None):
        target_date = period_service.normalize_date(target_date)
        self.expire_daily_tasks(target_date)

        sql = """
        SELECT *
        FROM tasks
        WHERE (task_type = 'daily' OR category = 'daily')
          AND parent_plan_task_id IS NOT NULL
          AND COALESCE(archived, 0) = 0
          AND COALESCE(is_deleted, 0) = 0
        """
        rows = self.db.fetch_all(sql)
        generated_ids = []

        for row in rows:
            template = Task.from_row(row)
            start_date = self.parse_date(template.period_start) or self.get_daily_task_start_date(template)
            end_date = self.parse_date(template.period_end)
            if start_date is None or end_date is None:
                continue
            if not start_date <= target_date <= end_date:
                continue

            parent = self.get_task_by_id(template.parent_plan_task_id)
            if parent is None or parent.archived:
                self.archive_daily_tasks_for_parent(template.parent_plan_task_id)
                continue

            generated_ids.append(
                self.get_or_create_generated_daily_plan_task(
                    source_daily_task_id=template.task_id,
                    parent_plan_task_id=template.parent_plan_task_id,
                    generated_date=target_date,
                    title=template.title,
                    description=template.description,
                )
            )

        return generated_ids

    def expire_daily_tasks(self, reference_date=None):
        reference_date = period_service.normalize_date(reference_date).isoformat()
        sql = """
        UPDATE tasks
        SET archived = 1
        WHERE (task_type = 'daily' OR category = 'daily')
          AND parent_plan_task_id IS NOT NULL
          AND period_end IS NOT NULL
          AND period_end < ?
          AND COALESCE(archived, 0) = 0
          AND COALESCE(is_deleted, 0) = 0
        """
        self.db.execute(sql, (reference_date,))

    def archive_daily_tasks_for_parent(self, parent_plan_task_id):
        sql = """
        UPDATE tasks
        SET archived = 1
        WHERE (task_type = 'daily' OR category = 'daily')
          AND parent_plan_task_id = ?
          AND COALESCE(archived, 0) = 0
          AND COALESCE(is_deleted, 0) = 0
        """
        self.db.execute(sql, (parent_plan_task_id,))

    def has_active_daily_tasks_for_parent(self, parent_plan_task_id):
        sql = """
        SELECT 1
        FROM tasks
        WHERE (task_type = 'daily' OR category = 'daily')
          AND parent_plan_task_id = ?
          AND COALESCE(archived, 0) = 0
          AND COALESCE(is_deleted, 0) = 0
        LIMIT 1
        """
        return self.db.fetch_one(sql, (parent_plan_task_id,)) is not None

    def get_uncompleted_tasks(self):
        self.refresh_daily_tasks()

        sql = """
        SELECT *
        FROM tasks
        WHERE is_completed = 0
          AND COALESCE(is_deleted, 0) = 0
        ORDER BY 
            CASE WHEN task_type = 'timed' THEN 0 ELSE 1 END,
            CASE WHEN task_type = 'timed' THEN scheduled_at END ASC,
            ddl IS NULL,
            ddl ASC,
            created_at DESC
        """

        rows = self.db.fetch_all(sql)
        return [Task.from_row(row) for row in rows]

    def get_completed_tasks(self):
        sql = """
        SELECT *
        FROM tasks
        WHERE is_completed = 1
          AND COALESCE(is_deleted, 0) = 0
        ORDER BY completed_at DESC
        """

        rows = self.db.fetch_all(sql)
        return [Task.from_row(row) for row in rows]

    def get_timed_tasks(self):
        sql = """
        SELECT *
        FROM tasks
        WHERE is_completed = 0
          AND task_type = 'timed'
          AND COALESCE(is_deleted, 0) = 0
        ORDER BY
            scheduled_at IS NULL,
            scheduled_at ASC,
            created_at DESC
        """

        rows = self.db.fetch_all(sql)
        return [Task.from_row(row) for row in rows]

    def get_tasks_by_category(self, category):
        self.refresh_daily_tasks()

        sql = """
        SELECT *
        FROM tasks
        WHERE is_completed = 0
          AND category = ?
          AND COALESCE(is_deleted, 0) = 0
        ORDER BY
            CASE WHEN task_type = 'timed' THEN 0 ELSE 1 END,
            CASE WHEN task_type = 'timed' THEN scheduled_at END ASC,
            ddl IS NULL,
            ddl ASC,
            created_at DESC
        """

        rows = self.db.fetch_all(sql, (category,))
        return [Task.from_row(row) for row in rows]

    def complete_task(self, task_id):
        return self.complete_task_with_daily_sync(task_id)

    def complete_task_with_daily_sync(self, task_id):
        task = self.get_task_by_id(task_id)

        if task is None or task.is_completed:
            return False

        completed_time = datetime.now()
        completed_at = completed_time.isoformat(timespec="seconds")

        with self.db.transaction() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE tasks
                SET is_completed = 1,
                    completed_at = ?
                WHERE id = ?
                """,
                (completed_at, task_id),
            )

            if task.task_type == "daily" or task.category == "daily":
                checkin_date = period_service.get_local_today().isoformat()
                self.upsert_daily_checkin(
                    cursor,
                    task.task_id,
                    checkin_date,
                    True,
                    completed_at,
                )
            elif task.source_daily_task_id and task.generated_date:
                self.upsert_daily_checkin(
                    cursor,
                    task.source_daily_task_id,
                    task.generated_date,
                    True,
                    completed_at,
                )

        task.completed_at = completed_at
        self.history_service.add_task_log(task)
        return True

    def set_daily_checkin_with_plan_sync(self, daily_task_id, target_date=None, completed=True):
        target_date = period_service.normalize_date(target_date)
        completed = bool(completed)
        timestamp = datetime.now().isoformat(timespec="seconds")

        if completed:
            self.ensure_daily_plan_tasks_for_date(target_date)

        generated_task = self.get_generated_daily_plan_task(daily_task_id, target_date)
        should_log_generated_task = (
            completed
            and generated_task is not None
            and not generated_task.is_completed
        )

        with self.db.transaction() as conn:
            cursor = conn.cursor()
            self.upsert_daily_checkin(
                cursor,
                daily_task_id,
                target_date.isoformat(),
                completed,
                timestamp,
            )

            if generated_task is not None:
                if completed:
                    cursor.execute(
                        """
                        UPDATE tasks
                        SET is_completed = 1,
                            completed_at = COALESCE(completed_at, ?)
                        WHERE id = ?
                        """,
                        (timestamp, generated_task.task_id),
                    )
                    generated_task.completed_at = generated_task.completed_at or timestamp
                else:
                    cursor.execute(
                        """
                        UPDATE tasks
                        SET is_completed = 0,
                            completed_at = NULL
                        WHERE id = ?
                        """,
                        (generated_task.task_id,),
                    )

        if should_log_generated_task:
            self.history_service.add_task_log(generated_task)
        return True

    def upsert_daily_checkin(self, cursor, task_id, checkin_date, completed, completed_at):
        cursor.execute(
            """
            INSERT INTO daily_checkins (task_id, checkin_date, is_completed, completed_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(task_id, checkin_date) DO UPDATE SET
                is_completed = excluded.is_completed,
                completed_at = excluded.completed_at
            """,
            (task_id, checkin_date, 1 if completed else 0, completed_at),
        )

    def get_daily_tasks(self):
        self.refresh_daily_tasks()

        sql = """
        SELECT *
        FROM tasks
        WHERE (task_type = 'daily' OR category = 'daily')
          AND COALESCE(is_deleted, 0) = 0
          AND (
              parent_plan_task_id IS NULL
              OR COALESCE(archived, 0) = 0
          )
        ORDER BY created_at DESC
        """

        rows = self.db.fetch_all(sql)
        return [Task.from_row(row) for row in rows]

    def refresh_daily_tasks(self, now=None):
        today = (
            period_service.normalize_date(now)
            if now is not None
            else period_service.get_local_today()
        )
        self.settle_daily_checkins(today)

        sql = """
        UPDATE tasks
        SET is_completed = 0,
            completed_at = NULL
        WHERE (task_type = 'daily' OR category = 'daily')
          AND is_completed = 1
          AND COALESCE(is_deleted, 0) = 0
          AND NOT EXISTS (
              SELECT 1
              FROM daily_checkins
              WHERE daily_checkins.task_id = tasks.id
                AND daily_checkins.checkin_date = ?
                AND daily_checkins.is_completed = 1
          )
        """

        self.db.execute(sql, (today.isoformat(),))

    def get_daily_cycle_date(self, value):
        return period_service.normalize_date(value)

    def settle_daily_checkins(self, today):
        sql = """
        SELECT *
        FROM tasks
        WHERE (task_type = 'daily' OR category = 'daily')
          AND COALESCE(is_deleted, 0) = 0
        """
        rows = self.db.fetch_all(sql)

        for row in rows:
            task = Task.from_row(row)
            start_date = self.get_daily_task_start_date(task)
            if start_date is None or start_date >= today:
                continue

            if task.is_completed and task.completed_at:
                completed_time = self.parse_datetime(task.completed_at)
                if completed_time is not None:
                    completed_date = period_service.normalize_date(completed_time)
                    if start_date <= completed_date < today:
                        self.checkin_service.add_daily_checkin(
                            task.task_id,
                            completed_date.isoformat(),
                            task.completed_at,
                        )

            existing_dates = self.get_daily_checkin_dates(task.task_id)
            day = start_date
            while day < today:
                date_str = day.isoformat()
                if date_str not in existing_dates:
                    settled_at = datetime.combine(day + timedelta(days=1), time.min).isoformat(timespec="seconds")
                    self.checkin_service.add_daily_missed(task.task_id, date_str, settled_at)
                day += timedelta(days=1)

    def get_daily_task_start_date(self, task):
        dates = []
        for value in (task.created_at, task.scheduled_at):
            parsed = self.parse_datetime(value)
            if parsed is not None:
                dates.append(parsed.date())
        return max(dates) if dates else None

    def get_daily_checkin_dates(self, task_id):
        sql = """
        SELECT checkin_date
        FROM daily_checkins
        WHERE task_id = ?
        """
        rows = self.db.fetch_all(sql, (task_id,))
        return {row["checkin_date"] for row in rows}

    def parse_datetime(self, value):
        if not value:
            return None
        try:
            return datetime.fromisoformat(str(value))
        except ValueError:
            try:
                return datetime.fromisoformat(str(value)[:10])
            except ValueError:
                return None

    def parse_date(self, value):
        if not value:
            return None
        if isinstance(value, date) and not isinstance(value, datetime):
            return value
        if isinstance(value, datetime):
            return value.date()
        try:
            return datetime.fromisoformat(str(value)[:10]).date()
        except ValueError:
            return None

    def delete_task(self, task_id):
        task = self.get_task_by_id(task_id)

        if task is not None and (task.task_type == "daily" or task.category == "daily"):
            self.archive_daily_task(task_id)
            return

        if task is not None and task.plan_level:
            self.archive_daily_tasks_for_parent(task_id)

        sql = """
        DELETE FROM tasks
        WHERE id = ?
        """

        self.db.execute(sql, (task_id,))

    def archive_daily_task(self, task_id):
        sql = """
        UPDATE tasks
        SET archived = 1,
            is_deleted = 1
        WHERE id = ?
        """

        self.db.execute(sql, (task_id,))

    def soft_delete_task(self, task_id):
        sql = """
        UPDATE tasks
        SET is_deleted = 1
        WHERE id = ?
        """

        self.db.execute(sql, (task_id,))

    def get_task_by_id(self, task_id):
        sql = """
        SELECT *
        FROM tasks
        WHERE id = ?
          AND COALESCE(is_deleted, 0) = 0
        """

        row = self.db.fetch_one(sql, (task_id,))

        if row is None:
            return None

        return Task.from_row(row)

    def update_task(
        self,
        task_id,
        title,
        description,
        category,
        ddl,
        task_type="normal",
        scheduled_at=None,
    ):
        if category == "timed" or task_type == "timed":
            category = "timed"
            task_type = "timed"
            ddl = None
        else:
            task_type = "daily" if category == "daily" else "normal"
            scheduled_at = None
            if task_type == "daily" and not ddl:
                ddl = get_daily_default_deadline().strftime("%Y-%m-%d %H:%M:%S")

        sql = """
        UPDATE tasks
        SET title = ?,
            description = ?,
            category = ?,
            ddl = ?,
            task_type = ?,
            scheduled_at = ?
        WHERE id = ?
        """

        self.db.execute(
            sql,
            (title, description, category, ddl, task_type, scheduled_at, task_id)
        )

    def normalize_plan_level(self, plan_level):
        if plan_level is None:
            return None
        if isinstance(plan_level, PlanLevel):
            return plan_level.value
        return str(plan_level)
