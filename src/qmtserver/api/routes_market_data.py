from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from qmtserver.api.dependencies import get_qmt_service
from qmtserver.data.backend import create_data_backend
from qmtserver.data.jobs import create_data_job_service
from qmtserver.errors import QmtJobNotFoundError, QmtServerError, QmtSnapshotNotFoundError

router = APIRouter(prefix="/market/data", tags=["market-data"])


class DataDownloadRequest(BaseModel):
    kind: str
    symbols: list[str] = Field(default_factory=list)
    start: str | None = None
    end: str | None = None
    adjust: str = "none"
    period: str | None = None
    format: str = "parquet"
    force: bool = False


class DataCoverageRequest(BaseModel):
    kind: str = "daily_bars"
    symbols: list[str] = Field(default_factory=list)
    start: str | None = None
    end: str | None = None
    adjust: str = "none"
    period: str | None = None


class DataBarsRequest(DataCoverageRequest):
    limit: int = Field(default=1000, ge=1, le=10000)


class DataExportRequest(DataCoverageRequest):
    format: str = "csv"
    limit: int = Field(default=10000, ge=1, le=1000000)


@router.post("/download")
def create_data_download(
    payload: DataDownloadRequest,
    request: Request,
) -> dict[str, Any]:
    try:
        service = _get_data_job_service(request)
        job = service.submit_download(payload.model_dump())
        return _success({"job": job})
    except QmtServerError as exc:
        return _error(exc.code, str(exc))


@router.post("/exports")
def create_data_export(
    payload: DataExportRequest,
    request: Request,
) -> dict[str, Any]:
    try:
        service = _get_data_job_service(request)
        return service.create_export(payload.model_dump())
    except QmtServerError as exc:
        return _error(exc.code, str(exc))


@router.get("/exports/{export_id}")
def get_data_export(export_id: str, request: Request) -> dict[str, Any]:
    try:
        service = _get_data_job_service(request)
        manifest = service.export_manifest(export_id)
        if manifest is None:
            return _error(QmtSnapshotNotFoundError.code, f"data export not found: {export_id}")
        return _success({"manifest": manifest})
    except QmtServerError as exc:
        return _error(exc.code, str(exc))


@router.get("/exports/{export_id}/download", response_model=None)
def download_data_export(export_id: str, request: Request) -> FileResponse | dict[str, Any]:
    try:
        service = _get_data_job_service(request)
        path = service.export_path(export_id)
        if path is None:
            return _error(QmtSnapshotNotFoundError.code, f"data export not found: {export_id}")
    except QmtServerError as exc:
        return _error(exc.code, str(exc))
    return FileResponse(path, media_type="text/csv", filename=path.name)


@router.get("/bars")
def get_data_bars(
    request: Request,
    kind: str = "daily_bars",
    symbols: str | None = None,
    start: str | None = None,
    end: str | None = None,
    adjust: str = "none",
    period: str | None = None,
    limit: int = 1000,
) -> dict[str, Any]:
    try:
        service = _get_data_job_service(request)
        return _success(
            service.query_bars(
                DataBarsRequest(
                    kind=kind,
                    symbols=_symbol_list(symbols),
                    start=start,
                    end=end,
                    adjust=adjust,
                    period=period,
                    limit=limit,
                ).model_dump()
            )
        )
    except QmtServerError as exc:
        return _error(exc.code, str(exc))


@router.get("/coverage")
def get_data_coverage(
    request: Request,
    kind: str = "daily_bars",
    symbols: str | None = None,
    start: str | None = None,
    end: str | None = None,
    adjust: str = "none",
    period: str | None = None,
) -> dict[str, Any]:
    try:
        service = _get_data_job_service(request)
        coverage = service.coverage(
            DataCoverageRequest(
                kind=kind,
                symbols=_symbol_list(symbols),
                start=start,
                end=end,
                adjust=adjust,
                period=period,
            ).model_dump()
        )
        return _success({"coverage": coverage})
    except QmtServerError as exc:
        return _error(exc.code, str(exc))


@router.get("/jobs/{job_id}")
def get_data_job(job_id: str, request: Request) -> dict[str, Any]:
    try:
        service = _get_data_job_service(request)
        job = service.get_job(job_id)
        if job is None:
            return _error(QmtJobNotFoundError.code, f"job not found: {job_id}")
        return _success({"job": job})
    except QmtServerError as exc:
        return _error(exc.code, str(exc))


def _get_data_job_service(request: Request) -> Any:
    get_qmt_service(request)
    if hasattr(request.app.state, "data_job_service"):
        return request.app.state.data_job_service
    backend = create_data_backend(request.app.state.settings)
    return create_data_job_service(backend, request.app.state.qmt_service)


def _success(data: Any) -> dict[str, Any]:
    return {"ok": True, "data": data, "error": None, "meta": {}}


def _error(code: str, message: str) -> dict[str, Any]:
    return {"ok": False, "data": None, "error": {"code": code, "message": message}, "meta": {}}


def _symbol_list(symbols: str | None) -> list[str]:
    if symbols is None:
        return []
    return [item.strip() for item in symbols.split(",") if item.strip()]
