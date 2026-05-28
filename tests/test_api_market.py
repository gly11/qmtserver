from __future__ import annotations

import unittest
from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient

from qmtserver.api import create_app
from qmtserver.config import load_settings
from qmtserver.market.subscription_adapter import XtDataSubscriptionAdapter
from qmtserver.market.subscription_service import MarketSubscriptionService
from tests.fakes import FakeService


class DisconnectedQuoteService(FakeService):
    def get_target(self, target: str) -> object:
        from qmtserver.errors import QmtTargetNotConnectedError

        if target == "xtdata":
            raise QmtTargetNotConnectedError("xtdata target is not connected")
        return super().get_target(target)


class RecordingXtData:
    def __init__(self) -> None:
        self.callbacks: list[Any] = []
        self.unsubscribe_calls: list[int] = []

    def subscribe_quote(self, **kwargs: Any) -> int:
        self.callbacks.append(kwargs["callback"])
        return len(self.callbacks)

    def unsubscribe_quote(self, seq: int) -> None:
        self.unsubscribe_calls.append(seq)


class SubscriptionQuoteService(FakeService):
    def __init__(self) -> None:
        super().__init__()
        self.xtdata = RecordingXtData()

    def get_target(self, target: str) -> object:
        if target == "xtdata":
            return self.xtdata
        return super().get_target(target)


def install_subscription_service(app: FastAPI, service: SubscriptionQuoteService) -> None:
    app.state.qmt_service = service
    app.state.market_subscription_service = MarketSubscriptionService(
        adapter=XtDataSubscriptionAdapter(service),
        event_bus=app.state.event_bus,
        id_factory=lambda: "sub_test",
    )


