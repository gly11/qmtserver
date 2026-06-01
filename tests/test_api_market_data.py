from __future__ import annotations

import unittest
from typing import Any

from fastapi.testclient import TestClient

from qmtserver.api import create_app
from qmtserver.config import load_settings
from qmtserver.data.jobs import DataJobRecord, DataJobStatus
from tests.fakes import FakeService


class ApiMarketDataTests(unittest.TestCase):
    def test_create_and_get_persistent_data_download_job(self) -> None:
        app = create_app(
            load_settings(_env_file=None, auto_connect=False),
            connect_on_startup=False,
        )
        fake_jobs = FakeDataJobService()

        with TestClient(app) as client:
            app.state.qmt_service = FakeService()
            app.state.data_job_service = fake_jobs
            created = client.post(
                "/v1/market/data/download",
                json={
                    "kind": "daily_bars",
                    "symbols": ["000001.SZ"],
                    "start": "2026-01-01",
                    "end": "2026-01-31",
                    "adjust": "none",
                    "format": "parquet",
                },
            )
            self.assertEqual(created.status_code, 200)
            job_id = created.json()["data"]["job"]["job_id"]
            fetched = client.get(f"/v1/market/data/jobs/{job_id}")

        self.assertTrue(created.json()["ok"])
        self.assertEqual(fetched.status_code, 200)
        self.assertEqual(fetched.json()["data"]["job"]["job_id"], job_id)
        self.assertEqual(fake_jobs.requests[0]["symbols"], ["000001.SZ"])

    def test_get_unknown_data_download_job_returns_stable_error(self) -> None:
        app = create_app(
            load_settings(_env_file=None, auto_connect=False),
            connect_on_startup=False,
        )

        with TestClient(app) as client:
            app.state.qmt_service = FakeService()
            app.state.data_job_service = FakeDataJobService()
            response = client.get("/v1/market/data/jobs/missing")

        body = response.json()
        self.assertFalse(body["ok"])
        self.assertEqual(body["error"]["code"], "JOB_NOT_FOUND")

    def test_get_data_coverage(self) -> None:
        app = create_app(
            load_settings(_env_file=None, auto_connect=False),
            connect_on_startup=False,
        )
        fake_jobs = FakeDataJobService()

        with TestClient(app) as client:
            app.state.qmt_service = FakeService()
            app.state.data_job_service = fake_jobs
            response = client.get(
                "/v1/market/data/coverage"
                "?kind=daily_bars&symbols=000001.SZ&start=2026-01-01&end=2026-01-31"
            )

        body = response.json()
        self.assertTrue(body["ok"])
        self.assertEqual(body["data"]["coverage"]["schema"], "market.data.coverage.v1")
        self.assertEqual(fake_jobs.coverage_requests[0]["symbols"], ["000001.SZ"])


class FakeDataJobService:
    def __init__(self) -> None:
        self.jobs: dict[str, DataJobRecord] = {}
        self.requests: list[dict[str, Any]] = []
        self.coverage_requests: list[dict[str, Any]] = []

    def submit_download(self, request: dict[str, Any]) -> dict[str, Any]:
        self.requests.append(request)
        job = DataJobRecord(
            job_type="market_data_download",
            request=request,
            status=DataJobStatus.SUCCEEDED,
            result={"downloaded": True},
        )
        self.jobs[job.job_id] = job
        return job.as_dict()

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        job = self.jobs.get(job_id)
        if job is None:
            return None
        return job.as_dict()

    def coverage(self, request: dict[str, Any]) -> dict[str, Any]:
        self.coverage_requests.append(request)
        return {
            "schema": "market.data.coverage.v1",
            "fully_covered": True,
            "coverage": [
                {
                    "symbol": "000001.SZ",
                    "coverage_start": "2026-01-01",
                    "coverage_end": "2026-01-31",
                    "row_count": 20,
                    "file_count": 1,
                }
            ],
            "missing_symbols": [],
        }


if __name__ == "__main__":
    unittest.main()
