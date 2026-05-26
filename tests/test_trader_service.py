from __future__ import annotations

import unittest

from qmtserver.config import load_settings
from qmtserver.errors import QmtAccountNotAllowedError, QmtTraderAccountRequiredError
from qmtserver.trader.service import TraderReadonlyService, resolve_stock_account
from tests.fakes import DisconnectedTraderService, FakeService, FakeTrader


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


class TraderReadonlyServiceTests(unittest.TestCase):
    def test_account_status_returns_stable_envelope(self) -> None:
        service = TraderReadonlyService(FakeService(account_id="10001"))

        response = service.account_status()

        self.assertTrue(response["ok"])
        self.assertEqual(response["meta"]["schema"], "trader.readonly.v1")
        self.assertEqual(response["data"]["statuses"][0]["account_type"], "STOCK")

    def test_account_status_hides_accounts_outside_allowlist(self) -> None:
        fake_service = FakeService(account_id="10001")
        fake_service.trader = _MultiAccountStatusTrader()
        service = TraderReadonlyService(fake_service)

        response = service.account_status()

        self.assertTrue(response["ok"])
        self.assertEqual(
            [item["account_id"] for item in response["data"]["statuses"]],
            ["10001"],
        )

    def test_asset_resolves_default_account(self) -> None:
        service = TraderReadonlyService(FakeService(account_id="123456789"))

        response = service.asset(account_id=None, account_type=None)

        self.assertTrue(response["ok"])
        self.assertEqual(response["data"]["asset"]["account_id"], "123456789")
        self.assertEqual(response["data"]["asset"]["cash"], 1000.0)
        self.assertEqual(response["meta"]["account_id"], "123****789")

    def test_positions_orders_and_trades_return_lists(self) -> None:
        service = TraderReadonlyService(FakeService(account_id="10001"))

        positions = service.positions(account_id=None, account_type=None)
        orders = service.orders(account_id=None, account_type=None, cancelable_only=True)
        trades = service.trades(account_id=None, account_type=None)

        self.assertEqual(positions["data"]["positions"][0]["stock_code"], "000001.SZ")
        self.assertTrue(orders["data"]["cancelable_only"])
        self.assertTrue(orders["data"]["orders"][0]["extra"]["cancelable_only"])
        self.assertEqual(trades["data"]["trades"][0]["trade_id"], "T10001")

    def test_missing_account_returns_error_response(self) -> None:
        service = TraderReadonlyService(FakeService(account_id=None))

        response = service.asset(account_id=None, account_type=None)

        self.assertFalse(response["ok"])
        self.assertEqual(response["error"]["code"], "TRADER_ACCOUNT_REQUIRED")

    def test_disconnected_trader_returns_error_response(self) -> None:
        service = TraderReadonlyService(DisconnectedTraderService(account_id="10001"))

        response = service.asset(account_id=None, account_type=None)

        self.assertFalse(response["ok"])
        self.assertEqual(response["error"]["code"], "TARGET_NOT_CONNECTED")


def _object(**values: object) -> object:
    item = type("RawObject", (), {})()
    for key, value in values.items():
        setattr(item, key, value)
    return item


class _MultiAccountStatusTrader(FakeTrader):
    def query_account_status(self) -> list[object]:
        return [
            _object(account_id="10001", account_type="STOCK", status=0),
            _object(account_id="10002", account_type="STOCK", status=0),
        ]


if __name__ == "__main__":
    unittest.main()
