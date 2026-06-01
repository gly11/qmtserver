from __future__ import annotations

import json
from typing import Any, Protocol

from qmtserver import __version__
from qmtserver.data.models import DataJobRecord, DataJobStatus, now_iso
from qmtserver.miniqmt import check_xtquant_import


class DuckDbBackendProtocol(Protocol):
    database_path: Any

    def connect(self, path: str) -> Any: ...


class DataJobRepository:
    def __init__(self, backend: DuckDbBackendProtocol) -> None:
        self.backend = backend

    def create(self, job_type: str, request: dict[str, Any]) -> DataJobRecord:
        job = DataJobRecord(job_type=job_type, request=request)
        self._execute(
            """
            INSERT INTO data_jobs (
                job_id, job_type, status, request_json, result_json, error_code, error_message,
                created_at, started_at, finished_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                job.job_id,
                job.job_type,
                job.status.value,
                json.dumps(job.request, ensure_ascii=False, sort_keys=True),
                None,
                None,
                None,
                job.created_at,
                None,
                None,
            ),
        )
        return job

    def get(self, job_id: str) -> DataJobRecord | None:
        connection = self.backend.connect(str(self.backend.database_path))
        try:
            cursor = connection.execute(
                """
                SELECT job_id, job_type, status, request_json, result_json, error_code,
                       error_message, created_at, started_at, finished_at
                FROM data_jobs
                WHERE job_id = ?
                """,
                (job_id,),
            )
            row = cursor.fetchone()
            if row is None:
                return None
            return _record_from_row(row)
        finally:
            connection.close()

    def mark_running(self, job_id: str) -> None:
        self._execute(
            "UPDATE data_jobs SET status = ?, started_at = ? WHERE job_id = ?",
            (DataJobStatus.RUNNING.value, now_iso(), job_id),
        )

    def mark_succeeded(self, job_id: str, result: dict[str, Any]) -> None:
        self._execute(
            """
            UPDATE data_jobs
            SET status = ?, result_json = ?, error_code = NULL, error_message = NULL,
                finished_at = ?
            WHERE job_id = ?
            """,
            (
                DataJobStatus.SUCCEEDED.value,
                json.dumps(result, ensure_ascii=False, sort_keys=True),
                now_iso(),
                job_id,
            ),
        )

    def mark_failed(self, job_id: str, error: dict[str, str]) -> None:
        self._execute(
            """
            UPDATE data_jobs
            SET status = ?, error_code = ?, error_message = ?, finished_at = ?
            WHERE job_id = ?
            """,
            (
                DataJobStatus.FAILED.value,
                error.get("code", "DATA_DOWNLOAD_FAILED"),
                error.get("message", "data download failed"),
                now_iso(),
                job_id,
            ),
        )

    def record_file(self, file_record: dict[str, Any]) -> None:
        xtquant = check_xtquant_import()
        self._execute(
            """
            INSERT INTO data_files (
                file_id, job_id, kind, symbol, period, adjust, format, path, hash, row_count,
                coverage_start, coverage_end, schema_version, qmtserver_version, xtquant_version,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                file_record["file_id"],
                file_record.get("job_id"),
                file_record["kind"],
                file_record["symbol"],
                file_record["period"],
                file_record["adjust"],
                file_record["format"],
                file_record["path"],
                file_record["hash"],
                file_record["row_count"],
                file_record.get("coverage_start"),
                file_record.get("coverage_end"),
                file_record.get("schema_version", "market.data.file.v1"),
                __version__,
                xtquant.get("version") if xtquant["ok"] else None,
                now_iso(),
            ),
        )
        self._record_coverage(file_record)

    def list_coverage(self, request: dict[str, Any]) -> list[dict[str, Any]]:
        symbols = {str(symbol) for symbol in request.get("symbols", [])}
        connection = self.backend.connect(str(self.backend.database_path))
        try:
            cursor = connection.execute(
                """
                SELECT coverage_id, kind, symbol, period, adjust, coverage_start, coverage_end,
                       row_count, file_count, updated_at
                FROM data_coverage
                WHERE kind = ? AND period = ? AND adjust = ?
                ORDER BY symbol
                """,
                (
                    request.get("kind"),
                    _period(request),
                    request.get("adjust", "none"),
                ),
            )
            coverage = [_coverage_from_row(row) for row in cursor.fetchall()]
            if symbols:
                return [row for row in coverage if str(row["symbol"]) in symbols]
            return coverage
        finally:
            connection.close()

    def list_files(self, request: dict[str, Any]) -> list[dict[str, Any]]:
        symbols = {str(symbol) for symbol in request.get("symbols", [])}
        connection = self.backend.connect(str(self.backend.database_path))
        try:
            cursor = connection.execute(
                """
                SELECT file_id, job_id, kind, symbol, period, adjust, format, path, hash,
                       row_count, coverage_start, coverage_end, schema_version,
                       qmtserver_version, xtquant_version, created_at
                FROM data_files
                WHERE kind = ? AND period = ? AND adjust = ?
                ORDER BY symbol, coverage_start
                """,
                (
                    request.get("kind"),
                    _period(request),
                    request.get("adjust", "none"),
                ),
            )
            files = [_file_from_row(row) for row in cursor.fetchall()]
            return [
                file_record
                for file_record in files
                if _file_matches_request(file_record, request, symbols=symbols)
            ]
        finally:
            connection.close()

    def _execute(self, sql: str, parameters: tuple[Any, ...]) -> Any:
        connection = self.backend.connect(str(self.backend.database_path))
        try:
            return connection.execute(sql, parameters)
        finally:
            connection.close()

    def _record_coverage(self, file_record: dict[str, Any]) -> None:
        coverage_id = _coverage_id(file_record)
        existing = self._get_coverage(coverage_id)
        merged = _merge_coverage(existing, file_record, coverage_id=coverage_id)
        self._execute("DELETE FROM data_coverage WHERE coverage_id = ?", (coverage_id,))
        self._execute(
            """
            INSERT INTO data_coverage (
                coverage_id, kind, symbol, period, adjust, coverage_start, coverage_end,
                row_count, file_count, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                merged["coverage_id"],
                merged["kind"],
                merged["symbol"],
                merged["period"],
                merged["adjust"],
                merged["coverage_start"],
                merged["coverage_end"],
                merged["row_count"],
                merged["file_count"],
                now_iso(),
            ),
        )

    def _get_coverage(self, coverage_id: str) -> dict[str, Any] | None:
        connection = self.backend.connect(str(self.backend.database_path))
        try:
            cursor = connection.execute(
                """
                SELECT coverage_id, kind, symbol, period, adjust, coverage_start, coverage_end,
                       row_count, file_count, updated_at
                FROM data_coverage
                WHERE coverage_id = ?
                """,
                (coverage_id,),
            )
            row = cursor.fetchone()
            if row is None:
                return None
            return _coverage_from_row(row)
        finally:
            connection.close()


def _record_from_row(row: tuple[Any, ...]) -> DataJobRecord:
    error = None
    if row[5] or row[6]:
        error = {"code": str(row[5]), "message": str(row[6])}
    return DataJobRecord(
        job_id=str(row[0]),
        job_type=str(row[1]),
        status=DataJobStatus(str(row[2])),
        request=json.loads(str(row[3])),
        result=json.loads(str(row[4])) if row[4] else None,
        error=error,
        created_at=str(row[7]),
        started_at=str(row[8]) if row[8] else None,
        finished_at=str(row[9]) if row[9] else None,
    )


def _coverage_from_row(row: tuple[Any, ...]) -> dict[str, Any]:
    return {
        "coverage_id": str(row[0]),
        "kind": str(row[1]),
        "symbol": str(row[2]),
        "period": str(row[3]),
        "adjust": str(row[4]),
        "coverage_start": str(row[5]) if row[5] else None,
        "coverage_end": str(row[6]) if row[6] else None,
        "row_count": int(row[7]),
        "file_count": int(row[8]),
        "updated_at": str(row[9]),
    }


def _file_from_row(row: tuple[Any, ...]) -> dict[str, Any]:
    return {
        "file_id": str(row[0]),
        "job_id": str(row[1]) if row[1] else None,
        "kind": str(row[2]),
        "symbol": str(row[3]),
        "period": str(row[4]),
        "adjust": str(row[5]),
        "format": str(row[6]),
        "path": str(row[7]),
        "hash": str(row[8]),
        "row_count": int(row[9]),
        "coverage_start": str(row[10]) if row[10] else None,
        "coverage_end": str(row[11]) if row[11] else None,
        "schema_version": str(row[12]),
        "qmtserver_version": str(row[13]),
        "xtquant_version": str(row[14]) if row[14] else None,
        "created_at": str(row[15]),
    }


def _file_matches_request(
    file_record: dict[str, Any],
    request: dict[str, Any],
    *,
    symbols: set[str],
) -> bool:
    if symbols and str(file_record["symbol"]) not in symbols:
        return False
    start = request.get("start")
    end = request.get("end")
    coverage_start = file_record.get("coverage_start")
    coverage_end = file_record.get("coverage_end")
    if isinstance(end, str) and isinstance(coverage_start, str) and coverage_start > end:
        return False
    return not (isinstance(start, str) and isinstance(coverage_end, str) and coverage_end < start)


def _coverage_id(record: dict[str, Any]) -> str:
    return ":".join(
        [
            str(record["kind"]),
            str(record["symbol"]),
            str(record["period"]),
            str(record["adjust"]),
        ]
    )


def _merge_coverage(
    existing: dict[str, Any] | None,
    file_record: dict[str, Any],
    *,
    coverage_id: str,
) -> dict[str, Any]:
    if existing is None:
        return {
            "coverage_id": coverage_id,
            "kind": file_record["kind"],
            "symbol": file_record["symbol"],
            "period": file_record["period"],
            "adjust": file_record["adjust"],
            "coverage_start": file_record.get("coverage_start"),
            "coverage_end": file_record.get("coverage_end"),
            "row_count": int(file_record.get("row_count", 0)),
            "file_count": 1,
        }
    starts = [
        item for item in [existing.get("coverage_start"), file_record.get("coverage_start")] if item
    ]
    ends = [
        item for item in [existing.get("coverage_end"), file_record.get("coverage_end")] if item
    ]
    return {
        **existing,
        "coverage_start": min(starts) if starts else None,
        "coverage_end": max(ends) if ends else None,
        "row_count": int(existing.get("row_count", 0)) + int(file_record.get("row_count", 0)),
        "file_count": int(existing.get("file_count", 0)) + 1,
    }


def _period(request: dict[str, Any]) -> str:
    if request.get("kind") == "daily_bars":
        return "1d"
    return str(request.get("period") or "unknown")
