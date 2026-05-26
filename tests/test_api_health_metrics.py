from __future__ import annotations

import asyncio
import unittest

from fastapi.testclient import TestClient

from qmtserver import __version__
from qmtserver.api import create_app
from qmtserver.config import load_settings
from tests.fakes import FakeService


class ApiHealthMetricsTests(unittest.TestCase):
    def test_health(self) -> None:
        app = create_app(load_settings(auto_connect=False), connect_on_startup=False)

        with TestClient(app) as client:
            response = client.get("/health")
            versioned = client.get("/v1/health")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])
        self.assertEqual(versioned.status_code, 200)
        self.assertIn("v1", versioned.json()["api_versions"])

    def test_fastapi_metadata_version_matches_package_version(self) -> None:
        app = create_app(load_settings(auto_connect=False), connect_on_startup=False)

        self.assertEqual(app.version, __version__)

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

    def test_orders_trades_and_recent_events_endpoints(self) -> None:
        app = create_app(load_settings(auto_connect=False), connect_on_startup=False)

        with TestClient(app) as client:
            app.state.qmt_service.callback.on_stock_order({"order_id": 1})
            app.state.qmt_service.callback.on_stock_trade({"trade_id": 2})
            asyncio.run(app.state.event_bus.publish("stock_order", {"order_id": 1}))
            orders = client.get("/v1/orders")
            order = client.get("/v1/orders/1")
            trades = client.get("/v1/trades")
            events = client.get("/v1/events/recent?types=stock_order")

        self.assertEqual(orders.json()["data"][0]["data"]["order_id"], 1)
        self.assertEqual(order.json()["data"]["data"]["order_id"], 1)
        self.assertEqual(trades.json()["data"][0]["data"]["trade_id"], 2)
        self.assertTrue(all(item["type"] == "stock_order" for item in events.json()["data"]))


if __name__ == "__main__":
    unittest.main()
