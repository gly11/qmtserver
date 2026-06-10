from __future__ import annotations

import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from qmtserver.data.maintenance import DataMaintenanceService, ParquetMetadataReader


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
        self.assertEqual(report["health"]["status"], "warning")

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

    def test_check_reports_registered_metadata_mismatches(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp)
            path = data_dir / "raw" / "bars" / "kind=daily_bars" / "period=1d" / "file.parquet"
            path.parent.mkdir(parents=True)
            path.write_bytes(b"parquet")
            registered = {
                "file_id": "file-1",
                "path": str(path),
                "hash": "sha256:old",
                "row_count": 2,
                "coverage_start": "2026-01-01",
                "coverage_end": "2026-01-02",
                "kind": "daily_bars",
                "symbol": "000001.SZ",
                "period": "1d",
                "adjust": "none",
            }
            actual = {**registered, "hash": "sha256:new", "row_count": 3}
            service = DataMaintenanceService(
                data_dir,
                repository=FakeFileRepository([registered]),
                metadata_reader=FakeMetadataReader({path: actual}),
            )

            report = service.check()

        mismatch = report["metadata_mismatches"][0]
        self.assertEqual(mismatch["file_id"], "file-1")
        self.assertEqual(mismatch["fields"], ["hash", "row_count"])
        self.assertEqual(report["health"]["metadata_mismatch_count"], 1)

    def test_check_reports_coverage_consistency_issues(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp)
            file_record = _file_record(
                data_dir,
                "000001.SZ",
                "a.parquet",
                "2026-01-01",
                "2026-01-10",
            )
            repository = FakeFileRepository(
                [file_record],
                coverage=[
                    {
                        "kind": "daily_bars",
                        "symbol": "000001.SZ",
                        "period": "1d",
                        "adjust": "none",
                        "coverage_start": "2026-01-01",
                        "coverage_end": "2026-01-09",
                        "row_count": 9,
                        "file_count": 1,
                    }
                ],
            )
            service = DataMaintenanceService(data_dir, repository=repository)

            report = service.check()

        issue = report["coverage_consistency_issues"][0]
        self.assertEqual(issue["symbol"], "000001.SZ")
        self.assertEqual(issue["fields"], ["coverage_end", "row_count"])
        self.assertEqual(report["health"]["coverage_consistency_issue_count"], 1)

    def test_rebuild_index_execute_records_parquet_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp)
            path = (
                data_dir
                / "raw"
                / "bars"
                / "kind=daily_bars"
                / "period=1d"
                / "adjust=none"
                / "symbol=000001.SZ"
                / "file.parquet"
            )
            path.parent.mkdir(parents=True)
            path.write_bytes(b"parquet")
            metadata = {
                "file_id": "file-1",
                "path": str(path),
                "hash": "sha256:file",
                "row_count": 2,
                "coverage_start": "2026-01-01",
                "coverage_end": "2026-01-02",
                "kind": "daily_bars",
                "symbol": "000001.SZ",
                "period": "1d",
                "adjust": "none",
                "format": "parquet",
            }
            repository = FakeFileRepository([])
            service = DataMaintenanceService(
                data_dir,
                repository=repository,
                metadata_reader=FakeMetadataReader({path: metadata}),
            )

            result = service.rebuild_index(execute=True)

        self.assertFalse(result["dry_run"])
        self.assertTrue(repository.cleared)
        self.assertEqual(repository.recorded_files, [metadata])
        self.assertEqual(result["rebuilt_file_count"], 1)

    def test_parquet_metadata_reader_ignores_hive_partition_columns(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp)
            path = (
                data_dir
                / "raw"
                / "bars"
                / "kind=daily_bars"
                / "period=1d"
                / "adjust=none"
                / "symbol=000001.SZ"
                / "file.parquet"
            )
            path.parent.mkdir(parents=True)
            pyarrow = __import__("pyarrow")
            parquet = __import__("pyarrow.parquet").parquet
            table = pyarrow.table(
                {
                    "date": ["2026-01-01", "2026-01-02"],
                    "symbol": ["000001.SZ", "000001.SZ"],
                    "close": [10.0, 10.5],
                }
            )
            parquet.write_table(table, path)

            metadata = ParquetMetadataReader().read(path)

        self.assertEqual(metadata["symbol"], "000001.SZ")
        self.assertEqual(metadata["row_count"], 2)
        self.assertEqual(metadata["coverage_start"], "2026-01-01")
        self.assertEqual(metadata["coverage_end"], "2026-01-02")

    def test_cleanup_can_delete_expired_exports(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp)
            exports = data_dir / "exports"
            exports.mkdir(parents=True)
            data_file = exports / "export-old.csv"
            manifest = exports / "export-old.manifest.json"
            data_file.write_text("date,symbol\n", encoding="utf-8")
            old_time = datetime.now(UTC) - timedelta(days=10)
            manifest.write_text(
                f'{{"export_id":"export-old","format":"csv","generated_at":"{old_time.isoformat()}"}}',
                encoding="utf-8",
            )
            service = DataMaintenanceService(data_dir, repository=FakeFileRepository([]))

            result = service.cleanup(delete=True, expired_days=1)

            self.assertFalse(data_file.exists())
            self.assertFalse(manifest.exists())

        self.assertEqual(len(result["expired_export_files"]), 2)

    def test_compaction_plan_groups_small_files_by_market_key(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp)
            files = [
                _file_record(data_dir, "000001.SZ", "a.parquet", "2026-01-01", "2026-01-10"),
                _file_record(data_dir, "000001.SZ", "b.parquet", "2026-01-11", "2026-01-20"),
                _file_record(data_dir, "600000.SH", "c.parquet", "2026-01-01", "2026-01-10"),
            ]
            service = DataMaintenanceService(data_dir, repository=FakeFileRepository(files))

            result = service.compact(execute=False, min_files=2)

        self.assertTrue(result["dry_run"])
        self.assertEqual(result["group_count"], 1)
        self.assertEqual(result["groups"][0]["symbol"], "000001.SZ")
        self.assertEqual(result["groups"][0]["source_file_count"], 2)
        self.assertEqual(result["compacted_file_count"], 0)

    def test_compaction_execute_replaces_sources_and_rebuilds_index(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp)
            files = [
                _file_record(data_dir, "000001.SZ", "a.parquet", "2026-01-01", "2026-01-10"),
                _file_record(data_dir, "000001.SZ", "b.parquet", "2026-01-11", "2026-01-20"),
            ]
            for file_record in files:
                path = Path(str(file_record["path"]))
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"parquet")
            repository = FakeFileRepository(files)
            service = DataMaintenanceService(
                data_dir,
                repository=repository,
                metadata_reader=FakeAnyMetadataReader(),
                compaction_engine=FakeCompactionEngine(),
            )

            result = service.compact(execute=True, min_files=2)

        self.assertFalse(result["dry_run"])
        self.assertEqual(result["compacted_file_count"], 1)
        self.assertEqual(result["deleted_source_count"], 2)
        self.assertFalse(Path(str(files[0]["path"])).exists())
        self.assertTrue(repository.cleared)
        self.assertEqual(len(repository.recorded_files), 1)
        self.assertEqual(result["rebuild_index"]["rebuilt_file_count"], 1)


