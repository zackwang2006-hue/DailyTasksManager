import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.services.integration_config_service import IntegrationConfigService
from app.services.report_config import LLMConfig
from app.services.report_generation_service import ReportGenerationService


class FakeSecretStore:
    def __init__(self):
        self.values = {}

    def save_secret(self, name, value):
        self.values[name] = "encrypted:" + value

    def load_secret(self, name):
        value = self.values.get(name, "")
        return value.removeprefix("encrypted:")

    def delete_secret(self, name):
        self.values.pop(name, None)


class FakeResponse:
    status = 200

    def read(self):
        return b'{"choices": [{"message": {"content": "OK"}}]}'

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False


class IntegrationConfigTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        root = Path(self.temp_dir.name)
        self.settings_path = root / "config" / "integration_settings.json"
        self.legacy_path = root / "legacy" / "report_delivery.json"
        self.secrets = FakeSecretStore()
        self.service = IntegrationConfigService(
            self.settings_path,
            secret_module=self.secrets,
            legacy_path=self.legacy_path,
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_plain_settings_and_secrets_are_separate(self):
        self.service.save_settings(
            base_url="https://example.test/v1",
            model="mock-model",
            sender="sender@example.test",
            smtp_host="smtp.example.test",
            smtp_port=465,
            encryption="ssl",
            recipient="recipient@example.test",
            api_key="fake-api-key",
            smtp_password="fake-smtp-password",
        )

        data = json.loads(self.settings_path.read_text(encoding="utf-8"))
        serialized = json.dumps(data)
        self.assertNotIn("fake-api-key", serialized)
        self.assertNotIn("fake-smtp-password", serialized)
        self.assertEqual(self.service.get_ai_config().api_key, "fake-api-key")
        self.assertEqual(self.service.get_email_config().auth_code, "fake-smtp-password")

    def test_corrupt_settings_fall_back_to_defaults(self):
        self.settings_path.parent.mkdir(parents=True)
        self.settings_path.write_text("{broken", encoding="utf-8")
        settings = self.service.load_settings()
        self.assertEqual(settings.ai.base_url, "https://api.openai.com/v1")
        self.assertEqual(settings.email.smtp_port, 465)

    def test_blank_secret_preserves_existing_secret_until_explicit_delete(self):
        self.service.save_settings(
            base_url="https://example.test/v1",
            model="mock-model",
            sender="sender@example.test",
            smtp_host="smtp.example.test",
            smtp_port=465,
            encryption="ssl",
            recipient="recipient@example.test",
            api_key="keep-api-key",
            smtp_password="keep-password",
        )
        self.service.save_settings(
            base_url="https://example.test/v1",
            model="mock-model",
            sender="sender@example.test",
            smtp_host="smtp.example.test",
            smtp_port=465,
            encryption="ssl",
            recipient="recipient@example.test",
        )
        self.assertEqual(self.service.get_ai_config().api_key, "keep-api-key")
        self.assertEqual(self.service.get_email_config().auth_code, "keep-password")

        self.service.save_settings(
            base_url="https://example.test/v1",
            model="mock-model",
            sender="sender@example.test",
            smtp_host="smtp.example.test",
            smtp_port=465,
            encryption="ssl",
            recipient="recipient@example.test",
            api_key="",
            smtp_password="",
        )
        self.assertEqual(self.service.get_ai_config().api_key, "")
        self.assertEqual(self.service.get_email_config().auth_code, "")

    def test_api_test_is_minimal_and_does_not_save_data(self):
        config = LLMConfig("https://example.test/v1", "fake-api-key", "mock-model", 3, 0.0)
        with patch("urllib.request.urlopen", return_value=FakeResponse()) as request:
            ReportGenerationService().test_connection(config)
        request.assert_called_once()
        self.assertNotIn(b"fake-api-key", request.call_args.args[0].data)


if __name__ == "__main__":
    unittest.main()
