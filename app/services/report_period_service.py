from datetime import date, timedelta

from app.models.plan import PLAN_LEVEL_ORDER, PlanLevel, PlanPeriod
from app.services.period_service import period_service
from app.services.report_repository import ReportRepository


REPORTING_ENABLED_AT_KEY = "reporting_enabled_at"


class ReportPeriodService:
    def __init__(self, repository: ReportRepository | None = None):
        self.repository = repository or ReportRepository()

    def ensure_enabled_baseline(self, today: date | None = None) -> date:
        today = period_service.normalize_date(today)
        value = self.repository.get_setting(REPORTING_ENABLED_AT_KEY)
        if value:
            return period_service.normalize_date(value)
        self.repository.set_setting(REPORTING_ENABLED_AT_KEY, today.isoformat())
        return today

    def find_ended_periods_since_enabled(self, today: date | None = None) -> list[PlanPeriod]:
        today = period_service.normalize_date(today)
        enabled_at = self.ensure_enabled_baseline(today)
        periods: list[PlanPeriod] = []
        for level in PLAN_LEVEL_ORDER:
            periods.extend(self.ended_periods_for_level(level, enabled_at, today))
        return sorted(periods, key=lambda period: (period.end, period.start, period.level.value))

    def ended_periods_for_level(self, level: PlanLevel, enabled_at: date, today: date) -> list[PlanPeriod]:
        probe = enabled_at
        periods_by_key: dict[str, PlanPeriod] = {}
        while probe < today:
            period = period_service.period_for_date(level, probe)
            if period.end >= enabled_at and period.end < today:
                periods_by_key[period.key] = period
            probe = period.end + timedelta(days=1)
        return list(periods_by_key.values())
