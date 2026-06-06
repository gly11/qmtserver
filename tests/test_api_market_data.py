from __future__ import annotations

import unittest
from pathlib import Path
from typing import Any
from unittest.mock import patch

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
                    "chunk_days": 31,
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

    def test_create_data_download_resolves_universe_and_exchange(self) -> None:
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
                    "universe": "all_a",
                    "exchange": "SH",
                    "start": "2026-01-01",
                    "end": "2026-01-31",
                    "adjust": "none",
                    "format": "parquet",
                },
            )

        request = fake_jobs.requests[0]
        self.assertTrue(created.json()["ok"])
        self.assertEqual(request["symbols"], ["600000.SH"])
        self.assertEqual(request["universe"], "all_a")
        self.assertEqual(request["exchange"], "SH")
        self.assertEqual(request["chunk_days"], 31)
        self.assertEqual(request["resolved_symbols"], ["600000.SH"])
        self.assertEqual(request["symbol_count"], 1)
        self.assertTrue(str(request["universe_hash"]).startswith("sha256:"))

    def test_create_data_download_rejects_empty_symbols_without_universe(self) -> None:
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
                    "symbols": [],
                    "start": "2026-01-01",
                    "end": "2026-01-31",
                    "adjust": "none",
                    "format": "parquet",
                },
            )

        body = created.json()
        self.assertEqual(created.status_code, 200)
        self.assertFalse(body["ok"])
        self.assertEqual(body["error"]["code"], "INVALID_MARKET_REQUEST")
        self.assertEqual(fake_jobs.requests, [])

    def test_create_data_download_rejects_invalid_exchange(self) -> None:
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
                    "universe": "all_a",
                    "exchange": "HK",
                    "start": "2026-01-01",
                    "end": "2026-01-31",
                    "adjust": "none",
                    "format": "parquet",
                },
            )

        body = created.json()
        self.assertEqual(created.status_code, 200)
        self.assertFalse(body["ok"])
        self.assertEqual(body["error"]["code"], "INVALID_MARKET_REQUEST")
        self.assertEqual(fake_jobs.requests, [])

    def test_create_data_download_rejects_unknown_storage_profile(self) -> None:
        app = create_app(
            load_settings(
                _env_file=None,
                auto_connect=False,
                data_storage_profiles="qmt_main=data/qmt_main",
            ),
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
                    "storage_profile": "D:/unsafe",
                },
            )

        body = created.json()
        self.assertEqual(created.status_code, 200)
        self.assertFalse(body["ok"])
        self.assertEqual(body["error"]["code"], "INVALID_MARKET_REQUEST")
        self.assertEqual(fake_jobs.requests, [])

    def test_create_data_download_records_known_storage_profile(self) -> None:
        app = create_app(
            load_settings(
                _env_file=None,
                auto_connect=False,
                data_storage_profiles="qmt_main=data/qmt_main",
            ),
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
                    "storage_profile": "qmt_main",
                },
            )

        self.assertTrue(created.json()["ok"])
        self.assertEqual(fake_jobs.requests[0]["storage_profile"], "qmt_main")

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

    def test_retry_failed_data_download_job(self) -> None:
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
                json={"kind": "daily_bars", "symbols": ["000001.SZ"]},
            )
            job_id = created.json()["data"]["job"]["job_id"]
            retried = client.post(f"/v1/market/data/jobs/{job_id}/retry-failed")

        body = retried.json()
        self.assertEqual(retried.status_code, 200)
        self.assertTrue(body["ok"])
        self.assertEqual(body["data"]["job"]["job_id"], job_id)
        self.assertEqual(fake_jobs.retry_requests, [job_id])

    def test_list_data_download_jobs(self) -> None:
        app = create_app(
            load_settings(_env_file=None, auto_connect=False),
            connect_on_startup=False,
        )
        fake_jobs = FakeDataJobService()
        fake_jobs.submit_download({"kind": "daily_bars", "symbols": ["000001.SZ"]})

        with TestClient(app) as client:
            app.state.qmt_service = FakeService()
            app.state.data_job_service = fake_jobs
            response = client.get("/v1/market/data/jobs?status=succeeded&limit=10")

        body = response.json()
        self.assertTrue(body["ok"])
        self.assertEqual(len(body["data"]["jobs"]), 1)
        self.assertEqual(fake_jobs.list_job_requests[0], {"status": "succeeded", "limit": 10})

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

    def test_get_data_bars(self) -> None:
        app = create_app(
            load_settings(_env_file=None, auto_connect=False),
            connect_on_startup=False,
        )
        fake_jobs = FakeDataJobService()

        with TestClient(app) as client:
            app.state.qmt_service = FakeService()
            app.state.data_job_service = fake_jobs
            response = client.get(
                "/v1/market/data/bars"
                "?kind=daily_bars&symbols=000001.SZ&start=2026-01-01&end=2026-01-31"
            )

        body = response.json()
        self.assertTrue(body["ok"])
        self.assertEqual(body["data"]["schema"], "market.data.bars.v1")
        self.assertEqual(body["data"]["bars"][0]["symbol"], "000001.SZ")
        self.assertEqual(fake_jobs.query_requests[0]["symbols"], ["000001.SZ"])

    def test_create_get_and_download_data_export(self) -> None:
        app = create_app(
            load_settings(_env_file=None, auto_connect=False),
            connect_on_startup=False,
        )
        fake_jobs = FakeDataJobService()

        with TestClient(app) as client:
            app.state.qmt_service = FakeService()
            app.state.data_job_service = fake_jobs
            created = client.post(
                "/v1/market/data/exports",
                json={
                    "kind": "daily_bars",
                    "symbols": ["000001.SZ"],
                    "start": "2026-01-01",
                    "end": "2026-01-31",
                    "format": "csv",
                },
            )
            export_id = created.json()["data"]["manifest"]["export_id"]
            listed = client.get("/v1/market/data/exports")
            manifest = client.get(f"/v1/market/data/exports/{export_id}")
            download = client.get(f"/v1/market/data/exports/{export_id}/download")
            ranged = client.get(
                f"/v1/market/data/exports/{export_id}/download",
                headers={"Range": "bytes=0-3"},
            )
            deleted = client.delete(f"/v1/market/data/exports/{export_id}")

        self.assertEqual(created.status_code, 200)
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(manifest.status_code, 200)
        self.assertEqual(download.status_code, 200)
        self.assertEqual(download.headers["accept-ranges"], "bytes")
        self.assertIn("content-length", download.headers)
        self.assertIn("etag", download.headers)
        self.assertEqual(ranged.status_code, 206)
        self.assertEqual(ranged.headers["content-range"], f"bytes 0-3/{len(download.content)}")
        self.assertEqual(ranged.content, download.content[:4])
        self.assertEqual(deleted.status_code, 200)
        self.assertEqual(fake_jobs.export_requests[0]["symbols"], ["000001.SZ"])

    def test_download_missing_data_export_returns_http_404(self) -> None:
        app = create_app(
            load_settings(_env_file=None, auto_connect=False),
            connect_on_startup=False,
        )
        fake_jobs = FakeDataJobService()

        with TestClient(app) as client:
            app.state.qmt_service = FakeService()
            app.state.data_job_service = fake_jobs
            response = client.get("/v1/market/data/exports/missing/download")

        body = response.json()
        self.assertEqual(response.status_code, 404)
        self.assertFalse(body["ok"])
        self.assertEqual(body["error"]["code"], "EXPORT_NOT_FOUND")

    def test_get_data_quality(self) -> None:
        app = create_app(
            load_settings(_env_file=None, auto_connect=False),
            connect_on_startup=False,
        )
        fake_jobs = FakeDataJobService()

        with TestClient(app) as client:
            app.state.qmt_service = FakeService()
            app.state.data_job_service = fake_jobs
            response = client.get(
                "/v1/market/data/quality"
                "?kind=daily_bars&symbols=000001.SZ&start=2026-01-01&end=2026-01-31"
            )

        body = response.json()
        self.assertTrue(body["ok"])
        self.assertEqual(body["meta"]["schema"], "market.quality.v1")
        self.assertEqual(fake_jobs.quality_requests[0]["symbols"], ["000001.SZ"])

    def test_data_job_service_is_cached_when_created_lazily(self) -> None:
        app = create_app(
            load_settings(_env_file=None, auto_connect=False),
            connect_on_startup=False,
        )
        fake_jobs = FakeDataJobService()

        with (
            patch("qmtserver.api.routes_market_data.create_data_backend", return_value=object()),
            patch(
                "qmtserver.api.routes_market_data.create_data_job_service",
                return_value=fake_jobs,
            ) as create_service,
            TestClient(app) as client,
        ):
            app.state.qmt_service = FakeService()
            first = client.get(
                "/v1/market/data/coverage"
                "?kind=daily_bars&symbols=000001.SZ&start=2026-01-01&end=2026-01-31"
            )
            second = client.get(
                "/v1/market/data/bars"
                "?kind=daily_bars&symbols=000001.SZ&start=2026-01-01&end=2026-01-31"
            )

        self.assertTrue(first.json()["ok"])
        self.assertTrue(second.json()["ok"])
        create_service.assert_called_once()
        self.assertIs(app.state.data_job_service, fake_jobs)


