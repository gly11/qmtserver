from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Protocol

from qmtserver.data.models import DataJobRecord, DataJobStatus


class DataJobRepository(Protocol):
    def list_jobs(self, *, status: str | None = None, limit: int = 50) -> list[DataJobRecord]: ...


def build_data_job_diagnostics(
    repository: DataJobRepository,
    *,
    now: str | None = None,
    stale_after_seconds: int = 300,
    limit: int = 50,
) -> dict[str, Any]:
    jobs = repository.list_jobs(limit=limit)
    now_value = _parse_time(now) or datetime.now(UTC)
    stale_jobs = [
        _job_diagnostic(job, now_value=now_value)
        for job in jobs
        if job.status in {DataJobStatus.QUEUED, DataJobStatus.RUNNING}
        and _job_age_seconds(job, now_value) >= stale_after_seconds
    ]
    failed_jobs = [
        _job_diagnostic(job, now_value=now_value)
        for job in jobs
        if job.status == DataJobStatus.FAILED
    ]
    status_counts = {status.value: 0 for status in DataJobStatus}
    for job in jobs:
        status_counts[job.status.value] = status_counts.get(job.status.value, 0) + 1
    return {
        "schema": "market.data.jobs.diagnostics.v1",
        "total": len(jobs),
        "queued": status_counts.get(DataJobStatus.QUEUED.value, 0),
        "running": status_counts.get(DataJobStatus.RUNNING.value, 0),
        "succeeded": status_counts.get(DataJobStatus.SUCCEEDED.value, 0),
        "failed": status_counts.get(DataJobStatus.FAILED.value, 0),
        "stale_running": len(stale_jobs),
        "stale_after_seconds": stale_after_seconds,
        "stale_running_jobs": stale_jobs,
        "failed_jobs": failed_jobs,
    }


def _job_diagnostic(job: DataJobRecord, *, now_value: datetime) -> dict[str, Any]:
    result = {
        "job_id": job.job_id,
        "status": job.status.value,
        "job_type": job.job_type,
        "age_seconds": _job_age_seconds(job, now_value),
        "created_at": job.created_at,
        "started_at": job.started_at,
        "finished_at": job.finished_at,
        "symbols": [str(symbol) for symbol in job.request.get("symbols", [])],
        "kind": job.request.get("kind"),
    }
    if job.error:
        result["error_code"] = job.error.get("code")
        result["error_message"] = job.error.get("message")
    return result


def _job_age_seconds(job: DataJobRecord, now_value: datetime) -> int:
    anchor = _parse_time(job.started_at) or _parse_time(job.created_at) or now_value
    return max(0, int((now_value - anchor).total_seconds()))


def _parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)
