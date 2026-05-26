from __future__ import annotations

import unittest

from qmtserver.jobs.models import JobStatus
from qmtserver.jobs.registry import JobRegistry


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


if __name__ == "__main__":
    unittest.main()
