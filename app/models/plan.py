from dataclasses import dataclass
from datetime import date
from enum import Enum


class PlanLevel(str, Enum):
    DAY = "day"
    WEEK = "week"
    MONTH = "month"
    QUARTER = "quarter"
    YEAR = "year"
    FIVE_YEAR = "five_year"


PLAN_LEVEL_ORDER = (
    PlanLevel.DAY,
    PlanLevel.WEEK,
    PlanLevel.MONTH,
    PlanLevel.QUARTER,
    PlanLevel.YEAR,
    PlanLevel.FIVE_YEAR,
)


PLAN_LEVEL_LABELS = {
    PlanLevel.DAY: "日计划",
    PlanLevel.WEEK: "周计划",
    PlanLevel.MONTH: "月计划",
    PlanLevel.QUARTER: "季计划",
    PlanLevel.YEAR: "年计划",
    PlanLevel.FIVE_YEAR: "五年计划",
}


@dataclass(frozen=True)
class PlanPeriod:
    level: PlanLevel
    start: date
    end: date
    key: str
    title: str
    display_text: str

