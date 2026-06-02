from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol


class DataFileIndex(Protocol):
    def list_all_files(self) -> list[dict[str, Any]]: ...


class DataMaintenanceService:
    def __init__(self, data_dir: Path, *, repository: DataFileIndex) -> None:
        self.data_dir = data_dir
        self.repository = repository

    def check(self) -> dict[str, Any]:
        registered = self.repository.list_all_files()
        registered_paths = {_normalized_path(file_record["path"]) for file_record in registered}
        missing_registered = [
            _file_summary(file_record)
            for file_record in registered
            if not Path(str(file_record["path"])).exists()
        ]
        orphan_parquet = [
            {"path": str(path)}
            for path in self._parquet_files()
            if _normalized_path(path) not in registered_paths
        ]
        return {
            "schema": "market.data.maintenance.v1",
            "data_dir": str(self.data_dir),
            "registered_file_count": len(registered),
            "missing_registered_files": missing_registered,
            "orphan_parquet_files": orphan_parquet,
            "orphan_export_files": self._orphan_export_files(),
        }

    def cleanup(self, *, delete: bool = False) -> dict[str, Any]:
        report = self.check()
        candidates = [
            *report["orphan_parquet_files"],
            *report["orphan_export_files"],
        ]
        deleted = []
        if delete:
            for candidate in candidates:
                path = Path(str(candidate["path"]))
                if self._can_delete(path) and path.exists():
                    path.unlink()
                    deleted.append({"path": str(path)})
        return {
            "schema": "market.data.cleanup.v1",
            "dry_run": not delete,
            "delete_candidates": candidates,
            "deleted_files": deleted,
        }

    def rebuild_index_plan(self) -> dict[str, Any]:
        parquet_files = [{"path": str(path)} for path in self._parquet_files()]
        return {
            "schema": "market.data.rebuild_index.v1",
            "dry_run": True,
            "parquet_file_count": len(parquet_files),
            "parquet_files": parquet_files,
        }

    def _parquet_files(self) -> list[Path]:
        raw = self.data_dir / "raw" / "bars"
        if not raw.exists():
            return []
        return sorted(raw.rglob("*.parquet"))

    def _orphan_export_files(self) -> list[dict[str, str]]:
        exports = self.data_dir / "exports"
        if not exports.exists():
            return []
        orphaned: list[dict[str, str]] = []
        for data_file in sorted(exports.glob("*.csv")):
            manifest = exports / f"{data_file.stem}.manifest.json"
            if not manifest.exists():
                orphaned.append({"path": str(data_file)})
        for manifest in sorted(exports.glob("*.manifest.json")):
            data_file = exports / f"{manifest.name.removesuffix('.manifest.json')}.csv"
            if not data_file.exists():
                orphaned.append({"path": str(manifest)})
        return orphaned

    def _can_delete(self, path: Path) -> bool:
        try:
            path.resolve().relative_to(self.data_dir.resolve())
        except ValueError:
            return False
        return path.is_file()


def _file_summary(file_record: dict[str, Any]) -> dict[str, Any]:
    return {
        "file_id": file_record.get("file_id"),
        "symbol": file_record.get("symbol"),
        "path": str(file_record.get("path")),
    }


def _normalized_path(path: object) -> str:
    return str(Path(str(path)))