class ApiMarketTests(unittest.TestCase):
    def test_market_capabilities(self) -> None:
        app = create_app(load_settings(auto_connect=False), connect_on_startup=False)

        with TestClient(app) as client:
            app.state.qmt_service = FakeService()
            response = client.get("/v1/market/capabilities")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["ok"])
        self.assertIn("market.bars.v1", body["data"]["schema_versions"])
        self.assertIn("market.subscription.v1", body["data"]["schema_versions"])
        self.assertIn("/v1/market/subscriptions", body["data"]["endpoints"])
        self.assertIn("/v1/market/quotes/latest", body["data"]["endpoints"])
        self.assertIn("1m", body["data"]["periods"])
        self.assertIn("none", body["data"]["adjust_modes"])

    def test_daily_bars_returns_stable_schema(self) -> None:
        app = create_app(load_settings(auto_connect=False), connect_on_startup=False)

        with TestClient(app) as client:
            app.state.qmt_service = FakeService()
            response = client.get(
                "/v1/market/bars/daily"
                "?symbols=000001.SZ&start=2026-01-01&end=2026-01-31&adjust=none"
            )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["ok"])
        self.assertEqual(body["error"], None)
        self.assertEqual(body["meta"]["schema"], "market.bars.v1")
        self.assertEqual(body["meta"]["row_count"], 1)
        self.assertEqual(body["meta"]["request"]["symbols"], ["000001.SZ"])
        self.assertIn("generated_at", body["meta"])
        self.assertIn("qmtserver_version", body["meta"])
        self.assertIn("xtquant_version", body["meta"])

        bar = body["data"]["bars"][0]
        self.assertEqual(
            set(bar),
            {"date", "symbol", "open", "high", "low", "close", "volume", "amount", "meta"},
        )

    def test_intraday_bars_returns_stable_schema(self) -> None:
        app = create_app(load_settings(auto_connect=False), connect_on_startup=False)

        with TestClient(app) as client:
            app.state.qmt_service = FakeService()
            response = client.get(
                "/v1/market/bars/intraday"
                "?symbols=000001.SZ&period=1m"
                "&start=2026-01-01T09:30:00+08:00&end=2026-01-01T15:00:00+08:00"
            )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["ok"])
        self.assertEqual(body["meta"]["row_count"], 1)
        bar = body["data"]["bars"][0]
        self.assertEqual(
            set(bar),
            {
                "timestamp",
                "symbol",
                "period",
                "open",
                "high",
                "low",
                "close",
                "volume",
                "amount",
                "meta",
            },
        )
        self.assertEqual(bar["period"], "1m")

    def test_daily_bars_rejects_invalid_request_with_stable_error(self) -> None:
        app = create_app(load_settings(auto_connect=False), connect_on_startup=False)

        with TestClient(app) as client:
            app.state.qmt_service = FakeService()
            response = client.get("/v1/market/bars/daily?symbols=&start=2026-01-01")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertFalse(body["ok"])
        self.assertEqual(body["error"]["code"], "INVALID_MARKET_REQUEST")

    def test_daily_bars_reports_target_not_connected(self) -> None:
        app = create_app(load_settings(auto_connect=False), connect_on_startup=False)

        with TestClient(app) as client:
            app.state.qmt_service = DisconnectedQuoteService()
            response = client.get(
                "/v1/market/bars/daily?symbols=000001.SZ&start=2026-01-01&end=2026-01-31"
            )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertFalse(body["ok"])
        self.assertEqual(body["error"]["code"], "TARGET_NOT_CONNECTED")

    def test_market_subscription_lifecycle_endpoints(self) -> None:
        app = create_app(load_settings(auto_connect=False), connect_on_startup=False)
        service = SubscriptionQuoteService()

        with TestClient(app) as client:
            install_subscription_service(app, service)
            created = client.post(
                "/v1/market/subscriptions",
                json={"symbols": ["000001.SZ"], "period": "tick"},
            )
            listed = client.get("/v1/market/subscriptions")
            fetched = client.get("/v1/market/subscriptions/sub_test")
            stopped = client.delete("/v1/market/subscriptions/sub_test")

        self.assertEqual(created.status_code, 200)
        self.assertTrue(created.json()["ok"])
        self.assertEqual(created.json()["data"]["subscription_id"], "sub_test")
        self.assertEqual(created.json()["data"]["status"], "active")
        self.assertEqual(listed.json()["data"]["subscriptions"][0]["subscription_id"], "sub_test")
        self.assertEqual(fetched.json()["data"]["subscription_id"], "sub_test")
        self.assertEqual(stopped.json()["data"]["status"], "stopped")
        self.assertEqual(service.xtdata.unsubscribe_calls, [1])

    def test_market_subscription_rejects_invalid_request_with_stable_error(self) -> None:
        app = create_app(load_settings(auto_connect=False), connect_on_startup=False)

        with TestClient(app) as client:
            response = client.post(
                "/v1/market/subscriptions",
                json={"symbols": [], "period": "tick"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["ok"])
        self.assertEqual(response.json()["error"]["code"], "INVALID_SUBSCRIPTION_REQUEST")

    def test_market_subscription_quote_callback_reaches_websocket(self) -> None:
        app = create_app(load_settings(auto_connect=False), connect_on_startup=False)
        service = SubscriptionQuoteService()

        with (
            TestClient(app) as client,
            client.websocket_connect("/v1/ws/events?types=market_quote") as websocket,
        ):
            install_subscription_service(app, service)
            response = client.post(
                "/v1/market/subscriptions",
                json={"symbols": ["000001.SZ"], "period": "tick"},
            )
            self.assertTrue(response.json()["ok"])

            service.xtdata.callbacks[0]({"000001.SZ": {"lastPrice": 10.25}})
            event = websocket.receive_json()

        self.assertEqual(event["type"], "market_quote")
        self.assertEqual(event["data"]["schema"], "market.quote.v1")
        self.assertEqual(event["data"]["symbol"], "000001.SZ")
        self.assertEqual(event["meta"]["subscription_id"], "sub_test")
        self.assertEqual(event["meta"]["event_seq"], 1)

    def test_market_latest_quotes_and_subscription_diagnostics_endpoints(self) -> None:
        app = create_app(load_settings(auto_connect=False), connect_on_startup=False)
        service = SubscriptionQuoteService()

        with TestClient(app) as client:
            install_subscription_service(app, service)
            created = client.post(
                "/v1/market/subscriptions",
                json={"symbols": ["000001.SZ"], "period": "tick"},
            )
            self.assertTrue(created.json()["ok"])
            service.xtdata.callbacks[0]({"000001.SZ": {"lastPrice": 10.25}})

            latest = client.get("/v1/market/quotes/latest?symbols=000001.SZ,600000.SH")
            diagnostics = client.get("/v1/market/subscriptions/sub_test/diagnostics")

        latest_body = latest.json()
        diagnostics_body = diagnostics.json()
        self.assertTrue(latest_body["ok"])
        self.assertEqual(latest_body["data"]["quotes"][0]["symbol"], "000001.SZ")
        self.assertEqual(latest_body["data"]["quotes"][0]["quote_source"], "callback")
        self.assertEqual(latest_body["data"]["missing_symbols"], ["600000.SH"])
        self.assertTrue(diagnostics_body["ok"])
        self.assertEqual(diagnostics_body["data"]["subscription_id"], "sub_test")
        self.assertEqual(diagnostics_body["data"]["callback_count"], 1)
        self.assertEqual(diagnostics_body["data"]["last_quote_source"], "callback")


if __name__ == "__main__":
    unittest.main()
