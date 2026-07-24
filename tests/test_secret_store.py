import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.security import secret_store


@unittest.skipUnless(os.name == "nt", "Windows DPAPI is only available on Windows")
class SecretStoreTests(unittest.TestCase):
    def test_dpapi_round_trip_uses_encrypted_temp_store(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "secrets.dat"
            with patch.object(secret_store, "SECRETS_PATH", path):
                secret_store.save_secret("ai_api_key", "fake-api-key")
                secret_store.save_secret("smtp_password", "fake-smtp-password")

                self.assertEqual(secret_store.load_secret("ai_api_key"), "fake-api-key")
                self.assertEqual(secret_store.load_secret("smtp_password"), "fake-smtp-password")
                serialized = path.read_text(encoding="utf-8")
                self.assertNotIn("fake-api-key", serialized)
                self.assertNotIn("fake-smtp-password", serialized)

                secret_store.delete_secret("ai_api_key")
                self.assertEqual(secret_store.load_secret("ai_api_key"), "")
                self.assertEqual(secret_store.load_secret("smtp_password"), "fake-smtp-password")


if __name__ == "__main__":
    unittest.main()
