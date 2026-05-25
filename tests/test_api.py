from __future__ import annotations

import unittest

from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from qmtserver.api import create_app
from qmtserver.config import load_settings


class FakeTarget:
    def get_full_tick(self, codes: list[str]) -> dict[str, object]:
        return {"codes": codes}


class FakeTrader:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[object, ...]]] = []

    def query_stock_asset(self, account: object) -> dict[str, object]:
        return {"account_id": getattr(account, "account_id", None)}

    def order_stock(self, *args: object) -> int:
        self.calls.append(("order_stock", args))
        return 10001


class FakeService:
    def __init__(
        self,
        *,
        enable_trading: bool = False,
        trading_dry_run: bool = True,
        account_id: str | None = None,
    ) -> None:
        self.settings = load_settings(
            auto_connect=False,
            enable_trading=enable_trading,
            trading_dry_run=trading_dry_run,
            account_id=account_id,
        )
        self.connected = False
        self.trader = FakeTrader()
        self.metrics: object | None = None

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
            return self.trader
        return FakeTarget()


class ApiTests(unittest.TestCase):
    def test_health(self) -> None:
        app = create_app(load_settings(auto_connect=False), connect_on_startup=False)

        with TestClient(app) as client:
            response = client.get("/health")
            versioned = client.get("/v1/health")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])
        self.assertEqual(versioned.status_code, 200)
        self.assertIn("v1", versioned.json()["api_versions"])

    def test_qmt_status_and_connect(self) -> None:
        app = create_app(load_settings(auto_connect=False), connect_on_startup=False)

        with TestClient(app) as client:
            app.state.qmt_service = FakeService()
            status = client.get("/qmt/status")
            connected = client.post("/qmt/connect")

        self.assertFalse(status.json()["quote"]["connected"])
        self.assertTrue(connected.json()["quote"]["connected"])

    def test_request_id_header_is_returned(self) -> None:
        app = create_app(load_settings(auto_connect=False), connect_on_startup=False)

        with TestClient(app) as client:
            response = client.get("/health", headers={"X-Request-ID": "test-request"})

        self.assertEqual(response.headers["X-Request-ID"], "test-request")

    def test_metrics_endpoint(self) -> None:
        app = create_app(load_settings(auto_connect=False), connect_on_startup=False)

        with TestClient(app) as client:
            service = FakeService()
            service.metrics = app.state.metrics
            app.state.qmt_service = service
            client.post(
                "/rpc",
                json={
                    "target": "xtdata",
                    "method": "get_full_tick",
                    "args": [["000001.SZ"]],
                    "kwargs": {},
                },
            )
            response = client.get("/metrics")

        body = response.json()
        self.assertTrue(body["ok"])
        self.assertEqual(body["rpc"]["total"], 1)
        self.assertIn("websocket", body)

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

    def test_websocket_receives_heartbeat(self) -> None:
        app = create_app(
            load_settings(auto_connect=False, ws_heartbeat_seconds=0.01),
            connect_on_startup=False,
        )

        with TestClient(app) as client, client.websocket_connect("/ws/events") as websocket:
            event = websocket.receive_json()

        self.assertEqual(event["type"], "heartbeat")

    def test_v1_websocket_receives_heartbeat(self) -> None:
        app = create_app(
            load_settings(auto_connect=False, ws_heartbeat_seconds=0.01),
            connect_on_startup=False,
        )

        with TestClient(app) as client, client.websocket_connect("/v1/ws/events") as websocket:
            event = websocket.receive_json()

        self.assertEqual(event["type"], "heartbeat")

    def test_websocket_receives_published_event(self) -> None:
        app = create_app(load_settings(auto_connect=False), connect_on_startup=False)

        with TestClient(app) as client, client.websocket_connect("/ws/events") as websocket:
            app.state.event_bus.publish_threadsafe("qmt_connected", {"ok": True})
            event = websocket.receive_json()

        self.assertEqual(event["type"], "qmt_connected")
        self.assertEqual(event["data"], {"ok": True})

    def test_websocket_requires_token_when_configured(self) -> None:
        app = create_app(
            load_settings(auto_connect=False, api_token="dev-token"),
            connect_on_startup=False,
        )

        with TestClient(app) as client:
            with self.assertRaises(WebSocketDisconnect), client.websocket_connect("/ws/events"):
                pass

            with client.websocket_connect("/ws/events?token=dev-token") as websocket:
                app.state.event_bus.publish_threadsafe("qmt_connected", {"ok": True})
                event = websocket.receive_json()

        self.assertEqual(event["type"], "qmt_connected")


if __name__ == "__main__":
    unittest.main()
