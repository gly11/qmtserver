from __future__ import annotations

from pathlib import Path
from threading import Thread
from typing import Any

from qmtserver.jobs.registry import JobRegistry
from qmtserver.market.adapter import XtDataMarketAdapter
from qmtserver.market.models import MarketRequest
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
        try:
            self._download_history(request)
            response = SnapshotService(self.qmt_service, root=self.snapshot_dir).create(request)
            if response["ok"]:
                self.registry.mark_succeeded(job_id, response["data"]["manifest"])
                return
            error = response["error"] or {"code": "JOB_FAILED", "message": "job failed"}
            self.registry.mark_failed(job_id, error)
        except Exception as exc:
            self.registry.mark_failed(
                job_id,
                {"code": "JOB_FAILED", "message": f"{type(exc).__name__}: {exc}"},
            )

    def _download_history(self, request: dict[str, Any]) -> None:
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
