"""Unified user configuration for report API and SMTP integrations."""

import json
import logging
import os
import re
from dataclasses import dataclass
from pathlib import Path

from app.config import BASE_DIR, CONFIG_DIR
from app.security import secret_store
from app.services.report_config import EmailConfig, LLMConfig, ReportDeliveryConfig


logger = logging.getLogger(__name__)
INTEGRATION_SETTINGS_PATH = CONFIG_DIR / "integration_settings.json"
LEGACY_CONFIG_PATH = BASE_DIR / "config" / "report_delivery.json"
DEFAULT_AI_BASE_URL = "https://api.openai.com/v1"
DEFAULT_AI_MODEL = ""
DEFAULT_SMTP_PORT = 465
DEFAULT_ENCRYPTION = "ssl"
EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


@dataclass(frozen=True)
class IntegrationSettings:
    ai: LLMConfig
    email: EmailConfig


class IntegrationConfigService:
    def __init__(
        self,
        path: Path = INTEGRATION_SETTINGS_PATH,
        secret_module=secret_store,
        legacy_path: Path | None = None,
    ):
        self.path = Path(path)
        self.secret_store = secret_module
        self._legacy_path = Path(legacy_path) if legacy_path is not None else LEGACY_CONFIG_PATH

    def default_settings(self) -> IntegrationSettings:
        return IntegrationSettings(
            ai=LLMConfig(DEFAULT_AI_BASE_URL, "", DEFAULT_AI_MODEL, 90, 0.3),
            email=EmailConfig("", DEFAULT_SMTP_PORT, True, "", "", "", DEFAULT_ENCRYPTION),
        )

    def load_settings(self) -> IntegrationSettings:
        self._migrate_legacy_if_needed()
        defaults = self.default_settings()
        data = self._read_json()
        ai_data = data.get("ai") if isinstance(data.get("ai"), dict) else {}
        email_data = data.get("email") if isinstance(data.get("email"), dict) else {}
        encryption = str(email_data.get("encryption") or DEFAULT_ENCRYPTION).lower()
        if encryption not in {"ssl", "starttls", "none"}:
            encryption = DEFAULT_ENCRYPTION
        port = self._safe_int(email_data.get("smtp_port"), defaults.email.smtp_port)
        use_ssl = encryption == "ssl"
        return IntegrationSettings(
            ai=LLMConfig(
                str(ai_data.get("base_url") or defaults.ai.base_url).rstrip("/"),
                self.secret_store.load_secret("ai_api_key"),
                str(ai_data.get("model") or defaults.ai.model),
                self._safe_int(ai_data.get("timeout_seconds"), defaults.ai.timeout_seconds),
                self._safe_float(ai_data.get("temperature"), defaults.ai.temperature),
            ),
            email=EmailConfig(
                str(email_data.get("smtp_host") or ""),
                port,
                use_ssl,
                str(email_data.get("sender") or ""),
                self.secret_store.load_secret("smtp_password"),
                str(email_data.get("recipient") or ""),
                encryption,
            ),
        )

    def get_ai_config(self) -> LLMConfig:
        return self.load_settings().ai

    def get_email_config(self) -> EmailConfig:
        return self.load_settings().email

    def get_report_config(self) -> ReportDeliveryConfig:
        settings = self.load_settings()
        errors = self.validate(settings.ai, settings.email)
        return ReportDeliveryConfig(True, settings.ai, settings.email, tuple(errors))

    def save_settings(
        self,
        *,
        base_url: str,
        model: str,
        sender: str,
        smtp_host: str,
        smtp_port: int,
        encryption: str,
        recipient: str,
        api_key: str | None = None,
        smtp_password: str | None = None,
    ) -> None:
        if encryption not in {"ssl", "starttls", "none"}:
            raise ValueError("加密方式无效")
        data = {
            "ai": {
                "base_url": base_url.strip().rstrip("/"),
                "model": model.strip(),
                "timeout_seconds": 90,
                "temperature": 0.3,
            },
            "email": {
                "sender": sender.strip(),
                "smtp_host": smtp_host.strip(),
                "smtp_port": int(smtp_port),
                "encryption": encryption,
                "recipient": recipient.strip(),
            },
        }
        self._atomic_write(data)
        if api_key is not None:
            if api_key:
                self.secret_store.save_secret("ai_api_key", api_key)
            else:
                self.secret_store.delete_secret("ai_api_key")
        if smtp_password is not None:
            if smtp_password:
                self.secret_store.save_secret("smtp_password", smtp_password)
            else:
                self.secret_store.delete_secret("smtp_password")

    def validate(self, ai: LLMConfig, email: EmailConfig) -> list[str]:
        errors = []
        if not ai.api_key:
            errors.append("API Key")
        if not ai.base_url:
            errors.append("API Base URL")
        if not ai.model:
            errors.append("模型名称")
        if not email.sender_email or not EMAIL_PATTERN.match(email.sender_email):
            errors.append("发件人邮箱")
        if not email.smtp_host:
            errors.append("SMTP 服务器")
        if not 1 <= email.smtp_port <= 65535:
            errors.append("SMTP 端口")
        if not email.auth_code:
            errors.append("邮箱授权码")
        if not email.recipient_email or not EMAIL_PATTERN.match(email.recipient_email):
            errors.append("收件人邮箱")
        return errors

    def _read_json(self) -> dict:
        if not self.path.exists():
            return {}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except (OSError, json.JSONDecodeError, UnicodeError):
            logger.warning("integration settings unreadable; using defaults")
            return {}

    def _atomic_write(self, data: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temporary, self.path)

    def _migrate_legacy_if_needed(self) -> None:
        if self.path.exists() or not self.legacy_path.exists():
            return
        try:
            data = json.loads(self.legacy_path.read_text(encoding="utf-8"))
            ai = data.get("llm") if isinstance(data.get("llm"), dict) else {}
            email = data.get("email") if isinstance(data.get("email"), dict) else {}
            encryption = "ssl" if bool(email.get("use_ssl", True)) else "starttls"
            migrated_settings = {
                "ai": {"base_url": str(ai.get("base_url") or DEFAULT_AI_BASE_URL), "model": str(ai.get("model") or ""), "timeout_seconds": 90, "temperature": 0.3},
                "email": {"sender": str(email.get("sender_email") or ""), "smtp_host": str(email.get("smtp_host") or ""), "smtp_port": self._safe_int(email.get("smtp_port"), DEFAULT_SMTP_PORT), "encryption": encryption, "recipient": str(email.get("recipient_email") or "")},
            }
            if ai.get("api_key"):
                self.secret_store.save_secret("ai_api_key", str(ai["api_key"]))
            if email.get("auth_code"):
                self.secret_store.save_secret("smtp_password", str(email["auth_code"]))
            self._atomic_write(migrated_settings)
            logger.info("legacy report configuration migrated")
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            logger.warning("legacy report configuration migration skipped")

    @property
    def legacy_path(self) -> Path:
        return self._legacy_path

    @staticmethod
    def _safe_int(value, default):
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _safe_float(value, default):
        try:
            return float(value)
        except (TypeError, ValueError):
            return default
