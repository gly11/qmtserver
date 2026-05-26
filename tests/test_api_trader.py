from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from qmtserver.api import create_app
from qmtserver.config import load_settings
from tests.fakes import DisconnectedTraderService, FakeService


class ApiTraderTests(unittest.TestCase):
    def test_trader_account_status_endpoint(self) -> None:
        app = create_app(load_settings(auto_connect=False), connect_on_startup=False)

        with TestClient(app) as client:
            app.state.qmt_service = FakeService(account_id="10001")
            response = client.get("/v1/trader/account-status")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["ok"])
        self.assertEqual(body["meta"]["schema"], "trader.readonly.v1")
        self.assertEqual(body["data"]["statuses"][0]["account_type"], "STOCK")

    def test_trader_asset_endpoint_resolves_account(self) -> None:
        app = create_app(load_settings(auto_connect=False), connect_on_startup=False)

        with TestClient(app) as client:
            app.state.qmt_service = FakeService(account_id="123456789")
            response = client.get("/v1/trader/asset")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["ok"])
        self.assertEqual(body["data"]["asset"]["account_id"], "123456789")
        self.assertEqual(body["meta"]["account_id"], "123****789")

    def test_trader_positions_orders_and_trades_endpoints(self) -> None:
        app = create_app(load_settings(auto_connect=False), connect_on_startup=False)

        with TestClient(app) as client:
            app.state.qmt_service = FakeService(account_id="10001")
            positions = client.get("/v1/trader/positions")
            orders = client.get("/v1/trader/orders?cancelable_only=true")
            trades = client.get("/v1/trader/trades")

        self.assertEqual(positions.status_code, 200)
        self.assertEqual(orders.status_code, 200)
        self.assertEqual(trades.status_code, 200)
        self.assertEqual(positions.json()["data"]["positions"][0]["stock_code"], "000001.SZ")
        self.assertTrue(orders.json()["data"]["cancelable_only"])
        self.assertEqual(trades.json()["data"]["trades"][0]["trade_id"], "T10001")

    def test_trader_endpoint_reports_missing_account(self) -> None:
        app = create_app(load_settings(auto_connect=False), connect_on_startup=False)

        with TestClient(app) as client:
            app.state.qmt_service = FakeService(account_id=None)
            response = client.get("/v1/trader/asset")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertFalse(body["ok"])
        self.assertEqual(body["error"]["code"], "TRADER_ACCOUNT_REQUIRED")

    def test_trader_endpoint_reports_disconnected_trader(self) -> None:
        app = create_app(load_settings(auto_connect=False), connect_on_startup=False)

        with TestClient(app) as client:
            app.state.qmt_service = DisconnectedTraderService(account_id="10001")
            response = client.get("/v1/trader/asset")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertFalse(body["ok"])
        self.assertEqual(body["error"]["code"], "TARGET_NOT_CONNECTED")


if __name__ == "__main__":
    unittest.main()
