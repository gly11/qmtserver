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
        self.assertTrue(settings.connect_on_startup)
        self.assertTrue(settings.connect_quote)
        self.assertTrue(settings.connect_trader)

    def test_overrides(self) -> None:
        settings = load_settings(userdata=Path("userdata_mini"), account_id="10001", port=9000)

        self.assertEqual(settings.userdata, Path("userdata_mini"))
        self.assertEqual(settings.account_id, "10001")
        self.assertEqual(settings.port, 9000)


if __name__ == "__main__":
    unittest.main()
