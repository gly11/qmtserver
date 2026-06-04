from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

from qmtserver.api.dependencies import get_qmt_service
from qmtserver.data.backend import create_data_backend
from qmtserver.data.jobs import create_data_job_service
from qmtserver.data.universe import canonicalize_download_request
from qmtserver.errors import (
    QmtInvalidMarketRequestError,
    QmtJobNotFoundError,
    QmtServerError,
    QmtSnapshotNotFoundError,
)

router = APIRouter(prefix="/market/data", tags=["market-data"])


class DataDownloadRequest(BaseModel):
    kind: str
    symbols: list[str] = Field(default_factory=list)
    universe: str | None = None
    exchange: str | None = None
    start: str | None = None
    end: str | None = None
    chunk_days: int = Field(default=31, ge=1, le=366)
    mode: str | None = None
    incremental: bool = False
    adjust: str = "none"
    period: str | None = None
    format: str = "parquet"
    force: bool = False
    storage_profile: str | None = None


class DataCoverageRequest(BaseModel):
    kind: str = "daily_bars"
    symbols: list[str] = Field(default_factory=list)
    start: str | None = None
    end: str | None = None
    adjust: str = "none"
    period: str | None = None
    storage_profile: str | None = None


class DataBarsRequest(DataCoverageRequest):
    limit: int = Field(default=1000, ge=1, le=10000)
    offset: int = Field(default=0, ge=0)


class DataExportRequest(DataCoverageRequest):
    format: str = "csv"
    limit: int = Field(default=10000, ge=1, le=1000000)


@router.post("/download")
def create_data_download(
    payload: DataDownloadRequest,
    request: Request,
) -> dict[str, Any]:
    try:
        canonical = canonicalize_download_request(
            payload.model_dump(),
            request.app.state.qmt_service,
        )
        canonical = _canonicalize_storage_profile(canonical, request)
        service = _get_data_job_service(request, canonical.get("storage_profile"))
        job = service.submit_download(canonical)
        return _success({"job": job})
    except QmtServerError as exc:
        return _error(exc.code, str(exc))


@router.post("/exports")
def create_data_export(
    payload: DataExportRequest,
    request: Request,
) -> dict[str, Any]:
    try:
        service = _get_data_job_service(request, payload.storage_profile)
        return service.create_export(payload.model_dump())
    except QmtServerError as exc:
        return _error(exc.code, str(exc))


@router.get("/exports")
def list_data_exports(request: Request) -> dict[str, Any]:
    try:
        service = _get_data_job_service(request)
        return _success({"exports": service.list_exports()})
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
def download_data_export(
    export_id: str, request: Request
) -> FileResponse | JSONResponse | dict[str, Any]:
    try:
        service = _get_data_job_service(request)
        path = service.export_path(export_id)
        if path is None:
            return _http_error(
                404,
                QmtSnapshotNotFoundError.code,
                f"data export not found: {export_id}",
            )
    except QmtSnapshotNotFoundError as exc:
        return _http_error(404, exc.code, str(exc))
    except QmtServerError as exc:
        return _error(exc.code, str(exc))
    return FileResponse(path, media_type=_download_media_type(path.name), filename=path.name)


@router.delete("/exports/{export_id}")
def delete_data_export(export_id: str, request: Request) -> dict[str, Any]:
    try:
        service = _get_data_job_service(request)
        deleted = service.delete_export(export_id)
        if not deleted:
            return _error(QmtSnapshotNotFoundError.code, f"data export not found: {export_id}")
        return _success({"deleted": True, "export_id": export_id})
    except QmtServerError as exc:
        return _error(exc.code, str(exc))


@router.get("/bars")
def get_data_bars(
    request: Request,
    kind: str = "daily_bars",
    symbols: str | None = None,
    start: str | None = None,
    end: str | None = None,
    adjust: str = "none",
    period: str | None = None,
    storage_profile: str | None = None,
    limit: int = 1000,
    offset: int = 0,
) -> dict[str, Any]:
    try:
        service = _get_data_job_service(request, storage_profile)
        return _success(
            service.query_bars(
                DataBarsRequest(
                    kind=kind,
                    symbols=_symbol_list(symbols),
                    start=start,
                    end=end,
                    adjust=adjust,
                    period=period,
                    storage_profile=storage_profile,
                    limit=limit,
                    offset=offset,
                ).model_dump()
            )
        )
    except QmtServerError as exc:
        return _error(exc.code, str(exc))


