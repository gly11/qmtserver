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
        reader = FakeBarReader()
        writer = FakeBarWriter()
        files = FakeDataFileRepository()
        coverage = FakeCoveragePlanner(fully_covered=False)
        service = DataDownloadJobService(
            repository,
            downloader=downloader,
            bar_reader=reader,
            file_writer=writer,
            file_repository=files,
            coverage_planner=coverage,
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
        self.assertEqual(reader.requests, [request])
        self.assertEqual(writer.requests, [request])
        self.assertEqual(files.records, writer.files)
        self.assertEqual(persisted.result["symbols"], ["000001.SZ"])
        self.assertEqual(persisted.result["file_count"], 1)
        self.assertEqual(persisted.result["row_count"], 1)
        self.assertEqual(
            persisted.result["symbol_results"],
            [
                {
                    "symbol": "000001.SZ",
                    "status": "succeeded",
                    "downloaded": True,
                    "cached": False,
                    "row_count": 1,
                    "file_count": 1,
                    "coverage_start": "2026-01-02",
                    "coverage_end": "2026-01-02",
                    "gaps": [],
                }
            ],
        )

    def test_submit_download_uses_cached_coverage_unless_force_is_set(self) -> None:
        repository = FakeDataJobRepository()
        downloader = FakeHistoryDownloader()
        coverage = FakeCoveragePlanner(fully_covered=True)
        service = DataDownloadJobService(
            repository,
            downloader=downloader,
            coverage_planner=coverage,
            run_async=False,
        )

        job = service.submit_download(
            {
                "kind": "daily_bars",
                "symbols": ["000001.SZ"],
                "start": "2026-01-01",
                "end": "2026-01-31",
                "adjust": "none",
                "force": False,
            }
        )

        persisted = repository.get(str(job["job_id"]))
        self.assertIsNotNone(persisted)
        assert persisted is not None
        self.assertEqual(persisted.status, DataJobStatus.SUCCEEDED)
        self.assertEqual(downloader.requests, [])
        self.assertIsNotNone(persisted.result)
        assert persisted.result is not None
        self.assertTrue(persisted.result["cached"])
        self.assertEqual(persisted.result["storage"], "qmtserver_data_lake")
        self.assertEqual(persisted.result["symbol_results"][0]["cached"], True)

    def test_submit_download_force_bypasses_cached_coverage(self) -> None:
        repository = FakeDataJobRepository()
        downloader = FakeHistoryDownloader()
        coverage = FakeCoveragePlanner(fully_covered=True)
        service = DataDownloadJobService(
            repository,
            downloader=downloader,
            coverage_planner=coverage,
            run_async=False,
        )
        request = {
            "kind": "daily_bars",
            "symbols": ["000001.SZ"],
            "start": "2026-01-01",
            "end": "2026-01-31",
            "adjust": "none",
            "force": True,
        }

        service.submit_download(request)

        self.assertEqual(downloader.requests, [request])

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

    def test_service_lists_persistent_jobs(self) -> None:
        repository = FakeDataJobRepository()
        service = DataDownloadJobService(
            repository,
            downloader=FakeHistoryDownloader(),
            run_async=False,
        )
        service.submit_download({"kind": "daily_bars", "symbols": ["000001.SZ"]})

        jobs = service.list_jobs(status="succeeded", limit=10)

        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]["status"], "succeeded")

    def test_service_diagnostics_reports_stale_and_failed_jobs(self) -> None:
        repository = FakeDataJobRepository()
        running = repository.create("market_data_download", {"kind": "daily_bars"})
        failed = repository.create("market_data_download", {"kind": "daily_bars"})
        repository.jobs[running.job_id].status = DataJobStatus.RUNNING
        repository.jobs[running.job_id].started_at = "2026-06-03T00:00:00+00:00"
        repository.jobs[failed.job_id].status = DataJobStatus.FAILED
        repository.jobs[failed.job_id].error = {
            "code": "DATA_DOWNLOAD_FAILED",
            "message": "boom",
        }
        service = DataDownloadJobService(
            repository,
            downloader=FakeHistoryDownloader(),
            run_async=False,
        )

        diagnostics = service.diagnostics(
            now="2026-06-03T00:10:00+00:00",
            stale_after_seconds=300,
        )

        self.assertEqual(diagnostics["schema"], "market.data.jobs.diagnostics.v1")
        self.assertEqual(diagnostics["total"], 2)
        self.assertEqual(diagnostics["failed"], 1)
        self.assertEqual(diagnostics["stale_running"], 1)
        self.assertEqual(diagnostics["stale_running_jobs"][0]["job_id"], running.job_id)
        self.assertEqual(diagnostics["failed_jobs"][0]["error_code"], "DATA_DOWNLOAD_FAILED")

    def test_duckdb_repository_records_file_and_lists_coverage(self) -> None:
        backend = FakeDuckDbBackend()
        repository = DataJobRepository(backend)
        backend.connection.rows = [
            (
                "daily_bars:000001.SZ:1d:none",
                "daily_bars",
                "000001.SZ",
                "1d",
                "none",
                "2026-01-01",
                "2026-01-31",
                20,
                1,
                "2026-06-02T01:00:00+00:00",
            )
        ]

        repository.record_file(
            {
                "file_id": "file-1",
                "job_id": "job-1",
                "kind": "daily_bars",
                "symbol": "000001.SZ",
                "period": "1d",
                "adjust": "none",
                "format": "parquet",
                "path": "data/market/raw/file.parquet",
                "hash": "sha256:test",
                "row_count": 20,
                "coverage_start": "2026-01-01",
                "coverage_end": "2026-01-31",
            }
        )
        coverage = repository.list_coverage(
            {
                "kind": "daily_bars",
                "symbols": ["000001.SZ"],
                "adjust": "none",
            }
        )

        executed_sql = "\n".join(sql for sql, _ in backend.connection.executed)
        self.assertIn("INSERT INTO data_files", executed_sql)
        self.assertIn("INSERT INTO data_coverage", executed_sql)
        self.assertEqual(coverage[0]["symbol"], "000001.SZ")
        self.assertEqual(coverage[0]["coverage_end"], "2026-01-31")


