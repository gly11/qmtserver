from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from qmtserver.api import create_app
from qmtserver.config import load_settings
from tests.fakes import FakeService


class ApiSnapshotTests(unittest.TestCase):
    def test_create_list_manifest_and_download_csv_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            app = create_app(
                load_settings(auto_connect=False, snapshot_dir=Path(tmp)),
                connect_on_startup=False,
            )

            with TestClient(app) as client:
                app.state.qmt_service = FakeService(snapshot_dir=Path(tmp))
                create = client.post(
                    "/v1/snapshots",
                    json={
                        "kind": "daily_bars",
                        "symbols": ["000001.SZ"],
                        "start": "2026-01-01",
                        "end": "2026-01-31",
                        "adjust": "none",
                        "format": "csv",
                    },
                )
                self.assertEqual(create.status_code, 200)
                body = create.json()
                snapshot_id = body["data"]["manifest"]["snapshot_id"]
                listed = client.get("/v1/snapshots")
                manifest = client.get(f"/v1/snapshots/{snapshot_id}/manifest")
                download = client.get(f"/v1/snapshots/{snapshot_id}/download")

        self.assertTrue(body["ok"])
        self.assertEqual(body["data"]["manifest"]["row_count"], 1)
        self.assertEqual(body["data"]["manifest"]["symbol_count"], 1)
        self.assertTrue(body["data"]["manifest"]["hash"].startswith("sha256:"))
        self.assertEqual(len(listed.json()["data"]["snapshots"]), 1)
        self.assertEqual(manifest.json()["data"]["manifest"]["snapshot_id"], snapshot_id)
        self.assertEqual(download.status_code, 200)
        self.assertIn("date,symbol,open,high,low,close,volume,amount,meta", download.text)

    def test_create_snapshot_reuses_existing_manifest_for_same_request(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            app = create_app(
                load_settings(auto_connect=False, snapshot_dir=Path(tmp)),
                connect_on_startup=False,
            )

            with TestClient(app) as client:
                app.state.qmt_service = FakeService(snapshot_dir=Path(tmp))
                payload = {
                    "kind": "daily_bars",
                    "symbols": ["000001.SZ"],
                    "start": "2026-01-01",
                    "end": "2026-01-31",
                    "adjust": "none",
                    "format": "csv",
                }
                first = client.post("/v1/snapshots", json=payload).json()
                second_response = client.post("/v1/snapshots", json=payload)
                self.assertEqual(second_response.status_code, 200)
                second = second_response.json()

        self.assertEqual(
            first["data"]["manifest"]["snapshot_id"],
            second["data"]["manifest"]["snapshot_id"],
        )
        self.assertTrue(second["data"]["cached"])


if __name__ == "__main__":
    unittest.main()
