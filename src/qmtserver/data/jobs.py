from __future__ import annotations

from threading import Thread
from typing import Any, Protocol

from qmtserver.data.backend import DuckDbDataBackend
from qmtserver.data.chunks import plan_download_chunks
from qmtserver.data.coverage import CoveragePlanner
from qmtserver.data.exports import DataExportService
from qmtserver.data.files import ParquetBarWriter
from qmtserver.data.job_diagnostics import build_data_job_diagnostics
from qmtserver.data.job_results import cached_result, download_result
from qmtserver.data.models import DataJobRecord, DataJobStatus  # noqa: F401
from qmtserver.data.query import DuckDbParquetBarReader, LocalBarQuery
from qmtserver.data.readers import XtDataBarReader
from qmtserver.data.repository import DataJobRepository
from qmtserver.data_quality.service import quality_response
from qmtserver.errors import QmtDataDownloadFailedError, QmtDataExportUnavailableError
from qmtserver.market.adapter import XtDataMarketAdapter
from qmtserver.market.models import MarketRequest


class DataJobRepositoryProtocol(Protocol):
    def create(self, job_type: str, request: dict[str, Any]) -> DataJobRecord: ...

    def get(self, job_id: str) -> DataJobRecord | None: ...

    def list_jobs(self, *, status: str | None = None, limit: int = 50) -> list[DataJobRecord]: ...

    def mark_running(self, job_id: str) -> None: ...

    def mark_succeeded(self, job_id: str, result: dict[str, Any]) -> None: ...

    def mark_failed(self, job_id: str, error: dict[str, str]) -> None: ...

    def create_chunks(self, job_id: str, chunks: list[dict[str, Any]]) -> None: ...

    def list_chunks(self, job_id: str) -> list[dict[str, Any]]: ...


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


class BarQuery(Protocol):
    def query_bars(self, request: dict[str, Any]) -> dict[str, Any]: ...


class ExportService(Protocol):
    def create(self, request: dict[str, Any]) -> dict[str, Any]: ...

    def list_exports(self) -> list[dict[str, Any]]: ...

    def manifest(self, export_id: str) -> dict[str, Any]: ...

    def download_path(self, export_id: str) -> Any: ...

    def delete(self, export_id: str) -> bool: ...


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
        bar_query: BarQuery | None = None,
        export_service: ExportService | None = None,
        run_async: bool = True,
    ) -> None:
        self.repository = repository
        self.downloader = downloader
        self.bar_reader = bar_reader
        self.file_writer = file_writer
        self.file_repository = file_repository
        self.coverage_planner = coverage_planner
        self.bar_query = bar_query
        self.export_service = export_service
        self.run_async = run_async

    def submit_download(self, request: dict[str, Any]) -> dict[str, Any]:
        job = self.repository.create("market_data_download", request)
        self.repository.create_chunks(job.job_id, plan_download_chunks(request))
        initial = job.as_dict()
        if self._is_cached(request):
            coverage = self.coverage_planner.coverage(request) if self.coverage_planner else {}
            self.repository.mark_succeeded(job.job_id, cached_result(request, coverage))
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

    def list_jobs(self, *, status: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        bounded_limit = max(1, min(limit, 200))
        return [
            job.as_dict() for job in self.repository.list_jobs(status=status, limit=bounded_limit)
        ]

    def diagnostics(
        self,
        *,
        now: str | None = None,
        stale_after_seconds: int = 300,
        limit: int = 50,
    ) -> dict[str, Any]:
        return build_data_job_diagnostics(
            self.repository,
            now=now,
            stale_after_seconds=stale_after_seconds,
            limit=limit,
        )

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

    def query_bars(self, request: dict[str, Any]) -> dict[str, Any]:
        if self.bar_query is None:
            return {
                "schema": "market.data.bars.v1",
                "request": request,
                "bars": [],
                "row_count": 0,
                "total_row_count": 0,
                "source_file_count": 0,
                "deduplicated_row_count": 0,
                "truncated": False,
                "next_offset": None,
            }
        return self.bar_query.query_bars(request)

    def quality(self, request: dict[str, Any]) -> dict[str, Any]:
        response = self.query_bars(request)
        return quality_response(
            response["bars"],
            start=request.get("start") if isinstance(request.get("start"), str) else None,
            end=request.get("end") if isinstance(request.get("end"), str) else None,
        )

    def create_export(self, request: dict[str, Any]) -> dict[str, Any]:
        if self.export_service is None:
            return {
                "ok": False,
                "data": None,
                "error": {
                    "code": QmtDataExportUnavailableError.code,
                    "message": "data export is unavailable",
                },
                "meta": {},
            }
        return self.export_service.create(request)

    def list_exports(self) -> list[dict[str, Any]]:
        if self.export_service is None:
            return []
        return self.export_service.list_exports()

    def export_manifest(self, export_id: str) -> dict[str, Any] | None:
        if self.export_service is None:
            return None
        return self.export_service.manifest(export_id)

    def export_path(self, export_id: str) -> Any:
        if self.export_service is None:
            return None
        return self.export_service.download_path(export_id)

    def delete_export(self, export_id: str) -> bool:
        if self.export_service is None:
            return False
        return self.export_service.delete(export_id)

    def _run_download(self, job_id: str, request: dict[str, Any]) -> None:
        self.repository.mark_running(job_id)
        try:
            self.downloader.download_history(request)
            files = self._write_files(job_id, request)
            self.repository.mark_succeeded(job_id, download_result(request, files))
        except Exception as exc:
            self.repository.mark_failed(
                job_id,
                {
                    "code": QmtDataDownloadFailedError.code,
                    "message": f"{type(exc).__name__}: {exc}",
                },
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
    query = LocalBarQuery(repository, reader=DuckDbParquetBarReader(backend))
    return DataDownloadJobService(
        repository,
        downloader=XtDataHistoryDownloader(qmt_service),
        bar_reader=XtDataBarReader(qmt_service),
        file_writer=ParquetBarWriter(backend.data_dir),
        file_repository=repository,
        coverage_planner=CoveragePlanner(repository),
        bar_query=query,
        export_service=DataExportService(query, root=backend.data_dir / "exports"),
        run_async=run_async,
    )
