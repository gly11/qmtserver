from __future__ import annotations

import unittest
from pathlib import Path

from qmtserver.miniqmt import QuoteCheckConfig, TraderCheckConfig, _to_plain


class MiniQmtModelTests(unittest.TestCase):
    def test_quote_config_defaults(self) -> None:
        config = QuoteCheckConfig()

        self.assertEqual(config.code, "000001.SZ")
        self.assertEqual(config.ip, "")
        self.assertIsNone(config.port)

    def test_trader_config_defaults(self) -> None:
        config = TraderCheckConfig(userdata=Path("userdata"))

        self.assertEqual(config.account_type, "STOCK")
        self.assertEqual(config.timeout_ms, 5000)
        self.assertIsNone(config.account_id)

    def test_to_plain_converts_objects(self) -> None:
        class Item:
            def __init__(self) -> None:
                self.value = 1
                self._private = "hidden"

        self.assertEqual(_to_plain(Item()), {"value": 1})


if __name__ == "__main__":
    unittest.main()