@router.get("/quality")
def get_data_quality(
    request: Request,
    kind: str = "daily_bars",
    symbols: str | None = None,
    start: str | None = None,
    end: str | None = None,
    adjust: str = "none",
    period: str | None = None,
    storage_profile: str | None = None,
    limit: int = 10000,
) -> dict[str, Any]:
    try:
        service = _get_data_job_service(request, storage_profile)
        return service.quality(
            DataBarsRequest(
                kind=kind,
                symbols=_symbol_list(symbols),
                start=start,
                end=end,
                adjust=adjust,
                period=period,
                storage_profile=storage_profile,
                limit=limit,
            ).model_dump()
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
    storage_profile: str | None = None,
) -> dict[str, Any]:
    try:
        service = _get_data_job_service(request, storage_profile)
        coverage = service.coverage(
            DataCoverageRequest(
                kind=kind,
                symbols=_symbol_list(symbols),
                start=start,
                end=end,
                adjust=adjust,
                period=period,
                storage_profile=storage_profile,
            ).model_dump()
        )
        return _success({"coverage": coverage})
    except QmtServerError as exc:
        return _error(exc.code, str(exc))


@router.get("/jobs")
def list_data_jobs(
    request: Request,
    status: str | None = None,
    limit: int = 50,
) -> dict[str, Any]:
    try:
        service = _get_data_job_service(request)
        return _success({"jobs": service.list_jobs(status=status, limit=limit)})
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


@router.post("/jobs/{job_id}/retry-failed")
def retry_failed_data_job(job_id: str, request: Request) -> dict[str, Any]:
    try:
        service = _get_data_job_service(request)
        job = service.retry_failed_chunks(job_id)
        if job is None:
            return _error(QmtJobNotFoundError.code, f"job not found: {job_id}")
        return _success({"job": job})
    except QmtServerError as exc:
        return _error(exc.code, str(exc))


def _get_data_job_service(request: Request, storage_profile: object = None) -> Any:
    get_qmt_service(request)
    existing_services = getattr(request.app.state, "data_job_services", None)
    if existing_services is None and hasattr(request.app.state, "data_job_service"):
        return request.app.state.data_job_service
    profile = _resolve_storage_profile(storage_profile, request)
    services = existing_services
    if services is None:
        services = {}
        request.app.state.data_job_services = services
    if profile in services:
        return services[profile]
    settings = request.app.state.settings
    profile_root = settings.data_storage_profile_roots()[profile]
    profile_settings = settings
    if profile != "default":
        profile_settings = settings.model_copy(
            update={"data_dir": profile_root, "data_db": profile_root / "db" / "qmtserver.duckdb"}
        )
    backend = create_data_backend(profile_settings)
    service = create_data_job_service(backend, request.app.state.qmt_service)
    services[profile] = service
    if profile == "default":
        request.app.state.data_job_service = service
    return service


def _canonicalize_storage_profile(payload: dict[str, Any], request: Request) -> dict[str, Any]:
    profile = _resolve_storage_profile(payload.get("storage_profile"), request)
    canonical = dict(payload)
    if payload.get("storage_profile") is not None:
        canonical["storage_profile"] = profile
    return canonical


def _resolve_storage_profile(storage_profile: object, request: Request) -> str:
    profile = str(storage_profile).strip() if isinstance(storage_profile, str) else ""
    if not profile:
        return "default"
    profiles = request.app.state.settings.data_storage_profile_roots()
    if profile not in profiles:
        raise QmtInvalidMarketRequestError(f"unknown storage_profile: {profile}")
    return profile


def _success(data: Any) -> dict[str, Any]:
    return {"ok": True, "data": data, "error": None, "meta": {}}


def _error(code: str, message: str) -> dict[str, Any]:
    return {"ok": False, "data": None, "error": {"code": code, "message": message}, "meta": {}}


def _http_error(status_code: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status_code, content=_error(code, message))


def _download_media_type(filename: str) -> str:
    if filename.endswith(".parquet"):
        return "application/vnd.apache.parquet"
    return "text/csv"


def _symbol_list(symbols: str | None) -> list[str]:
    if symbols is None:
        return []
    return [item.strip() for item in symbols.split(",") if item.strip()]
