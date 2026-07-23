from calendar import monthrange
from datetime import date, datetime, timedelta

from app.models.plan import PLAN_LEVEL_LABELS, PlanLevel, PlanPeriod


FIVE_YEAR_BASE_YEAR = 2026
FIVE_YEAR_SPAN = 5


class PeriodService:
    def __init__(self, date_provider=None):
        self._date_provider = date_provider

    def set_date_provider(self, date_provider):
        self._date_provider = date_provider

    def get_local_today(self):
        if self._date_provider is None:
            return date.today()
        return self.normalize_date(self._date_provider())

    def current_period(self, level, today=None):
        target_date = self.normalize_date(today)
        return self.period_for_date(level, target_date)

    def previous_period(self, level, today=None):
        current = self.current_period(level, today)
        previous_date = current.start - timedelta(days=1)
        return self.period_for_date(level, previous_date)

    def period_for_date(self, level, target_date):
        level = self.normalize_level(level)
        target_date = self.normalize_date(target_date)

        if level == PlanLevel.DAY:
            start = end = target_date
            title = self.format_date_cn(start)
            display_text = title
        elif level == PlanLevel.WEEK:
            start = target_date - timedelta(days=target_date.weekday())
            end = start + timedelta(days=6)
            title = f"{self.format_date_cn(start)} - {self.format_date_cn(end)}"
            display_text = title
        elif level == PlanLevel.MONTH:
            start = date(target_date.year, target_date.month, 1)
            end = date(target_date.year, target_date.month, monthrange(target_date.year, target_date.month)[1])
            title = f"{target_date.year}年{target_date.month}月"
            display_text = f"{self.format_date_cn(start)} - {self.format_date_cn(end)}"
        elif level == PlanLevel.QUARTER:
            quarter = (target_date.month - 1) // 3 + 1
            start_month = (quarter - 1) * 3 + 1
            end_month = start_month + 2
            start = date(target_date.year, start_month, 1)
            end = date(target_date.year, end_month, monthrange(target_date.year, end_month)[1])
            title = f"{target_date.year}年第{quarter}季度"
            display_text = f"{title}\n{self.format_date_cn(start)} - {self.format_date_cn(end)}"
        elif level == PlanLevel.YEAR:
            start = date(target_date.year, 1, 1)
            end = date(target_date.year, 12, 31)
            title = f"{target_date.year}年"
            display_text = f"{self.format_date_cn(start)} - {self.format_date_cn(end)}"
        elif level == PlanLevel.FIVE_YEAR:
            start_year = self.five_year_start(target_date.year)
            end_year = start_year + FIVE_YEAR_SPAN - 1
            start = date(start_year, 1, 1)
            end = date(end_year, 12, 31)
            title = f"{start_year}年 - {end_year}年"
            display_text = title
        else:
            raise ValueError(f"Unsupported plan level: {level}")

        return PlanPeriod(
            level=level,
            start=start,
            end=end,
            key=self.period_key(level, start),
            title=title,
            display_text=display_text,
        )

    def period_key(self, level, start):
        level = self.normalize_level(level)
        return f"{level.value}:{start.isoformat()}"

    def five_year_start(self, year):
        offset = (int(year) - FIVE_YEAR_BASE_YEAR) // FIVE_YEAR_SPAN
        return FIVE_YEAR_BASE_YEAR + offset * FIVE_YEAR_SPAN

    def normalize_level(self, level):
        if isinstance(level, PlanLevel):
            return level
        return PlanLevel(str(level))

    def normalize_date(self, value=None):
        if value is None:
            return self.get_local_today()
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        return datetime.fromisoformat(str(value)[:10]).date()

    def label_for_level(self, level):
        return PLAN_LEVEL_LABELS[self.normalize_level(level)]

    def format_date_cn(self, value):
        return f"{value.year}年{value.month}月{value.day}日"


period_service = PeriodService()
