from datetime import date, datetime, time, timedelta

from app.database.db_manager import DBManager
from app.models.plan import PlanLevel
from app.models.priority import normalize_priority_state
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

MINIMAL_ACTION_MAX_LENGTH = 12
DEFAULT_MINIMAL_ACTION = "开始行动"
MIN_COMPLETION_NOTE_CHARS = 5


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
        fixed_time=None,
        plan_level=None,
        period_key=None,
        period_start=None,
        period_end=None,
        archived=False,
        parent_plan_task_id=None,
        source_daily_task_id=None,
        generated_date=None,
        is_important=False,
        is_urgent=False,
        is_fixed_event=False,
        minimal_action=None,
        now=None,
    ):
        now_value = now or datetime.now()
        if isinstance(now_value, date) and not isinstance(now_value, datetime):
            now_value = datetime.combine(now_value, time.min)
        elif not isinstance(now_value, datetime):
            now_value = datetime.fromisoformat(str(now_value))
        created_at = now_value.isoformat(timespec="seconds")

        normalized_plan_level = self.normalize_plan_level(plan_level)
        is_day_plan = normalized_plan_level == PlanLevel.DAY.value
        is_daily_task = category == "daily" or task_type == "daily"
        requires_minimal_action = is_day_plan or is_daily_task
        minimal_action = self.normalize_minimal_action(
            minimal_action,
            title=title,
            required=requires_minimal_action and minimal_action is not None,
        )
        fixed_time = fixed_time or self.time_part(scheduled_at)

        if plan_level:
            category = "plan"
            task_type = "normal"
            ddl = None
            if not is_day_plan:
                scheduled_at = None
                fixed_time = None
                is_important = False
                is_urgent = False
                is_fixed_event = False
        elif category == "timed" or task_type == "timed":
            category = "timed"
            task_type = "timed"
            ddl = None
            is_important = False
            is_urgent = False
            is_fixed_event = False
            fixed_time = self.time_part(scheduled_at)
        else:
            task_type = "daily" if category == "daily" else "normal"
            if task_type != "daily":
                scheduled_at = None
                fixed_time = None
                is_important = False
                is_urgent = False
                is_fixed_event = False
            if task_type == "daily" and not ddl:
                ddl = get_daily_default_deadline(now_value).strftime("%Y-%m-%d %H:%M:%S")

        if not is_day_plan and not is_daily_task:
            scheduled_at = None
            fixed_time = None
            is_important = False
            is_urgent = False
            is_fixed_event = False
        priority_state = normalize_priority_state(
            fixed_time,
            is_urgent=is_urgent,
            is_important=is_important,
            is_fixed_event=is_fixed_event,
        )
        fixed_time = priority_state["fixed_time"]
        is_important = priority_state["is_important"]
        is_urgent = priority_state["is_urgent"]
        is_fixed_event = priority_state["is_fixed_event"]
        priority_level = priority_state["priority_level"]
        if is_fixed_event and is_day_plan:
            scheduled_at = self.compose_scheduled_at(period_start, fixed_time)
        elif is_daily_task and category == "daily":
            scheduled_at = None
        elif not is_fixed_event and not (category == "timed" or task_type == "timed"):
            scheduled_at = None

        sql = """
        INSERT INTO tasks (
            title, description, category, ddl, task_type, scheduled_at,
            is_completed, is_deleted, created_at, completed_at,
            plan_level, period_key, period_start, period_end, archived,
            parent_plan_task_id, source_daily_task_id, generated_date,
            is_important, is_urgent, is_fixed_event, priority_level, fixed_time,
            minimal_action
        )
        VALUES (?, ?, ?, ?, ?, ?, 0, 0, ?, NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                normalized_plan_level,
                period_key,
                period_start,
                period_end,
                1 if archived else 0,
                parent_plan_task_id,
                source_daily_task_id,
                generated_date,
                1 if is_important else 0,
                1 if is_urgent else 0,
                1 if is_fixed_event else 0,
                priority_level,
                fixed_time,
                minimal_action,
            ),
        )

    def add_plan_task(
        self,
        title,
        description="",
        plan_level=PlanLevel.DAY,
        scheduled_at=None,
        fixed_time=None,
        is_important=False,
        is_urgent=False,
        is_fixed_event=False,
        minimal_action=None,
        now=None,
    ):
        period = period_service.current_period(plan_level, now)
        return self.add_task(
            title=title,
            description=description,
            category="plan",
            ddl=None,
            task_type="normal",
            scheduled_at=scheduled_at,
            fixed_time=fixed_time,
            plan_level=period.level,
            period_key=period.key,
            period_start=period.start.isoformat(),
            period_end=period.end.isoformat(),
            archived=False,
            is_important=is_important,
            is_urgent=is_urgent,
            is_fixed_event=is_fixed_event,
            minimal_action=minimal_action,
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
        scheduled_at=None,
        fixed_time=None,
        is_important=False,
        is_urgent=False,
        is_fixed_event=False,
        minimal_action=None,
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
            scheduled_at=scheduled_at,
            fixed_time=fixed_time,
            plan_level=PlanLevel.DAY,
            period_key=period.key,
            period_start=period.start.isoformat(),
            period_end=period.end.isoformat(),
            archived=False,
            parent_plan_task_id=parent_plan_task_id,
            source_daily_task_id=source_daily_task_id,
            generated_date=generated_date.isoformat(),
            is_important=is_important,
            is_urgent=is_urgent,
            is_fixed_event=is_fixed_event,
            minimal_action=minimal_action,
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

    def add_daily_task_rule(
        self,
        title,
        description,
        parent_plan_task_id,
        scheduled_at=None,
        fixed_time=None,
        is_important=False,
        is_urgent=False,
        is_fixed_event=False,
        minimal_action=None,
        today=None,
    ):
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
            scheduled_at=scheduled_at,
            fixed_time=fixed_time,
            plan_level=None,
            period_key=None,
            period_start=target_date.isoformat(),
            period_end=parent_period_end.isoformat(),
            archived=False,
            parent_plan_task_id=parent.task_id,
            source_daily_task_id=None,
            generated_date=None,
            is_important=is_important,
            is_urgent=is_urgent,
            is_fixed_event=is_fixed_event,
            minimal_action=minimal_action,
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
                    scheduled_at=self.compose_scheduled_at(target_date, template.fixed_time),
                    fixed_time=template.fixed_time,
                    is_important=template.is_important,
                    is_urgent=template.is_urgent,
                    is_fixed_event=template.is_fixed_event,
                    minimal_action=template.minimal_action,
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

    def normalize_completion_note(self, completion_note):
        text = (completion_note or "").strip()
        effective_length = len("".join(str(text).split()))
        if effective_length < MIN_COMPLETION_NOTE_CHARS:
            raise ValueError("完成情况至少填写5个有效字符")
        return text

    def complete_task(self, task_id, completion_note=None):
        return self.complete_task_with_daily_sync(task_id, completion_note)

    def complete_task_with_daily_sync(self, task_id, completion_note=None):
        task = self.get_task_by_id(task_id)

        if task is None:
            raise ValueError("对应任务不存在")
        if task.is_completed:
            raise ValueError("任务已经完成")
        completion_note = self.normalize_completion_note(completion_note)

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
                    completion_note,
                )
            elif task.source_daily_task_id and task.generated_date:
                self.upsert_daily_checkin(
                    cursor,
                    task.source_daily_task_id,
                    task.generated_date,
                    True,
                    completed_at,
                    completion_note,
                )

            task.completed_at = completed_at
            self.history_service.add_task_log(task, completion_note=completion_note, cursor=cursor)
        return True

    def set_daily_checkin_with_plan_sync(self, daily_task_id, target_date=None, completed=True, completion_note=None):
        target_date = period_service.normalize_date(target_date)
        completed = bool(completed)
        timestamp = datetime.now().isoformat(timespec="seconds")
        if completed:
            completion_note = self.normalize_completion_note(completion_note)

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
                completion_note if completed else None,
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
                    self.history_service.add_task_log(
                        generated_task,
                        completion_note=completion_note,
                        cursor=cursor,
                    )
        return True

    def upsert_daily_checkin(self, cursor, task_id, checkin_date, completed, completed_at, completion_note=None):
        cursor.execute(
            """
            INSERT INTO daily_checkins (task_id, checkin_date, is_completed, completed_at, completion_note)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(task_id, checkin_date) DO UPDATE SET
                is_completed = excluded.is_completed,
                completed_at = excluded.completed_at,
                completion_note = excluded.completion_note
            """,
            (task_id, checkin_date, 1 if completed else 0, completed_at, completion_note),
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

    def normalize_minimal_action(self, minimal_action, title="", required=False):
        if minimal_action is None:
            text = ""
        else:
            text = str(minimal_action).strip()

        if not text:
            if required:
                raise ValueError("请填写最小动作")
            text = (title or "").strip()[:MINIMAL_ACTION_MAX_LENGTH] or DEFAULT_MINIMAL_ACTION

        if len(text) > MINIMAL_ACTION_MAX_LENGTH:
            raise ValueError("最小动作不能超过12个字符")
        return text

    def time_part(self, value):
        if not value:
            return None
        text = str(value).strip()
        if len(text) >= 19 and text[10] in {" ", "T"}:
            text = text[11:19]
        elif len(text) >= 8:
            text = text[:8]
        try:
            return time.fromisoformat(text).strftime("%H:%M:%S")
        except ValueError:
            return None

    def compose_scheduled_at(self, target_date, fixed_time):
        fixed_time = self.time_part(fixed_time)
        if not fixed_time:
            return None
        target_date = period_service.normalize_date(target_date)
        return f"{target_date.isoformat()}T{fixed_time}"

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
        fixed_time=None,
        is_important=False,
        is_urgent=False,
        is_fixed_event=False,
        minimal_action=None,
    ):
        task = self.get_task_by_id(task_id)
        normalized_plan_level = self.normalize_plan_level(getattr(task, "plan_level", None))
        is_day_plan = normalized_plan_level == PlanLevel.DAY.value
        is_daily_task = category == "daily" or task_type == "daily"
        minimal_action = self.normalize_minimal_action(
            minimal_action if minimal_action is not None else getattr(task, "minimal_action", None),
            title=title,
            required=(is_day_plan or is_daily_task) and minimal_action is not None,
        )
        fixed_time = fixed_time or self.time_part(scheduled_at)

        if category == "timed" or task_type == "timed":
            category = "timed"
            task_type = "timed"
            ddl = None
            is_important = False
            is_urgent = False
            is_fixed_event = False
            fixed_time = self.time_part(scheduled_at)
        else:
            task_type = "daily" if category == "daily" else "normal"
            if not is_day_plan and task_type != "daily":
                scheduled_at = None
                fixed_time = None
                is_important = False
                is_urgent = False
                is_fixed_event = False
            if task_type == "daily" and not ddl:
                ddl = get_daily_default_deadline().strftime("%Y-%m-%d %H:%M:%S")

        if not is_day_plan and not is_daily_task:
            scheduled_at = None
            fixed_time = None
            is_important = False
            is_urgent = False
            is_fixed_event = False
        priority_state = normalize_priority_state(
            fixed_time,
            is_urgent=is_urgent,
            is_important=is_important,
            is_fixed_event=is_fixed_event,
        )
        fixed_time = priority_state["fixed_time"]
        is_important = priority_state["is_important"]
        is_urgent = priority_state["is_urgent"]
        is_fixed_event = priority_state["is_fixed_event"]
        priority_level = priority_state["priority_level"]
        if is_fixed_event and is_day_plan:
            scheduled_at = self.compose_scheduled_at(task.period_start, fixed_time)
        elif is_daily_task and category == "daily":
            scheduled_at = None
        elif not is_fixed_event and not (category == "timed" or task_type == "timed"):
            scheduled_at = None

        sql = """
        UPDATE tasks
        SET title = ?,
            description = ?,
            category = ?,
            ddl = ?,
            task_type = ?,
            scheduled_at = ?,
            is_important = ?,
            is_urgent = ?,
            is_fixed_event = ?,
            priority_level = ?,
            fixed_time = ?,
            minimal_action = ?
        WHERE id = ?
        """

        self.db.execute(
            sql,
            (
                title,
                description,
                category,
                ddl,
                task_type,
                scheduled_at,
                1 if is_important else 0,
                1 if is_urgent else 0,
                1 if is_fixed_event else 0,
                priority_level,
                fixed_time,
                minimal_action,
                task_id,
            )
        )

    def normalize_plan_level(self, plan_level):
        if plan_level is None:
            return None
        if isinstance(plan_level, PlanLevel):
            return plan_level.value
        return str(plan_level)
