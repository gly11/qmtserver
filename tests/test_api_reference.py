from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from qmtserver.api import create_app
from qmtserver.config import load_settings
from tests.fakes import FakeService


class ApiReferenceTests(unittest.TestCase):
    def test_reference_endpoints_return_stable_schema(self) -> None:
        app = create_app(load_settings(auto_connect=False), connect_on_startup=False)

        with TestClient(app) as client:
            app.state.qmt_service = FakeService()
            calendar = client.get("/v1/reference/calendar?start=2026-01-01&end=2026-01-05")
            universe = client.get("/v1/reference/universe?name=all_a")
            instruments = client.get("/v1/reference/instruments?symbols=000001.SZ")

        self.assertTrue(calendar.json()["ok"])
        self.assertIn("2026-01-02", calendar.json()["data"]["dates"])
        self.assertTrue(universe.json()["data"]["symbols"])
        self.assertEqual(instruments.json()["data"]["instruments"][0]["symbol"], "000001.SZ")

    def test_all_a_universe_uses_local_xtdata_sector_name(self) -> None:
        app = create_app(load_settings(auto_connect=False), connect_on_startup=False)
        service = RecordingReferenceService()

        with TestClient(app) as client:
            app.state.qmt_service = service
            response = client.get("/v1/reference/universe?name=all_a")

        self.assertTrue(response.json()["data"]["symbols"])
        self.assertEqual(service.target.sector_calls, ["沪深A股"])

    def test_bars_quality_endpoint_returns_report(self) -> None:
        app = create_app(load_settings(auto_connect=False), connect_on_startup=False)

        with TestClient(app) as client:
            app.state.qmt_service = FakeService()
            response = client.get(
                "/v1/market/bars/daily/quality?symbols=000001.SZ&start=2026-01-01&end=2026-01-05"
            )

        body = response.json()
        self.assertTrue(body["ok"])
        self.assertEqual(body["meta"]["schema"], "market.quality.v1")
        self.assertIn("missing_dates", body["data"])

    def test_snapshot_quality_endpoint_returns_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            app = create_app(
                load_settings(auto_connect=False, snapshot_dir=Path(tmp)),
                connect_on_startup=False,
            )

            with TestClient(app) as client:
                app.state.qmt_service = FakeService(snapshot_dir=Path(tmp))
                created = client.post(
                    "/v1/snapshots",
                    json={
                        "kind": "daily_bars",
                        "symbols": ["000001.SZ"],
                        "start": "2026-01-01",
                        "end": "2026-01-05",
                        "format": "csv",
                    },
                )
                snapshot_id = created.json()["data"]["manifest"]["snapshot_id"]
                response = client.get(f"/v1/snapshots/{snapshot_id}/quality")

        body = response.json()
        self.assertTrue(body["ok"])
        self.assertEqual(body["meta"]["schema"], "market.quality.v1")


if __name__ == "__main__":
    unittest.main()


class RecordingReferenceTarget:
    def __init__(self) -> None:
        self.sector_calls: list[str] = []

    def get_stock_list_in_sector(self, sector: str) -> list[str]:
        self.sector_calls.append(sector)
        return ["000001.SZ"]


class RecordingReferenceService:
    def __init__(self) -> None:
        self.target = RecordingReferenceTarget()

    def get_target(self, target: str) -> Any:
        if target != "xtdata":
            raise AssertionError(f"unexpected target: {target}")
        return self.target
