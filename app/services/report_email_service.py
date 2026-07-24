import html
import hashlib
import logging
import re
import smtplib
import socket
import ssl
import time
from dataclasses import dataclass
from email import policy
from email.headerregistry import Address
from email.message import EmailMessage
from email.utils import formatdate

from app.services.report_config import EmailConfig


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class EmailDiagnostics:
    exception_type: str
    smtp_code: int | None
    server_response: str
    smtp_host: str
    smtp_port: int
    use_ssl: bool
    sender_email: str
    recipient_email: str
    stage: str = "smtp"


class ReportEmailError(RuntimeError):
    def __init__(self, user_message: str, diagnostics: EmailDiagnostics, original_error: Exception):
        super().__init__(user_message)
        self.user_message = user_message
        self.diagnostics = diagnostics
        self.original_error = original_error


class ReportEmailService:
    def __init__(self, sleep_func=time.sleep):
        self.sleep_func = sleep_func

    def send_report(
        self,
        email_config: EmailConfig,
        subject: str,
        markdown: str,
        period_key: str,
    ) -> None:
        try:
            message = self.build_message(email_config, subject, markdown, period_key)
        except UnicodeEncodeError as error:
            raise self.make_error(error, email_config, stage="message_serialization") from error
        self._send_message(email_config, message)

    def send_test_email(self, email_config: EmailConfig) -> None:
        errors = self.validate_email_config(email_config)
        if errors:
            raise ValueError("邮件配置不完整：" + "、".join(errors))
        try:
            message = self.build_message(
                email_config,
                "计划炼金台邮件配置测试",
                "如果你收到这封邮件，说明计划炼金台的邮件发送配置正常。",
                "test|2026-01-01|2026-01-01",
            )
        except UnicodeEncodeError as error:
            raise self.make_error(error, email_config, stage="message_serialization") from error
        self._send_message(email_config, message)

    def validate_email_config(self, email_config: EmailConfig) -> list[str]:
        errors = []
        if not email_config.smtp_host:
            errors.append("smtp_host")
        if not 1 <= email_config.smtp_port <= 65535:
            errors.append("smtp_port")
        if not email_config.sender_email:
            errors.append("sender_email")
        if not email_config.auth_code:
            errors.append("auth_code")
        if not email_config.recipient_email:
            errors.append("recipient_email")
        return errors

    def _send_message(self, email_config: EmailConfig, message: EmailMessage) -> None:
        last_error = None
        for attempt in range(3):
            try:
                encryption = getattr(email_config, "encryption", "") or ("ssl" if email_config.use_ssl else "starttls")
                if encryption == "ssl":
                    with smtplib.SMTP_SSL(email_config.smtp_host, email_config.smtp_port, timeout=30) as smtp:
                        smtp.login(email_config.sender_email, email_config.auth_code)
                        smtp.send_message(
                            message,
                            from_addr=email_config.sender_email,
                            to_addrs=[email_config.recipient_email],
                        )
                elif encryption == "starttls":
                    with smtplib.SMTP(email_config.smtp_host, email_config.smtp_port, timeout=30) as smtp:
                        smtp.ehlo()
                        smtp.starttls()
                        smtp.ehlo()
                        smtp.login(email_config.sender_email, email_config.auth_code)
                        smtp.send_message(message, from_addr=email_config.sender_email, to_addrs=[email_config.recipient_email])
                else:
                    with smtplib.SMTP(email_config.smtp_host, email_config.smtp_port, timeout=30) as smtp:
                        smtp.login(email_config.sender_email, email_config.auth_code)
                        smtp.send_message(message, from_addr=email_config.sender_email, to_addrs=[email_config.recipient_email])
                return
            except UnicodeEncodeError as error:
                raise self.make_error(error, email_config, stage="message_serialization") from error
            except Exception as error:
                last_error = error
                if isinstance(error, smtplib.SMTPAuthenticationError):
                    break
                if attempt < 2:
                    self.sleep_func(2 ** attempt)
        if last_error is not None:
            raise self.make_error(last_error, email_config, stage="smtp") from last_error

    def make_error(
        self,
        error: Exception,
        email_config: EmailConfig,
        *,
        stage: str = "smtp",
    ) -> ReportEmailError:
        diagnostics = EmailDiagnostics(
            exception_type=type(error).__name__,
            smtp_code=self.smtp_code(error),
            server_response=self.sanitize_server_response(
                self.server_response(error),
                secrets=(email_config.auth_code,),
            ),
            smtp_host=email_config.smtp_host,
            smtp_port=email_config.smtp_port,
            use_ssl=email_config.use_ssl,
            sender_email=self.mask_email(email_config.sender_email),
            recipient_email=self.mask_email(email_config.recipient_email),
            stage=stage,
        )
        user_message = self.user_message(error, diagnostics)
        logger.warning(
            "SMTP send failed exception_type=%s smtp_code=%s server_response=%r "
            "stage=%s smtp_host=%s smtp_port=%s use_ssl=%s sender_email=%s recipient_email=%s",
            diagnostics.exception_type,
            diagnostics.smtp_code,
            diagnostics.server_response,
            diagnostics.stage,
            diagnostics.smtp_host,
            diagnostics.smtp_port,
            diagnostics.use_ssl,
            diagnostics.sender_email,
            diagnostics.recipient_email,
        )
        return ReportEmailError(user_message, diagnostics, error)

    def user_message(self, error: Exception, diagnostics: EmailDiagnostics) -> str:
        code = diagnostics.smtp_code if diagnostics.smtp_code is not None else "未知"
        response = diagnostics.server_response or "服务器未提供说明"
        if isinstance(error, UnicodeEncodeError) or diagnostics.stage == "message_serialization":
            return "邮件内容编码失败：邮件主题或正文包含未正确编码的中文字符。请更新程序后重试。"
        if isinstance(error, smtplib.SMTPAuthenticationError):
            if "application-specific password" in response.lower():
                return "Gmail 要求使用应用专用密码，请不要填写普通 Google 账号密码。"
            return (
                f"Gmail 身份验证失败（SMTP {code}）。请确认发件邮箱与应用专用密码属于同一 Google 账号，"
                "并且填写的是应用专用密码而不是登录密码。"
            )
        if isinstance(error, (smtplib.SMTPConnectError, socket.timeout, socket.gaierror)):
            mode = "SSL" if diagnostics.use_ssl else "STARTTLS"
            return (
                f"无法连接 Gmail SMTP 服务器。当前配置：{diagnostics.smtp_host}:{diagnostics.smtp_port}，"
                f"加密方式：{mode}。请检查网络、防火墙和端口配置。"
            )
        if isinstance(error, ssl.SSLError):
            return "SMTP 加密方式不匹配。端口 465 应使用 SSL；端口 587 应使用 STARTTLS。"
        if isinstance(error, smtplib.SMTPRecipientsRefused):
            return "收件邮箱被服务器拒绝，请检查收件地址。"
        if isinstance(error, smtplib.SMTPSenderRefused):
            return "发件地址被服务器拒绝，请确认 sender_email 与登录 Gmail 账号一致。"
        if isinstance(error, smtplib.SMTPDataError):
            return f"Gmail 在接收邮件内容时拒绝了请求（SMTP {code}）：{response}"
        return f"邮件发送失败：{diagnostics.exception_type}：{response}"

    def smtp_code(self, error: Exception) -> int | None:
        code = getattr(error, "smtp_code", None)
        if isinstance(code, int):
            return code
        recipients = getattr(error, "recipients", None)
        if isinstance(recipients, dict):
            for value in recipients.values():
                if isinstance(value, tuple) and value and isinstance(value[0], int):
                    return value[0]
        return None

    def server_response(self, error: Exception) -> str:
        response = getattr(error, "smtp_error", None)
        if response is None:
            recipients = getattr(error, "recipients", None)
            if isinstance(recipients, dict):
                response = " ".join(str(value) for value in recipients.values())
        if response is None:
            response = str(error)
        if isinstance(response, bytes):
            return response.decode("utf-8", errors="replace")
        return str(response)

    def sanitize_server_response(self, response: str, secrets=()) -> str:
        sanitized = " ".join(response.replace("\x00", " ").split())
        for secret in secrets:
            if secret:
                sanitized = sanitized.replace(str(secret), "[REDACTED]")
        sanitized = re.sub(
            r"(?i)(password|passcode|auth(?:entication)?)[=: ]+\S+",
            r"\1=[REDACTED]",
            sanitized,
        )
        sanitized = re.sub(r"(?i)bearer\s+\S+", "Bearer [REDACTED]", sanitized)
        sanitized = re.sub(
            r"\b([A-Za-z0-9.!#$%&'*+/=?^_`{|}~-])([A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]*)@([A-Za-z0-9.-]+)",
            lambda match: self.mask_email(match.group(0)),
            sanitized,
        )
        return sanitized[:240]

    def mask_email(self, address: str) -> str:
        if not address or "@" not in address:
            return "[empty]" if not address else "[redacted]"
        local, domain = address.split("@", 1)
        return f"{local[:1]}***@{domain}"

    def build_message(
        self,
        email_config: EmailConfig,
        subject: str,
        markdown: str,
        period_key: str,
    ) -> EmailMessage:
        message = EmailMessage(policy=policy.SMTP)
        username, domain = email_config.sender_email.rsplit("@", 1)
        message["From"] = Address(
            display_name="日程表",
            username=username,
            domain=domain,
        )
        message["To"] = email_config.recipient_email
        message["Subject"] = subject
        message["Date"] = formatdate(localtime=True)
        message["Message-ID"] = self.build_message_id_for_period_key(
            period_key,
            email_config.sender_email,
        )
        message.set_content(markdown, subtype="plain", charset="utf-8")
        message.add_alternative(self.markdown_to_html(markdown), subtype="html", charset="utf-8")
        return message

    def build_message_id(
        self,
        period_type: str,
        period_start: str,
        period_end: str,
        sender_email: str,
    ) -> str:
        raw_key = f"{period_type}|{period_start}|{period_end}|{sender_email}"
        digest = hashlib.sha256(
            raw_key.encode("utf-8")
        ).hexdigest()[:32]
        sender_domain = sender_email.rsplit("@", 1)[-1]
        safe_domain = sender_domain.encode("idna").decode("ascii")
        return f"<scheduleapp-{digest}@{safe_domain}>"

    def build_message_id_for_period_key(self, period_key: str, sender_email: str) -> str:
        match = re.fullmatch(
            r"(.+)-(\d{4}-\d{2}-\d{2})-(\d{4}-\d{2}-\d{2})",
            period_key,
        )
        if match:
            return self.build_message_id(*match.groups(), sender_email)
        return self.build_message_id(period_key, "", "", sender_email)

    def markdown_to_html(self, markdown: str) -> str:
        lines = markdown.splitlines()
        html_lines = [
            "<!doctype html>",
            '<html><head><meta charset="utf-8">',
            '<style>body{font-family:-apple-system,BlinkMacSystemFont,\'Segoe UI\',sans-serif;line-height:1.65;color:#1f2937;}h1,h2{color:#111827;}li{margin:4px 0;}pre{white-space:pre-wrap;}</style>',
            "</head><body>",
        ]
        in_list = False
        for line in lines:
            stripped = line.strip()
            if not stripped:
                if in_list:
                    html_lines.append("</ul>")
                    in_list = False
                continue
            if stripped.startswith("# "):
                if in_list:
                    html_lines.append("</ul>")
                    in_list = False
                html_lines.append(f"<h1>{html.escape(stripped[2:])}</h1>")
            elif stripped.startswith("## "):
                if in_list:
                    html_lines.append("</ul>")
                    in_list = False
                html_lines.append(f"<h2>{html.escape(stripped[3:])}</h2>")
            elif re.match(r"^[-*]\s+", stripped):
                if not in_list:
                    html_lines.append("<ul>")
                    in_list = True
                html_lines.append(f"<li>{html.escape(stripped[2:])}</li>")
            else:
                if in_list:
                    html_lines.append("</ul>")
                    in_list = False
                html_lines.append(f"<p>{html.escape(stripped)}</p>")
        if in_list:
            html_lines.append("</ul>")
        html_lines.append("</body></html>")
        return "\n".join(html_lines)
