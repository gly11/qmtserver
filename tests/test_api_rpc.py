from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from qmtserver.api import create_app
from qmtserver.config import load_settings
from tests.fakes import FakeService


class ApiRpcTests(unittest.TestCase):
    def test_rpc_methods(self) -> None:
        app = create_app(load_settings(auto_connect=False), connect_on_startup=False)

        with TestClient(app) as client:
            app.state.qmt_service = FakeService()
            response = client.get("/rpc/methods")

        self.assertIn("get_full_tick", response.json()["methods"]["xtdata"])
        self.assertIn("specs", response.json())

    def test_rpc_dispatch(self) -> None:
        app = create_app(load_settings(auto_connect=False), connect_on_startup=False)

        with TestClient(app) as client:
            app.state.qmt_service = FakeService()
            response = client.post(
                "/rpc",
                json={
                    "target": "xtdata",
                    "method": "get_full_tick",
                    "args": [["000001.SZ"]],
                    "kwargs": {},
                },
            )

        body = response.json()
        self.assertTrue(body["ok"])
        self.assertEqual(body["data"], {"codes": ["000001.SZ"]})

    def test_v1_rpc_response_includes_contract_meta(self) -> None:
        app = create_app(load_settings(auto_connect=False), connect_on_startup=False)

        with TestClient(app) as client:
            app.state.qmt_service = FakeService()
            response = client.post(
                "/v1/rpc",
                headers={"X-Request-ID": "contract-request"},
                json={
                    "target": "trader",
                    "method": "order_stock",
                    "args": [],
                    "kwargs": {},
                },
            )

        body = response.json()
        self.assertFalse(body["ok"])
        self.assertEqual(body["error"]["code"], "TRADING_DISABLED")
        self.assertEqual(body["meta"]["request_id"], "contract-request")
        self.assertEqual(body["meta"]["version"], "v1")

    def test_v1_methods_metrics_and_old_routes_are_available(self) -> None:
        app = create_app(load_settings(auto_connect=False), connect_on_startup=False)

        with TestClient(app) as client:
            app.state.qmt_service = FakeService()
            old_methods = client.get("/rpc/methods")
            versioned_methods = client.get("/v1/rpc/methods")
            versioned_metrics = client.get("/v1/metrics")

        self.assertEqual(old_methods.status_code, 200)
        self.assertEqual(versioned_methods.status_code, 200)
        self.assertIn("specs", versioned_methods.json())
        self.assertTrue(versioned_metrics.json()["ok"])

    def test_rpc_rejects_trading_method(self) -> None:
        app = create_app(load_settings(auto_connect=False), connect_on_startup=False)

        with TestClient(app) as client:
            app.state.qmt_service = FakeService()
            response = client.post(
                "/rpc",
                json={
                    "target": "trader",
                    "method": "order_stock",
                    "args": [],
                    "kwargs": {},
                },
            )

        body = response.json()
        self.assertFalse(body["ok"])
        self.assertEqual(body["error"]["code"], "TRADING_DISABLED")

    def test_rpc_trading_dry_run(self) -> None:
        app = create_app(
            load_settings(auto_connect=False, account_id="10001"),
            connect_on_startup=False,
        )

        with TestClient(app) as client:
            service = FakeService(enable_trading=True, trading_dry_run=True, account_id="10001")
            app.state.qmt_service = service
            response = client.post(
                "/rpc",
                json={
                    "target": "trader",
                    "method": "order_stock",
                    "args": [
                        {
                            "__type__": "StockAccount",
                            "account_id": "10001",
                            "account_type": "STOCK",
                        },
                        "000001.SZ",
                        23,
                        100,
                        5,
                        10.5,
                    ],
                    "kwargs": {},
                },
            )

        body = response.json()
        self.assertTrue(body["ok"])
        self.assertEqual(body["data"]["dry_run"], True)
        self.assertEqual(service.trader.calls, [])

    def test_rpc_dispatches_trader_query_stock_asset(self) -> None:
        app = create_app(load_settings(auto_connect=False), connect_on_startup=False)

        with TestClient(app) as client:
            app.state.qmt_service = FakeService()
            response = client.post(
                "/rpc",
                json={
                    "target": "trader",
                    "method": "query_stock_asset",
                    "args": [
                        {
                            "__type__": "StockAccount",
                            "account_id": "10001",
                            "account_type": "STOCK",
                        }
                    ],
                    "kwargs": {},
                },
            )

        body = response.json()
        self.assertTrue(body["ok"])
        self.assertEqual(body["data"], {"account_id": "10001"})


if __name__ == "__main__":
    unittest.main()
