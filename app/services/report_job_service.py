import logging
import smtplib
import threading
from dataclasses import dataclass
from datetime import date

from app.models.plan import PlanPeriod
from app.models.report_record import (
    REPORT_STATUS_FAILED,
    REPORT_STATUS_GENERATED,
    REPORT_STATUS_GENERATING,
    REPORT_STATUS_PENDING,
    REPORT_STATUS_SENDING,
    REPORT_STATUS_SENT,
    REPORT_STATUS_SKIPPED_NO_DATA,
    ReportRecord,
)
from app.services.period_service import period_service
from app.services.report_config import ReportConfigLoader, ReportDeliveryConfig
from app.services.report_data_service import ReportDataService
from app.services.report_email_service import ReportEmailError, ReportEmailService
from app.services.report_generation_service import ReportGenerationService
from app.services.report_period_service import ReportPeriodService
from app.services.report_prompt_builder import PERIOD_REPORT_NAMES, ReportPromptBuilder
from app.services.report_repository import ReportRepository


logger = logging.getLogger(__name__)


class ReportJobService:
    def __init__(
        self,
        config_loader: ReportConfigLoader | None = None,
        repository: ReportRepository | None = None,
        period_service_obj: ReportPeriodService | None = None,
        data_service: ReportDataService | None = None,
        generation_service: ReportGenerationService | None = None,
        email_service: ReportEmailService | None = None,
        prompt_builder: ReportPromptBuilder | None = None,
    ):
        self.config_loader = config_loader or ReportConfigLoader()
        self.repository = repository or ReportRepository()
        self.period_service = period_service_obj or ReportPeriodService(self.repository)
        self.data_service = data_service or ReportDataService(self.repository.db)
        self.generation_service = generation_service or ReportGenerationService()
        self.email_service = email_service or ReportEmailService()
        self.prompt_builder = prompt_builder or ReportPromptBuilder()

    def run_once(self, today: date | None = None) -> dict:
        if not self.repository.get_auto_send_enabled(self.config_loader):
            logger.info("period report skipped: auto send disabled")
            return {"processed": 0, "skipped": "disabled"}

        config = self.config_loader.load()
        if not config.llm.api_key:
            raise ReportManualSendError(
                "config_incomplete",
                "尚未配置 API Key，请先前往“设置 → API 与邮件配置”完成配置。",
            )
        if config.errors:
            self.log_config_skip(config)
            return {"processed": 0, "skipped": "invalid_config"}

        today = period_service.normalize_date(today)
        self.reset_interrupted_reports()
        created = self.discover_reports(today)
        processed = 0
        for record in self.repository.get_retryable_reports():
            if record.status in {REPORT_STATUS_SENT, REPORT_STATUS_SKIPPED_NO_DATA}:
                continue
            self.process_record(record, config)
            processed += 1
        logger.info("period report job finished created=%s processed=%s", created, processed)
        return {"created": created, "processed": processed}

    def log_config_skip(self, config: ReportDeliveryConfig) -> None:
        if config.errors:
            logger.info("period report skipped: %s", "; ".join(config.errors))
        else:
            logger.info("period report skipped: disabled")

    def reset_interrupted_reports(self) -> None:
        for record in self.repository.get_retryable_reports():
            if record.status == REPORT_STATUS_GENERATING:
                self.repository.update_status(record.report_id, REPORT_STATUS_FAILED, "上次生成过程中断，等待重试")
            elif record.status == REPORT_STATUS_SENDING:
                self.repository.update_status(record.report_id, REPORT_STATUS_GENERATED, "上次发送过程中断，等待重试")

    def discover_reports(self, today: date) -> int:
        count = 0
        periods = self.period_service.find_ended_periods_since_enabled(today)
        for period in periods:
            before = self.repository.get_report_by_period(
                period.level.value,
                period.start.isoformat(),
                period.end.isoformat(),
            )
            self.repository.get_or_create_period_report(
                period.level.value,
                period.start.isoformat(),
                period.end.isoformat(),
            )
            if before is None:
                count += 1
        return count

    def process_record(self, record: ReportRecord, config: ReportDeliveryConfig) -> None:
        try:
            self._process_record(record, config)
        except Exception as error:
            record = self.repository.get_report_by_id(record.report_id) or record
            self.repository.update_status(record.report_id, REPORT_STATUS_FAILED, str(error))
            logger.info(
                "period report failed type=%s start=%s end=%s error=%s",
                record.period_type,
                record.period_start,
                record.period_end,
                error.__class__.__name__,
            )

    def _process_record(
        self,
        record: ReportRecord,
        config: ReportDeliveryConfig,
        *,
        allow_sent_resend: bool = False,
        update_no_data_status: bool = True,
    ) -> ReportRecord | None:
        record = self.repository.get_report_by_id(record.report_id)
        if record is None:
            return
        if record.status == REPORT_STATUS_SENT and not allow_sent_resend:
            return record

        period = self.period_from_record(record)
        period_data = self.data_service.collect_period_data(period)
        if not self.data_service.has_meaningful_data(period_data):
            if update_no_data_status:
                self.repository.update_status(record.report_id, REPORT_STATUS_SKIPPED_NO_DATA)
                return self.repository.get_report_by_id(record.report_id)
            raise ReportManualSendError("no_data", "该周期没有可用于生成报告的任务记录。")

        if record.status != REPORT_STATUS_SENT and (not record.markdown or not record.file_path):
            self.repository.update_status(record.report_id, REPORT_STATUS_GENERATING)
            self.repository.increment_api_attempts(record.report_id)
            try:
                title, markdown = self.generation_service.generate_report(period_data, config.llm)
            except Exception as error:
                raise ReportManualSendError("api_failed", "API 调用失败") from error
            try:
                file_path = self.generation_service.save_report(period_data, title, markdown)
            except Exception as error:
                raise ReportManualSendError("save_failed", "报告保存失败") from error
            self.repository.mark_generated(record.report_id, title, str(file_path), markdown)
            record = self.repository.get_report_by_id(record.report_id)

        if record is None:
            return
        self.repository.update_status(record.report_id, REPORT_STATUS_SENDING)
        self.repository.increment_email_attempts(record.report_id)
        try:
            self.email_service.send_report(
                config.email,
                self.email_subject(record),
                record.markdown or "",
                self.period_message_key(record),
            )
        except ReportEmailError as error:
            raise ReportManualSendError("email_failed", error.user_message) from error
        except smtplib.SMTPAuthenticationError as error:
            diagnosis = ReportEmailService().make_error(error, config.email)
            raise ReportManualSendError("email_auth_failed", diagnosis.user_message) from error
        except Exception as error:
            raise ReportManualSendError("email_failed", "邮件发送失败") from error
        self.repository.mark_sent(record.report_id)
        return self.repository.get_report_by_id(record.report_id)

    def period_from_record(self, record: ReportRecord) -> PlanPeriod:
        period = period_service.period_for_date(record.period_type, record.period_start)
        if period.start.isoformat() == record.period_start and period.end.isoformat() == record.period_end:
            return period
        return PlanPeriod(
            level=period.level,
            start=period_service.normalize_date(record.period_start),
            end=period_service.normalize_date(record.period_end),
            key=period_service.period_key(period.level, period_service.normalize_date(record.period_start)),
            title=period.title,
            display_text=f"{record.period_start} - {record.period_end}",
        )

    def send_period_report_manually(
        self,
        period_type,
        period_start,
        period_end,
        *,
        allow_resend: bool = False,
    ) -> "ManualReportResult":
        config = self.config_loader.load()
        if config.errors:
            raise ReportManualSendError("config_incomplete", "API 配置不完整")

        level = period_service.normalize_level(period_type)
        record = self.repository.get_or_create_period_report(
            level.value,
            period_service.normalize_date(period_start).isoformat(),
            period_service.normalize_date(period_end).isoformat(),
        )
        if record.status == REPORT_STATUS_SENT and not allow_resend:
            raise ReportManualSendError("already_sent", "该周期报告已经发送过。")

        record = self._process_record(
            record,
            config,
            allow_sent_resend=allow_resend,
            update_no_data_status=False,
        )
        return ManualReportResult(record=record, message="报告已发送")

    def email_subject(self, record: ReportRecord) -> str:
        report_name = PERIOD_REPORT_NAMES.get(record.period_type, "周期报告")
        if record.period_start == record.period_end:
            return f"[日程表] {record.period_start} {report_name}"
        return f"[日程表] {record.period_start} 至 {record.period_end} {report_name}"

    def period_message_key(self, record: ReportRecord) -> str:
        return f"{record.period_type}-{record.period_start}-{record.period_end}"


class ReportManualSendError(RuntimeError):
    def __init__(self, code: str, user_message: str):
        super().__init__(user_message)
        self.code = code
        self.user_message = user_message


@dataclass(frozen=True)
class ManualReportResult:
    record: ReportRecord | None
    message: str


class ReportStartupRunner:
    _lock = threading.Lock()
    _running = False

    def __init__(self, job_service: ReportJobService | None = None):
        self.job_service = job_service or ReportJobService()
        self.thread: threading.Thread | None = None

    def start_once(self) -> bool:
        with self._lock:
            if self.__class__._running:
                return False
            self.__class__._running = True
        self.thread = threading.Thread(target=self.run, name="PeriodReportJob", daemon=True)
        self.thread.start()
        return True

    def run(self) -> None:
        try:
            self.job_service.run_once()
        except Exception as error:
            logger.info("period report startup job crashed: %s", error.__class__.__name__)
        finally:
            with self._lock:
                self.__class__._running = False
