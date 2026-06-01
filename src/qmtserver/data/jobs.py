from __future__ import annotations

from threading import Thread
from typing import Any, Protocol

from qmtserver.data.backend import DuckDbDataBackend
from qmtserver.data.coverage import CoveragePlanner
from qmtserver.data.files import ParquetBarWriter
from qmtserver.data.models import DataJobRecord, DataJobStatus
from qmtserver.data.readers import XtDataBarReader
from qmtserver.data.repository import DataJobRepository
from qmtserver.market.adapter import XtDataMarketAdapter
from qmtserver.market.models import MarketRequest

__all__ = [
    "DataDownloadJobService",
    "DataJobRecord",
    "DataJobRepository",
    "DataJobStatus",
    "XtDataHistoryDownloader",
    "create_data_job_service",
]


class DataJobRepositoryProtocol(Protocol):
    def create(self, job_type: str, request: dict[str, Any]) -> DataJobRecord: ...

    def get(self, job_id: str) -> DataJobRecord | None: ...

    def mark_running(self, job_id: str) -> None: ...

    def mark_succeeded(self, job_id: str, result: dict[str, Any]) -> None: ...

    def mark_failed(self, job_id: str, error: dict[str, str]) -> None: ...


class DataFileRepositoryProtocol(Protocol):
    def record_file(self, file_record: dict[str, Any]) -> None: ...


class CoveragePlannerProtocol(Protocol):
    def coverage(self, request: dict[str, Any]) -> dict[str, Any]: ...


class HistoryDownloader(Protocol):
    def download_history(self, request: dict[str, Any]) -> None: ...


class BarReader(Protocol):
    def read_bars(self, request: dict[str, Any]) -> list[dict[str, Any]]: ...


class BarWriter(Protocol):
    def write_bars(
        self,
        request: dict[str, Any],
        bars: list[dict[str, Any]],
    ) -> list[dict[str, Any]]: ...


class DataDownloadJobService:
    def __init__(
        self,
        repository: DataJobRepositoryProtocol,
        *,
        downloader: HistoryDownloader,
        bar_reader: BarReader | None = None,
        file_writer: BarWriter | None = None,
        file_repository: DataFileRepositoryProtocol | None = None,
        coverage_planner: CoveragePlannerProtocol | None = None,
        run_async: bool = True,
    ) -> None:
        self.repository = repository
        self.downloader = downloader
        self.bar_reader = bar_reader
        self.file_writer = file_writer
        self.file_repository = file_repository
        self.coverage_planner = coverage_planner
        self.run_async = run_async

    def submit_download(self, request: dict[str, Any]) -> dict[str, Any]:
        job = self.repository.create("market_data_download", request)
        initial = job.as_dict()
        if self._is_cached(request):
            coverage = self.coverage_planner.coverage(request) if self.coverage_planner else {}
            self.repository.mark_succeeded(job.job_id, _cached_result(request, coverage))
            return initial
        if self.run_async:
            worker = Thread(target=self._run_download, args=(job.job_id, request), daemon=True)
            worker.start()
        else:
            self._run_download(job.job_id, request)
        return initial

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        job = self.repository.get(job_id)
        if job is None:
            return None
        return job.as_dict()

    def coverage(self, request: dict[str, Any]) -> dict[str, Any]:
        if self.coverage_planner is None:
            return {
                "schema": "market.data.coverage.v1",
                "request": request,
                "fully_covered": False,
                "coverage": [],
                "missing_symbols": [str(symbol) for symbol in request.get("symbols", [])],
            }
        return self.coverage_planner.coverage(request)

    def _run_download(self, job_id: str, request: dict[str, Any]) -> None:
        self.repository.mark_running(job_id)
        try:
            self.downloader.download_history(request)
            files = self._write_files(job_id, request)
            self.repository.mark_succeeded(job_id, _download_result(request, files))
        except Exception as exc:
            self.repository.mark_failed(
                job_id,
                {"code": "DATA_DOWNLOAD_FAILED", "message": f"{type(exc).__name__}: {exc}"},
            )

    def _write_files(self, job_id: str, request: dict[str, Any]) -> list[dict[str, Any]]:
        if self.bar_reader is None or self.file_writer is None:
            return []
        bars = self.bar_reader.read_bars(request)
        files = self.file_writer.write_bars(request, bars)
        for file_record in files:
            file_record["job_id"] = job_id
            if self.file_repository is not None:
                self.file_repository.record_file(file_record)
        return files

    def _is_cached(self, request: dict[str, Any]) -> bool:
        if request.get("force") or self.coverage_planner is None:
            return False
        return bool(self.coverage_planner.coverage(request).get("fully_covered"))


class XtDataHistoryDownloader:
    def __init__(self, qmt_service: Any) -> None:
        self.qmt_service = qmt_service

    def download_history(self, request: dict[str, Any]) -> None:
        symbols = request.get("symbols")
        if not isinstance(symbols, list):
            return
        kind = request.get("kind")
        period = "1d" if kind == "daily_bars" else request.get("period")
        if not isinstance(period, str):
            return
        XtDataMarketAdapter(self.qmt_service).download_history(
            MarketRequest(
                symbols=[str(symbol).strip() for symbol in symbols if str(symbol).strip()],
                start=request.get("start") if isinstance(request.get("start"), str) else None,
                end=request.get("end") if isinstance(request.get("end"), str) else None,
                adjust=str(request.get("adjust", "none")),
                period=period,
            )
        )


def create_data_job_service(
    backend: DuckDbDataBackend,
    qmt_service: Any,
    *,
    run_async: bool = True,
) -> DataDownloadJobService:
    backend.initialize()
    repository = DataJobRepository(backend)
    return DataDownloadJobService(
        repository,
        downloader=XtDataHistoryDownloader(qmt_service),
        bar_reader=XtDataBarReader(qmt_service),
        file_writer=ParquetBarWriter(backend.data_dir),
        file_repository=repository,
        coverage_planner=CoveragePlanner(repository),
        run_async=run_async,
    )


def _download_result(request: dict[str, Any], files: list[dict[str, Any]]) -> dict[str, Any]:
    symbols = request.get("symbols")
    row_count = sum(int(file_record.get("row_count", 0)) for file_record in files)
    return {
        "schema": "market.data.download.v1",
        "downloaded": True,
        "symbols": symbols if isinstance(symbols, list) else [],
        "kind": request.get("kind"),
        "period": _period(request),
        "storage": "qmtserver_data_lake" if files else "miniqmt_cache",
        "file_count": len(files),
        "row_count": row_count,
        "files": files,
        "next_step": None if files else "parquet_writer_pending",
    }


def _cached_result(request: dict[str, Any], coverage: dict[str, Any]) -> dict[str, Any]:
    rows = coverage.get("coverage", [])
    row_count = sum(int(row.get("row_count", 0)) for row in rows if isinstance(row, dict))
    file_count = sum(int(row.get("file_count", 0)) for row in rows if isinstance(row, dict))
    return {
        "schema": "market.data.download.v1",
        "downloaded": False,
        "cached": True,
        "symbols": [str(symbol) for symbol in request.get("symbols", [])],
        "kind": request.get("kind"),
        "period": _period(request),
        "storage": "qmtserver_data_lake",
        "file_count": file_count,
        "row_count": row_count,
        "coverage": coverage,
        "files": [],
        "next_step": None,
    }


def _period(request: dict[str, Any]) -> str:
    if request.get("kind") == "daily_bars":
        return "1d"
    return str(request.get("period") or "unknown")
