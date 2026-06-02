from __future__ import annotations

import hashlib
import importlib
import json
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Protocol

from qmtserver.data.compaction import (
    CompactionEngine,
    ParquetCompactionEngine,
    plan_compaction_groups,
)


class DataFileIndex(Protocol):
    def list_all_files(self) -> list[dict[str, Any]]: ...

    def clear_file_index(self) -> None: ...

    def record_file(self, file_record: dict[str, Any]) -> None: ...


class ParquetMetadataReaderProtocol(Protocol):
    def read(self, path: Path) -> dict[str, Any]: ...


class DataMaintenanceService:
    def __init__(
        self,
        data_dir: Path,
        *,
        repository: DataFileIndex,
        metadata_reader: ParquetMetadataReaderProtocol | None = None,
        compaction_engine: CompactionEngine | None = None,
    ) -> None:
        self.data_dir = data_dir
        self.repository = repository
        self.metadata_reader = metadata_reader or ParquetMetadataReader()
        self.compaction_engine = compaction_engine or ParquetCompactionEngine()

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
        metadata_mismatches = self._metadata_mismatches(registered)
        return {
            "schema": "market.data.maintenance.v1",
            "data_dir": str(self.data_dir),
            "registered_file_count": len(registered),
            "missing_registered_files": missing_registered,
            "orphan_parquet_files": orphan_parquet,
            "orphan_export_files": self._orphan_export_files(),
            "metadata_mismatches": metadata_mismatches,
            "health": self.health_summary(
                registered=registered,
                missing_registered=missing_registered,
                orphan_parquet=orphan_parquet,
                orphan_exports=self._orphan_export_files(),
                metadata_mismatches=metadata_mismatches,
            ),
        }

    def cleanup(self, *, delete: bool = False, expired_days: int | None = None) -> dict[str, Any]:
        report = self.check()
        expired_exports = self._expired_export_files(expired_days=expired_days)
        candidates = [
            *report["orphan_parquet_files"],
            *report["orphan_export_files"],
            *expired_exports,
        ]
        deleted = []
        if delete:
            for candidate in _unique_candidates(candidates):
                path = Path(str(candidate["path"]))
                if self._can_delete(path) and path.exists():
                    path.unlink()
                    deleted.append({"path": str(path)})
        return {
            "schema": "market.data.cleanup.v1",
            "dry_run": not delete,
            "delete_candidates": _unique_candidates(candidates),
            "expired_export_files": expired_exports,
            "deleted_files": deleted,
        }

    def rebuild_index_plan(self) -> dict[str, Any]:
        return self.rebuild_index(execute=False)

    def rebuild_index(self, *, execute: bool = False) -> dict[str, Any]:
        parquet_files = [{"path": str(path)} for path in self._parquet_files()]
        metadata = []
        errors = []
        for path in self._parquet_files():
            try:
                metadata.append(self.metadata_reader.read(path))
            except Exception as exc:
                errors.append({"path": str(path), "error": f"{type(exc).__name__}: {exc}"})
        if execute:
            self.repository.clear_file_index()
            for file_record in metadata:
                self.repository.record_file(file_record)
        return {
            "schema": "market.data.rebuild_index.v1",
            "dry_run": not execute,
            "parquet_file_count": len(parquet_files),
            "parquet_files": parquet_files,
            "metadata": metadata,
            "metadata_error_count": len(errors),
            "metadata_errors": errors,
            "rebuilt_file_count": len(metadata) if execute else 0,
        }

    def compact(self, *, execute: bool = False, min_files: int = 2) -> dict[str, Any]:
        groups = plan_compaction_groups(
            self.repository.list_all_files(),
            data_dir=self.data_dir,
            min_files=min_files,
        )
        compacted = []
        deleted = []
        rebuild = None
        if execute:
            for group in groups:
                file_record = self.compaction_engine.compact(group, Path(str(group["output_path"])))
                compacted.append(file_record)
                for source in group["source_files"]:
                    source_path = Path(str(source["path"]))
                    if self._can_delete(source_path) and source_path.exists():
                        source_path.unlink()
                        deleted.append({"path": str(source_path)})
            rebuild = self.rebuild_index(execute=True)
        return {
            "schema": "market.data.compaction.v1",
            "dry_run": not execute,
            "group_count": len(groups),
            "groups": groups,
            "compacted_file_count": len(compacted),
            "compacted_files": compacted,
            "deleted_source_count": len(deleted),
            "deleted_source_files": deleted,
            "rebuild_index": rebuild,
        }

    def health_summary(
        self,
        *,
        registered: list[dict[str, Any]] | None = None,
        missing_registered: list[dict[str, Any]] | None = None,
        orphan_parquet: list[dict[str, Any]] | None = None,
        orphan_exports: list[dict[str, Any]] | None = None,
        metadata_mismatches: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        registered = registered if registered is not None else self.repository.list_all_files()
        missing_registered = missing_registered if missing_registered is not None else []
        orphan_parquet = orphan_parquet if orphan_parquet is not None else []
        orphan_exports = orphan_exports if orphan_exports is not None else []
        metadata_mismatches = metadata_mismatches if metadata_mismatches is not None else []
        warning_count = (
            len(missing_registered)
            + len(orphan_parquet)
            + len(orphan_exports)
            + len(metadata_mismatches)
        )
        return {
            "schema": "market.data.health.v1",
            "status": "ok" if warning_count == 0 else "warning",
            "data_dir": str(self.data_dir),
            "data_dir_exists": self.data_dir.exists(),
            "registered_file_count": len(registered),
            "parquet_file_count": len(self._parquet_files()),
            "missing_registered_count": len(missing_registered),
            "orphan_parquet_count": len(orphan_parquet),
            "orphan_export_count": len(orphan_exports),
            "metadata_mismatch_count": len(metadata_mismatches),
            "data_dir_bytes": _directory_size(self.data_dir),
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

    def _expired_export_files(self, *, expired_days: int | None) -> list[dict[str, str]]:
        if expired_days is None:
            return []
        exports = self.data_dir / "exports"
        if not exports.exists():
            return []
        cutoff = datetime.now(UTC) - timedelta(days=max(0, expired_days))
        expired: list[dict[str, str]] = []
        for manifest in sorted(exports.glob("*.manifest.json")):
            generated_at = _export_generated_at(manifest)
            if generated_at is None or generated_at > cutoff:
                continue
            export_id = manifest.name.removesuffix(".manifest.json")
            expired.append({"path": str(manifest), "reason": "expired_export"})
            for data_file in sorted(exports.glob(f"{export_id}.*")):
                if data_file != manifest:
                    expired.append({"path": str(data_file), "reason": "expired_export"})
        return expired

    def _metadata_mismatches(self, registered: list[dict[str, Any]]) -> list[dict[str, Any]]:
        mismatches = []
        for file_record in registered:
            path = Path(str(file_record.get("path") or ""))
            if not path.exists():
                continue
            try:
                actual = self.metadata_reader.read(path)
            except Exception as exc:
                mismatches.append(
                    {
                        "file_id": file_record.get("file_id"),
                        "path": str(path),
                        "fields": ["metadata"],
                        "error": f"{type(exc).__name__}: {exc}",
                    }
                )
                continue
            fields = [
                field
                for field in (
                    "hash",
                    "row_count",
                    "coverage_start",
                    "coverage_end",
                    "kind",
                    "symbol",
                    "period",
                    "adjust",
                )
                if file_record.get(field) != actual.get(field)
            ]
            if fields:
                mismatches.append(
                    {
                        "file_id": file_record.get("file_id"),
                        "path": str(path),
                        "fields": fields,
                    }
                )
        return mismatches

    def _can_delete(self, path: Path) -> bool:
        try:
            path.resolve().relative_to(self.data_dir.resolve())
        except ValueError:
            return False
        return path.is_file()


class ParquetMetadataReader:
    def __init__(self, *, import_module: Callable[[str], object] = importlib.import_module) -> None:
        self.import_module = import_module

    def read(self, path: Path) -> dict[str, Any]:
        parquet: Any = self.import_module("pyarrow.parquet")
        table = parquet.read_table(path)
        rows = table.to_pylist()
        partitions = _path_partitions(path)
        kind = partitions.get("kind", "daily_bars")
        data_hash = _rows_hash(rows)
        coverage_start, coverage_end = _coverage(kind, rows)
        return {
            "file_id": data_hash.removeprefix("sha256:")[:16],
            "kind": kind,
            "symbol": partitions.get("symbol", _symbol_from_rows(rows)),
            "period": partitions.get("period", "1d" if kind == "daily_bars" else "unknown"),
            "adjust": partitions.get("adjust", "none"),
            "format": "parquet",
            "path": str(path),
            "hash": data_hash,
            "row_count": len(rows),
            "coverage_start": coverage_start,
            "coverage_end": coverage_end,
        }


def _file_summary(file_record: dict[str, Any]) -> dict[str, Any]:
    return {
        "file_id": file_record.get("file_id"),
        "symbol": file_record.get("symbol"),
        "path": str(file_record.get("path")),
    }


def _normalized_path(path: object) -> str:
    return str(Path(str(path)))


def _coverage(kind: str, rows: list[dict[str, Any]]) -> tuple[str | None, str | None]:
    key = "date" if kind == "daily_bars" else "timestamp"
    values = sorted(str(row[key]) for row in rows if row.get(key))
    if not values:
        return None, None
    return values[0], values[-1]


def _rows_hash(rows: list[dict[str, Any]]) -> str:
    payload = json.dumps(rows, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _path_partitions(path: Path) -> dict[str, str]:
    partitions: dict[str, str] = {}
    for part in path.parts:
        if "=" not in part:
            continue
        key, value = part.split("=", 1)
        partitions[key] = value
    return partitions


def _symbol_from_rows(rows: list[dict[str, Any]]) -> str:
    for row in rows:
        symbol = row.get("symbol")
        if symbol:
            return str(symbol)
    return "unknown"


def _directory_size(root: Path) -> int:
    if not root.exists():
        return 0
    total = 0
    for path in root.rglob("*"):
        if path.is_file():
            total += path.stat().st_size
    return total


def _export_generated_at(path: Path) -> datetime | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    value = payload.get("generated_at")
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _unique_candidates(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    unique = {}
    for candidate in candidates:
        unique[str(candidate["path"])] = candidate
    return list(unique.values())
