from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from qmtserver.api.dependencies import get_qmt_service
from qmtserver.errors import QmtJobNotFoundError, QmtJobNotReadyError
from qmtserver.jobs import JobRunner

router = APIRouter(prefix="/jobs", tags=["jobs"])


class HistoryDownloadRequest(BaseModel):
    kind: str
    symbols: list[str] = Field(default_factory=list)
    start: str | None = None
    end: str | None = None
    adjust: str = "none"
    period: str | None = None
    format: str = "csv"


@router.post("/history-download")
def create_history_download(
    request: HistoryDownloadRequest,
    http_request: Request,
) -> dict[str, object]:
    service = get_qmt_service(http_request)
    runner = JobRunner(
        http_request.app.state.job_registry,
        service,
        snapshot_dir=service.settings.snapshot_dir,
    )
    job = runner.submit_history_download(request.model_dump())
    return {"ok": True, "data": {"job": job}, "error": None, "meta": {}}


@router.get("/{job_id}")
def get_job(job_id: str, request: Request) -> dict[str, object]:
    get_qmt_service(request)
    job = request.app.state.job_registry.get(job_id)
    if job is None:
        return _error(QmtJobNotFoundError.code, f"job not found: {job_id}")
    return {"ok": True, "data": {"job": job.as_dict()}, "error": None, "meta": {}}


@router.get("/{job_id}/result")
def get_job_result(job_id: str, request: Request) -> dict[str, object]:
    get_qmt_service(request)
    job = request.app.state.job_registry.get(job_id)
    if job is None:
        return _error(QmtJobNotFoundError.code, f"job not found: {job_id}")
    if job.result is None:
        return _error(QmtJobNotReadyError.code, f"job result is not ready: {job_id}")
    return {"ok": True, "data": {"manifest": job.result}, "error": None, "meta": {}}


@router.post("/{job_id}/cancel")
def cancel_job(job_id: str, request: Request) -> dict[str, object]:
    get_qmt_service(request)
    if request.app.state.job_registry.get(job_id) is None:
        return _error(QmtJobNotFoundError.code, f"job not found: {job_id}")
    cancelled = request.app.state.job_registry.cancel(job_id)
    job = request.app.state.job_registry.get(job_id)
    return {
        "ok": cancelled,
        "data": {"job": job.as_dict() if job is not None else None},
        "error": None
        if cancelled
        else {"code": "JOB_NOT_CANCELLABLE", "message": "job cannot be cancelled"},
        "meta": {},
    }


def _error(code: str, message: str) -> dict[str, Any]:
    return {"ok": False, "data": None, "error": {"code": code, "message": message}, "meta": {}}