class FakeDataJobRepository:
    def __init__(self) -> None:
        self.jobs: dict[str, DataJobRecord] = {}

    def create(self, job_type: str, request: dict[str, Any]) -> DataJobRecord:
        job = DataJobRecord(job_type=job_type, request=request)
        self.jobs[job.job_id] = job
        return job

    def get(self, job_id: str) -> DataJobRecord | None:
        return self.jobs.get(job_id)

    def list_jobs(self, *, status: str | None = None, limit: int = 50) -> list[DataJobRecord]:
        jobs = list(self.jobs.values())
        if status is not None:
            jobs = [job for job in jobs if job.status.value == status]
        return jobs[:limit]

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


class FakeBarReader:
    def __init__(self) -> None:
        self.requests: list[dict[str, Any]] = []

    def read_bars(self, request: dict[str, Any]) -> list[dict[str, Any]]:
        self.requests.append(request)
        return [{"symbol": "000001.SZ", "date": "2026-01-02", "close": 10.3}]


class FakeBarWriter:
    def __init__(self) -> None:
        self.requests: list[dict[str, Any]] = []
        self.files = [
            {
                "file_id": "file-1",
                "kind": "daily_bars",
                "symbol": "000001.SZ",
                "period": "1d",
                "adjust": "none",
                "format": "parquet",
                "path": "data/market/raw/bars/kind=daily_bars/period=1d/file.parquet",
                "hash": "sha256:test",
                "row_count": 1,
                "coverage_start": "2026-01-02",
                "coverage_end": "2026-01-02",
            }
        ]

    def write_bars(
        self,
        request: dict[str, Any],
        bars: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        del bars
        self.requests.append(request)
        return self.files


class FakeDataFileRepository:
    def __init__(self) -> None:
        self.records: list[dict[str, Any]] = []

    def record_file(self, file_record: dict[str, Any]) -> None:
        self.records.append(file_record)


class FakeCoveragePlanner:
    def __init__(self, *, fully_covered: bool) -> None:
        self.result = {
            "schema": "market.data.coverage.v1",
            "fully_covered": fully_covered,
            "coverage": [
                {
                    "symbol": "000001.SZ",
                    "coverage_start": "2026-01-01",
                    "coverage_end": "2026-01-31",
                    "row_count": 20,
                    "file_count": 1,
                }
            ],
            "missing_symbols": [] if fully_covered else ["000001.SZ"],
        }
        self.requests: list[dict[str, Any]] = []

    def coverage(self, request: dict[str, Any]) -> dict[str, Any]:
        self.requests.append(request)
        return self.result


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
        self.rows: list[tuple[Any, ...]] = []

    def execute(
        self,
        sql: str,
        parameters: tuple[Any, ...] | None = None,
    ) -> FakeDuckDbConnection:
        self.executed.append((sql, parameters or ()))
        return self

    def fetchone(self) -> tuple[Any, ...] | None:
        return self.row

    def fetchall(self) -> list[tuple[Any, ...]]:
        return self.rows

    def close(self) -> None:
        return None


if __name__ == "__main__":
    unittest.main()
