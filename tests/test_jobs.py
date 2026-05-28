from __future__ import annotations

import tempfile
import time
import unittest
from pathlib import Path
from typing import Any

from qmtserver.config import load_settings
from qmtserver.jobs.models import JobStatus
from qmtserver.jobs.registry import JobRegistry
from qmtserver.jobs.runner import JobRunner


class JobRegistryTests(unittest.TestCase):
    def test_job_registry_creates_and_updates_status(self) -> None:
        registry = JobRegistry()

        job = registry.create("history_download", {"kind": "daily_bars"})
        registry.mark_running(job.job_id)
        registry.mark_succeeded(job.job_id, {"snapshot_id": "daily_bars-abc"})

        stored = registry.get(job.job_id)
        assert stored is not None
        self.assertEqual(stored.status, JobStatus.SUCCEEDED)
        self.assertEqual(stored.result, {"snapshot_id": "daily_bars-abc"})

    def test_cancel_only_changes_queued_job(self) -> None:
        registry = JobRegistry()
        job = registry.create("history_download", {})

        self.assertTrue(registry.cancel(job.job_id))
        stored = registry.get(job.job_id)
        assert stored is not None
        self.assertEqual(stored.status, JobStatus.CANCELLED)

    def test_history_download_job_downloads_before_snapshot(self) -> None:
        target = RecordingHistoryTarget()
        service = RecordingHistoryService(target)
        registry = JobRegistry()
        with tempfile.TemporaryDirectory() as tmp:
            runner = JobRunner(registry, service, snapshot_dir=Path(tmp))

            job = runner.submit_history_download(
                {
                    "kind": "daily_bars",
                    "symbols": ["000001.SZ"],
                    "start": "2026-01-01",
                    "end": "2026-01-31",
                    "adjust": "none",
                    "format": "csv",
                }
            )
            stored = self._wait_for_status(registry, job["job_id"], JobStatus.SUCCEEDED)

        self.assertEqual(stored.status, JobStatus.SUCCEEDED)
        self.assertEqual(target.download_calls[0]["stock_code"], "000001.SZ")
        self.assertEqual(target.market_data_calls[0]["stock_list"], ["000001.SZ"])

    def _wait_for_status(
        self,
        registry: JobRegistry,
        job_id: str,
        expected: JobStatus,
    ) -> Any:
        stored = registry.get(job_id)
        for _ in range(50):
            stored = registry.get(job_id)
            if stored is not None and stored.status == expected:
                return stored
            time.sleep(0.02)
        assert stored is not None
        return stored


class RecordingHistoryTarget:
    def __init__(self) -> None:
        self.download_calls: list[dict[str, Any]] = []
        self.market_data_calls: list[dict[str, Any]] = []

    def download_history_data(self, **kwargs: Any) -> None:
        self.download_calls.append(kwargs)

    def get_market_data_ex(self, **kwargs: Any) -> dict[str, list[dict[str, object]]]:
        self.market_data_calls.append(kwargs)
        return {
            "000001.SZ": [
                {
                    "date": "2026-01-02",
                    "open": 10.1,
                    "high": 10.5,
                    "low": 10.0,
                    "close": 10.3,
                    "volume": 1200000,
                    "amount": 12345678.9,
                }
            ]
        }


class RecordingHistoryService:
    def __init__(self, target: RecordingHistoryTarget) -> None:
        self.target = target
        self.settings = load_settings(_env_file=None, auto_connect=False)

    def get_target(self, target: str) -> RecordingHistoryTarget:
        if target != "xtdata":
            raise AssertionError(f"unexpected target: {target}")
        return self.target


if __name__ == "__main__":
    unittest.main()
