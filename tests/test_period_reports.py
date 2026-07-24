import json
import socket
import ssl
import smtplib
import tempfile
import threading
import time
import unittest
from datetime import date
from email import policy
from pathlib import Path
from unittest.mock import patch

from app.database import db_manager
from app.database.db_manager import DBManager
from app.models.plan import PlanLevel
from app.models.report_record import REPORT_STATUS_SENT
from app.services.period_service import period_service
from app.services.report_config import EmailConfig, LLMConfig, ReportConfigLoader, ReportDeliveryConfig
from app.services.report_data_service import ReportDataService
from app.services.report_generation_service import ReportGenerationService
from app.services.report_email_service import ReportEmailError, ReportEmailService
from app.services.report_job_service import ReportJobService, ReportStartupRunner
from app.services.report_period_service import ReportPeriodService
from app.services.report_prompt_builder import ReportPromptBuilder
from app.services.report_repository import ReportRepository
from app.services.task_service import TaskService


class FakeConfigLoader:
    def __init__(self, config):
        self.config = config

    def load(self):
        return self.config


class FakeGenerationService:
    def __init__(self, reports_dir: Path, fail=False):
        self.reports_dir = reports_dir
        self.fail = fail
        self.calls = 0
        self.real = ReportGenerationService(reports_dir=reports_dir, sleep_func=lambda seconds: None)

    def generate_report(self, period_data, llm_config):
        self.calls += 1
        if self.fail:
            raise RuntimeError("api failed")
        return self.real.prompt_builder.report_title(period_data), "# 测试报告\n\n内容来自任务记录"

    def save_report(self, period_data, title, markdown):
        return self.real.save_report(period_data, title, markdown)


class FakeEmailService:
    def __init__(self, fail_first=False):
        self.fail_first = fail_first
        self.calls = 0
        self.subjects = []

    def send_report(self, email_config, subject, markdown, period_key):
        self.calls += 1
        self.subjects.append(subject)
        if self.fail_first and self.calls == 1:
            raise RuntimeError("smtp failed")


class FakeAuthFailureEmailService(FakeEmailService):
    def send_report(self, email_config, subject, markdown, period_key):
        self.calls += 1
        raise smtplib.SMTPAuthenticationError(535, b"auth failed")


class SlowJob:
    def __init__(self):
        self.started = threading.Event()

    def run_once(self):
        self.started.set()
        time.sleep(0.2)


class FakeHTTPResponse:
    def __init__(self, payload: bytes):
        self.payload = payload

    def read(self):
        return self.payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False


class FakeSMTP:
    instances = []

    def __init__(self, host, port, timeout=30):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.sent_messages = []
        self.logged_in = None
        self.started_tls = False
        self.__class__.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def ehlo(self):
        return None

    def starttls(self):
        self.started_tls = True

    def login(self, user, password):
        self.logged_in = (user, password)

    def send_message(self, message, from_addr=None, to_addrs=None):
        self.sent_messages.append(message)
        self.envelope = (from_addr, to_addrs)


class PeriodReportTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.root = Path(self.temp_dir.name)
        self.data_dir = self.root / "data"
        self.db_path = self.data_dir / "schedule.db"
        self.config_path = self.root / "config" / "report_delivery.json"
        self.reports_dir = self.root / "reports"
        self.data_dir_patch = patch.object(db_manager, "DATA_DIR", self.data_dir)
        self.db_path_patch = patch.object(db_manager, "DB_PATH", self.db_path)
        self.data_dir_patch.start()
        self.db_path_patch.start()
        period_service.set_date_provider(lambda: date(2026, 7, 25))

    def tearDown(self):
        period_service.set_date_provider(None)
        self.db_path_patch.stop()
        self.data_dir_patch.stop()
        self.temp_dir.cleanup()

    def ready_config(self):
        return ReportDeliveryConfig(
            enabled=True,
            llm=LLMConfig("https://example.test/v1", "secret-api-key", "mock-model", 3, 0.3),
            email=EmailConfig("smtp.example.test", 465, True, "from@example.test", "secret-auth", "to@example.test"),
        )

    def make_job(self, config=None, generation=None, email=None):
        repository = ReportRepository(DBManager())
        return ReportJobService(
            config_loader=FakeConfigLoader(config or self.ready_config()),
            repository=repository,
            period_service_obj=ReportPeriodService(repository),
            data_service=ReportDataService(repository.db),
            generation_service=generation or FakeGenerationService(self.reports_dir),
            email_service=email or FakeEmailService(),
            prompt_builder=ReportPromptBuilder(),
        )

    def add_completed_day_task(self, service, title="日报任务", day=date(2026, 7, 24)):
        task_id = service.add_plan_task(
            title,
            "任务描述",
            plan_level=PlanLevel.DAY,
            minimal_action="打开文档",
            now=day,
        )
        service.complete_task(task_id, "完成情况记录")
        service.db.execute(
            """
            UPDATE task_logs
            SET completed_at = ?, record_date = ?
            WHERE task_id = ?
            """,
            (f"{day.isoformat()}T20:00:00", day.isoformat(), task_id),
        )
        service.db.execute(
            "UPDATE tasks SET completed_at = ? WHERE id = ?",
            (f"{day.isoformat()}T20:00:00", task_id),
        )
        return task_id

    def test_config_read_and_missing_safe_skip(self):
        loader = ReportConfigLoader(self.config_path)
        config = loader.load()
        self.assertFalse(config.enabled)
        self.assertTrue(self.config_path.exists())

        self.config_path.write_text(
            json.dumps(
                {
                    "enabled": True,
                    "llm": {"base_url": "https://example.test/v1", "api_key": "secret", "model": ""},
                    "email": {"smtp_host": "", "auth_code": "secret-auth"},
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        config = loader.load()
        self.assertTrue(config.enabled)
        self.assertTrue(config.errors)

    def test_config_errors_do_not_log_secrets(self):
        config = ReportDeliveryConfig(
            enabled=True,
            llm=LLMConfig("", "secret-api-key", "", 90, 0.3),
            email=EmailConfig("", 465, True, "", "secret-auth", ""),
            errors=("llm.model 不能为空", "email.smtp_host 不能为空"),
        )
        job = self.make_job(config=config)
        with self.assertLogs("app.services.report_job_service", level="INFO") as logs:
            job.run_once(date(2026, 7, 25))
        text = "\n".join(logs.output)
        self.assertNotIn("secret-api-key", text)
        self.assertNotIn("secret-auth", text)

    def test_period_boundaries_and_current_period_excluded(self):
        repo = ReportRepository(DBManager())
        repo.set_setting("reporting_enabled_at", "2026-07-01")
        service = ReportPeriodService(repo)
        periods = service.find_ended_periods_since_enabled(date(2026, 8, 1))
        keys = {(period.level, period.start, period.end) for period in periods}

        self.assertIn((PlanLevel.DAY, date(2026, 7, 31), date(2026, 7, 31)), keys)
        self.assertIn((PlanLevel.WEEK, date(2026, 7, 20), date(2026, 7, 26)), keys)
        self.assertIn((PlanLevel.MONTH, date(2026, 7, 1), date(2026, 7, 31)), keys)
        self.assertNotIn((PlanLevel.DAY, date(2026, 8, 1), date(2026, 8, 1)), keys)

    def test_first_enable_does_not_retroactively_report_history(self):
        service = TaskService()
        self.add_completed_day_task(service, day=date(2026, 7, 24))
        job = self.make_job()
        result = job.run_once(date(2026, 7, 25))
        rows = job.repository.db.fetch_all("SELECT * FROM period_reports")

        self.assertEqual(result["created"], 0)
        self.assertEqual(rows, [])

    def test_auto_send_database_switch_disables_startup_discovery(self):
        service = TaskService()
        self.add_completed_day_task(service, day=date(2026, 7, 24))
        generation = FakeGenerationService(self.reports_dir)
        email = FakeEmailService()
        job = self.make_job(generation=generation, email=email)
        job.repository.set_auto_send_enabled(False)
        job.repository.set_setting("reporting_enabled_at", "2026-07-24")

        result = job.run_once(date(2026, 7, 25))
        rows = job.repository.db.fetch_all("SELECT * FROM period_reports")

        self.assertEqual(result["skipped"], "disabled")
        self.assertEqual(rows, [])
        self.assertEqual(generation.calls, 0)
        self.assertEqual(email.calls, 0)

    def test_auto_send_setting_initializes_from_existing_json_enabled_flag(self):
        repo = ReportRepository(DBManager())
        loader = FakeConfigLoader(self.ready_config())

        self.assertTrue(repo.get_auto_send_enabled(loader))
        self.assertEqual(repo.get_setting("auto_send_enabled"), "1")

    def test_late_start_creates_missing_reports_without_duplicates(self):
        service = TaskService()
        self.add_completed_day_task(service, "day24", date(2026, 7, 24))
        self.add_completed_day_task(service, "day25", date(2026, 7, 25))
        job = self.make_job()
        job.repository.set_setting("reporting_enabled_at", "2026-07-24")

        job.discover_reports(date(2026, 7, 26))
        job.discover_reports(date(2026, 7, 26))
        rows = job.repository.db.fetch_all(
            "SELECT period_type, period_start, period_end FROM period_reports WHERE period_type = 'day'"
        )
        self.assertEqual(len(rows), 2)

    def test_no_task_period_is_skipped(self):
        job = self.make_job()
        job.repository.set_setting("reporting_enabled_at", "2026-07-24")
        job.run_once(date(2026, 7, 25))
        row = job.repository.db.fetch_one("SELECT status FROM period_reports WHERE period_type = 'day'")
        self.assertEqual(row["status"], "skipped_no_data")

    def test_prompt_contains_completed_and_uncompleted_task_facts(self):
        service = TaskService()
        self.add_completed_day_task(service, "已完成任务", date(2026, 7, 24))
        service.add_plan_task(
            "未完成任务",
            "未完成描述",
            plan_level=PlanLevel.DAY,
            minimal_action="开始行动",
            now=date(2026, 7, 24),
        )
        period = period_service.period_for_date(PlanLevel.DAY, date(2026, 7, 24))
        data = ReportDataService(DBManager()).collect_period_data(period)
        prompt = ReportPromptBuilder().build_user_prompt(data)

        self.assertIn("已完成任务", prompt)
        self.assertIn("未完成任务", prompt)
        self.assertIn("任务描述", prompt)
        self.assertIn("完成情况记录", prompt)

    def test_successful_full_flow_saves_markdown_and_marks_sent(self):
        service = TaskService()
        self.add_completed_day_task(service, day=date(2026, 7, 24))
        generation = FakeGenerationService(self.reports_dir)
        email = FakeEmailService()
        job = self.make_job(generation=generation, email=email)
        job.repository.set_setting("reporting_enabled_at", "2026-07-24")

        job.run_once(date(2026, 7, 25))
        row = job.repository.db.fetch_one("SELECT * FROM period_reports WHERE period_type = 'day'")

        self.assertEqual(row["status"], REPORT_STATUS_SENT)
        self.assertEqual(generation.calls, 1)
        self.assertEqual(email.calls, 1)
        self.assertTrue(Path(row["file_path"]).exists())
        self.assertIn("测试报告", Path(row["file_path"]).read_text(encoding="utf-8"))

    def test_manual_send_ignores_auto_switch_and_sends_exact_period(self):
        service = TaskService()
        self.add_completed_day_task(service, day=date(2026, 7, 20))
        generation = FakeGenerationService(self.reports_dir)
        email = FakeEmailService()
        job = self.make_job(generation=generation, email=email)
        job.repository.set_auto_send_enabled(False)

        result = job.send_period_report_manually("day", "2026-07-20", "2026-07-20")
        row = job.repository.db.fetch_one("SELECT * FROM period_reports WHERE period_type = 'day'")

        self.assertEqual(result.message, "报告已发送")
        self.assertEqual(row["period_start"], "2026-07-20")
        self.assertEqual(row["period_end"], "2026-07-20")
        self.assertEqual(row["status"], "sent")
        self.assertEqual(generation.calls, 1)
        self.assertEqual(email.calls, 1)

    def test_manual_send_no_data_does_not_mark_skipped(self):
        job = self.make_job()

        with self.assertRaisesRegex(Exception, "该周期没有可用于生成报告的任务记录"):
            job.send_period_report_manually("week", "2026-07-20", "2026-07-26")

        row = job.repository.db.fetch_one("SELECT status FROM period_reports WHERE period_type = 'week'")
        self.assertEqual(row["status"], "pending")

    def test_manual_resend_reuses_sent_report_without_new_generation_or_duplicate(self):
        service = TaskService()
        self.add_completed_day_task(service, day=date(2026, 7, 24))
        generation = FakeGenerationService(self.reports_dir)
        email = FakeEmailService()
        job = self.make_job(generation=generation, email=email)

        job.send_period_report_manually("day", "2026-07-24", "2026-07-24")
        with self.assertRaisesRegex(Exception, "该周期报告已经发送过"):
            job.send_period_report_manually("day", "2026-07-24", "2026-07-24")
        job.send_period_report_manually("day", "2026-07-24", "2026-07-24", allow_resend=True)

        rows = job.repository.db.fetch_all("SELECT * FROM period_reports WHERE period_type = 'day'")
        self.assertEqual(len(rows), 1)
        self.assertEqual(generation.calls, 1)
        self.assertEqual(email.calls, 2)
        self.assertEqual(rows[0]["email_attempts"], 2)

    def test_manual_retry_generated_report_does_not_regenerate(self):
        service = TaskService()
        self.add_completed_day_task(service, day=date(2026, 7, 24))
        generation = FakeGenerationService(self.reports_dir)
        email = FakeEmailService(fail_first=True)
        job = self.make_job(generation=generation, email=email)

        with self.assertRaisesRegex(Exception, "邮件发送失败"):
            job.send_period_report_manually("day", "2026-07-24", "2026-07-24")
        job.send_period_report_manually("day", "2026-07-24", "2026-07-24")

        row = job.repository.db.fetch_one(
            "SELECT status, api_attempts, email_attempts FROM period_reports WHERE period_type = 'day'"
        )
        self.assertEqual(row["status"], "sent")
        self.assertEqual(row["api_attempts"], 1)
        self.assertEqual(row["email_attempts"], 2)
        self.assertEqual(generation.calls, 1)

    def test_manual_email_auth_failure_uses_safe_user_message(self):
        service = TaskService()
        self.add_completed_day_task(service, day=date(2026, 7, 24))
        job = self.make_job(email=FakeAuthFailureEmailService())

        with self.assertRaisesRegex(Exception, "Gmail 身份验证失败（SMTP 535）") as context:
            job.send_period_report_manually("day", "2026-07-24", "2026-07-24")

        self.assertNotIn("secret-api-key", str(context.exception))
        self.assertNotIn("secret-auth", str(context.exception))

    def test_openai_compatible_generation_uses_chat_completions(self):
        service = TaskService()
        self.add_completed_day_task(service, day=date(2026, 7, 24))
        period = period_service.period_for_date(PlanLevel.DAY, date(2026, 7, 24))
        period_data = ReportDataService(DBManager()).collect_period_data(period)
        response = {
            "choices": [
                {"message": {"content": "```markdown\n# 生成报告\n\n正文\n```"}}
            ]
        }
        captured = {}

        def fake_urlopen(request, timeout):
            captured["url"] = request.full_url
            captured["timeout"] = timeout
            captured["body"] = json.loads(request.data.decode("utf-8"))
            captured["auth"] = request.headers.get("Authorization")
            return FakeHTTPResponse(json.dumps(response).encode("utf-8"))

        generation = ReportGenerationService(reports_dir=self.reports_dir, sleep_func=lambda seconds: None)
        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            title, markdown = generation.generate_report(period_data, self.ready_config().llm)

        self.assertIn("/chat/completions", captured["url"])
        self.assertEqual(captured["body"]["model"], "mock-model")
        self.assertEqual(captured["timeout"], 3)
        self.assertEqual(captured["auth"], "Bearer secret-api-key")
        self.assertEqual(markdown, "# 生成报告\n\n正文")
        self.assertIn("日报", title)

    def test_smtp_email_service_builds_plain_html_message(self):
        FakeSMTP.instances = []
        email_config = self.ready_config().email
        service = ReportEmailService(sleep_func=lambda seconds: None)

        with patch("smtplib.SMTP_SSL", FakeSMTP):
            service.send_report(
                email_config,
                "[日程表] 2026-07-24 日报",
                "# 标题\n\n- 条目",
                "day-2026-07-24-2026-07-24",
            )

        smtp = FakeSMTP.instances[0]
        message = smtp.sent_messages[0]
        self.assertEqual(smtp.logged_in, ("from@example.test", "secret-auth"))
        self.assertEqual(message["To"], "to@example.test")
        self.assertIn("Message-ID", message)
        self.assertTrue(message.is_multipart())
        self.assertIn("text/plain", str(message))
        self.assertIn("text/html", str(message))

    def test_chinese_email_headers_bodies_and_period_keys_are_ascii_safe(self):
        service = ReportEmailService(sleep_func=lambda seconds: None)
        config = self.ready_config().email
        period_types = ["日报", "周报", "月报", "季度报告", "年报", "五年报告"]

        for period_type in period_types:
            with self.subTest(period_type=period_type):
                message = service.build_message(
                    config,
                    f"[日程表] 2026-07-24 {period_type}",
                    f"这是{period_type}的中文正文。",
                    f"{period_type}|2026-07-24|2026-07-24",
                )
                raw = message.as_bytes(policy=policy.SMTP)
                self.assertIsInstance(raw, bytes)
                message["Message-ID"].encode("ascii")
                self.assertNotIn(period_type.encode("utf-8"), raw.split(b"Message-ID:", 1)[1].split(b"\r\n", 1)[0])
                self.assertIn("=?utf-8?", raw.decode("ascii", errors="ignore").lower())

    def test_chinese_test_email_uses_send_message_without_serialization_error(self):
        service = ReportEmailService(sleep_func=lambda seconds: None)
        FakeSMTP.instances = []
        with patch("smtplib.SMTP_SSL", FakeSMTP):
            service.send_test_email(self.ready_config().email)

        smtp = FakeSMTP.instances[0]
        self.assertEqual(smtp.envelope, ("from@example.test", ["to@example.test"]))
        raw = smtp.sent_messages[0].as_bytes(policy=policy.SMTP)
        self.assertIn(b"=?utf-8?b?", raw.lower())
        self.assertIn("如果你收到这封邮件，说明计划炼金台的邮件发送配置正常。", smtp.sent_messages[0].get_body("plain").get_content())

    def test_unicode_encode_error_is_classified_as_message_serialization(self):
        service = ReportEmailService(sleep_func=lambda seconds: None)
        error = UnicodeEncodeError("ascii", "中文", 0, 1, "ordinal not in range")

        diagnosed = service.make_error(
            error,
            self.ready_config().email,
            stage="message_serialization",
        )

        self.assertEqual(diagnosed.diagnostics.stage, "message_serialization")
        self.assertEqual(
            str(diagnosed),
            "邮件内容编码失败：邮件主题或正文包含未正确编码的中文字符。请更新程序后重试。",
        )

    def test_smtp_auth_535_keeps_code_and_redacts_secret(self):
        service = ReportEmailService(sleep_func=lambda seconds: None)
        error = smtplib.SMTPAuthenticationError(535, b"5.7.8 Authentication failed secret-auth")

        with patch("smtplib.SMTP_SSL", side_effect=error), self.assertLogs(
            "app.services.report_email_service", level="WARNING"
        ) as logs:
            with self.assertRaises(ReportEmailError) as context:
                service.send_report(self.ready_config().email, "subject", "body", "test")

        self.assertIn("Gmail 身份验证失败（SMTP 535）", str(context.exception))
        self.assertNotIn("secret-auth", str(context.exception))
        self.assertNotIn("secret-auth", "\n".join(logs.output))
        self.assertEqual(context.exception.diagnostics.smtp_code, 535)

    def test_smtp_auth_534_application_password_message(self):
        service = ReportEmailService(sleep_func=lambda seconds: None)
        error = smtplib.SMTPAuthenticationError(534, b"5.7.9 Application-specific password required")

        with patch("smtplib.SMTP_SSL", side_effect=error):
            with self.assertRaises(ReportEmailError) as context:
                service.send_report(self.ready_config().email, "subject", "body", "test")

        self.assertEqual(
            str(context.exception),
            "Gmail 要求使用应用专用密码，请不要填写普通 Google 账号密码。",
        )

    def test_smtp_465_uses_ssl_and_587_uses_starttls(self):
        service = ReportEmailService(sleep_func=lambda seconds: None)
        FakeSMTP.instances = []
        with patch("smtplib.SMTP_SSL", FakeSMTP):
            service.send_test_email(self.ready_config().email)
        ssl_smtp = FakeSMTP.instances[-1]
        self.assertEqual((ssl_smtp.host, ssl_smtp.port), ("smtp.example.test", 465))
        self.assertFalse(ssl_smtp.started_tls)

        FakeSMTP.instances = []
        starttls_config = EmailConfig(
            "smtp.example.test", 587, False, "from@example.test", "secret-auth", "to@example.test"
        )
        with patch("smtplib.SMTP", FakeSMTP):
            service.send_test_email(starttls_config)
        starttls_smtp = FakeSMTP.instances[-1]
        self.assertEqual((starttls_smtp.host, starttls_smtp.port), ("smtp.example.test", 587))
        self.assertTrue(starttls_smtp.started_tls)
        self.assertEqual(starttls_smtp.logged_in[0], "from@example.test")

    def test_smtp_recipient_and_sender_refusals_are_classified(self):
        service = ReportEmailService(sleep_func=lambda seconds: None)
        recipient_error = smtplib.SMTPRecipientsRefused(
            {"to@example.test": (550, b"5.1.1 recipient rejected")}
        )
        with patch("smtplib.SMTP_SSL", side_effect=recipient_error):
            with self.assertRaises(ReportEmailError) as recipient_context:
                service.send_test_email(self.ready_config().email)
        self.assertEqual(str(recipient_context.exception), "收件邮箱被服务器拒绝，请检查收件地址。")
        self.assertEqual(recipient_context.exception.diagnostics.smtp_code, 550)

        sender_error = smtplib.SMTPSenderRefused(553, b"sender rejected", "from@example.test")
        with patch("smtplib.SMTP_SSL", side_effect=sender_error):
            with self.assertRaises(ReportEmailError) as sender_context:
                service.send_test_email(self.ready_config().email)
        self.assertEqual(str(sender_context.exception), "发件地址被服务器拒绝，请确认 sender_email 与登录 Gmail 账号一致。")
        self.assertEqual(sender_context.exception.diagnostics.smtp_code, 553)

    def test_smtp_ssl_error_and_timeout_are_classified(self):
        service = ReportEmailService(sleep_func=lambda seconds: None)
        with patch("smtplib.SMTP_SSL", side_effect=ssl.SSLError("wrong version")):
            with self.assertRaises(ReportEmailError) as ssl_context:
                service.send_test_email(self.ready_config().email)
        self.assertIn("SMTP 加密方式不匹配", str(ssl_context.exception))

        with patch("smtplib.SMTP_SSL", side_effect=socket.timeout("timed out")):
            with self.assertRaises(ReportEmailError) as timeout_context:
                service.send_test_email(self.ready_config().email)
        self.assertIn("无法连接 Gmail SMTP 服务器", str(timeout_context.exception))

    def test_remaining_smtp_and_socket_types_keep_diagnostics(self):
        service = ReportEmailService(sleep_func=lambda seconds: None)
        cases = [
            (smtplib.SMTPConnectError(421, b"connect refused"), "SMTPConnectError"),
            (smtplib.SMTPServerDisconnected("server closed"), "SMTPServerDisconnected"),
            (socket.gaierror("name lookup failed"), "gaierror"),
            (OSError("connection reset"), "OSError"),
        ]
        for error, error_type in cases:
            with self.subTest(error_type=error_type), patch("smtplib.SMTP_SSL", side_effect=error):
                with self.assertRaises(ReportEmailError) as context:
                    service.send_test_email(self.ready_config().email)
            self.assertEqual(context.exception.diagnostics.exception_type, error_type)

        data_error = smtplib.SMTPDataError(554, b"message rejected")
        with patch("smtplib.SMTP_SSL", side_effect=data_error):
            with self.assertRaises(ReportEmailError) as context:
                service.send_test_email(self.ready_config().email)
        self.assertIn("SMTP 554", str(context.exception))
        self.assertIn("message rejected", str(context.exception))

    def test_test_email_has_fixed_content_and_creates_no_report(self):
        service = ReportEmailService(sleep_func=lambda seconds: None)
        FakeSMTP.instances = []
        with patch("smtplib.SMTP_SSL", FakeSMTP):
            service.send_test_email(self.ready_config().email)

        message = FakeSMTP.instances[0].sent_messages[0]
        self.assertEqual(message["Subject"], "计划炼金台邮件配置测试")
        self.assertIn("如果你收到这封邮件，说明计划炼金台的邮件发送配置正常。", message.get_body("plain").get_content())
        self.assertEqual(ReportRepository(DBManager()).db.fetch_all("SELECT * FROM period_reports"), [])

    def test_api_failure_is_retryable(self):
        service = TaskService()
        self.add_completed_day_task(service, day=date(2026, 7, 24))
        generation = FakeGenerationService(self.reports_dir, fail=True)
        job = self.make_job(generation=generation)
        job.repository.set_setting("reporting_enabled_at", "2026-07-24")

        job.run_once(date(2026, 7, 25))
        row = job.repository.db.fetch_one("SELECT status, api_attempts FROM period_reports WHERE period_type = 'day'")
        self.assertEqual(row["status"], "failed")
        self.assertEqual(row["api_attempts"], 1)

    def test_email_failure_retries_without_regenerating_report(self):
        service = TaskService()
        self.add_completed_day_task(service, day=date(2026, 7, 24))
        generation = FakeGenerationService(self.reports_dir)
        email = FakeEmailService(fail_first=True)
        job = self.make_job(generation=generation, email=email)
        job.repository.set_setting("reporting_enabled_at", "2026-07-24")

        job.run_once(date(2026, 7, 25))
        first = job.repository.db.fetch_one("SELECT status, api_attempts, email_attempts FROM period_reports WHERE period_type = 'day'")
        self.assertEqual(first["status"], "failed")
        self.assertEqual(first["api_attempts"], 1)
        self.assertEqual(first["email_attempts"], 1)

        job.run_once(date(2026, 7, 25))
        second = job.repository.db.fetch_one("SELECT status, api_attempts, email_attempts FROM period_reports WHERE period_type = 'day'")
        self.assertEqual(second["status"], "sent")
        self.assertEqual(second["api_attempts"], 1)
        self.assertEqual(second["email_attempts"], 2)
        self.assertEqual(generation.calls, 1)
        self.assertEqual(email.calls, 2)

    def test_sent_and_interrupted_status_handling(self):
        service = TaskService()
        self.add_completed_day_task(service, day=date(2026, 7, 24))
        generation = FakeGenerationService(self.reports_dir)
        email = FakeEmailService()
        job = self.make_job(generation=generation, email=email)
        job.repository.set_setting("reporting_enabled_at", "2026-07-24")
        job.run_once(date(2026, 7, 25))
        job.run_once(date(2026, 7, 25))
        self.assertEqual(email.calls, 1)

        repo = job.repository
        generating = repo.get_or_create_period_report("week", "2026-07-20", "2026-07-26")
        sending = repo.get_or_create_period_report("month", "2026-07-01", "2026-07-31")
        repo.update_status(generating.report_id, "generating")
        repo.update_status(sending.report_id, "sending")
        job.reset_interrupted_reports()
        self.assertEqual(repo.get_report_by_id(generating.report_id).status, "failed")
        self.assertEqual(repo.get_report_by_id(sending.report_id).status, "generated")

    def test_startup_runner_does_not_block(self):
        runner = ReportStartupRunner(SlowJob())
        start = time.monotonic()
        self.assertTrue(runner.start_once())
        elapsed = time.monotonic() - start
        self.assertLess(elapsed, 0.1)
        self.assertTrue(runner.job_service.started.wait(1))
        runner.thread.join(1)


if __name__ == "__main__":
    unittest.main()
