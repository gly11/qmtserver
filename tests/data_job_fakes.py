from __future__ import annotations

from pathlib import Path
from typing import Any

from qmtserver.data.jobs import DataJobRecord, DataJobStatus


class FakeApiDataJobService:
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


class FakeDataJobRepository:
    def __init__(self) -> None:
        self.jobs: dict[str, DataJobRecord] = {}
        self.chunks: dict[str, list[dict[str, Any]]] = {}

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

    def mark_failed(
        self,
        job_id: str,
        error: dict[str, str],
        *,
        result: dict[str, Any] | None = None,
    ) -> None:
        self.jobs[job_id].status = DataJobStatus.FAILED
        self.jobs[job_id].error = error
        self.jobs[job_id].result = result

    def create_chunks(self, job_id: str, chunks: list[dict[str, Any]]) -> None:
        self.chunks[job_id] = [
            {**chunk, "chunk_id": f"{job_id}:{index:06d}", "job_id": job_id}
            for index, chunk in enumerate(chunks)
        ]

    def list_chunks(self, job_id: str) -> list[dict[str, Any]]:
        return self.chunks.get(job_id, [])

    def mark_chunk_running(self, chunk_id: str) -> None:
        chunk = self._chunk(chunk_id)
        chunk["status"] = "running"
        chunk["attempts"] = int(chunk.get("attempts", 0)) + 1

    def mark_chunk_succeeded(self, chunk_id: str, *, row_count: int, file_count: int) -> None:
        chunk = self._chunk(chunk_id)
        chunk["status"] = "succeeded"
        chunk["row_count"] = row_count
        chunk["file_count"] = file_count
        chunk["error_code"] = None
        chunk["error_message"] = None

    def mark_chunk_failed(self, chunk_id: str, error: dict[str, str]) -> None:
        chunk = self._chunk(chunk_id)
        chunk["status"] = "failed"
        chunk["error_code"] = error.get("code")
        chunk["error_message"] = error.get("message")

    def _chunk(self, chunk_id: str) -> dict[str, Any]:
        for chunks in self.chunks.values():
            for chunk in chunks:
                if chunk["chunk_id"] == chunk_id:
                    return chunk
        raise KeyError(chunk_id)


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
    def __init__(
        self,
        *,
        fully_covered: bool,
        gaps: list[dict[str, str]] | None = None,
    ) -> None:
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
            "gaps": gaps or [],
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
