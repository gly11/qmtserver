from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from threading import Thread
from typing import Any, Protocol
from uuid import uuid4

from qmtserver.data.backend import DuckDbDataBackend
from qmtserver.market.adapter import XtDataMarketAdapter
from qmtserver.market.models import MarketRequest


class DataJobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class DataJobRepositoryProtocol(Protocol):
    def create(self, job_type: str, request: dict[str, Any]) -> DataJobRecord: ...

    def get(self, job_id: str) -> DataJobRecord | None: ...

    def mark_running(self, job_id: str) -> None: ...

    def mark_succeeded(self, job_id: str, result: dict[str, Any]) -> None: ...

    def mark_failed(self, job_id: str, error: dict[str, str]) -> None: ...


class HistoryDownloader(Protocol):
    def download_history(self, request: dict[str, Any]) -> None: ...


class DuckDbBackendProtocol(Protocol):
    database_path: Any

    def connect(self, path: str) -> Any: ...


def _now() -> str:
    return datetime.now(UTC).isoformat()


@dataclass
class DataJobRecord:
    job_type: str
    request: dict[str, Any]
    job_id: str = field(default_factory=lambda: str(uuid4()))
    status: DataJobStatus = DataJobStatus.QUEUED
    created_at: str = field(default_factory=_now)
    started_at: str | None = None
    finished_at: str | None = None
    result: dict[str, Any] | None = None
    error: dict[str, str] | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "kind": self.job_type,
            "status": self.status.value,
            "request": self.request,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "result": self.result,
            "error": self.error,
        }


class DataJobRepository:
    def __init__(self, backend: DuckDbBackendProtocol) -> None:
        self.backend = backend

    def create(self, job_type: str, request: dict[str, Any]) -> DataJobRecord:
        job = DataJobRecord(job_type=job_type, request=request)
        self._execute(
            """
            INSERT INTO data_jobs (
                job_id, job_type, status, request_json, result_json, error_code, error_message,
                created_at, started_at, finished_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                job.job_id,
                job.job_type,
                job.status.value,
                json.dumps(job.request, ensure_ascii=False, sort_keys=True),
                None,
                None,
                None,
                job.created_at,
                None,
                None,
            ),
        )
        return job

    def get(self, job_id: str) -> DataJobRecord | None:
        connection = self.backend.connect(str(self.backend.database_path))
        try:
            cursor = connection.execute(
                """
                SELECT job_id, job_type, status, request_json, result_json, error_code,
                       error_message, created_at, started_at, finished_at
                FROM data_jobs
                WHERE job_id = ?
                """,
                (job_id,),
            )
            row = cursor.fetchone()
            if row is None:
                return None
            return _record_from_row(row)
        finally:
            connection.close()

    def mark_running(self, job_id: str) -> None:
        self._execute(
            "UPDATE data_jobs SET status = ?, started_at = ? WHERE job_id = ?",
            (DataJobStatus.RUNNING.value, _now(), job_id),
        )

    def mark_succeeded(self, job_id: str, result: dict[str, Any]) -> None:
        self._execute(
            """
            UPDATE data_jobs
            SET status = ?, result_json = ?, error_code = NULL, error_message = NULL,
                finished_at = ?
            WHERE job_id = ?
            """,
            (
                DataJobStatus.SUCCEEDED.value,
                json.dumps(result, ensure_ascii=False, sort_keys=True),
                _now(),
                job_id,
            ),
        )

    def mark_failed(self, job_id: str, error: dict[str, str]) -> None:
        self._execute(
            """
            UPDATE data_jobs
            SET status = ?, error_code = ?, error_message = ?, finished_at = ?
            WHERE job_id = ?
            """,
            (
                DataJobStatus.FAILED.value,
                error.get("code", "DATA_DOWNLOAD_FAILED"),
                error.get("message", "data download failed"),
                _now(),
                job_id,
            ),
        )

    def _execute(self, sql: str, parameters: tuple[Any, ...]) -> Any:
        connection = self.backend.connect(str(self.backend.database_path))
        try:
            return connection.execute(sql, parameters)
        finally:
            connection.close()


class DataDownloadJobService:
    def __init__(
        self,
        repository: DataJobRepositoryProtocol,
        *,
        downloader: HistoryDownloader,
        run_async: bool = True,
    ) -> None:
        self.repository = repository
        self.downloader = downloader
        self.run_async = run_async

    def submit_download(self, request: dict[str, Any]) -> dict[str, Any]:
        job = self.repository.create("market_data_download", request)
        initial = job.as_dict()
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

    def _run_download(self, job_id: str, request: dict[str, Any]) -> None:
        self.repository.mark_running(job_id)
        try:
            self.downloader.download_history(request)
            self.repository.mark_succeeded(job_id, _download_result(request))
        except Exception as exc:
            self.repository.mark_failed(
                job_id,
                {"code": "DATA_DOWNLOAD_FAILED", "message": f"{type(exc).__name__}: {exc}"},
            )


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
    return DataDownloadJobService(
        DataJobRepository(backend),
        downloader=XtDataHistoryDownloader(qmt_service),
        run_async=run_async,
    )


def _download_result(request: dict[str, Any]) -> dict[str, Any]:
    symbols = request.get("symbols")
    return {
        "schema": "market.data.download.v1",
        "downloaded": True,
        "symbols": symbols if isinstance(symbols, list) else [],
        "kind": request.get("kind"),
        "period": "1d" if request.get("kind") == "daily_bars" else request.get("period"),
        "storage": "miniqmt_cache",
        "next_step": "parquet_writer_pending",
    }


def _record_from_row(row: tuple[Any, ...]) -> DataJobRecord:
    error = None
    if row[5] or row[6]:
        error = {"code": str(row[5]), "message": str(row[6])}
    return DataJobRecord(
        job_id=str(row[0]),
        job_type=str(row[1]),
        status=DataJobStatus(str(row[2])),
        request=json.loads(str(row[3])),
        result=json.loads(str(row[4])) if row[4] else None,
        error=error,
        created_at=str(row[7]),
        started_at=str(row[8]) if row[8] else None,
        finished_at=str(row[9]) if row[9] else None,
    )
