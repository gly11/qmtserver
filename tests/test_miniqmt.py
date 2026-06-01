from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from qmtserver.miniqmt import (
    QuoteCheckConfig,
    TraderCheckConfig,
    _to_plain,
)
from qmtserver.trader.diagnostics import build_trader_diagnostics


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

    def test_trader_diagnostics_explains_connect_result_without_leaking_account(self) -> None:
        with (
            TemporaryDirectory() as tmp,
            patch(
                "qmtserver.trader.diagnostics.check_xtquant_import",
                return_value={"ok": True, "path": "site-packages/xtquant", "version": None},
            ),
            patch(
                "qmtserver.trader.diagnostics.load_trader_classes",
                return_value=(ConnectMinusOneTrader, FakeStockAccount),
            ),
        ):
            report = build_trader_diagnostics(
                TraderCheckConfig(
                    userdata=Path(tmp),
                    account_id="123456789",
                    account_type="STOCK",
                    session_id=10001,
                )
            )

        self.assertFalse(report["ok"])
        self.assertEqual(report["connect_result"], -1)
        self.assertIn("MiniQMT", " ".join(report["hints"]))
        self.assertIn("123****789", repr(report))
        self.assertNotIn("123456789", repr(report))
        self.assertIn("trader_connect", [step["name"] for step in report["steps"]])

    def test_trader_diagnostics_reports_missing_userdata_without_full_path(self) -> None:
        missing = Path("C:/private/userdata_mini_missing")

        with patch(
            "qmtserver.trader.diagnostics.check_xtquant_import",
            return_value={"ok": True, "path": "site-packages/xtquant", "version": None},
        ):
            report = build_trader_diagnostics(TraderCheckConfig(userdata=missing))

        self.assertFalse(report["ok"])
        self.assertEqual(report["userdata"]["name"], "userdata_mini_missing")
        self.assertFalse(report["userdata"]["exists"])
        self.assertNotIn("C:/private", repr(report))


class FakeStockAccount:
    def __init__(self, account_id: str, account_type: str = "STOCK") -> None:
        self.account_id = account_id
        self.account_type = account_type


class ConnectMinusOneTrader:
    def __init__(self, userdata: str, session_id: int, callback: object) -> None:
        self.userdata = userdata
        self.session_id = session_id
        self.callback = callback
        self.started = False

    def set_timeout(self, timeout_ms: int) -> None:
        self.timeout_ms = timeout_ms

    def start(self) -> None:
        self.started = True

    def connect(self) -> int:
        return -1

    def stop(self) -> None:
        self.started = False


if __name__ == "__main__":
    unittest.main()
