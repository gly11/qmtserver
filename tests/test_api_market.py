from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from qmtserver.api import create_app
from qmtserver.config import load_settings
from tests.fakes import FakeService


class DisconnectedQuoteService(FakeService):
    def get_target(self, target: str) -> object:
        from qmtserver.errors import QmtTargetNotConnectedError

        if target == "xtdata":
            raise QmtTargetNotConnectedError("xtdata target is not connected")
        return super().get_target(target)


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


if __name__ == "__main__":
    unittest.main()
