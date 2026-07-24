from dataclasses import dataclass


REPORT_STATUS_PENDING = "pending"
REPORT_STATUS_GENERATING = "generating"
REPORT_STATUS_GENERATED = "generated"
REPORT_STATUS_SENDING = "sending"
REPORT_STATUS_SENT = "sent"
REPORT_STATUS_FAILED = "failed"
REPORT_STATUS_SKIPPED_NO_DATA = "skipped_no_data"


@dataclass(frozen=True)
class ReportRecord:
    report_id: int | None
    period_type: str
    period_start: str
    period_end: str
    report_title: str | None = None
    file_path: str | None = None
    markdown: str | None = None
    status: str = REPORT_STATUS_PENDING
    api_attempts: int = 0
    email_attempts: int = 0
    last_error: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    sent_at: str | None = None

    @classmethod
    def from_row(cls, row):
        return cls(
            report_id=row["id"],
            period_type=row["period_type"],
            period_start=row["period_start"],
            period_end=row["period_end"],
            report_title=row["report_title"],
            file_path=row["file_path"],
            markdown=row["markdown"],
            status=row["status"],
            api_attempts=row["api_attempts"],
            email_attempts=row["email_attempts"],
            last_error=row["last_error"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            sent_at=row["sent_at"],
        )
