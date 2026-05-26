from __future__ import annotations

from threading import Lock
from typing import Any

from qmtserver.jobs.models import JobRecord, JobStatus, _now


class JobRegistry:
    def __init__(self) -> None:
        self._lock = Lock()
        self._jobs: dict[str, JobRecord] = {}

    def create(self, kind: str, request: dict[str, Any]) -> JobRecord:
        job = JobRecord(kind=kind, request=request)
        with self._lock:
            self._jobs[job.job_id] = job
        return job

    def get(self, job_id: str) -> JobRecord | None:
        with self._lock:
            return self._jobs.get(job_id)

    def status_counts(self) -> dict[str, int]:
        counts = {status.value: 0 for status in JobStatus}
        with self._lock:
            for job in self._jobs.values():
                counts[job.status.value] += 1
        return counts

    def mark_running(self, job_id: str) -> None:
        self._set_status(job_id, JobStatus.RUNNING)

    def mark_succeeded(self, job_id: str, result: dict[str, Any]) -> None:
        with self._lock:
            job = self._jobs[job_id]
            job.status = JobStatus.SUCCEEDED
            job.updated_at = _now()
            job.result = result
            job.error = None

    def mark_failed(self, job_id: str, error: dict[str, str]) -> None:
        with self._lock:
            job = self._jobs[job_id]
            job.status = JobStatus.FAILED
            job.updated_at = _now()
            job.error = error

    def cancel(self, job_id: str) -> bool:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None or job.status is not JobStatus.QUEUED:
                return False
            job.status = JobStatus.CANCELLED
            job.updated_at = _now()
            return True

    def _set_status(self, job_id: str, status: JobStatus) -> None:
        with self._lock:
            job = self._jobs[job_id]
            job.status = status
            job.updated_at = _now()