class FakeFileRepository:
    def __init__(
        self,
        files: list[dict[str, Any]],
        coverage: list[dict[str, Any]] | None = None,
    ) -> None:
        self.files = files
        self.coverage = coverage or []
        self.cleared = False
        self.recorded_files: list[dict[str, Any]] = []

    def list_all_files(self) -> list[dict[str, Any]]:
        return self.files

    def list_coverage(self, request: dict[str, Any]) -> list[dict[str, Any]]:
        del request
        return self.coverage

    def clear_file_index(self) -> None:
        self.cleared = True

    def record_file(self, file_record: dict[str, Any]) -> None:
        self.recorded_files.append(file_record)


class FakeMetadataReader:
    def __init__(self, records: dict[Path, dict[str, Any]]) -> None:
        self.records = records

    def read(self, path: Path) -> dict[str, Any]:
        return self.records[path]


class FakeAnyMetadataReader:
    def read(self, path: Path) -> dict[str, Any]:
        return {
            "file_id": "rebuilt-file",
            "path": str(path),
            "hash": "sha256:rebuilt",
            "row_count": 20,
            "coverage_start": "2026-01-01",
            "coverage_end": "2026-01-20",
            "kind": "daily_bars",
            "symbol": "000001.SZ",
            "period": "1d",
            "adjust": "none",
            "format": "parquet",
        }


class FakeCompactionEngine:
    def compact(self, group: dict[str, Any], output_path: Path) -> dict[str, Any]:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"compact")
        return {
            "file_id": "compact-file",
            "path": str(output_path),
            "hash": "sha256:compact",
            "row_count": group["row_count"],
            "coverage_start": group["coverage_start"],
            "coverage_end": group["coverage_end"],
            "kind": group["kind"],
            "symbol": group["symbol"],
            "period": group["period"],
            "adjust": group["adjust"],
            "format": "parquet",
        }


def _file_record(
    data_dir: Path,
    symbol: str,
    filename: str,
    start: str,
    end: str,
) -> dict[str, Any]:
    path = (
        data_dir
        / "raw"
        / "bars"
        / "kind=daily_bars"
        / "period=1d"
        / "adjust=none"
        / f"symbol={symbol}"
        / filename
    )
    return {
        "file_id": filename,
        "path": str(path),
        "hash": f"sha256:{filename}",
        "row_count": 10,
        "coverage_start": start,
        "coverage_end": end,
        "kind": "daily_bars",
        "symbol": symbol,
        "period": "1d",
        "adjust": "none",
        "format": "parquet",
    }


if __name__ == "__main__":
    unittest.main()
