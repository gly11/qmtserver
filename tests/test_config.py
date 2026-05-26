from __future__ import annotations

import unittest
from pathlib import Path

from qmtserver.config import load_settings


class SettingsTests(unittest.TestCase):
    def test_defaults(self) -> None:
        settings = load_settings(_env_file=None)

        self.assertEqual(settings.host, "127.0.0.1")
        self.assertEqual(settings.port, 8000)
        self.assertEqual(settings.account_type, "STOCK")
        self.assertFalse(settings.enable_trading)
        self.assertTrue(settings.trading_dry_run)
        self.assertEqual(settings.max_order_volume, 100000)
        self.assertEqual(settings.max_order_amount, 1000000)
        self.assertEqual(settings.daily_max_order_volume, 1000000)
        self.assertEqual(settings.daily_max_order_amount, 5000000)
        self.assertTrue(settings.require_trade_confirmation)
        self.assertEqual(settings.trade_confirmation_text, "I_UNDERSTAND_REAL_TRADING")
        self.assertTrue(settings.trade_audit_log)
        self.assertEqual(settings.trading_allowed_accounts(), set())
        self.assertEqual(settings.trading_allowed_symbols(), set())
        self.assertEqual(settings.trading_blocked_symbols(), set())
        self.assertEqual(settings.order_cache_size, 1000)
        self.assertEqual(settings.event_cache_size, 1000)
        self.assertEqual(settings.log_level, "INFO")
        self.assertEqual(settings.log_dir, Path("logs"))
        self.assertFalse(settings.log_json)
        self.assertFalse(settings.require_token)
        self.assertTrue(settings.audit_log)
        self.assertTrue(settings.audit_log_args)
        self.assertTrue(settings.connect_on_startup)
        self.assertTrue(settings.connect_quote)
        self.assertTrue(settings.connect_trader)
        self.assertFalse(settings.transparent_rpc)
        self.assertEqual(settings.transparent_rpc_allowed_targets(), {"xtdata"})
        self.assertFalse(settings.transparent_rpc_allow_trader)
        self.assertFalse(settings.transparent_rpc_allow_trading)

    def test_overrides(self) -> None:
        settings = load_settings(userdata=Path("userdata_mini"), account_id="10001", port=9000)

        self.assertEqual(settings.userdata, Path("userdata_mini"))
        self.assertEqual(settings.account_id, "10001")
        self.assertEqual(settings.port, 9000)

    def test_require_token_requires_api_token(self) -> None:
        with self.assertRaises(ValueError):
            load_settings(_env_file=None, require_token=True, api_token="")

    def test_trading_allowed_accounts_falls_back_to_account_id(self) -> None:
        settings = load_settings(account_id="10001")

        self.assertEqual(settings.trading_allowed_accounts(), {"10001"})

    def test_trading_allowed_accounts_parses_comma_list(self) -> None:
        settings = load_settings(account_id="10001", allowed_accounts="10002, 10003")

        self.assertEqual(settings.trading_allowed_accounts(), {"10002", "10003"})

    def test_trading_symbol_lists_parse_comma_lists(self) -> None:
        settings = load_settings(
            allowed_symbols="000001.SZ, 600000.SH",
            blocked_symbols="300001.SZ",
        )

        self.assertEqual(settings.trading_allowed_symbols(), {"000001.SZ", "600000.SH"})
        self.assertEqual(settings.trading_blocked_symbols(), {"300001.SZ"})

    def test_transparent_rpc_targets_parse_comma_list(self) -> None:
        settings = load_settings(transparent_rpc_targets="xtdata, trader")

        self.assertEqual(settings.transparent_rpc_allowed_targets(), {"xtdata", "trader"})


if __name__ == "__main__":
    unittest.main()
