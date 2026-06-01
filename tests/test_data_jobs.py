from __future__ import annotations

import unittest
from typing import Any

from qmtserver.data.jobs import (
    DataDownloadJobService,
    DataJobRecord,
    DataJobRepository,
    DataJobStatus,
)


class DataDownloadJobServiceTests(unittest.TestCase):
    def test_submit_download_persists_and_runs_history_download(self) -> None:
        repository = FakeDataJobRepository()
        downloader = FakeHistoryDownloader()
        service = DataDownloadJobService(
            repository,
            downloader=downloader,
            run_async=False,
        )
        request = {
            "kind": "daily_bars",
            "symbols": ["000001.SZ"],
            "start": "2026-01-01",
            "end": "2026-01-31",
            "adjust": "none",
            "format": "parquet",
        }

        job = service.submit_download(request)

        self.assertEqual(job["status"], "queued")
        persisted = repository.get(str(job["job_id"]))
        self.assertIsNotNone(persisted)
        assert persisted is not None
        self.assertEqual(persisted.status, DataJobStatus.SUCCEEDED)
        self.assertEqual(downloader.requests, [request])
        self.assertIsNotNone(persisted.result)
        assert persisted.result is not None
        self.assertEqual(persisted.result["symbols"], ["000001.SZ"])

    def test_submit_download_marks_job_failed_when_downloader_raises(self) -> None:
        repository = FakeDataJobRepository()
        service = DataDownloadJobService(
            repository,
            downloader=FailingHistoryDownloader(),
            run_async=False,
        )

        job = service.submit_download({"kind": "daily_bars", "symbols": ["000001.SZ"]})

        persisted = repository.get(str(job["job_id"]))
        self.assertIsNotNone(persisted)
        assert persisted is not None
        self.assertEqual(persisted.status, DataJobStatus.FAILED)
        self.assertIsNotNone(persisted.error)
        assert persisted.error is not None
        self.assertEqual(persisted.error["code"], "DATA_DOWNLOAD_FAILED")

    def test_duckdb_repository_writes_and_reads_job_rows(self) -> None:
        backend = FakeDuckDbBackend()
        repository = DataJobRepository(backend)
        request = {"kind": "daily_bars", "symbols": ["000001.SZ"]}

        created = repository.create("market_data_download", request)
        backend.connection.row = (
            created.job_id,
            created.job_type,
            "succeeded",
            '{"kind": "daily_bars", "symbols": ["000001.SZ"]}',
            '{"downloaded": true}',
            None,
            None,
            created.created_at,
            "2026-06-02T01:00:00+00:00",
            "2026-06-02T01:00:01+00:00",
        )
        fetched = repository.get(created.job_id)

        self.assertIsNotNone(fetched)
        assert fetched is not None
        self.assertEqual(fetched.status, DataJobStatus.SUCCEEDED)
        self.assertEqual(fetched.request["symbols"], ["000001.SZ"])
        self.assertEqual(fetched.result, {"downloaded": True})
        self.assertIn("INSERT INTO data_jobs", backend.connection.executed[0][0])


class FakeDataJobRepository:
    def __init__(self) -> None:
        self.jobs: dict[str, DataJobRecord] = {}

    def create(self, job_type: str, request: dict[str, Any]) -> DataJobRecord:
        job = DataJobRecord(job_type=job_type, request=request)
        self.jobs[job.job_id] = job
        return job

    def get(self, job_id: str) -> DataJobRecord | None:
        return self.jobs.get(job_id)

    def mark_running(self, job_id: str) -> None:
        self.jobs[job_id].status = DataJobStatus.RUNNING

    def mark_succeeded(self, job_id: str, result: dict[str, Any]) -> None:
        self.jobs[job_id].status = DataJobStatus.SUCCEEDED
        self.jobs[job_id].result = result
        self.jobs[job_id].error = None

    def mark_failed(self, job_id: str, error: dict[str, str]) -> None:
        self.jobs[job_id].status = DataJobStatus.FAILED
        self.jobs[job_id].error = error


class FakeHistoryDownloader:
    def __init__(self) -> None:
        self.requests: list[dict[str, Any]] = []

    def download_history(self, request: dict[str, Any]) -> None:
        self.requests.append(request)


class FailingHistoryDownloader:
    def download_history(self, request: dict[str, Any]) -> None:
        del request
        raise RuntimeError("boom")


class FakeDuckDbBackend:
    def __init__(self) -> None:
        from pathlib import Path

        self.database_path = Path("data/market/db/qmtserver.duckdb")
        self.connection = FakeDuckDbConnection()

    def connect(self, path: str) -> FakeDuckDbConnection:
        del path
        return self.connection


class FakeDuckDbConnection:
    def __init__(self) -> None:
        self.executed: list[tuple[str, tuple[Any, ...]]] = []
        self.row: tuple[Any, ...] | None = None

    def execute(
        self,
        sql: str,
        parameters: tuple[Any, ...] | None = None,
    ) -> FakeDuckDbConnection:
        self.executed.append((sql, parameters or ()))
        return self

    def fetchone(self) -> tuple[Any, ...] | None:
        return self.row

    def close(self) -> None:
        return None


if __name__ == "__main__":
    unittest.main()
