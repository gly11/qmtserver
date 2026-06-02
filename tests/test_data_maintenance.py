from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from typing import Any

from qmtserver.data.maintenance import DataMaintenanceService


class DataMaintenanceServiceTests(unittest.TestCase):
    def test_check_reports_missing_registered_files_and_orphan_parquet(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp)
            orphan = data_dir / "raw" / "bars" / "orphan.parquet"
            orphan.parent.mkdir(parents=True)
            orphan.write_bytes(b"parquet")
            missing = data_dir / "raw" / "bars" / "missing.parquet"
            service = DataMaintenanceService(
                data_dir,
                repository=FakeFileRepository([{"file_id": "file-1", "path": str(missing)}]),
            )

            report = service.check()

        self.assertEqual(report["schema"], "market.data.maintenance.v1")
        self.assertEqual(report["registered_file_count"], 1)
        self.assertEqual(report["missing_registered_files"][0]["file_id"], "file-1")
        self.assertEqual(report["orphan_parquet_files"][0]["path"], str(orphan))

    def test_cleanup_defaults_to_dry_run_and_keeps_orphan_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp)
            orphan = data_dir / "raw" / "bars" / "orphan.parquet"
            orphan.parent.mkdir(parents=True)
            orphan.write_bytes(b"parquet")
            service = DataMaintenanceService(data_dir, repository=FakeFileRepository([]))

            result = service.cleanup(delete=False)

            self.assertTrue(orphan.exists())

        self.assertTrue(result["dry_run"])
        self.assertEqual(result["deleted_files"], [])
        self.assertEqual(result["delete_candidates"][0]["path"], str(orphan))

    def test_cleanup_with_delete_removes_orphan_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp)
            orphan = data_dir / "exports" / "orphan.csv"
            orphan.parent.mkdir(parents=True)
            orphan.write_text("date,symbol\n", encoding="utf-8")
            service = DataMaintenanceService(data_dir, repository=FakeFileRepository([]))

            result = service.cleanup(delete=True)

            self.assertFalse(orphan.exists())

        self.assertFalse(result["dry_run"])
        self.assertEqual(result["deleted_files"][0]["path"], str(orphan))


class FakeFileRepository:
    def __init__(self, files: list[dict[str, Any]]) -> None:
        self.files = files

    def list_all_files(self) -> list[dict[str, Any]]:
        return self.files


if __name__ == "__main__":
    unittest.main()
