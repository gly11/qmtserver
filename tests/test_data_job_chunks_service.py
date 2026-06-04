from __future__ import annotations

import unittest
from typing import Any

from qmtserver.data.jobs import DataDownloadJobService, DataJobRepository, DataJobStatus
from tests.test_data_jobs import (
    FakeBarReader,
    FakeBarWriter,
    FakeCoveragePlanner,
    FakeDataFileRepository,
    FakeDataJobRepository,
    FakeDuckDbBackend,
    FakeHistoryDownloader,
)


class DataJobChunkServiceTests(unittest.TestCase):
    def test_submit_download_persists_planned_chunks(self) -> None:
        repository = FakeDataJobRepository()
        service = DataDownloadJobService(
            repository,
            downloader=FakeHistoryDownloader(),
            coverage_planner=FakeCoveragePlanner(fully_covered=False),
            run_async=False,
        )

        job = service.submit_download(
            {
                "kind": "daily_bars",
                "symbols": ["000001.SZ"],
                "start": "2026-01-01",
                "end": "2026-02-15",
                "adjust": "none",
                "chunk_days": 31,
            }
        )

        chunks = repository.list_chunks(str(job["job_id"]))
        self.assertEqual(len(chunks), 2)
        self.assertEqual(chunks[0]["symbol"], "000001.SZ")
        self.assertEqual(chunks[0]["chunk_start"], "2026-01-01")
        self.assertEqual(chunks[1]["chunk_end"], "2026-02-15")

    def test_download_runs_each_planned_chunk_and_records_progress(self) -> None:
        repository = FakeDataJobRepository()
        downloader = FakeHistoryDownloader()
        service = DataDownloadJobService(
            repository,
            downloader=downloader,
            bar_reader=FakeBarReader(),
            file_writer=FakeBarWriter(),
            file_repository=FakeDataFileRepository(),
            coverage_planner=FakeCoveragePlanner(fully_covered=False),
            run_async=False,
        )

        job = service.submit_download(
            {
                "kind": "daily_bars",
                "symbols": ["000001.SZ", "600000.SH"],
                "start": "2026-01-01",
                "end": "2026-02-15",
                "adjust": "none",
                "chunk_days": 31,
            }
        )

        self.assertEqual(
            [
                (request["symbols"], request["start"], request["end"])
                for request in downloader.requests
            ],
            [
                (["000001.SZ"], "2026-01-01", "2026-01-31"),
                (["000001.SZ"], "2026-02-01", "2026-02-15"),
                (["600000.SH"], "2026-01-01", "2026-01-31"),
                (["600000.SH"], "2026-02-01", "2026-02-15"),
            ],
        )
        chunks = repository.list_chunks(str(job["job_id"]))
        self.assertEqual({chunk["status"] for chunk in chunks}, {"succeeded"})
        fetched = service.get_job(str(job["job_id"]))
        assert fetched is not None
        self.assertEqual(fetched["progress"]["total_symbols"], 2)
        self.assertEqual(fetched["progress"]["finished_symbols"], 2)
        self.assertEqual(fetched["progress"]["finished_chunks"], 4)
        self.assertEqual(fetched["progress"]["row_count"], 4)

    def test_download_records_failed_chunk_without_hiding_other_progress(self) -> None:
        repository = FakeDataJobRepository()
        downloader = FailingOnSymbolDownloader("600000.SH")
        service = DataDownloadJobService(
            repository,
            downloader=downloader,
            bar_reader=FakeBarReader(),
            file_writer=FakeBarWriter(),
            file_repository=FakeDataFileRepository(),
            coverage_planner=FakeCoveragePlanner(fully_covered=False),
            run_async=False,
        )

        job = service.submit_download(
            {
                "kind": "daily_bars",
                "symbols": ["000001.SZ", "600000.SH"],
                "start": "2026-01-01",
                "end": "2026-01-31",
                "adjust": "none",
            }
        )

        persisted = repository.get(str(job["job_id"]))
        self.assertIsNotNone(persisted)
        assert persisted is not None
        self.assertEqual(persisted.status, DataJobStatus.FAILED)
        fetched = service.get_job(str(job["job_id"]))
        assert fetched is not None
        self.assertEqual(fetched["progress"]["finished_symbols"], 1)
        self.assertEqual(fetched["progress"]["failed_symbols"], 1)
        self.assertEqual(fetched["progress"]["failed_chunks"], 1)
        failed_chunks = [chunk for chunk in fetched["chunks"] if chunk["status"] == "failed"]
        self.assertEqual(failed_chunks[0]["symbol"], "600000.SH")
        self.assertEqual(failed_chunks[0]["error_code"], "DATA_DOWNLOAD_FAILED")
        result = fetched["result"]
        self.assertIsNotNone(result)
        assert result is not None
        self.assertTrue(result["partial"])
        self.assertEqual(
            result["symbol_results"],
            [
                {
                    "symbol": "000001.SZ",
                    "status": "succeeded",
                    "downloaded": True,
                    "cached": False,
                    "failed": False,
                    "row_count": 1,
                    "file_count": 1,
                    "coverage_start": "2026-01-01",
                    "coverage_end": "2026-01-31",
                    "gaps": [],
                    "error": None,
                },
                {
                    "symbol": "600000.SH",
                    "status": "failed",
                    "downloaded": False,
                    "cached": False,
                    "failed": True,
                    "row_count": 0,
                    "file_count": 0,
                    "coverage_start": None,
                    "coverage_end": None,
                    "gaps": [
                        {
                            "gap_start": "2026-01-01",
                            "gap_end": "2026-01-31",
                            "reason": "download_failed",
                        }
                    ],
                    "error": {
                        "code": "DATA_DOWNLOAD_FAILED",
                        "message": "RuntimeError: symbol failed",
                    },
                },
            ],
        )

    def test_cached_download_marks_planned_chunks_finished(self) -> None:
        repository = FakeDataJobRepository()
        service = DataDownloadJobService(
            repository,
            downloader=FakeHistoryDownloader(),
            coverage_planner=FakeCoveragePlanner(fully_covered=True),
            run_async=False,
        )

        job = service.submit_download(
            {
                "kind": "daily_bars",
                "symbols": ["000001.SZ"],
                "start": "2026-01-01",
                "end": "2026-02-15",
                "adjust": "none",
                "chunk_days": 31,
            }
        )

        fetched = service.get_job(str(job["job_id"]))
        assert fetched is not None
        self.assertEqual(fetched["progress"]["queued_chunks"], 0)
        self.assertEqual(fetched["progress"]["finished_chunks"], 2)

    def test_ensure_download_only_runs_coverage_gaps(self) -> None:
        repository = FakeDataJobRepository()
        downloader = FakeHistoryDownloader()
        service = DataDownloadJobService(
            repository,
            downloader=downloader,
            bar_reader=FakeBarReader(),
            file_writer=FakeBarWriter(),
            file_repository=FakeDataFileRepository(),
            coverage_planner=FakeCoveragePlanner(
                fully_covered=False,
                gaps=[
                    {
                        "symbol": "000001.SZ",
                        "gap_start": "2026-01-11",
                        "gap_end": "2026-01-12",
                        "reason": "segment_gap",
                    }
                ],
            ),
            run_async=False,
        )

        job = service.submit_download(
            {
                "kind": "daily_bars",
                "symbols": ["000001.SZ"],
                "start": "2026-01-01",
                "end": "2026-01-31",
                "adjust": "none",
                "mode": "ensure",
                "chunk_days": 31,
            }
        )

        self.assertEqual(
            [
                (request["symbols"], request["start"], request["end"])
                for request in downloader.requests
            ],
            [(["000001.SZ"], "2026-01-11", "2026-01-12")],
        )
        chunks = repository.list_chunks(str(job["job_id"]))
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0]["gap_reason"], "segment_gap")

    def test_duckdb_repository_updates_chunk_status(self) -> None:
        backend = FakeDuckDbBackend()
        repository = DataJobRepository(backend)

        repository.mark_chunk_running("job-1:000000")
        repository.mark_chunk_succeeded("job-1:000000", row_count=20, file_count=1)
        repository.mark_chunk_failed(
            "job-1:000001",
            {"code": "DATA_DOWNLOAD_FAILED", "message": "boom"},
        )

        executed_sql = "\n".join(sql for sql, _ in backend.connection.executed)
        self.assertIn("attempts = attempts + 1", executed_sql)
        self.assertIn("row_count = ?", executed_sql)
        self.assertIn("error_code = ?", executed_sql)


class FailingOnSymbolDownloader:
    def __init__(self, symbol: str) -> None:
        self.symbol = symbol
        self.requests: list[dict[str, Any]] = []

    def download_history(self, request: dict[str, Any]) -> None:
        self.requests.append(request)
        if request.get("symbols") == [self.symbol]:
            raise RuntimeError("symbol failed")


if __name__ == "__main__":
    unittest.main()
