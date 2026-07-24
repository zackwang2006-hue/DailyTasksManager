import json
from dataclasses import dataclass
from pathlib import Path

from app.config import REPORT_DELIVERY_CONFIG_PATH


DEFAULT_REPORT_CONFIG = {
    "enabled": False,
    "llm": {
        "base_url": "https://api.openai.com/v1",
        "api_key": "",
        "model": "",
        "timeout_seconds": 90,
        "temperature": 0.3,
    },
    "email": {
        "smtp_host": "",
        "smtp_port": 465,
        "use_ssl": True,
        "sender_email": "",
        "auth_code": "",
        "recipient_email": "",
    },
}


@dataclass(frozen=True)
class LLMConfig:
    base_url: str
    api_key: str
    model: str
    timeout_seconds: int
    temperature: float


@dataclass(frozen=True)
class EmailConfig:
    smtp_host: str
    smtp_port: int
    use_ssl: bool
    sender_email: str
    auth_code: str
    recipient_email: str
    encryption: str = ""


@dataclass(frozen=True)
class ReportDeliveryConfig:
    enabled: bool
    llm: LLMConfig
    email: EmailConfig
    errors: tuple[str, ...] = ()

    @property
    def is_ready(self) -> bool:
        return not self.errors


class ReportConfigLoader:
    def __init__(self, path: Path | None = None):
        self.path = Path(path) if path is not None else None
        self._integration_service = None
        if path is None:
            from app.services.integration_config_service import IntegrationConfigService

            self._integration_service = IntegrationConfigService()

    def ensure_default_file(self) -> None:
        if self._integration_service is not None:
            return
        if self.path.exists():
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(DEFAULT_REPORT_CONFIG, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def load(self) -> ReportDeliveryConfig:
        if self._integration_service is not None:
            return self._integration_service.get_report_config()
        self.ensure_default_file()
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            return self.disabled_with_error(f"报告配置读取失败：{error.__class__.__name__}")

        if not isinstance(data, dict):
            return self.disabled_with_error("报告配置格式错误：根节点必须是对象")

        enabled = bool(data.get("enabled", False))
        llm_data = data.get("llm") if isinstance(data.get("llm"), dict) else {}
        email_data = data.get("email") if isinstance(data.get("email"), dict) else {}

        llm = LLMConfig(
            base_url=str(llm_data.get("base_url") or "").rstrip("/"),
            api_key=str(llm_data.get("api_key") or ""),
            model=str(llm_data.get("model") or ""),
            timeout_seconds=self.safe_int(llm_data.get("timeout_seconds"), 90),
            temperature=self.safe_float(llm_data.get("temperature"), 0.3),
        )
        email = EmailConfig(
            smtp_host=str(email_data.get("smtp_host") or ""),
            smtp_port=self.safe_int(email_data.get("smtp_port"), 465),
            use_ssl=bool(email_data.get("use_ssl", True)),
            sender_email=str(email_data.get("sender_email") or ""),
            auth_code=str(email_data.get("auth_code") or ""),
            recipient_email=str(email_data.get("recipient_email") or ""),
        )

        return ReportDeliveryConfig(
            enabled=enabled,
            llm=llm,
            email=email,
            errors=tuple(self.validate_required_fields(llm, email)),
        )

    def disabled_with_error(self, message: str) -> ReportDeliveryConfig:
        return ReportDeliveryConfig(
            enabled=False,
            llm=LLMConfig("", "", "", 90, 0.3),
            email=EmailConfig("", 465, True, "", "", ""),
            errors=(message,),
        )

    def validate_required_fields(self, llm: LLMConfig, email: EmailConfig) -> list[str]:
        errors = []
        if not llm.base_url:
            errors.append("llm.base_url 不能为空")
        if not llm.api_key:
            errors.append("llm.api_key 不能为空")
        if not llm.model:
            errors.append("llm.model 不能为空")
        if llm.timeout_seconds <= 0:
            errors.append("llm.timeout_seconds 必须大于 0")
        if not email.smtp_host:
            errors.append("email.smtp_host 不能为空")
        if email.smtp_port <= 0:
            errors.append("email.smtp_port 必须大于 0")
        if not email.sender_email:
            errors.append("email.sender_email 不能为空")
        if not email.auth_code:
            errors.append("email.auth_code 不能为空")
        if not email.recipient_email:
            errors.append("email.recipient_email 不能为空")
        return errors

    def safe_int(self, value, default: int) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    def safe_float(self, value, default: float) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default
