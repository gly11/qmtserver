from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from qmtserver.api import create_app
from qmtserver.config import load_settings


class FakeTarget:
    def get_full_tick(self, codes: list[str]) -> dict[str, object]:
        return {"codes": codes}


class FakeTrader:
    def query_stock_asset(self, account: object) -> dict[str, object]:
        return {"account_id": getattr(account, "account_id", None)}


class FakeService:
    def __init__(self, *, enable_trading: bool = False) -> None:
        self.settings = load_settings(auto_connect=False, enable_trading=enable_trading)
        self.connected = False

    def status(self) -> dict[str, object]:
        return {
            "ok": True,
            "quote": {"connected": self.connected},
            "trader": {"connected": self.connected},
            "lifecycle": {
                "state": "connected" if self.connected else "disconnected",
                "last_error": None,
            },
        }

    def connect(self) -> dict[str, object]:
        self.connected = True
        return self.status()

    def reconnect(self) -> dict[str, object]:
        self.connected = True
        return self.status()

    def disconnect(self) -> dict[str, object]:
        self.connected = False
        return self.status()

    def get_target(self, target: str) -> object:
        if target == "xtdata":
            return FakeTarget()
        if target == "trader":
            return FakeTrader()
        return FakeTarget()


class ApiTests(unittest.TestCase):
    def test_health(self) -> None:
        app = create_app(load_settings(auto_connect=False), connect_on_startup=False)

        with TestClient(app) as client:
            response = client.get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])

    def test_qmt_status_and_connect(self) -> None:
        app = create_app(load_settings(auto_connect=False), connect_on_startup=False)

        with TestClient(app) as client:
            app.state.qmt_service = FakeService()
            status = client.get("/qmt/status")
            connected = client.post("/qmt/connect")

        self.assertFalse(status.json()["quote"]["connected"])
        self.assertTrue(connected.json()["quote"]["connected"])

    def test_qmt_reconnect_and_disconnect(self) -> None:
        app = create_app(load_settings(auto_connect=False), connect_on_startup=False)

        with TestClient(app) as client:
            app.state.qmt_service = FakeService()
            reconnected = client.post("/qmt/reconnect")
            disconnected = client.post("/qmt/disconnect")

        self.assertTrue(reconnected.json()["quote"]["connected"])
        self.assertFalse(disconnected.json()["quote"]["connected"])
        self.assertEqual(disconnected.json()["lifecycle"]["state"], "disconnected")

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

    def test_health_does_not_require_token(self) -> None:
        app = create_app(
            load_settings(auto_connect=False, api_token="dev-token"),
            connect_on_startup=False,
        )

        with TestClient(app) as client:
            response = client.get("/health")

        self.assertEqual(response.status_code, 200)

    def test_protected_routes_require_token_when_configured(self) -> None:
        app = create_app(
            load_settings(auto_connect=False, api_token="dev-token"),
            connect_on_startup=False,
        )

        with TestClient(app) as client:
            app.state.qmt_service = FakeService()
            status = client.get("/qmt/status")
            methods = client.get("/rpc/methods")
            rpc = client.post(
                "/rpc",
                json={"target": "xtdata", "method": "get_full_tick", "args": [], "kwargs": {}},
            )

        self.assertEqual(status.status_code, 401)
        self.assertEqual(methods.status_code, 401)
        self.assertEqual(rpc.status_code, 401)
        self.assertEqual(status.json()["detail"]["code"], "UNAUTHORIZED")

    def test_protected_routes_accept_valid_bearer_token(self) -> None:
        app = create_app(
            load_settings(auto_connect=False, api_token="dev-token"),
            connect_on_startup=False,
        )

        with TestClient(app) as client:
            app.state.qmt_service = FakeService()
            response = client.get(
                "/qmt/status",
                headers={"Authorization": "Bearer dev-token"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertIn("quote", response.json())

    def test_protected_routes_reject_invalid_bearer_token(self) -> None:
        app = create_app(
            load_settings(auto_connect=False, api_token="dev-token"),
            connect_on_startup=False,
        )

        with TestClient(app) as client:
            app.state.qmt_service = FakeService()
            response = client.get(
                "/qmt/status",
                headers={"Authorization": "Bearer wrong-token"},
            )

        self.assertEqual(response.status_code, 401)


if __name__ == "__main__":
    unittest.main()
