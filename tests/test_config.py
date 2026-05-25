from __future__ import annotations

import unittest
from pathlib import Path

from qmtserver.config import load_settings


class SettingsTests(unittest.TestCase):
    def test_defaults(self) -> None:
        settings = load_settings()

        self.assertEqual(settings.host, "127.0.0.1")
        self.assertEqual(settings.port, 8000)
        self.assertEqual(settings.account_type, "STOCK")
        self.assertFalse(settings.enable_trading)
        self.assertFalse(settings.require_token)
        self.assertTrue(settings.audit_log)
        self.assertTrue(settings.audit_log_args)
        self.assertTrue(settings.connect_on_startup)
        self.assertTrue(settings.connect_quote)
        self.assertTrue(settings.connect_trader)

    def test_overrides(self) -> None:
        settings = load_settings(userdata=Path("userdata_mini"), account_id="10001", port=9000)

        self.assertEqual(settings.userdata, Path("userdata_mini"))
        self.assertEqual(settings.account_id, "10001")
        self.assertEqual(settings.port, 9000)

    def test_require_token_requires_api_token(self) -> None:
        with self.assertRaises(ValueError):
            load_settings(require_token=True, api_token="")


if __name__ == "__main__":
    unittest.main()
