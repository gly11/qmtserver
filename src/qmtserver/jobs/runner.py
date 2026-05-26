from __future__ import annotations

from pathlib import Path
from threading import Thread
from typing import Any

from qmtserver.jobs.registry import JobRegistry
from qmtserver.snapshots import SnapshotService


class JobRunner:
    def __init__(self, registry: JobRegistry, qmt_service: Any, *, snapshot_dir: Path) -> None:
        self.registry = registry
        self.qmt_service = qmt_service
        self.snapshot_dir = snapshot_dir

    def submit_history_download(self, request: dict[str, Any]) -> dict[str, Any]:
        job = self.registry.create("history_download", request)
        worker = Thread(target=self._run_history_download, args=(job.job_id, request), daemon=True)
        worker.start()
        return job.as_dict()

    def _run_history_download(self, job_id: str, request: dict[str, Any]) -> None:
        self.registry.mark_running(job_id)
        response = SnapshotService(self.qmt_service, root=self.snapshot_dir).create(request)
        if response["ok"]:
            self.registry.mark_succeeded(job_id, response["data"]["manifest"])
            return
        error = response["error"] or {"code": "JOB_FAILED", "message": "job failed"}
        self.registry.mark_failed(job_id, error)
