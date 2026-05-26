from __future__ import annotations

import tempfile
import time
import unittest
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from qmtserver.api import create_app
from qmtserver.config import load_settings
from tests.fakes import FakeService


class ApiJobsTests(unittest.TestCase):
    def test_history_download_job_succeeds_and_returns_snapshot_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            app = create_app(
                load_settings(auto_connect=False, snapshot_dir=Path(tmp)),
                connect_on_startup=False,
            )

            with TestClient(app) as client:
                app.state.qmt_service = FakeService()
                created = client.post(
                    "/v1/jobs/history-download",
                    json={
                        "kind": "daily_bars",
                        "symbols": ["000001.SZ"],
                        "start": "2026-01-01",
                        "end": "2026-01-31",
                        "format": "csv",
                    },
                )
                self.assertEqual(created.status_code, 200)
                job_id = created.json()["data"]["job"]["job_id"]
                status = self._wait_for_status(client, job_id, "succeeded")
                result = client.get(f"/v1/jobs/{job_id}/result")

        self.assertEqual(status["data"]["job"]["status"], "succeeded")
        self.assertEqual(result.status_code, 200)
        self.assertTrue(result.json()["data"]["manifest"]["snapshot_id"].startswith("daily_bars-"))

    def test_cancel_unknown_job_returns_stable_error(self) -> None:
        app = create_app(load_settings(auto_connect=False), connect_on_startup=False)

        with TestClient(app) as client:
            app.state.qmt_service = FakeService()
            response = client.post("/v1/jobs/missing/cancel")

        body = response.json()
        self.assertFalse(body["ok"])
        self.assertEqual(body["error"]["code"], "JOB_NOT_FOUND")

    def _wait_for_status(self, client: TestClient, job_id: str, expected: str) -> dict[str, Any]:
        last: dict[str, Any] = {}
        for _ in range(50):
            response = client.get(f"/v1/jobs/{job_id}")
            last = response.json()
            if last["data"]["job"]["status"] == expected:
                return last
            time.sleep(0.02)
        return last


if __name__ == "__main__":
    unittest.main()
