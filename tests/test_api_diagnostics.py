from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from qmtserver.api import create_app
from qmtserver.config import load_settings
from qmtserver.market.subscription_models import MarketSubscription
from tests.fakes import FakeService


class ApiDiagnosticsTests(unittest.TestCase):
    def test_diagnostics_returns_connection_clock_version_and_sample(self) -> None:
        app = create_app(load_settings(auto_connect=False), connect_on_startup=False)

        with TestClient(app) as client:
            app.state.qmt_service = FakeService()
            response = client.get("/v1/diagnostics")

        body = response.json()
        self.assertTrue(body["ok"])
        self.assertIn("qmt", body["data"])
        self.assertIn("clock", body["data"])
        self.assertIn("version", body["data"])
        self.assertIn("sample", body["data"])
        self.assertEqual(body["data"]["sample"]["symbol"], "000001.SZ")

    def test_diagnostics_includes_runtime_health_summary(self) -> None:
        app = create_app(load_settings(auto_connect=False), connect_on_startup=False)
        subscription = MarketSubscription(
            subscription_id="sub_1",
            symbols=["000001.SZ"],
            period="tick",
            status="active",
            created_at="2026-06-01T01:00:00+00:00",
            updated_at="2026-06-01T01:00:00+00:00",
        )

        with TestClient(app) as client:
            app.state.qmt_service = FakeService()
            app.state.qmt_service.connected = True
            app.state.market_subscription_service = RuntimeHealthSubscriptionService(subscription)
            response = client.get("/v1/diagnostics")

        health = response.json()["data"]["runtime_health"]
        self.assertEqual(health["schema"], "runtime.health.v1")
        self.assertEqual(health["status"], "degraded")
        self.assertEqual(health["quote"]["status"], "connected")
        self.assertEqual(health["trader"]["status"], "connected")
        self.assertEqual(health["subscriptions"]["total"], 1)
        self.assertEqual(health["subscriptions"]["active"], 1)
        self.assertEqual(health["subscriptions"]["stale_callbacks"], 1)


class RuntimeHealthSubscriptionService:
    def __init__(self, subscription: MarketSubscription) -> None:
        self.subscription = subscription

    def list_subscriptions(self) -> list[MarketSubscription]:
        return [self.subscription]

    def diagnostics(self, subscription_id: str) -> dict[str, object]:
        return {
            "subscription_id": subscription_id,
            "status": "active",
            "callback_count": 3,
            "is_callback_active": False,
            "seconds_since_last_callback": 120.0,
        }


if __name__ == "__main__":
    unittest.main()