class FakeDataJobService:
    def __init__(self) -> None:
        self.jobs: dict[str, DataJobRecord] = {}
        self.requests: list[dict[str, Any]] = []
        self.coverage_requests: list[dict[str, Any]] = []
        self.query_requests: list[dict[str, Any]] = []
        self.quality_requests: list[dict[str, Any]] = []
        self.export_requests: list[dict[str, Any]] = []
        self.list_job_requests: list[dict[str, Any]] = []
        self.retry_requests: list[str] = []
        self.exports: dict[str, dict[str, Any]] = {}

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

    def list_jobs(self, *, status: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        self.list_job_requests.append({"status": status, "limit": limit})
        jobs = [job for job in self.jobs.values() if status is None or job.status.value == status]
        return [job.as_dict() for job in jobs[:limit]]

    def retry_failed_chunks(self, job_id: str) -> dict[str, Any] | None:
        self.retry_requests.append(job_id)
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

    def query_bars(self, request: dict[str, Any]) -> dict[str, Any]:
        self.query_requests.append(request)
        return {
            "schema": "market.data.bars.v1",
            "request": request,
            "bars": [{"symbol": "000001.SZ", "date": "2026-01-02", "close": 10.3}],
            "row_count": 1,
            "truncated": False,
        }

    def create_export(self, request: dict[str, Any]) -> dict[str, Any]:
        self.export_requests.append(request)
        manifest = {
            "export_id": "export-test",
            "format": "csv",
            "request": request,
            "row_count": 1,
            "hash": "sha256:test",
        }
        self.exports["export-test"] = manifest
        return {
            "ok": True,
            "data": {"manifest": manifest, "cached": False},
            "error": None,
            "meta": {},
        }

    def list_exports(self) -> list[dict[str, Any]]:
        return list(self.exports.values())

    def export_manifest(self, export_id: str) -> dict[str, Any] | None:
        manifest = self.exports.get(export_id)
        if manifest is None:
            return None
        return manifest

    def export_path(self, export_id: str) -> Path | None:
        if export_id not in self.exports:
            return None
        path = Path("data") / f"{export_id}.csv"
        path.parent.mkdir(exist_ok=True)
        path.write_text("date,symbol,close\n2026-01-02,000001.SZ,10.3\n", encoding="utf-8")
        return path

    def delete_export(self, export_id: str) -> bool:
        return self.exports.pop(export_id, None) is not None

    def quality(self, request: dict[str, Any]) -> dict[str, Any]:
        self.quality_requests.append(request)
        return {
            "ok": True,
            "data": {
                "missing_dates": [],
                "duplicate_rows": [],
                "price_anomalies": [],
                "volume_anomalies": [],
            },
            "error": None,
            "meta": {"schema": "market.quality.v1", "row_count": 1},
        }


if __name__ == "__main__":
    unittest.main()
