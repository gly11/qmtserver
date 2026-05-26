from __future__ import annotations

import unittest

from qmtserver.config import load_settings
from qmtserver.errors import QmtAccountNotAllowedError, QmtTraderAccountRequiredError
from qmtserver.trader.service import resolve_stock_account


class TraderServiceAccountTests(unittest.TestCase):
    def test_resolves_default_account_from_settings(self) -> None:
        settings = load_settings(_env_file=None, account_id="10001", account_type="STOCK")

        account = resolve_stock_account(settings, account_id=None, account_type=None)

        self.assertEqual(account.account_id, "10001")
        self.assertEqual(account.account_type, "STOCK")

    def test_explicit_account_overrides_settings_account(self) -> None:
        settings = load_settings(
            _env_file=None,
            account_id="10001",
            account_type="STOCK",
            allowed_accounts="10001,10002",
        )

        account = resolve_stock_account(settings, account_id="10002", account_type="CREDIT")

        self.assertEqual(account.account_id, "10002")
        self.assertEqual(account.account_type, "CREDIT")

    def test_rejects_account_outside_allowlist(self) -> None:
        settings = load_settings(
            _env_file=None,
            account_id="10001",
            allowed_accounts="10001",
        )

        with self.assertRaises(QmtAccountNotAllowedError):
            resolve_stock_account(settings, account_id="10002", account_type="STOCK")

    def test_requires_account_id(self) -> None:
        settings = load_settings(_env_file=None, account_id=None)

        with self.assertRaises(QmtTraderAccountRequiredError):
            resolve_stock_account(settings, account_id=None, account_type=None)


class TraderServiceNormalizerTests(unittest.TestCase):
    def test_asset_normalizer_uses_stable_fields_and_extra(self) -> None:
        from qmtserver.trader.models import normalize_asset

        raw = _object(
            account_id="10001",
            cash=100.0,
            frozen_cash=1.0,
            market_value=200.0,
            total_asset=300.0,
            fetch_balance=99.0,
            unknown_field="kept",
            _private="hidden",
        )

        self.assertEqual(
            normalize_asset(raw),
            {
                "account_id": "10001",
                "cash": 100.0,
                "frozen_cash": 1.0,
                "market_value": 200.0,
                "total_asset": 300.0,
                "fetch_balance": 99.0,
                "extra": {"unknown_field": "kept"},
            },
        )

    def test_position_normalizer_uses_stable_fields(self) -> None:
        from qmtserver.trader.models import normalize_position

        raw = _object(
            account_id="10001",
            stock_code="000001.SZ",
            volume=100,
            can_use_volume=80,
            open_price=10.0,
            market_value=1100.0,
        )

        self.assertEqual(normalize_position(raw)["stock_code"], "000001.SZ")
        self.assertEqual(normalize_position(raw)["volume"], 100)
        self.assertIn("extra", normalize_position(raw))

    def test_order_trade_and_account_status_normalizers(self) -> None:
        from qmtserver.trader.models import (
            normalize_account_status,
            normalize_order,
            normalize_trade,
        )

        status = normalize_account_status(
            _object(account_id="10001", account_type="STOCK", status=0)
        )
        order = normalize_order(_object(account_id="10001", order_id=1, stock_code="000001.SZ"))
        trade = normalize_trade(_object(account_id="10001", trade_id="T1", stock_code="000001.SZ"))

        self.assertEqual(status["account_type"], "STOCK")
        self.assertEqual(order["order_id"], 1)
        self.assertEqual(trade["trade_id"], "T1")


def _object(**values: object) -> object:
    item = type("RawObject", (), {})()
    for key, value in values.items():
        setattr(item, key, value)
    return item


if __name__ == "__main__":
    unittest.main()
